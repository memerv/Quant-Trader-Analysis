"""
quant_engine.py
===============
The scoring core. This is deliberately separate from data fetching so the
logic can be tested without any network access.

Philosophy (read this before tweaking):
- We do NOT predict tomorrow's price. We score companies on factors that have
  historically been associated with long-horizon outperformance, then rank them.
- Every metric is scored CROSS-SECTIONALLY (relative to the other stocks in the
  pool), not against fixed thresholds. A P/E of 25 is "cheap" or "expensive"
  only relative to its peers in the universe.
- Scores are 0-100 percentiles. A factor sub-score is the average of its
  metrics' percentiles. The composite is a weighted average of factor scores.
- Missing data is normal (yfinance is patchy). We never crash on it; we track
  coverage so the user can see how complete each company's data was.

Nothing here is investment advice. It is a transparent ranking tool.
"""

from __future__ import annotations
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# METRIC CONFIG
# Each entry: raw_column -> (factor_name, direction)
#   direction =  1  -> higher raw value is better (e.g. ROE, growth)
#   direction = -1  -> lower raw value is better  (e.g. P/E, debt, volatility)
# To add/remove a signal, edit this table. Nothing else needs to change.
# ---------------------------------------------------------------------------
METRIC_CONFIG = {
    # raw column            (factor,       direction)
    "roe":                  ("quality",     1),
    "profit_margin":        ("quality",     1),
    "operating_margin":     ("quality",     1),
    "debt_to_equity":       ("quality",    -1),
    "fcf_yield":            ("quality",     1),

    "pe":                   ("value",      -1),
    "peg":                  ("value",      -1),
    "pb":                   ("value",      -1),
    "ps":                   ("value",      -1),

    "revenue_growth":       ("growth",      1),
    "earnings_growth":      ("growth",      1),
    "pe_improvement":       ("growth",      1),  # (trailingPE - forwardPE)/trailingPE

    "mom_12_1":             ("momentum",    1),  # 12-month return, skipping last month
    "price_vs_ma200":       ("momentum",    1),

    "volatility":           ("low_risk",   -1),
    "beta_dist":            ("low_risk",   -1),  # |beta - 1|, lower = steadier
    "max_drawdown":         ("low_risk",   -1),  # stored as positive magnitude
}

FACTORS = ["quality", "value", "growth", "momentum", "low_risk"]

# Default weights. Must be overridable from config.py. Sum need not be 1; the
# engine normalises over whatever factors actually have data for a given stock.
DEFAULT_WEIGHTS = {
    "quality":  0.25,
    "value":    0.20,
    "growth":   0.25,
    "momentum": 0.15,
    "low_risk": 0.15,
}

# A stock must have at least this fraction of all metrics present to be ranked.
MIN_COVERAGE = 0.45


def _winsorized_percentile(series: pd.Series, direction: int) -> pd.Series:
    """
    Convert a column of raw values into 0-100 percentile scores, robustly.

    Steps:
      1. Clip extreme outliers to the 2nd/98th percentile (winsorize) so one
         crazy value doesn't compress everyone else.
      2. Rank to a percentile in [0, 100].
      3. If direction == -1 (lower is better), invert so high score = good.

    NaNs stay NaN (they are not scored, not penalised as zero).
    """
    s = series.astype(float).copy()
    valid = s.dropna()
    if valid.nunique() <= 1:
        # No spread (all same or <=1 value): give everyone a neutral 50.
        out = pd.Series(np.where(s.notna(), 50.0, np.nan), index=s.index)
        return out

    lo, hi = valid.quantile(0.02), valid.quantile(0.98)
    clipped = s.clip(lower=lo, upper=hi)
    # rank -> percentile 0..1 over the non-NaN values
    pct = clipped.rank(pct=True)  # NaNs propagate as NaN
    score = pct * 100.0
    if direction == -1:
        score = 100.0 - score
    return score


def compute_factor_scores(
    raw: pd.DataFrame,
    weights: dict | None = None,
    min_coverage: float = MIN_COVERAGE,
) -> pd.DataFrame:
    """
    Main entry point.

    Parameters
    ----------
    raw : DataFrame indexed by ticker, containing the raw metric columns named
          in METRIC_CONFIG (any may be missing/NaN) plus optional display
          columns (name, sector, price, ...) which are carried through.
    weights : factor weights dict; falls back to DEFAULT_WEIGHTS.
    min_coverage : drop stocks with less than this fraction of metrics present.

    Returns
    -------
    DataFrame with: one column per factor (0-100), 'composite' (0-100),
    'coverage' (0-1), 'rank', plus all carried-through display columns,
    sorted by composite descending.
    """
    weights = {**DEFAULT_WEIGHTS, **(weights or {})}
    df = raw.copy()

    metric_cols = [c for c in METRIC_CONFIG if c in df.columns]
    if not metric_cols:
        raise ValueError("None of the expected metric columns are present.")

    # 1) Per-metric percentile scores
    metric_scores = pd.DataFrame(index=df.index)
    for col in metric_cols:
        factor, direction = METRIC_CONFIG[col]
        metric_scores[col] = _winsorized_percentile(df[col], direction)

    # 2) Coverage = fraction of metrics that were present (non-NaN)
    coverage = metric_scores.notna().sum(axis=1) / len(metric_cols)
    df["coverage"] = coverage

    # 3) Factor sub-scores = mean of that factor's metric scores (skip NaN)
    for factor in FACTORS:
        cols = [c for c in metric_cols if METRIC_CONFIG[c][0] == factor]
        if cols:
            df[factor] = metric_scores[cols].mean(axis=1, skipna=True)
        else:
            df[factor] = np.nan

    # 4) Composite = weighted mean over factors that have a score for this stock
    def _composite(row):
        num, den = 0.0, 0.0
        for factor in FACTORS:
            val = row.get(factor, np.nan)
            w = weights.get(factor, 0.0)
            if pd.notna(val) and w > 0:
                num += w * val
                den += w
        return num / den if den > 0 else np.nan

    df["composite"] = df.apply(_composite, axis=1)

    # 5) Filter low-coverage names, rank the rest
    df = df[df["coverage"] >= min_coverage].copy()
    df = df.sort_values("composite", ascending=False)
    df["rank"] = range(1, len(df) + 1)

    return df


def top_n(scored: pd.DataFrame, n: int = 3) -> pd.DataFrame:
    """Return the top n rows by composite (scored is already sorted)."""
    return scored.head(n).copy()


def explain(row: pd.Series, top_k: int = 3) -> list[str]:
    """
    Produce human-readable reasons for a pick, derived from its strongest
    factor scores. This makes the ranking transparent rather than a black box.
    """
    blurbs = {
        "quality":  "strong profitability and balance-sheet quality",
        "value":    "reasonably priced relative to peers",
        "growth":   "above-average revenue / earnings growth",
        "momentum": "positive medium-term price trend",
        "low_risk": "steadier price behaviour than peers",
    }
    available = [(f, row[f]) for f in FACTORS if pd.notna(row.get(f, np.nan))]
    available.sort(key=lambda x: x[1], reverse=True)
    reasons = []
    for factor, score in available[:top_k]:
        if score >= 55:  # only mention genuine relative strengths
            reasons.append(f"{blurbs[factor]} (scores {score:.0f}/100 on {factor})")
    if not reasons:
        reasons.append("ranks here on a balanced mix of factors, with no single standout strength")
    return reasons
