import ccxt
import pandas as pd
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# ─── CONFIG ──────────────────────────────────────────────────────────────────
EXCHANGE_ID   = "kraken"
RSI_PERIOD    = 14
HISTORY_BARS  = 500    # fetch this many candles to let smoothing converge
CCXT_TIMEOUT  = 30000  # in ms

# Initialize Kraken
exchange = getattr(ccxt, EXCHANGE_ID)({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"},
    "timeout": CCXT_TIMEOUT,
})
exchange.load_markets()

def fetch_ohlc_ccxt(symbol: str, timeframe: str, limit: int = HISTORY_BARS):
    """
    Fetch `limit` OHLCV bars via CCXT and return a pandas Series of closes 
    (oldest first) so smoothing has enough history to match TradingView.
    """
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=["ts","open","high","low","close","vol"])
    df = df.sort_values("ts")
    return df["close"].astype(float).reset_index(drop=True)

def compute_rsi(closes: pd.Series, period: int = RSI_PERIOD) -> float:
    """
    Compute Wilder’s RSI over the full `closes` history and return the final value.
    This matches TradingView’s native indicator exactly.
    """
    delta = closes.diff().dropna()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)

    # initial average gain/loss (simple mean over first `period` deltas)
    avg_gain = gains.iloc[:period].mean()
    avg_loss = losses.iloc[:period].mean()

    # Wilder smoothing across the rest of the data
    gains_rest  = gains.iloc[period:]
    losses_rest = losses.iloc[period:]
    for g, l in zip(gains_rest, losses_rest):
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + l) / period

    rs  = avg_gain / avg_loss if avg_loss != 0 else float("inf")
    return 100 - (100 / (1 + rs))

def _rsi_for(symbol: str, tf: str) -> float:
    closes = fetch_ohlc_ccxt(symbol, tf)
    return compute_rsi(closes)

def fetch_rsi_intervals(symbol: str) -> dict:
    """
    Concurrently fetch RSI for 1h, 4h, and 1d for `symbol`.
    """
    funcs = {
        "1h": lambda s: _rsi_for(s, "1h"),
        "4h": lambda s: _rsi_for(s, "4h"),
        "1d": lambda s: _rsi_for(s, "1d"),
    }
    results = {}
    with ThreadPoolExecutor(max_workers=3) as ex:
        futures = { ex.submit(fn, symbol): tf for tf, fn in funcs.items() }
        for f in as_completed(futures):
            tf = futures[f]
            try:
                results[tf] = f.result()
            except Exception:
                results[tf] = None
    return results

# ─── EXAMPLE USAGE ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    tokens = ["BTC/USD", "ETH/USD", "XRP/USD"]
    all_results = []
    with ThreadPoolExecutor(max_workers=len(tokens)) as ex:
        futures = { ex.submit(fetch_rsi_intervals, t): t for t in tokens }
        for f in as_completed(futures):
            sym = futures[f]
            r = f.result()
            all_results.append((sym, r["1h"], r["4h"], r["1d"]))

    for sym, r1, r4, rD in all_results:
        print(f"{sym:<8} | RSI 1h: {r1:6.2f} | RSI 4h: {r4:6.2f} | RSI 1d: {rD:6.2f}")
