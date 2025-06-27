#!/usr/bin/env python3
from dotenv import load_dotenv
import os
import sys
import requests

# ─── Load .env ────────────────────────────────────────────────────────────────
load_dotenv()  # pip install python-dotenv
API_KEY = os.getenv("CHART_IMG_API_KEY")
if not API_KEY:
    print("❌ CHART_IMG_API_KEY not found in .env", file=sys.stderr)
    sys.exit(1)

# ─── Common payload settings ───────────────────────────────────────────────────
COMMON = {
    "width": 800,
    "height": 600,
    "theme": "Dark",
    "timezone": "Etc/UTC",
    "studies": [
        {"name": "Volume", "forceOverlay": True},
        {"name": "Relative Strength Index"},
        {
            "name": "Stochastic RSI",
            "forceOverlay": False,
            "input": {"in_0": 14, "in_1": 14, "in_2": 3, "in_3": 3},
            "override": {
                "%K.visible": True,
                "%K.linewidth": 1,
                "%K.plottype": "line",
                "%K.color": "rgb(33,150,243)",
                "%D.visible": True,
                "%D.linewidth": 1,
                "%D.plottype": "line",
                "%D.color": "rgb(255,109,0)",
                "UpperLimit.visible": True,
                "UpperLimit.linestyle": 2,
                "UpperLimit.linewidth": 1,
                "UpperLimit.value": 80,
                "UpperLimit.color": "rgb(120,123,134)",
                "LowerLimit.visible": True,
                "LowerLimit.linestyle": 2,
                "LowerLimit.linewidth": 1,
                "LowerLimit.value": 20,
                "LowerLimit.color": "rgb(120,123,134)",
                "Hlines Background.visible": True,
                "Hlines Background.color": "rgba(33,150,243,0.1)",
            },
        },
    ],
}

_API_URL = "https://api.chart-img.com/v2/tradingview/advanced-chart"


def fetch_chart_bytes(symbol: str, interval: str = "1h") -> bytes:
    """
    Fetches a rendered chart PNG for the given symbol+interval.
    Returns the raw bytes of the PNG.
    """
    payload = {
        **COMMON,
        "symbol": symbol,
        "interval": interval,
    }
    headers = {
        "x-api-key": API_KEY,
        "Content-Type": "application/json",
    }

    resp = requests.post(_API_URL, headers=headers, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.content


def save_chart(symbol: str, interval: str = "1h", out_dir: str = "charts") -> str:
    """
    Fetches and writes the PNG to disk.
    Returns the filepath.
    """
    os.makedirs(out_dir, exist_ok=True)
    data = fetch_chart_bytes(symbol, interval)
    filename = f"chart-{symbol.replace(':','_')}-{interval}.png"
    path = os.path.join(out_dir, filename)
    with open(path, "wb") as f:
        f.write(data)
    return path


# ─── CLI Entrypoint ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Fetch and save a tradingview-style chart image"
    )
    parser.add_argument("symbol", help="e.g. BINANCE:BTCUSDT or COINBASE:ETHUSD")
    parser.add_argument(
        "--interval", "-i", default="1h", help="Candlestick interval (1h, 4h, 1D, etc.)"
    )
    parser.add_argument(
        "--out", "-o", default=None, help="Output PNG file (defaults to charts/…) "
    )
    args = parser.parse_args()

    try:
        if args.out:
            out_path = args.out
            data = fetch_chart_bytes(args.symbol, args.interval)
            with open(out_path, "wb") as fp:
                fp.write(data)
        else:
            out_path = save_chart(args.symbol, args.interval)
        print(f"✅ {args.symbol} ({args.interval}) → {out_path}")
    except requests.HTTPError as e:
        print(
            f"❌ Failed ({e}) – {e.response.text}",
            file=sys.stderr,
        )
        sys.exit(1)
