# ◆ Quant Desk

A single-page **trading-terminal dashboard** that ranks a pool of stocks on five
investing **factors** — quality, value, growth, momentum, and low-risk — and
surfaces the strongest **long-horizon** candidates with transparent scores. Also
shows a market-pulse strip (S&P 500 / Nasdaq / Dow / Gold), a candlestick chart
with moving averages and volume, and a **daily gold price** panel (XAU, US$/oz).

> **Not investment advice.** This is an educational research tool. It does **not**
> predict prices and cannot tell you what will go up. Every score describes the
> past and present, which need not repeat. Do your own research.

---

## Why factors instead of "predictions"

Nobody can reliably predict which stock rises tomorrow — short-term moves are
mostly noise. What *is* measurable is a company's **fundamentals and price
behaviour**. Decades of research link certain traits (cheap valuation, high
quality, positive momentum, low volatility) to better long-run returns *on
average, across many names* — never as a guarantee for one stock. Quant Desk
scores those traits **relative to the pool** and ranks them. Every number is
auditable; nothing is a black box.

## Files

| File | Purpose |
|------|---------|
| `app.py` | The Streamlit UI (hero, pick cards, charts, tables) |
| `quant_engine.py` | The scoring logic — pure, testable, no network |
| `data_loader.py` | Pulls fundamentals + 5y prices from Yahoo Finance |
| `config.py` | **Tweak me** — factor weights & settings |
| `tickers.txt` | **Edit me** — the universe of stocks to rank |
| `.streamlit/config.toml` | Dark theme colours |
| `requirements.txt` | Dependencies |

## Run it locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

It opens at `http://localhost:8501`.

## Deploy free on Streamlit Community Cloud

1. Push this folder to a **GitHub** repo (keep the file structure, including the
   `.streamlit/` folder).
2. Go to **share.streamlit.io**, sign in with GitHub.
3. Click **New app**, pick your repo/branch, set the main file to `app.py`,
   and **Deploy**.

That's it — it builds from `requirements.txt` automatically.

## Customize

- **Which stocks to rank:** edit `tickers.txt` (one Yahoo Finance symbol per
  line; `#` starts a comment). More names = a fairer comparison; aim for 20+.
- **Your strategy:** change `FACTOR_WEIGHTS` in `config.py`, or move the sliders
  in the app's sidebar live. Raise the factors you believe in.
- **Look:** colours live in `config.py` (`COLORS`) and `.streamlit/config.toml`.

## How the score works (short version)

Each raw metric (ROE, P/E, revenue growth, 12-month momentum, volatility, …) is
turned into a **0–100 percentile across the pool**, direction-corrected so higher
is always better. A factor's score is the average of its metrics; the
**composite** is the weighted average of the five factors. Stocks missing too
much data are dropped, and each pick shows its **data coverage**. Full details
are in the app's *Methodology* panel.
