import ccxt
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

def calculate_ema(series, period=9):
    return series.ewm(span=period, adjust=False).mean()

def get_ohlcv_df(exchange, symbol, timeframe='1d', limit=100):
    data = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    return df

def get_trend_strength_and_direction(df, short_ema=9, long_ema=21):
    # Calculate short and long EMAs for trend determination.
    df['short_ema'] = df['close'].ewm(span=short_ema, adjust=False).mean()
    df['long_ema'] = df['close'].ewm(span=long_ema, adjust=False).mean()
    latest_short = df.iloc[-1]['short_ema']
    latest_long = df.iloc[-1]['long_ema']
    if latest_short > latest_long:
        return 'bullish'
    elif abs(latest_short - latest_long) < 0.01 * latest_long:
        return 'neutral'
    else:
        return 'bearish'

def assign_bounce_likelihood(diff_percent, trend_direction, approach_direction):
    if trend_direction == 'bullish':
        if approach_direction == 'above':
            return "High"
        else:
            return "Medium"
    elif trend_direction == 'bearish':
        if approach_direction == 'below':
            return "High"
        else:
            return "Medium"
    else:
        return "Medium" if approach_direction == 'above' else "Low"

def fetch_symbol_data(exchange, symbol, timeframe, limit, threshold_percent, ema_period=9):
    try:
        df = get_ohlcv_df(exchange, symbol, timeframe=timeframe, limit=limit)
        if df.empty:
            return None
        # Calculate the EMA based on the given period (e.g., 9 or 15)
        ema_label = f"{ema_period}_EMA"
        df[ema_label] = calculate_ema(df['close'], period=ema_period)
        # Determine the trend using the chosen short EMA vs a 21-period long EMA
        trend = get_trend_strength_and_direction(df, short_ema=ema_period, long_ema=21)
        latest = df.iloc[-1]
        latest_close = latest['close']
        latest_ema = latest[ema_label]
        diff = latest_close - latest_ema
        diff_percent = (diff / latest_ema) * 100 if latest_ema != 0 else None
        approach_direction = "above" if diff > 0 else "below"
        # Check if the last candle 'touched' the EMA
        touched_ema = (latest['low'] <= latest_ema <= latest['high'])
        if diff_percent is not None and (abs(diff_percent) <= threshold_percent) and (not touched_ema):
            bounce_prediction = assign_bounce_likelihood(diff_percent, trend, approach_direction)
            return {
                'Symbol': symbol,
                'Last Close': round(latest_close, 4),
                ema_label: round(latest_ema, 4),
                'Diff': round(diff, 4),
                'Diff (%)': round(diff_percent, 2),
                'Trend': trend,
                'Approach': approach_direction,
                'Bounce Likelihood': bounce_prediction
            }
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
    return None

def scan_cryptos_close_to_ema_with_prediction(exchange, symbols, ema_period=9,
                                              threshold_percent=1.0,
                                              timeframe='1d', limit=100):
    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_symbol = {
            executor.submit(fetch_symbol_data, exchange, symbol, timeframe, limit, threshold_percent, ema_period): symbol 
            for symbol in symbols
        }
        for future in as_completed(future_to_symbol):
            result = future.result()
            if result:
                results.append(result)
    if results:
        out_df = pd.DataFrame(results)
        # Sort by the absolute value of Diff (%)
        out_df.sort_values(by='Diff (%)', key=abs, inplace=True)
        out_df.reset_index(drop=True, inplace=True)
        return out_df
    else:
        ema_label = f"{ema_period}_EMA"
        return pd.DataFrame(columns=[
            'Symbol', 'Last Close', ema_label, 'Diff', 'Diff (%)',
            'Trend', 'Approach', 'Bounce Likelihood'
        ])

if __name__ == "__main__":
    # Initialize Kraken exchange via ccxt
    kraken = ccxt.kraken()
    kraken.load_markets()

    # Get tickers and extract top 50 /USD pairs by 24h volume
    tickers = kraken.fetch_tickers()
    usd_pairs = []
    for sym, info in tickers.items():
        if sym.endswith("/USD") and not sym.startswith("GBP") and not sym.startswith("EUR") and not sym.startswith("AUD"):
            volume_24h = info.get('quoteVolume', info.get('volume', 0.0))
            usd_pairs.append((sym, float(volume_24h)))
    usd_pairs.sort(key=lambda x: x[1], reverse=True)
    top_50_kraken_usd_pairs = [x[0] for x in usd_pairs[:50]]

    threshold = 1.0  # +/- 1% threshold from the chosen EMA

    # To use the 15 EMA instead of 9, simply set ema_period=15
    ema_period = 9  # Change to 9 if you want the original behavior
    results_df = scan_cryptos_close_to_ema_with_prediction(
        exchange=kraken,
        symbols=top_50_kraken_usd_pairs,
        ema_period=ema_period,
        threshold_percent=threshold,
        timeframe='1d',
        limit=100
    )

    if not results_df.empty:
        print(f"Pairs near the {ema_period} EMA (±{threshold}%) *without* touching it, plus bounce likelihood:")
        print(results_df)
    else:
        print(f"No cryptos found within ±{threshold}% of their {ema_period} EMA without touching it.")
        ema_period = 15  # Change to 9 if you want the original behavior
        results_df = scan_cryptos_close_to_ema_with_prediction(
            exchange=kraken,
            symbols=top_50_kraken_usd_pairs,
            ema_period=ema_period,
            threshold_percent=threshold,
            timeframe='1d',
            limit=100
        )
        if not results_df.empty:
            print(f"Pairs near the {ema_period} EMA (±{threshold}%) *without* touching it, plus bounce likelihood:")
            print(results_df)
        else:
            print(f"No cryptos found within ±{threshold}% of their {ema_period} EMA without touching it.")