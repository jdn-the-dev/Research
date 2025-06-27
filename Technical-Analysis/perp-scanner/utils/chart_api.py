from dotenv import load_dotenv
import os
import requests

load_dotenv()
API_KEY = os.getenv("CHART_IMG_API_KEY")

URL = "https://api.chart-img.com/v2/tradingview/advanced-chart"
HEADERS = {
    "x-api-key": API_KEY if API_KEY else "",
    "Content-Type": "application/json",
}

COMMON = {
    "width": 800,
    "height": 600,
    "theme": "Dark",
    "timezone": "Etc/UTC",
    "studies": [
        {"name": "Volume", "forceOverlay": True},
        {"name": "Relative Strength Index"},
    ],
}

def fetch_chart(symbol: str, interval: str) -> bytes:
    """Return raw PNG bytes for the given symbol and interval."""
    if not API_KEY:
        raise RuntimeError("CHART_IMG_API_KEY not set")
    payload = {**COMMON, "symbol": symbol, "interval": interval}
    resp = requests.post(URL, headers=HEADERS, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.content
