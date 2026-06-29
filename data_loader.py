"""
data_loader.py
==============
Pulls fundamentals + price history from Yahoo Finance (via `yfinance`) and
builds the raw-metric table the engine expects, plus market-pulse / gold data.

yfinance is free but patchy: every fetch is wrapped in try/except, failures are
skipped (never fatal). Results are cached so tweaking factor weights does NOT
re-download anything.
"""

from __future__ import annotations
import numpy as np
import pandas as pd

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None

try:
    import streamlit as st
    _cache = st.cache_data
except Exception:  # pragma: no cover
    def _cache(*a, **k):
        def deco(fn):
            return fn
        return deco

_TTL = getattr(__import__("config"), "CACHE_TTL_SECONDS", 21600)


def read_tickers(path: str) -> list[str]:
    out = []
    with open(path) as fh:
        for line in fh:
            line = line.split("#", 1)[0].strip().upper()
            if line:
                out.append(line)
    seen, uniq = set(), []
    for t in out:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq


def _safe(d: dict, *keys):
    for k in keys:
        v = d.get(k)
        if v is not None and isinstance(v, (int, float)) and np.isfinite(v):
            return float(v)
    return np.nan


def _positive_or_nan(x):
    return x if (x is not None and np.isfinite(x) and x > 0) else np.nan


def _price_metrics(close: pd.Series) -> dict:
    out = dict(mom_12_1=np.nan, price_vs_ma200=np.nan, volatility=np.nan,
               max_drawdown=np.nan, ret_5y=np.nan, last_price=np.nan,
               hi_52w=np.nan, lo_52w=np.nan)
    close = close.dropna()
    if len(close) < 30:
        return out
    out["last_price"] = float(close.iloc[-1])
    if len(close) >= 252:
        p_then, p_recent = close.iloc[-252], close.iloc[-21]
        if p_then > 0:
            out["mom_12_1"] = float(p_recent / p_then - 1.0)
    if len(close) >= 200:
        ma200 = close.iloc[-200:].mean()
        if ma200 > 0:
            out["price_vs_ma200"] = float(close.iloc[-1] / ma200 - 1.0)
    rets = close.pct_change().dropna()
    if len(rets) > 20:
        out["volatility"] = float(rets.std() * np.sqrt(252))
    roll_max = close.cummax()
    dd = (close / roll_max - 1.0).min()
    if np.isfinite(dd):
        out["max_drawdown"] = float(abs(dd))
    if close.iloc[0] > 0:
        out["ret_5y"] = float(close.iloc[-1] / close.iloc[0] - 1.0)
    last_252 = close.iloc[-252:] if len(close) >= 252 else close
    out["hi_52w"] = float(last_252.max())
    out["lo_52w"] = float(last_252.min())
    return out


def _fundamentals(info: dict) -> dict:
    pe = _positive_or_nan(_safe(info, "trailingPE"))
    fwd_pe = _positive_or_nan(_safe(info, "forwardPE"))
    fcf = _safe(info, "freeCashflow")
    mcap = _safe(info, "marketCap")
    beta = _safe(info, "beta")
    fcf_yield = (fcf / mcap) if (np.isfinite(fcf) and np.isfinite(mcap) and mcap > 0) else np.nan
    pe_improvement = ((pe - fwd_pe) / pe) if (np.isfinite(pe) and np.isfinite(fwd_pe)) else np.nan
    beta_dist = abs(beta - 1.0) if np.isfinite(beta) else np.nan
    return dict(
        roe=_safe(info, "returnOnEquity"),
        profit_margin=_safe(info, "profitMargins"),
        operating_margin=_safe(info, "operatingMargins"),
        debt_to_equity=_safe(info, "debtToEquity"),
        fcf_yield=fcf_yield,
        pe=pe,
        peg=_positive_or_nan(_safe(info, "trailingPegRatio", "pegRatio")),
        pb=_positive_or_nan(_safe(info, "priceToBook")),
        ps=_positive_or_nan(_safe(info, "priceToSalesTrailing12Months")),
        revenue_growth=_safe(info, "revenueGrowth"),
        earnings_growth=_safe(info, "earningsGrowth", "earningsQuarterlyGrowth"),
        pe_improvement=pe_improvement,
        beta_dist=beta_dist,
        name=info.get("shortName") or info.get("longName") or "",
        sector=info.get("sector") or "—",
        market_cap=mcap,
    )


@_cache(ttl=_TTL, show_spinner=False)
def load_universe(tickers: tuple[str, ...], period: str = "5y"):
    """
    Returns:
      raw_df  : DataFrame indexed by ticker (raw metrics + display cols)
      history : dict {ticker -> OHLCV DataFrame with MA50/MA200}
      failed  : list of tickers that could not be loaded
    `tickers` is a tuple so Streamlit can cache on it.
    """
    if yf is None:
        raise RuntimeError("yfinance is not installed. Run: pip install yfinance")
    rows, history, failed = {}, {}, []
    for sym in tickers:
        try:
            tk = yf.Ticker(sym)
            info = tk.info or {}
            hist = tk.history(period=period, interval="1d", auto_adjust=True)
            if hist is None or hist.empty or "Close" not in hist:
                failed.append(sym)
                continue
            close = hist["Close"]
            row = _fundamentals(info)
            row.update(_price_metrics(close))
            rows[sym] = row
            keep = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in hist.columns]
            h = hist[keep].copy()
            h["MA50"] = h["Close"].rolling(50, min_periods=20).mean()
            h["MA200"] = h["Close"].rolling(200, min_periods=50).mean()
            history[sym] = h
        except Exception:
            failed.append(sym)
            continue
    raw_df = pd.DataFrame.from_dict(rows, orient="index")
    return raw_df, history, failed


@_cache(ttl=_TTL, show_spinner=False)
def load_market_extras(symbols: tuple[str, ...], period: str = "1y"):
    """Fetch OHLC history for index / gold tickers. Returns {sym -> DataFrame}."""
    if yf is None:
        raise RuntimeError("yfinance is not installed.")
    out = {}
    for sym in symbols:
        try:
            h = yf.Ticker(sym).history(period=period, interval="1d", auto_adjust=True)
            if h is None or h.empty or "Close" not in h:
                continue
            keep = [c for c in ["Open", "High", "Low", "Close"] if c in h.columns]
            out[sym] = h[keep].copy()
        except Exception:
            continue
    return out


def quote_from_history(df: pd.DataFrame):
    """Return (last_price, daily_change_pct) from an OHLC DataFrame."""
    if df is None or df.empty or "Close" not in df:
        return np.nan, np.nan
    close = df["Close"].dropna()
    if len(close) < 2:
        return (float(close.iloc[-1]) if len(close) else np.nan), np.nan
    return float(close.iloc[-1]), float(close.iloc[-1] / close.iloc[-2] - 1.0)
