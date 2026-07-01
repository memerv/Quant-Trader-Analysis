"""
app.py  —  QUANT DESK  (clean dashboard + Custom Login)
========================================
Single-scroll dark dashboard: market-pulse KPIs, candlestick chart, daily gold,
factor-ranked shortlist, and a green/red watchlist.
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

C = config.COLORS

# ---------------------------------------------------------------------------
# 1. ตั้งค่าหน้าเพจ (ต้องอยู่ส่วนบนสุดเสมอ)
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Quant Desk", page_icon="◆", layout="wide",
                   initial_sidebar_state="expanded")

# ---------------------------------------------------------------------------
# 2. ระบบ LOGIN STATE และ UI (เพิ่มเข้ามาใหม่)
# ---------------------------------------------------------------------------
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    # --- CSS บังคับธีมสว่างและจำลองหน้าต่าง Modal แบบในรูป ---
    st.markdown("""
    <style>
    /* บังคับพื้นหลังสีสว่าง ไม่สน Dark Mode ของ Browser */
    [data-testid="stAppViewContainer"] {
        background: radial-gradient(circle at center, #F5F7FA 0%, #E8EAF2 100%) !important;
        color-scheme: light !important;
    }
    /* ซ่อน Sidebar และ Header ของ Streamlit ในหน้า Login */
    [data-testid="stSidebar"] { display: none !important; }
    header[data-testid="stHeader"] { display: none !important; }

    /* ปรับกรอบหลักให้กลายเป็น Card สีขาวตรงกลาง */
    .block-container {
        max-width: 800px !important;
        padding: 0 !important;
        background: white;
        border-radius: 20px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        margin-top: 15vh !important;
        overflow: hidden;
    }

    /* ปรับแต่ง Input ของ Streamlit ให้กลืนกับดีไซน์ */
    div[data-baseweb="input"] {
        background-color: #F8F9FA !important;
        border: 1px solid #E0E0E0 !important;
        border-radius: 8px !important;
    }
    div[data-baseweb="input"] input {
        color: #333 !important;
        background-color: transparent !important;
    }
    
    /* ปุ่ม SIGN IN สีม่วง */
    button[kind="primary"] {
        background-color: #5D3DF8 !important;
        color: white !important;
        border: none !important;
        font-weight: bold;
        padding: 10px;
        border-radius: 8px;
        transition: 0.3s;
    }
    button[kind="primary"]:hover { background-color: #4B2CC3 !important; }
    </style>
    """, unsafe_allow_html=True)

    # --- สร้าง Layout แบ่งซ้าย(ฟอร์ม) / ขวา(ป้ายสีม่วง) ---
    col_left, col_right = st.columns([1.2, 1], gap="medium")
    
    with col_left:
        st.write("") 
        st.write("") 
        st.markdown("<h2 style='color: black; text-align: center; margin-bottom: 5px; font-weight: 800;'>Sign In</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #888; font-size: 13px; margin-bottom: 20px;'>or use your email password</p>", unsafe_allow_html=True)
        
        # ช่องกรอกข้อมูล (เชื่อมกับ Python)
        email = st.text_input("Email", placeholder="Email", label_visibility="collapsed")
        password = st.text_input("Password", type="password", placeholder="Password", label_visibility="collapsed")
        st.markdown("<a href='#' style='color: #888; text-decoration: none; font-size: 12px;'>Forget Your Password?</a><br><br>", unsafe_allow_html=True)
        
        # พอกดปุ่ม SIGN IN จะเปลี่ยนสถานะและรีโหลดหน้าใหม่
        if st.button("SIGN IN", type="primary", use_container_width=True):
            # ตรงนี้คุณสามารถเพิ่มเงื่อนไขเช็คอีเมล/รหัสผ่านจริงได้ในอนาคต
            st.session_state.logged_in = True
            st.rerun()

    with col_right:
        # ส่วนกราฟิกด้านขวา (ตกแต่งด้วย HTML เพื่อให้ได้ดีไซน์เป๊ะๆ)
        st.markdown("""
        <div style="background: linear-gradient(135deg, #6C4AF2 0%, #4B2CC3 100%);
                    height: 100%; min-height: 400px; display: flex; flex-direction: column; 
                    justify-content: center; align-items: center; color: white; 
                    padding: 40px; text-align: center; margin: -1rem -1rem -1rem 0;">
            <h2 style="color: white; margin-bottom:15px; font-weight: 700;">Hello, Friend!</h2>
            <p style="margin-bottom:30px; font-size: 14px; line-height: 1.5; color: #E8EAF2;">
                Register with your personal details to use all of site features
            </p>
            <button style="background: transparent; border: 2px solid white; color: white;
                           padding: 10px 35px; border-radius: 25px; font-weight: bold; cursor: pointer;">
                SIGN UP
            </button>
        </div>
        """, unsafe_allow_html=True)

    # *** สำคัญมาก: คำสั่งนี้จะหยุดการทำงานตรงนี้ ไม่ให้โหลด Dashboard หุ้นขึ้นมาจนกว่าจะ Login ***
    st.stop()


# ===========================================================================
# 3. QUANT DESK DASHBOARD (โค้ดเดิมของคุณทั้งหมด นำมาต่อตรงนี้)
# โค้ดนี้จะรันก็ต่อเมื่อ st.session_state.logged_in = True เท่านั้น
# ===========================================================================

UP, DOWN, ACC, GOLD, INK, MUT = (C["up"], C["down"], C["accent"], C["gold"],
                                 C["ink"], C["muted"])

# ---------------------------------------------------------------------------
# STYLE  — everything readable regardless of the Streamlit theme file
# ---------------------------------------------------------------------------
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Inter:wght@400;500;600;700;800&display=swap');

:root {{ --ink:{INK}; --muted:{MUT}; --acc:{ACC}; --bg:{C['bg']};
  --panel:{C['panel']}; --border:{C['border']}; }}

/* Apple-style system font first, Inter fallback */
html, body, .stApp, [class*="css"], button, input, select, textarea,
[data-testid="stSidebar"] *, [data-testid="stMarkdownContainer"] * {{
  font-family:-apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Roboto,
              Helvetica, Arial, sans-serif !important;
  -webkit-font-smoothing:antialiased;
}}
.mono, .mono * {{ font-family:'IBM Plex Mono', ui-monospace, monospace !important;
  font-variant-numeric:tabular-nums; }}

.stApp {{ background:
  radial-gradient(1100px 520px at 82% -8%, #16294a 0%, rgba(11,18,32,0) 55%),
  {C['bg']} !important; color:{INK}; }}

/* kill the white default header + tidy the cloud toolbar */
[data-testid="stHeader"] {{ background:transparent !important; }}
[data-testid="stToolbar"] {{ right:.6rem; }}
.block-container {{ padding-top:3rem; padding-bottom:3rem; max-width:1180px; }}

/* generic readable text */
.stApp, p, span, li, label, div {{ color:{INK}; }}
.muted {{ color:{MUT} !important; }}

/* ---- SIDEBAR: force high contrast even without config.toml ---- */
[data-testid="stSidebar"] {{ background:#0C1626; border-right:1px solid {C['border']}; }}
[data-testid="stSidebar"] * {{ color:{INK}; }}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"],
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] * {{
  color:#9CABC4 !important; font-size:.78rem; line-height:1.35; }}
/* recolor the (otherwise red) slider to brand cyan, best-effort */
[data-testid="stSidebar"] [data-baseweb="slider"] [role="slider"] {{
  background:{ACC} !important; box-shadow:0 0 0 2px {C['bg']} !important; }}
[data-testid="stSidebar"] [data-baseweb="slider"] > div > div > div {{
  background:{ACC} !important; }}
.side-h {{ font-weight:700; font-size:1.05rem; color:{INK}; margin-bottom:.2rem; }}
.side-p {{ color:#9CABC4; font-size:.82rem; line-height:1.45; margin-bottom:1rem; }}

/* ---- headers / hierarchy ---- */
.brand {{ font-weight:800; font-size:1.55rem; letter-spacing:-.02em; color:{INK}; }}
.brand b {{ color:{ACC}; }}
.kicker {{ font-size:.7rem; letter-spacing:.18em; text-transform:uppercase;
  color:{MUT}; margin-top:.15rem; }}
.h2 {{ font-weight:700; font-size:1.5rem; letter-spacing:-.02em; color:{INK};
  margin:2.6rem 0 .15rem; }}
.sub {{ color:{MUT}; font-size:.92rem; margin-bottom:1rem; max-width:42rem; }}

/* ---- cards: style Streamlit's bordered container as a dark panel ---- */
[data-testid="stVerticalBlockBorderWrapper"] {{
  background:{C['panel']}; border:1px solid {C['border']} !important;
  border-radius:18px; }}

.kpi {{ background:{C['panel']}; border:1px solid {C['border']}; border-radius:16px;
  padding:1.05rem 1.15rem; height:100%; }}
.kpi .lab {{ font-size:.7rem; letter-spacing:.13em; text-transform:uppercase;
  color:{MUT}; margin-bottom:.4rem; }}
.kpi .px {{ font-family:'IBM Plex Mono',monospace; font-weight:600; font-size:1.7rem;
  color:{INK}; letter-spacing:-.01em; line-height:1.1; }}
.kpi .chg {{ font-family:'IBM Plex Mono',monospace; font-size:.85rem; margin-top:.45rem;
  display:inline-block; }}

.panel {{ background:{C['panel']}; border:1px solid {C['border']}; border-radius:16px;
  padding:1.1rem 1.2rem; }}
.phead {{ font-size:.7rem; letter-spacing:.16em; text-transform:uppercase; color:{MUT};
  margin-bottom:.45rem; }}

.coname {{ font-weight:700; font-size:1.3rem; letter-spacing:-.01em; color:{INK}; }}
.cometa {{ font-family:'IBM Plex Mono',monospace; font-size:.74rem; color:{MUT};
  letter-spacing:.04em; margin-top:.15rem; }}
.rankpill {{ font-family:'IBM Plex Mono',monospace; font-weight:600; font-size:.68rem;
  letter-spacing:.1em; color:{C['bg']}; background:{ACC}; padding:.18rem .6rem;
  border-radius:999px; }}
.tag {{ font-family:'IBM Plex Mono',monospace; font-size:.74rem; font-weight:600;
  padding:.22rem .6rem; border-radius:7px; display:inline-block; margin-top:.5rem; }}

.bigscore {{ font-family:'IBM Plex Mono',monospace; font-weight:600; font-size:2.6rem;
  color:{ACC}; line-height:1; }}
.bigscore small {{ font-size:1rem; color:{MUT}; }}

.reasons {{ list-style:none; padding:0; margin:.5rem 0 .2rem; }}
.reasons li {{ color:{INK}; font-size:.9rem; line-height:1.5; padding:.2rem 0 .2rem 1.1rem;
  position:relative; }}
.reasons li:before {{ content:'▸'; color:{ACC}; position:absolute; left:0; }}

.stat {{ display:flex; justify-content:space-between; font-family:'IBM Plex Mono',monospace;
  font-size:.85rem; padding:.32rem 0; border-bottom:1px solid {C['border']}; }}
.stat span:first-child {{ color:{MUT}; }}
.stat span:last-child {{ color:{INK}; }}

.disc {{ font-size:.8rem; color:{MUT}; border:1px solid {C['border']}; border-radius:14px;
  padding:1.1rem 1.3rem; margin-top:1.4rem; line-height:1.6; }}
.disc b {{ color:{INK}; }}
hr {{ border-color:{C['border']}; }}

/* เพิ่มเติม: ปุ่ม Logout สำหรับกลับไปหน้า Login */
button[kind="secondary"] {
    border-color: {C['border']};
    color: {MUT};
}
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
    return f'<span class="chg" style="color:{col}">{arr} {abs(pct)*100:.2f}%</span>'

def standing(score):
    if score >= 70: return "Strong factor standing", UP
    if score >= 50: return "Moderate factor standing", ACC
    return "Weaker factor standing", DOWN


# ---------------------------------------------------------------------------
# CHART BUILDERS
# ---------------------------------------------------------------------------
def _dark(fig, h):
    fig.update_layout(height=h, margin=dict(l=6, r=6, t=10, b=6),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="IBM Plex Mono", color=MUT, size=11),
        hoverlabel=dict(bgcolor=C["panel"], font_family="IBM Plex Mono",
                        bordercolor=C["border"]))
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
        fig.add_trace(go.Scatter(x=h.index, y=h["MA50"], line=dict(color=ACC, width=1.3),
            name="MA50", hovertemplate="MA50 $%{y:.2f}<extra></extra>"), row=1, col=1)
    if "MA200" in h:
        fig.add_trace(go.Scatter(x=h.index, y=h["MA200"], line=dict(color=GOLD, width=1.3, dash="dot"),
            name="MA200", hovertemplate="MA200 $%{y:.2f}<extra></extra>"), row=1, col=1)
    if has_vol:
        vc = [UP if c >= o else DOWN for o, c in zip(h["Open"], h["Close"])]
        fig.add_trace(go.Bar(x=h.index, y=h["Volume"], marker_color=vc, opacity=0.4,
            showlegend=False, hovertemplate="vol %{y:,.0f}<extra></extra>"), row=2, col=1)
    fig.update_xaxes(rangeslider_visible=False, showgrid=False, color=MUT)
    fig.update_yaxes(showgrid=True, gridcolor=C["grid"], color=MUT)
    fig.update_layout(legend=dict(orientation="h", y=1.07, x=0, bgcolor="rgba(0,0,0,0)"))
    return _dark(fig, 440)

def area_chart(close, color, h=230):
    rgba = "rgba(232,179,65,0.16)" if color == GOLD else "rgba(57,186,230,0.14)"
    fig = go.Figure(go.Scatter(x=close.index, y=close, mode="lines",
        line=dict(color=color, width=2), fill="tozeroy", fillcolor=rgba,
        hovertemplate="%{x|%d %b %Y}<br>%{y:.2f}<extra></extra>"))
    fig.update_xaxes(showgrid=False, color=MUT)
    fig.update_yaxes(showgrid=True, gridcolor=C["grid"], color=MUT)
    return _dark(fig, h)

def mini_price(hist, h=210):
    close = hist["Close"]
    up = close.iloc[-1] >= close.iloc[0]
    col = UP if up else DOWN
    rgba = "rgba(38,208,124,0.14)" if up else "rgba(242,91,91,0.14)"
    fig = go.Figure(go.Scatter(x=close.index, y=close, mode="lines",
        line=dict(color=col, width=2), fill="tozeroy", fillcolor=rgba,
        hovertemplate="%{x|%b %Y}<br>$%{y:.2f}<extra></extra>"))
    fig.update_xaxes(showgrid=False, color=MUT)
    fig.update_yaxes(showgrid=True, gridcolor=C["grid"], color=MUT, tickprefix="$")
    return _dark(fig, h)

def radar(row, h=260):
    labels = ["Quality","Value","Growth","Momentum","Low-risk"]
    vals = [0 if pd.isna(row.get(f)) else row.get(f) for f in FACTORS]
    fig = go.Figure(go.Scatterpolar(r=vals+[vals[0]], theta=labels+[labels[0]],
        fill="toself", line=dict(color=ACC, width=2),
        fillcolor="rgba(57,167,240,0.22)",
        hovertemplate="%{theta}: %{r:.0f}/100<extra></extra>"))
    fig.update_layout(height=h, margin=dict(l=44,r=44,t=26,b=26),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="IBM Plex Mono", color=MUT, size=10),
        polar=dict(bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(range=[0,100], showticklabels=False, gridcolor=C["grid"], linecolor=C["grid"]),
            angularaxis=dict(gridcolor=C["grid"], linecolor=C["grid"], color=INK)))
    return fig

def stat(label, value): return f'<div class="stat"><span>{label}</span><span>{value}</span></div>'
PLT = {"displayModeBar": False}


# ---------------------------------------------------------------------------
# SIDEBAR — with plain-language explanations for every control
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown('<div class="side-h">⚙︎ Tune the strategy</div>'
                '<div class="side-p">Each slider sets how much that <b>style of signal</b> '
                'counts toward a stock\'s final score (0–100). Drag any of them and the '
                'whole ranking re-sorts instantly. There is no single "right" mix — it '
                'reflects what kind of company you care about.</div>', unsafe_allow_html=True)

    d = config.FACTOR_WEIGHTS
    w = {}
    w["quality"] = st.slider("Quality", 0.0, 1.0, float(d["quality"]), 0.05,
        help="Return on equity, profit margins, low debt, free cash flow.")
    st.caption("↑ Favors profitable, low-debt, financially solid companies.")

    w["value"] = st.slider("Value", 0.0, 1.0, float(d["value"]), 0.05,
        help="P/E, PEG, price-to-book, price-to-sales vs. peers.")
    st.caption("↑ Favors cheaper stocks over expensive ones (bargain hunting).")

    w["growth"] = st.slider("Growth", 0.0, 1.0, float(d["growth"]), 0.05,
        help="Revenue & earnings growth, expected forward improvement.")
    st.caption("↑ Favors companies growing sales and profits quickly.")

    w["momentum"] = st.slider("Momentum", 0.0, 1.0, float(d["momentum"]), 0.05,
        help="12-month price trend (skipping the last month) and price vs. 200-day average.")
    st.caption("↑ Favors stocks whose price has been trending up.")

    w["low_risk"] = st.slider("Low-risk", 0.0, 1.0, float(d["low_risk"]), 0.05,
        help="Volatility, beta near 1, and worst historical drawdown.")
    st.caption("↑ Favors steadier stocks with calmer price swings.")

    st.divider()
    n_picks = st.number_input("Number of picks", 1, 10, config.N_PICKS,
        help="How many top-ranked stocks to feature in the shortlist below.")

    st.divider()
    if st.button("↻ Refresh market data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.caption("Prices via Yahoo Finance, cached ~6h. Long-horizon scoring "
               "doesn't need real-time data.")
    
    # เพิ่มปุ่ม Logout ใน Sidebar
    st.divider()
    if st.button("← Logout", use_container_width=True):
        st.session_state.logged_in = False
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
    st.markdown('<div class="brand">◆ QUANT <b>DESK</b></div>'
                '<div class="kicker">Factor terminal · long-horizon ranking</div>',
                unsafe_allow_html=True)
with hc2:
    st.markdown(f'<div class="kicker" style="text-align:right">As of</div>'
                f'<div class="mono" style="text-align:right;color:{INK};font-size:1.05rem;'
                f'font-weight:600">{today}</div>', unsafe_allow_html=True)

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
        tag_txt, tag_col = standing(r["composite"])
        st.markdown(f'<div class="phead">Factor scorecard</div>'
                    f'<div class="coname">{r.get("name") or sel}</div>'
                    f'<div class="cometa">{sel} · rank #{int(r["rank"])} of {len(scored)}</div>'
                    f'<div class="bigscore" style="margin-top:.55rem">{r["composite"]:.0f}'
                    f'<small> / 100</small></div>'
                    f'<span class="tag" style="background:rgba(57,167,240,.14);color:{tag_col}">'
                    f'{tag_txt}</span>', unsafe_allow_html=True)
        st.plotly_chart(radar(r, h=250), use_container_width=True, config=PLT)


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
            f'<div style="margin-top:.35rem">{chg_html(gchg)} '
            f'<span class="cometa">vs. yesterday</span></div>'
            f'<div style="margin-top:.9rem">'
            f'{stat("52-week high", "—" if g52.empty else f"${g52.max():,.2f}")}'
            f'{stat("52-week low", "—" if g52.empty else f"${g52.min():,.2f}")}'
            f'</div>', unsafe_allow_html=True)
    with gc2:
        if gold_df is not None and not gold_df.empty:
            st.plotly_chart(area_chart(gold_df["Close"], GOLD), use_container_width=True, config=PLT)
        else:
            st.info("Gold data unavailable right now — hit ↻ Refresh.")


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
                        f'<span class="coname">&nbsp;{row.get("name") or sym}</span>'
                        f'<div class="cometa">{sym} · {row.get("sector","—")}</div>',
                        unsafe_allow_html=True)
            if sym in history:
                st.plotly_chart(mini_price(history[sym]), use_container_width=True, config=PLT)
        with c2:
            st.markdown('<div class="phead">Composite score</div>'
                        f'<div class="bigscore">{row["composite"]:.0f}<small> / 100</small></div>'
                        f'<div class="phead" style="margin-top:.6rem">Why it ranks here</div>',
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
            st.markdown(f'<div style="margin-top:.6rem">{stats}</div>', unsafe_allow_html=True)


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
    return f"color:{UP}" if v >= 0 else f"color:{DOWN}"

sty = (tbl.style
       .format({"Price": "${:,.2f}", "5y return": "{:+.0%}", "Score": "{:.1f}",
                "quality": "{:.0f}", "value": "{:.0f}", "growth": "{:.0f}",
                "momentum": "{:.0f}", "low-risk": "{:.0f}"})
       .map(color_ret, subset=["5y return"])
       .background_gradient(subset=["Score"], cmap="Blues"))
st.dataframe(sty, use_container_width=True, hide_index=True, height=440)

if failed:
    st.caption("⚠︎ Skipped (no data): " + ", ".join(failed))


# ---------------------------------------------------------------------------
# METHODOLOGY + DISCLAIMER
# ---------------------------------------------------------------------------
with st.expander("How the score is built (methodology)"):
    st.markdown("""
Every company is scored **relative to the others** on five factor groups —
never against fixed thresholds. "Cheap" or "fast-growing" only means so
*compared to today's pool*.

1. **Quality** — return on equity, margins, low debt, free-cash-flow yield.
2. **Value** — P/E, PEG, price-to-book, price-to-sales (cheaper ranks higher).
3. **Growth** — revenue & earnings growth, plus expected forward improvement.
4. **Momentum** — 12-month price trend (skipping the last month) and price vs. its 200-day average.
5. **Low-risk** — volatility, distance of beta from 1, and worst historical drawdown.

Each raw metric is winsorised, turned into a **0–100 percentile** across the
pool, and direction-corrected so higher = better. A factor score is the average
of its metrics; the **composite** is the weighted average of the five factors
(weights from the sidebar). Low-coverage names are dropped, and each pick shows
its **data coverage**.

These factors are linked to long-run returns *on average, across many names and
years* — never as a guarantee for any single stock. This tool surfaces factor
exposure transparently; it does not forecast prices.
""")

st.markdown(f"""
<div class="disc">
<b>Not investment advice.</b> Quant Desk is an educational research tool. It ranks
stocks on historical and fundamental factors; it does <b>not</b> predict future
prices. Factor scores describe the past and present, which need not repeat. A
short shortlist is highly concentrated and ignores your goals, horizon, and risk
tolerance. Gold and equity data from Yahoo Finance may be delayed or inaccurate.
Do your own research and consider a licensed financial professional before
investing. You alone are responsible for your decisions.
</div>
""", unsafe_allow_html=True)
