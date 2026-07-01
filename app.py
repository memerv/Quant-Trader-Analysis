"""
app.py  —  QUANT DESK  (Modern UI Dashboard)
========================================
Single-scroll dashboard: market-pulse KPIs, candlestick chart, daily gold,
factor-ranked shortlist, and a green/red watchlist.

UI Updated: Modern light theme with deep purple accents, rounded cards, 
soft shadows, and forced styling independent of Streamlit's base theme.
"""

from __future__ import annotations
import datetime as dt

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import config
from data_loader import (read_tickers, load_universe, load_market_extras,
                         quote_from_history)
from quant_engine import compute_factor_scores, top_n, explain, FACTORS

st.set_page_config(page_title="Quant Desk", page_icon="◆", layout="wide",
                   initial_sidebar_state="expanded")

# ---------------------------------------------------------------------------
# COLOR PALETTE (Modern Light Theme with Purple Accents from the image)
# ---------------------------------------------------------------------------
UP = "#10B981"      # Modern Emerald Green
DOWN = "#EF4444"    # Modern Red
ACC = "#5D3DF8"     # Deep Purple (from your image)
GOLD = "#F59E0B"    # Modern Gold/Amber
INK = "#1E293B"     # Dark Slate (Main text)
MUT = "#64748B"     # Slate Gray (Muted text)
BG = "#F1F5F9"      # App Background (Very light grayish-blue)
PANEL = "#FFFFFF"   # Pure white for cards
SHADOW = "0 10px 25px rgba(0, 0, 0, 0.05)" # Soft dimension

# ---------------------------------------------------------------------------
# STYLE  — everything readable regardless of the Streamlit theme file
# ---------------------------------------------------------------------------
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Inter:wght@400;500;600;700;800&display=swap');

/* Force Light Theme at root level */
:root {{ color-scheme: light !important; }}

/* Base Font */
html, body, .stApp, [class*="css"], button, input, select, textarea,
[data-testid="stMarkdownContainer"] * {{
  font-family:-apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Roboto,
              Helvetica, Arial, sans-serif !important;
  -webkit-font-smoothing:antialiased;
}}
.mono, .mono * {{ font-family:'IBM Plex Mono', ui-monospace, monospace !important;
  font-variant-numeric:tabular-nums; }}

/* App Background */
.stApp {{ background: {BG} !important; color:{INK}; }}

/* Header and Toolbar */
[data-testid="stHeader"] {{ background:transparent !important; }}
[data-testid="stToolbar"] {{ right:.6rem; }}
.block-container {{ padding-top:3rem; padding-bottom:3rem; max-width:1180px; }}

/* Generic Text */
p, span, li, label, div {{ color:{INK}; }}
.muted {{ color:{MUT} !important; }}

