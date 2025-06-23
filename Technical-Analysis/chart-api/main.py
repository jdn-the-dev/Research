#!/usr/bin/env python3
from dotenv import load_dotenv
import os, sys, requests

# ─── Load .env ────────────────────────────────────────────────────────────────
load_dotenv()  # pip install python-dotenv
API_KEY = os.getenv("CHART_IMG_API_KEY")
if not API_KEY:
    print("❌ CHART_IMG_API_KEY not found in .env", file=sys.stderr)
    sys.exit(1)

# ─── Config ───────────────────────────────────────────────────────────────────
intervals = {
    "1h": {"symbol": "BINANCE:BTCUSDT", "interval": "1h"},
    "4h": {"symbol": "BINANCE:BTCUSDT", "interval": "4h"},
    "1d": {"symbol": "BINANCE:BTCUSDT", "interval": "1D"},
}

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
      "input": {
        "in_0": 14,
        "in_1": 14,
        "in_2": 3,
        "in_3": 3
      },
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
        "Hlines Background.color": "rgba(33,150,243,0.1)"
      }
    }
    ],
}

OUT_DIR = "charts"
os.makedirs(OUT_DIR, exist_ok=True)

def fetch_and_save(name, params):
    url = "https://api.chart-img.com/v2/tradingview/advanced-chart"
    headers = {
        "x-api-key": API_KEY,
        "Content-Type": "application/json",
    }
    payload = {**COMMON, **params}
    resp = requests.post(url, headers=headers, json=payload, timeout=15)
    resp.raise_for_status()
    path = os.path.join(OUT_DIR, f"chart-{name}.png")
    with open(path, "wb") as f:
        f.write(resp.content)
    print(f"✅ {name} → {path}")

if __name__ == "__main__":
    for name, p in intervals.items():
        try:
            fetch_and_save(name, p)
        except requests.HTTPError as e:
            print(f"❌ {name} failed: {e} – {e.response.text}", file=sys.stderr)
