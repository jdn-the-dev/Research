# ---------- CONFIG ----------
from dotenv import load_dotenv, find_dotenv
import os, ast

load_dotenv(find_dotenv())        # loads .env from project root

EXCHANGE      = os.getenv("EXCHANGE", "kraken")
PAIRS_LIMIT   = int(os.getenv("PAIRS_LIMIT", 10))
TF            = os.getenv("TF", "1h")
EMA_LEN       = int(os.getenv("EMA_LEN", 200))
LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", 90))
ORDERFLOW_WIN = int(os.getenv("ORDERFLOW_WIN", 50))
CRYPP_API_KEY = os.getenv("CRYPP_API_KEY", "")
# parse the comma string into a dict like {'A':0.35, ...}
w_str = os.getenv("WEIGHTS", "0.35,0.25,0.25,0.15")
w_vals = [float(x) for x in w_str.split(",")]
WEIGHTS = dict(A=w_vals[0], B=w_vals[1], C=w_vals[2], D=w_vals[3])


# ---------- SET-UP ----------
import ccxt, pandas as pd, numpy as np, datetime as dt, requests, math
exch = ccxt.kraken({'enableRateLimit': True})

# ---------- EMA helper (pure pandas) ----------
def ema(series, length):
    """Exponential Moving Average via pandas; TA-Lib not required."""
    return series.ewm(span=length, adjust=False).mean()

# ---------- HELPERS ----------
STABLES = {'USDT', 'USDC', 'FDUSD', 'DAI', 'BUSD', 'TUSD'}

def top_volume_pairs(limit=10):
    tickers = exch.fetch_tickers()
    pairs = []
    for sym, t in tickers.items():
        if '/USDT' not in sym or t['quoteVolume'] is None:
            continue
        base = sym.split('/')[0]
        if base in STABLES:            # <- FILTER
            continue
        pairs.append((sym, t['quoteVolume']))
    pairs.sort(key=lambda x: x[1], reverse=True)
    return [s for s, _ in pairs[:limit]]