/* ---- SIDEBAR: Modern Purple Gradient (inspired by the image's right panel) ---- */
[data-testid="stSidebar"] {{ 
    background: linear-gradient(135deg, #6C4AF2 0%, #4B2CC3 100%) !important; 
    border-right: none !important;
    box-shadow: 4px 0 24px rgba(75, 44, 195, 0.15);
}}
[data-testid="stSidebar"] *, [data-testid="stSidebar"] label {{ color: #FFFFFF !important; }}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] *, .side-p {{
  color: #E2E8F0 !important; font-size:.82rem; line-height:1.45; }}
/* Recolor the slider to White/Light Purple */
[data-testid="stSidebar"] [data-baseweb="slider"] [role="slider"] {{
  background: #FFFFFF !important; box-shadow:0 0 0 2px #4B2CC3 !important; }}
[data-testid="stSidebar"] [data-baseweb="slider"] > div > div > div {{
  background: #FFFFFF !important; }}
.side-h {{ font-weight:700; font-size:1.1rem; color:#FFFFFF; margin-bottom:.2rem; }}

/* ---- Headers / Hierarchy ---- */
.brand {{ font-weight:800; font-size:1.55rem; letter-spacing:-.02em; color:{INK}; }}
.brand b {{ color:{ACC}; }}
.kicker {{ font-size:.7rem; letter-spacing:.18em; text-transform:uppercase;
  color:{MUT}; margin-top:.15rem; font-weight: 600; }}
.h2 {{ font-weight:800; font-size:1.5rem; letter-spacing:-.02em; color:{INK};
  margin:2.6rem 0 .15rem; }}
.sub {{ color:{MUT}; font-size:.92rem; margin-bottom:1rem; max-width:45rem; line-height: 1.5; }}

/* ---- Cards & Panels (The "Dimensional & Rounded" Look) ---- */
/* Streamlit's container */
[data-testid="stVerticalBlockBorderWrapper"] {{
  background: {PANEL} !important; 
  border: none !important;
  border-radius: 24px !important; 
  box-shadow: {SHADOW} !important;
  padding: 10px !important;
}}

/* Custom KPI and Info cards */
.kpi, .panel, .disc {{ 
  background: {PANEL}; 
  border: none; 
  border-radius: 20px;
  box-shadow: {SHADOW};
}}
.kpi {{ padding:1.2rem 1.4rem; height:100%; transition: transform 0.2s; }}
.kpi:hover {{ transform: translateY(-2px); }}
.kpi .lab {{ font-size:.7rem; letter-spacing:.13em; text-transform:uppercase;
  color:{MUT}; margin-bottom:.5rem; font-weight: 600; }}
.kpi .px {{ font-family:'IBM Plex Mono',monospace; font-weight:700; font-size:1.8rem;
  color:{INK}; letter-spacing:-.01em; line-height:1.1; }}
.kpi .chg {{ font-family:'IBM Plex Mono',monospace; font-size:.85rem; margin-top:.45rem;
  display:inline-block; font-weight: 500; }}

.phead {{ font-size:.7rem; letter-spacing:.16em; text-transform:uppercase; color:{MUT};
  margin-bottom:.45rem; font-weight: 600; }}

.coname {{ font-weight:800; font-size:1.4rem; letter-spacing:-.01em; color:{INK}; }}
.cometa {{ font-family:'IBM Plex Mono',monospace; font-size:.74rem; color:{MUT};
  letter-spacing:.04em; margin-top:.2rem; }}
.rankpill {{ font-family:'IBM Plex Mono',monospace; font-weight:700; font-size:.7rem;
  letter-spacing:.1em; color:{PANEL}; background:{ACC}; padding:.25rem .7rem;
  border-radius:999px; box-shadow: 0 4px 10px rgba(93, 61, 248, 0.3); }}
.tag {{ font-family:'IBM Plex Mono',monospace; font-size:.74rem; font-weight:600;
  padding:.3rem .7rem; border-radius:8px; display:inline-block; margin-top:.6rem; }}

.bigscore {{ font-family:'IBM Plex Mono',monospace; font-weight:700; font-size:2.8rem;
  color:{ACC}; line-height:1; }}
.bigscore small {{ font-size:1rem; color:{MUT}; font-weight: 500; }}

.reasons {{ list-style:none; padding:0; margin:.8rem 0 .2rem; }}
.reasons li {{ color:{INK}; font-size:.92rem; line-height:1.6; padding:.2rem 0 .2rem 1.2rem;
  position:relative; }}
.reasons li:before {{ content:'▸'; color:{ACC}; position:absolute; left:0; font-weight: bold; }}

.stat {{ display:flex; justify-content:space-between; font-family:'IBM Plex Mono',monospace;
  font-size:.85rem; padding:.4rem 0; border-bottom:1px solid #F1F5F9; }}
.stat span:first-child {{ color:{MUT}; }}
.stat span:last-child {{ color:{INK}; font-weight: 600; }}

.disc {{ font-size:.8rem; color:{MUT}; padding:1.5rem; margin-top:2rem; line-height:1.6; }}
.disc b {{ color:{INK}; }}
hr {{ border-color:#E2E8F0; margin: 2rem 0; }}

/* Streamlit DataFrame tweaks for light mode */
[data-testid="stDataFrame"] {{ border-radius: 16px; overflow: hidden; box-shadow: {SHADOW}; }}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# FORMAT HELPERS
# ---------------------------------------------------------------------------
def f_pct(x, dp=1): return "—" if pd.isna(x) else f"{x*100:.{dp}f}%"
def f_ratio(x, dp=1): return "—" if pd.isna(x) else f"{x:.{dp}f}"
def f_price(x): return "—" if pd.isna(x) else f"${x:,.2f}"
def f_money(x):
    if pd.isna(x): return "—"
    for div, suf in [(1e12,"T"),(1e9,"B"),(1e6,"M")]:
        if abs(x) >= div: return f"${x/div:.2f}{suf}"
    return f"${x:,.0f}"

def chg_html(pct):
    if pd.isna(pct): return f'<span class="chg muted">—</span>'
    col = UP if pct >= 0 else DOWN
    arr = "▲" if pct >= 0 else "▼"
    # Adjusted background pill for changes
    bg_col = "rgba(16,185,129,0.1)" if pct >= 0 else "rgba(239,68,68,0.1)"
    return f'<span class="chg" style="color:{col}; background:{bg_col}; padding:0.2rem 0.5rem; border-radius:6px;">{arr} {abs(pct)*100:.2f}%</span>'

def standing(score):
    if score >= 70: return "Strong factor standing", UP, "rgba(16,185,129,0.1)"
    if score >= 50: return "Moderate factor standing", ACC, "rgba(93,61,248,0.1)"
    return "Weaker factor standing", DOWN, "rgba(239,68,68,0.1)"


# ---------------------------------------------------------------------------
# CHART BUILDERS (Updated for Light Theme readability)
# ---------------------------------------------------------------------------
def _light(fig, h):
    fig.update_layout(height=h, margin=dict(l=6, r=6, t=10, b=6),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="IBM Plex Mono", color=MUT, size=11),
        hoverlabel=dict(bgcolor=PANEL, font_family="IBM Plex Mono", bordercolor="#E2E8F0"))
    return fig

def candle_chart(hist, bars=160):
    h = hist.tail(bars)
    has_vol = "Volume" in h.columns
    fig = make_subplots(rows=2 if has_vol else 1, cols=1, shared_xaxes=True,
        row_heights=[0.76, 0.24] if has_vol else [1.0], vertical_spacing=0.03)
    fig.add_trace(go.Candlestick(x=h.index, open=h["Open"], high=h["High"],
        low=h["Low"], close=h["Close"], name="OHLC", showlegend=False,
        increasing_line_color=UP, decreasing_line_color=DOWN,
        increasing_fillcolor=UP, decreasing_fillcolor=DOWN), row=1, col=1)
    if "MA50" in h:
        fig.add_trace(go.Scatter(x=h.index, y=h["MA50"], line=dict(color=ACC, width=1.5),
            name="MA50", hovertemplate="MA50 $%{y:.2f}<extra></extra>"), row=1, col=1)
    if "MA200" in h:
        fig.add_trace(go.Scatter(x=h.index, y=h["MA200"], line=dict(color=GOLD, width=1.5, dash="dot"),
            name="MA200", hovertemplate="MA200 $%{y:.2f}<extra></extra>"), row=1, col=1)
    if has_vol:
        vc = [UP if c >= o else DOWN for o, c in zip(h["Open"], h["Close"])]
        fig.add_trace(go.Bar(x=h.index, y=h["Volume"], marker_color=vc, opacity=0.5,
            showlegend=False, hovertemplate="vol %{y:,.0f}<extra></extra>"), row=2, col=1)
    fig.update_xaxes(rangeslider_visible=False, showgrid=False, color=MUT)
    fig.update_yaxes(showgrid=True, gridcolor="#F1F5F9", color=MUT)
    fig.update_layout(legend=dict(orientation="h", y=1.07, x=0, bgcolor="rgba(0,0,0,0)"))
    return _light(fig, 440)

def area_chart(close, color, h=230):
    rgba = "rgba(245,158,11,0.15)" if color == GOLD else "rgba(93,61,248,0.1)"
    fig = go.Figure(go.Scatter(x=close.index, y=close, mode="lines",
        line=dict(color=color, width=2.5), fill="tozeroy", fillcolor=rgba,
        hovertemplate="%{x|%d %b %Y}<br>%{y:.2f}<extra></extra>"))
    fig.update_xaxes(showgrid=False, color=MUT)
    fig.update_yaxes(showgrid=True, gridcolor="#F1F5F9", color=MUT)
    return _light(fig, h)

def mini_price(hist, h=210):
    close = hist["Close"]
    up = close.iloc[-1] >= close.iloc[0]
    col = UP if up else DOWN
    rgba = "rgba(16,185,129,0.15)" if up else "rgba(239,68,68,0.15)"
    fig = go.Figure(go.Scatter(x=close.index, y=close, mode="lines",
        line=dict(color=col, width=2.5), fill="tozeroy", fillcolor=rgba,
        hovertemplate="%{x|%b %Y}<br>$%{y:.2f}<extra></extra>"))
    fig.update_xaxes(showgrid=False, color=MUT)
    fig.update_yaxes(showgrid=True, gridcolor="#F1F5F9", color=MUT, tickprefix="$")
    return _light(fig, h)

def radar(row, h=260):
    labels = ["Quality","Value","Growth","Momentum","Low-risk"]
    vals = [0 if pd.isna(row.get(f)) else row.get(f) for f in FACTORS]
    fig = go.Figure(go.Scatterpolar(r=vals+[vals[0]], theta=labels+[labels[0]],
        fill="toself", line=dict(color=ACC, width=2),
        fillcolor="rgba(93,61,248,0.15)",
        hovertemplate="%{theta}: %{r:.0f}/100<extra></extra>"))
    fig.update_layout(height=h, margin=dict(l=44,r=44,t=26,b=26),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="IBM Plex Mono", color=INK, size=11, weight="bold"),
        polar=dict(bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(range=[0,100], showticklabels=False, gridcolor="#E2E8F0", linecolor="#E2E8F0"),
            angularaxis=dict(gridcolor="#E2E8F0", linecolor="#E2E8F0", color=INK)))
    return fig

def stat(label, value): return f'<div class="stat"><span>{label}</span><span>{value}</span></div>'
PLT = {"displayModeBar": False}


# ---------------------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown('<div class="side-h">⚙︎ Tune the strategy</div>'
                '<div class="side-p">Each slider sets how much that <b>style of signal</b> '
                'counts toward a stock\'s final score (0–100).</div><br>', unsafe_allow_html=True)

    d = config.FACTOR_WEIGHTS
    w = {}
    w["quality"] = st.slider("Quality", 0.0, 1.0, float(d["quality"]), 0.05)
    w["value"] = st.slider("Value", 0.0, 1.0, float(d["value"]), 0.05)
    w["growth"] = st.slider("Growth", 0.0, 1.0, float(d["growth"]), 0.05)
    w["momentum"] = st.slider("Momentum", 0.0, 1.0, float(d["momentum"]), 0.05)
    w["low_risk"] = st.slider("Low-risk", 0.0, 1.0, float(d["low_risk"]), 0.05)

    st.markdown("<br>", unsafe_allow_html=True)
    n_picks = st.number_input("Number of picks", 1, 10, config.N_PICKS)

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("↻ Refresh market data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


# ---------------------------------------------------------------------------
# LOAD
# ---------------------------------------------------------------------------
tickers = tuple(read_tickers(config.TICKERS_FILE))
today = dt.date.today().strftime("%d %b %Y")

with st.spinner(f"Scanning {len(tickers)} companies + market data…"):
    try:
        raw_df, history, failed = load_universe(tickers, config.HISTORY_PERIOD)
        extras = load_market_extras(tuple(config.KPI_TICKERS), "1y")
    except Exception as e:
        st.error(f"Could not load market data: {e}")
        st.stop()

if raw_df.empty:
    st.error("No data came back. Check your connection or tickers.txt, then hit ↻ Refresh.")
    st.stop()

scored = compute_factor_scores(raw_df, weights=w, min_coverage=config.MIN_COVERAGE)
picks = top_n(scored, int(n_picks))


# ---------------------------------------------------------------------------
# HEADER + MARKET PULSE
# ---------------------------------------------------------------------------
hc1, hc2 = st.columns([3, 1])
with hc1:
    st.markdown('<div class="brand">◆ QUANT <b style="color:#5D3DF8">DESK</b></div>'
                '<div class="kicker">Factor terminal · long-horizon ranking</div>',
                unsafe_allow_html=True)
with hc2:
    st.markdown(f'<div class="kicker" style="text-align:right">As of</div>'
                f'<div class="mono" style="text-align:right;color:{INK};font-size:1.05rem;'
                f'font-weight:700">{today}</div>', unsafe_allow_html=True)

st.write("")
kcols = st.columns(len(config.KPI_TICKERS), gap="medium")
for col, (sym, label) in zip(kcols, config.KPI_TICKERS.items()):
    price, chg = quote_from_history(extras.get(sym))
    dollar = "$" if sym == config.GOLD_TICKER else ""
    px = "—" if pd.isna(price) else f"{dollar}{price:,.2f}"
    with col:
        st.markdown(f'<div class="kpi"><div class="lab">{label}</div>'
                    f'<div class="px">{px}</div>{chg_html(chg)}</div>',
                    unsafe_allow_html=True)

st.write("")
st.write("")

# ---------------------------------------------------------------------------
# FEATURED: candlestick (left) + factor scorecard (right)
# ---------------------------------------------------------------------------
st.markdown('<div class="h2">Featured chart</div>'
            '<div class="sub">Daily candlesticks with 50- and 200-day average lines and '
            'volume. Pick any company from the pool to inspect it.</div>',
            unsafe_allow_html=True)

with st.container(border=True):
    fc1, fc2 = st.columns([1.7, 1], gap="large")
    with fc1:
        opts = list(scored.index)
        labelmap = {s: f"{s} · {scored.loc[s,'name']}" for s in opts}
        sel = st.selectbox("Company", opts, index=0, format_func=lambda s: labelmap[s],
                           label_visibility="collapsed")
        if sel in history:
            st.plotly_chart(candle_chart(history[sel]), use_container_width=True, config=PLT)
    with fc2:
        r = scored.loc[sel]
        tag_txt, tag_col, tag_bg = standing(r["composite"])
        st.markdown(f'<div class="phead">Factor scorecard</div>'
                    f'<div class="coname">{r.get("name") or sel}</div>'
                    f'<div class="cometa">{sel} · rank #{int(r["rank"])} of {len(scored)}</div>'
                    f'<div class="bigscore" style="margin-top:.55rem">{r["composite"]:.0f}'
                    f'<small> / 100</small></div>'
                    f'<span class="tag" style="background:{tag_bg};color:{tag_col}">'
                    f'{tag_txt}</span>', unsafe_allow_html=True)
        st.plotly_chart(radar(r, h=250), use_container_width=True, config=PLT)

st.write("")
st.write("")

# ---------------------------------------------------------------------------
# DAILY GOLD
# ---------------------------------------------------------------------------
gold_df = extras.get(config.GOLD_TICKER)
gprice, gchg = quote_from_history(gold_df)
st.markdown('<div class="h2">Gold · daily</div>'
            '<div class="sub">COMEX gold futures (XAU), US$ per troy ounce. Updates each day '
            '— a classic safe-haven reference alongside the stock market.</div>',
            unsafe_allow_html=True)

with st.container(border=True):
    gc1, gc2 = st.columns([1, 1.7], gap="large")
    with gc1:
        g52 = gold_df["Close"] if gold_df is not None else pd.Series(dtype=float)
        st.markdown(
            f'<div class="phead">Spot · XAU / oz</div>'
            f'<div class="bigscore mono" style="color:{GOLD}">'
            f'{"—" if pd.isna(gprice) else f"${gprice:,.2f}"}</div>'
            f'<div style="margin-top:.5rem">{chg_html(gchg)} '
            f'<span class="cometa" style="margin-left: 8px;">vs. yesterday</span></div>'
            f'<div style="margin-top:1.2rem">'
            f'{stat("52-week high", "—" if g52.empty else f"${g52.max():,.2f}")}'
            f'{stat("52-week low", "—" if g52.empty else f"${g52.min():,.2f}")}'
            f'</div>', unsafe_allow_html=True)
    with gc2:
        if gold_df is not None and not gold_df.empty:
            st.plotly_chart(area_chart(gold_df["Close"], GOLD), use_container_width=True, config=PLT)
        else:
            st.info("Gold data unavailable right now — hit ↻ Refresh.")

st.write("")
st.write("")

# ---------------------------------------------------------------------------
# THE SHORTLIST
# ---------------------------------------------------------------------------
st.markdown('<div class="h2">The shortlist</div>'
            '<div class="sub">The top factor-ranked candidates for a 1–10 year horizon. '
            'Each card shows the 5-year price and exactly why it ranks where it does.</div>',
            unsafe_allow_html=True)

for sym, row in picks.iterrows():
    with st.container(border=True):
        c1, c2 = st.columns([1.6, 1], gap="large")
        with c1:
            st.markdown(f'<span class="rankpill">RANK {int(row["rank"])}</span> '
                        f'<span class="coname" style="margin-left: 8px;">{row.get("name") or sym}</span>'
                        f'<div class="cometa" style="margin-top: 8px;">{sym} · {row.get("sector","—")}</div>',
                        unsafe_allow_html=True)
            if sym in history:
                st.plotly_chart(mini_price(history[sym]), use_container_width=True, config=PLT)
        with c2:
            st.markdown('<div class="phead">Composite score</div>'
                        f'<div class="bigscore">{row["composite"]:.0f}<small> / 100</small></div>'
                        f'<div class="phead" style="margin-top:1rem">Why it ranks here</div>',
                        unsafe_allow_html=True)
            st.markdown('<ul class="reasons">' +
                        "".join(f"<li>{x}</li>" for x in explain(row)) + "</ul>",
                        unsafe_allow_html=True)
            stats = (stat("Price", f_price(row.get("last_price")))
                     + stat("5-year return", f_pct(row.get("ret_5y"), 0))
                     + stat("Market cap", f_money(row.get("market_cap")))
                     + stat("P/E ratio", f_ratio(row.get("pe")))
                     + stat("Revenue growth", f_pct(row.get("revenue_growth")))
                     + stat("Data coverage", f_pct(row.get("coverage"), 0)))
            st.markdown(f'<div style="margin-top:.8rem">{stats}</div>', unsafe_allow_html=True)
    st.write("")

st.write("")

# ---------------------------------------------------------------------------
# WATCHLIST
# ---------------------------------------------------------------------------
st.markdown('<div class="h2">Watchlist · full ranking</div>'
            '<div class="sub">Every scored company, ranked. Green/red shows the 5-year '
            'price return; the blue shading tracks the composite score.</div>',
            unsafe_allow_html=True)

tbl = scored.copy()
tbl.insert(0, "Ticker", tbl.index)
cols = ["rank", "Ticker", "name", "last_price", "ret_5y", "composite"] + FACTORS
tbl = tbl[cols].rename(columns={"rank": "#", "name": "Company",
    "last_price": "Price", "ret_5y": "5y return", "composite": "Score", "low_risk": "low-risk"})

def color_ret(v):
    if pd.isna(v): return f"color:{MUT}"
    return f"color:{UP}; font-weight: 600;" if v >= 0 else f"color:{DOWN}; font-weight: 600;"

sty = (tbl.style
       .format({"Price": "${:,.2f}", "5y return": "{:+.0%}", "Score": "{:.1f}",
                "quality": "{:.0f}", "value": "{:.0f}", "growth": "{:.0f}",
                "momentum": "{:.0f}", "low-risk": "{:.0f}"})
       .map(color_ret, subset=["5y return"])
       .background_gradient(subset=["Score"], cmap="Purples")) # เปลี่ยนเป็นเฉดสีม่วงให้เข้ากับธีม
st.dataframe(sty, use_container_width=True, hide_index=True, height=440)

if failed:
    st.caption("⚠︎ Skipped (no data): " + ", ".join(failed))

# ---------------------------------------------------------------------------
# METHODOLOGY + DISCLAIMER
# ---------------------------------------------------------------------------
st.markdown(f"""
<div class="disc">
<b style="font-size: 1rem; margin-bottom: 0.5rem; display: inline-block;">Not investment advice.</b><br>
Quant Desk is an educational research tool. It ranks
stocks on historical and fundamental factors; it does <b>not</b> predict future
prices. Factor scores describe the past and present, which need not repeat. A
short shortlist is highly concentrated and ignores your goals, horizon, and risk
tolerance. Gold and equity data from Yahoo Finance may be delayed or inaccurate.
Do your own research and consider a licensed financial professional before
investing. You alone are responsible for your decisions.
</div>
""", unsafe_allow_html=True)
