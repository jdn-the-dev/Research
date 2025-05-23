#!/usr/bin/env python3
"""
EMA-200  (1 d)  +  Stoch-RSI (4 h momentum)  +  EMA-50 proximity (15 m trigger)
Multi-time-frame scanner for high-volume USD pairs on Kraken.

author: Jaydon Lynch – 2025-05-23
"""

from __future__ import annotations
import math, os, time
from datetime import datetime, timezone

# --- third-party ------------------------------------------------------------
import numpy as np
# NumPy ≥2.0 no longer exports NaN (capital N).  Patch it back if needed.
if not hasattr(np, "NaN"):
    np.NaN = np.nan

import pandas as pd
import pandas_ta as ta
import ccxt
from tabulate import tabulate

# ---------------------------------------------------------------------------#
#                              CONFIGURATION                                 #
# ---------------------------------------------------------------------------#
EXCHANGE_ID          = "kraken"      # any ccxt spot exchange will work
TOP_N_BY_VOLUME      = 20            # how many symbols to scan
QUOTE_CURRENCY       = "USD"
EMA_DAILY_LEN        = 200
EMA_FAST_15M         = 50
STOCH_LEN            = 14
PROXIMITY_PCT        = 0.25          # price within ±0.25 % of EMA-50 (15 m)
MAX_RISK_PCT         = 0.02          # 2 % account risk per trade
ACCOUNT_EQUITY_USD   = 30_000        # <-- tweak to match your bankroll
# ---------------------------------------------------------------------------#

# initialise exchange (public endpoints only → no keys required)
exchange = getattr(ccxt, EXCHANGE_ID)({"enableRateLimit": True})

# ------------------------------ helpers ------------------------------------#
def ohlcv_df(symbol: str, tf: str, limit: int = 500) -> pd.DataFrame:
    """Fetch OHLCV and return as a typed DataFrame indexed by UTC timestamp."""
    raw = exchange.fetch_ohlcv(symbol, timeframe=tf, limit=limit)
    df  = pd.DataFrame(
        raw, columns=["ts", "open", "high", "low", "close", "volume"]
    )
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    return df.set_index("ts")

def stoch_rsi(series: pd.Series, length: int = 14) -> pd.DataFrame:
    """Return DataFrame with standard 'k' and 'd' columns (robust to version)."""
    df = ta.stochrsi(series, length=length, rsi_length=length, k=3, d=3)
    mapper = {}
    for col in df.columns:
        if "k" in col.lower():
            mapper[col] = "k"
        if "d" in col.lower():
            mapper[col] = "d"
    return df.rename(columns=mapper)

def last_cross_up(k: pd.Series) -> bool:
    return k.iat[-2] < 20 and k.iat[-1] > 20

def last_cross_dn(k: pd.Series) -> bool:
    return k.iat[-2] > 80 and k.iat[-1] < 80

def fit_score(dist_pct: float, cross: bool) -> int:
    """Rough 0-100 heuristic for prioritising the cleanness of the setup."""
    proximity = 1 - abs(dist_pct) / PROXIMITY_PCT        # 0-1
    momentum  = 1 if cross else 0.5
    return int(100 * proximity * momentum)

def position_size(entry: float, stop: float) -> float:
    risk_per_unit = abs(entry - stop)
    usd_at_risk   = ACCOUNT_EQUITY_USD * MAX_RISK_PCT
    return round(usd_at_risk / risk_per_unit, 3)

# -------------------------- build universe ---------------------------------#
tickers = exchange.fetch_tickers()
pairs = [
    sym
    for sym, tick in sorted(
        tickers.items(), key=lambda kv: kv[1]["quoteVolume"], reverse=True
    )
    if sym.endswith("/" + QUOTE_CURRENCY)
][:TOP_N_BY_VOLUME]
#filter: remove USDC and USDT pairs
for p in pairs:
    if p.startswith("USDC") or p.startswith("USDT") or p.startswith("EUR"):
        pairs.remove(p)

# ------------------------------ scan loop ----------------------------------#
ideas: list[dict] = []

for sym in pairs:
    try:
        d1  = ohlcv_df(sym, "1d", 365)
        h4  = ohlcv_df(sym, "4h", 250)
        m15 = ohlcv_df(sym, "15m", 250)
    except Exception as exc:
        print(f"{sym}: fetch error → {exc}")
        continue

    # require enough history to compute the 200-EMA
    if len(d1) < EMA_DAILY_LEN + 5:
        continue

    d1["ema200"] = ta.ema(d1["close"], length=EMA_DAILY_LEN)
    if pd.isna(d1["ema200"].iat[-1]) or pd.isna(d1["close"].iat[-1]):
        continue

    close_last = float(d1["close"].iat[-1])
    ema_last   = float(d1["ema200"].iat[-1])
    bias_long  = close_last > ema_last
    bias_short = close_last < ema_last

    # momentum filter – 4 h Stoch-RSI
    srsi4  = stoch_rsi(h4["close"])
    srsi15 = stoch_rsi(m15["close"])

    # 15 m trigger – EMA-50 proximity & local Stoch-RSI
    m15["ema50"] = ta.ema(m15["close"], length=EMA_FAST_15M)
    dist_pct     = (
        (m15["close"].iat[-1] - m15["ema50"].iat[-1]) / m15["close"].iat[-1] * 100
    )

    long_setup = (
        bias_long
        and last_cross_up(srsi4["k"])
        and abs(dist_pct) <= PROXIMITY_PCT
        and srsi15["k"].iat[-1] < 20
    )
    short_setup = (
        bias_short
        and last_cross_dn(srsi4["k"])
        and abs(dist_pct) <= PROXIMITY_PCT
        and srsi15["k"].iat[-1] > 80
    )

    if not (long_setup or short_setup):
        continue

    side  = "LONG" if long_setup else "SHORT"
    entry = float(m15["close"].iat[-1])
    atr14 = ta.atr(m15["high"], m15["low"], m15["close"], length=14).iat[-1]

    stop  = entry - 2 * atr14 if side == "LONG" else entry + 2 * atr14
    tgt   = (
        float(m15["high"][-30:-1].max())
        if side == "LONG"
        else float(m15["low"][-30:-1].min())
    )

    ideas.append(
        {
            "sym": sym,
            "side": side,
            "entry": round(entry, 3),
            "sl": round(stop, 3),
            "tgt": round(tgt, 3),
            "score": fit_score(dist_pct, long_setup or short_setup),
        }
    )

# ----------------------------- output --------------------------------------#
if ideas:
    df = pd.DataFrame(ideas).sort_values("score", ascending=False)
    print("\n--- Candidates that match EMA + Stoch-RSI playbook ---\n")
    print(tabulate(df, headers="keys", showindex=False, floatfmt=".3f"))
else:
    print("No pairs hit every filter right now – check again in ~15 m.")
