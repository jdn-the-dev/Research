import ccxt
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# ─── CONFIGURATION ────────────────────────────────────────────────────────────
EXCHANGE_ID            = 'kraken'
PERCENT_THRESHOLD      = 1.0        # ≥ 10% 24 h change triggers an alert
TOP_N_BY_VOLUME        = 20          # only consider the top 20 symbols by 24 h quoteVolume
SCAN_INTERVAL_SEC      = 5           # run once every 5 s
MAX_WORKERS            = 50          # max threads to fetch tickers concurrently

# ─── GLOBAL STATE ──────────────────────────────────────────────────────────────
alerted_set = set()                  # symbols we have already “alerted” on

# ─── UTILITIES ─────────────────────────────────────────────────────────────────
def print_alert(symbol: str, pct: float):
    """
    Notify when a symbol crosses above PERCENT_THRESHOLD.
    Replace this body with e.g. Telegram/email/webhook as needed.
    """
    ts = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    print(f"[{ts}] 🔔 {symbol} is up {pct:.2f}% in the last 24 h! 🔔")


def fetch_ticker(exchange: ccxt.Exchange, symbol: str):
    """
    Fetch a single ticker and return (symbol, ticker_dict or None on error).
    """
    try:
        ticker = exchange.fetch_ticker(symbol)
        return symbol, ticker
    except Exception as e:
        ts = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
        print(f"[{ts}] Error fetching {symbol}: {e}")
        return symbol, None


def main():
    # 1. Instantiate Kraken (spot) in sync mode
    exchange = getattr(ccxt, EXCHANGE_ID)({
        'enableRateLimit': True,
    })

    # 2. Load markets once at startup and collect all active spot symbols
    exchange.load_markets()
    spot_symbols = [
        symbol
        for symbol, market in exchange.markets.items()
        if market.get('spot') and market.get('active')
    ]

    if not spot_symbols:
        print("⚠️  No active spot symbols found on Kraken. Check exchange ID/market filtering.")
        return

    print(
        f"Scanning {len(spot_symbols)} active spot symbols on Kraken every "
        f"{SCAN_INTERVAL_SEC} s (threshold: {PERCENT_THRESHOLD:.1f}% / top {TOP_N_BY_VOLUME} by volume)\n"
    )

    # 3. Continuous scan loop
    while True:
        ts = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
        print(f"[{ts}] Starting new scan...")

        valid_tickers = []

        # 3a. Use ThreadPoolExecutor to fetch tickers in parallel
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_symbol = {
                executor.submit(fetch_ticker, exchange, sym): sym
                for sym in spot_symbols
            }

            for future in as_completed(future_to_symbol):
                sym = future_to_symbol[future]
                sym, ticker = future.result()
                if not ticker:
                    continue
                qvol = ticker.get('quoteVolume')
                pct  = ticker.get('percentage')   # 24 h change in %
                if qvol is None or pct is None:
                    continue
                valid_tickers.append((sym, ticker))

        if not valid_tickers:
            print("⚠️  No valid tickers fetched this round.")
        else:
            # 4. Sort by quoteVolume descending, take top N
            valid_tickers.sort(key=lambda pair: pair[1]['quoteVolume'], reverse=True)
            top_n = valid_tickers[:TOP_N_BY_VOLUME]

            # 5. Check percentage threshold among top N
            for sym, ticker in top_n:
                pct = ticker['percentage']
                if pct >= PERCENT_THRESHOLD:
                    if sym not in alerted_set:
                        alerted_set.add(sym)
                        print_alert(sym, pct)
                else:
                    if sym in alerted_set:
                        alerted_set.remove(sym)

        # 6. Sleep until next scan
        time.sleep(SCAN_INTERVAL_SEC)


if __name__ == '__main__':
    main()