def ohlcv_df(sym, since_ms):
    data = exch.fetch_ohlcv(sym, TF, since=since_ms)
    if not data or len(data) == 0:
        # Return empty DataFrame with expected columns if no data
        return pd.DataFrame(columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
    df = pd.DataFrame(data, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
    df['ts'] = pd.to_datetime(df['ts'], unit='ms', utc=True)
    return df

def ema_bounce_prob(df):
    e = ema(df['close'], EMA_LEN)
    price = df['close']
    events = hits = 0
    for i in range(len(df) - 5):
        if abs(price[i] - e[i]) / e[i] < 0.01:          # within ±1 %
            events += 1
            if (price.iloc[i + 1:i + 5] > e.iloc[i + 1:i + 5]).any():
                hits += 1
    return hits / events if events else np.nan, events

def orderflow_score(df):
    if len(df) < ORDERFLOW_WIN + 2:
        return np.nan                   # not enough candles

    price_diff = df['close'].diff()
    std = price_diff.std()
    if std == 0 or np.isnan(std):
        return np.nan                  # flat price ⇒ meaningless delta

    buys  = price_diff.clip(lower=0).rolling(ORDERFLOW_WIN).sum().iloc[-1]
    sells = price_diff.clip(upper=0).abs().rolling(ORDERFLOW_WIN).sum().iloc[-1]
    delta = buys - sells

    # RVOL
    rvol_med = df['vol'].rolling(24 * 30).median().iloc[-1]
    if rvol_med == 0 or np.isnan(rvol_med):
        rvol = 1                       # neutral
    else:
        rvol = df['vol'].iloc[-ORDERFLOW_WIN:].sum() / (rvol_med * ORDERFLOW_WIN)

    z = (delta / std) + (rvol - 1)
    return 100 * (1 / (1 + np.exp(-z)))   # sigmoid 0-100

def structure_score(df):
    if df.empty or 'ts' not in df.columns or 'close' not in df.columns:
        return 50  # or another neutral/default score
    # Ensure 'ts' is datetime and set as index for resampling
    if not pd.api.types.is_datetime64_any_dtype(df['ts']):
        df['ts'] = pd.to_datetime(df['ts'], utc=True, errors='coerce')
    # Drop rows with NaT in 'ts'
    df = df.dropna(subset=['ts'])
    if df.empty:
        return 50
    trend4h = df['close'].iloc[-1] > ema(df['close'], 200).iloc[-1]
    daily = df.set_index('ts')['close'].resample('1D').last().dropna()
    trend1d = daily.iloc[-1] > ema(daily, 200).iloc[-1]
    trend_bias = 100 if trend4h and trend1d else 50 if (trend4h or trend1d) else 0
    swings = df['close'].rolling(5, center=True).apply(
        lambda x: x.iloc[2] if len(x) == 5 and (x.iloc[2] == x.max() or x.iloc[2] == x.min()) else np.nan
    ).dropna()
    up = swings.diff().dropna() > 0
    struct = 100 * up.mean()
    return 0.6 * trend_bias + 0.4 * struct

def news_sentiment(symbol, max_items=5):
    """
    Returns (sentiment_score_0-100, headlines_list).

    headlines_list = [
        {'title': str, 'pos': int, 'neg': int, 'url': str},
        ...
    ]  (up to max_items, newest first)
    """
    ticker = symbol.split('/')[0]
    url = (f'https://cryptopanic.com/api/v1/posts/?auth_token={CRYPP_API_KEY}'
           f'&currencies={ticker}&filter=hot')
    try:
        res = requests.get(url, timeout=5).json()
        items = []
        deltas = []
        for post in res['results'][:max_items]:
            pos = post['votes']['positive']
            neg = post['votes']['negative']
            deltas.append(pos - neg)
            items.append({
                'title': post['title'][:120],   # trim long titles
                'pos': pos,
                'neg': neg,
                'url': post['url']
            })
        if not deltas:
            return 50, []                     # neutral if no coverage
        score = np.tanh(np.mean(deltas))      # –1 … +1
        return ((score + 1) / 2) * 100, items
    except Exception:
        return 50, []                         # neutral on API hiccup
def composite(row):
    # Map WEIGHTS keys to actual DataFrame columns
    mapping = dict(A='Bounce_%', B='OrderFlow_%', C='Structure_%', D='Sentiment_%')
    return sum(row[mapping[k]] * WEIGHTS[k] for k in WEIGHTS)

# ---------- MAIN LOOP ----------
since = int((dt.datetime.utcnow() - dt.timedelta(days=LOOKBACK_DAYS)).timestamp() * 1000)
rows = []
for sym in top_volume_pairs(PAIRS_LIMIT):
    df = ohlcv_df(sym, since)
    pA, events = ema_bounce_prob(df)
    if np.isnan(pA) or events < 8:
        continue
    sent_score, headlines = news_sentiment(sym)
    rows.append({
        'symbol':        sym,
        'Bounce_%':      pA * 100,
        'OrderFlow_%':   orderflow_score(df),
        'Structure_%':   structure_score(df),
        'Sentiment_%':   sent_score,
        'news':          headlines          # <-- keep for later printing
    })
# ----- summary table -----
out = pd.DataFrame(rows).fillna(50)
out['Composite_%'] = out.apply(composite, axis=1)

cols = ['symbol', 'Composite_%', 'Bounce_%',
        'OrderFlow_%', 'Structure_%', 'Sentiment_%']
table = out[cols].round(0).sort_values('Composite_%', ascending=False).head(10)

print("\n=== EMA-Bounce Long Setups (scores 0-100) ===")
print(table.to_string(index=False))

# ----- headlines for each symbol -----
print("\nTop news driving Sentiment:")
for _, row in table.iterrows():
    sym = row['symbol']
    news_items = out[out['symbol'] == sym]['news'].iloc[0]
    if not news_items:
        continue
    print(f"\n[{sym}]")
    for it in news_items:
        arrow = '↑' if it['pos'] > it['neg'] else '↓' if it['neg'] > it['pos'] else '→'
        print(f" {arrow}  +{it['pos']} / -{it['neg']}  {it['title']}")
        print(f"    {it['url']}")