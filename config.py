"""
config.py
=========
All user-tunable settings live here. Edit, save, and Streamlit reloads.

The factor weights decide how much each "style" of signal matters. They do NOT
need to sum to 1 — the engine normalises them.
"""

# How many stocks to surface as highlighted picks.
N_PICKS = 3

# Pool of stocks to rank (one ticker per line; '#' = comment). These are the
# CANDIDATES, not recommendations.
TICKERS_FILE = "tickers.txt"

# Price history window (used for charts, momentum, volatility).
HISTORY_PERIOD = "5y"

# Cache lifetime for downloaded data, in seconds. Long-horizon scoring does not
# need real-time data; refreshing a few times a day is plenty.
CACHE_TTL_SECONDS = 60 * 60 * 6  # 6 hours

# A company must have at least this fraction of metrics present to be ranked.
MIN_COVERAGE = 0.45

# Market-pulse tickers shown as KPI cards at the top. Gold (GC=F) doubles as the
# data source for the daily gold panel.
KPI_TICKERS = {
    "^GSPC": "S&P 500",
    "^IXIC": "Nasdaq",
    "^DJI":  "Dow Jones",
    "GC=F":  "Gold · oz",
}
GOLD_TICKER = "GC=F"   # COMEX gold futures, USD per troy ounce

# ---------------------------------------------------------------------------
# FACTOR WEIGHTS  (the heart of your strategy)
# ---------------------------------------------------------------------------
FACTOR_WEIGHTS = {
    "quality":  0.25,
    "value":    0.20,
    "growth":   0.25,
    "momentum": 0.15,
    "low_risk": 0.15,
}

# ---------------------------------------------------------------------------
# THEME  (all colours are 6-digit hex or rgba() — both valid in Plotly AND CSS.
# Never use 8-digit hex like #112233AA here: Plotly rejects it.)
# ---------------------------------------------------------------------------
COLORS = {
    "bg":      "#0B1220",   # deep navy backdrop
    "panel":   "#111C30",   # card surface
    "border":  "#1F2D45",   # hairline borders
    "ink":     "#E7EEF7",   # primary text
    "muted":   "#7C89A0",   # secondary text
    "accent":  "#39BAE6",   # cyan signature
    "accent2": "#7C5CFF",   # violet (radar / secondary)
    "up":      "#26D07C",   # gains
    "down":    "#F25B5B",   # losses
    "grid":    "#1E2B42",   # chart gridlines
    "gold":    "#E8B341",   # gold panel accent
}
