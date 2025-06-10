import requests
import time
from PyQt5.QtCore import QObject, pyqtSignal
from concurrent.futures import ThreadPoolExecutor, as_completed
from plyer import notification

# ─── CONFIGURATION ────────────────────────────────────────────────────────────
SPOT_API_BASE       = "https://api.kraken.com/0/public"
FUTURES_API_BASE    = "https://futures.kraken.com/derivatives/api/v3"
PERCENT_THRESHOLD   = 10.0            # only alert if |24h change| ≥ 10%
DEVIATION_THRESHOLD = 5.0             # remove only if change from initial ≥ 5%
TOP_N_BY_VOLUME     = 100             # consider top 100 USD pairs by 24h volume
SCAN_INTERVAL_SEC   = 60              # default scan interval (seconds)
MAX_WORKERS         = 50              # max threads to fetch tickers concurrently

# ─── GLOBAL STATE ──────────────────────────────────────────────────────────────
spot_alerted_map     = {}   # { wsname: {'initial': float, 'prev': float} }
spot_pair_wsname_map = {}

fut_alerted_map      = {}   # { symbol: {'initial': float, 'prev': float} }


# ─── SPOT SCANNER WORKER ─────────────────────────────────────────────────────────
class SpotWorker(QObject):
    update_spot_table   = pyqtSignal(list)  # Emits rows: [(symbol, init, prev, now, vol, price, prev_high, prev_low), ...]
    started_spot_scan   = pyqtSignal()
    finished_spot_scan  = pyqtSignal()
    log_message         = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.usd_pairs = self.get_usd_pairs()
        if not self.usd_pairs:
            self.log_message.emit("⚠️  No active USD spot pairs found. Spot worker exiting.")

    def get_usd_pairs(self):
        url = f"{SPOT_API_BASE}/AssetPairs"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
        except Exception as e:
            self.log_message.emit(f"Error fetching AssetPairs (spot): {e}")
            return []
        data = resp.json().get("result", {})
        usd_pairs = []
        for pair_code, info in data.items():
            if info.get("isFrozen") == "1":
                continue
            wsname = info.get("wsname")
            if not wsname or not wsname.endswith("/USD"):
                continue
            if ".d" in wsname or ".s" in wsname:
                continue
            spot_pair_wsname_map[pair_code] = wsname
            usd_pairs.append(pair_code)
        return usd_pairs

    def fetch_ticker(self, pair_code: str):
        url = f"{SPOT_API_BASE}/Ticker?pair={pair_code}"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            result = resp.json().get("result", {})
            info = result.get(pair_code)
            if not info:
                return None, None, None, None, None, None

            last_price_str = info.get("c", [None])[0]
            open_price_str = info.get("o")
            volume_24h_str = info.get("v", [None, None])[1]
            high_24h_str   = info.get("h", [None, None])[1]
            low_24h_str    = info.get("l", [None, None])[1]

            if not (last_price_str and open_price_str and volume_24h_str and high_24h_str and low_24h_str):
                return None, None, None, None, None, None

            last_price = float(last_price_str)
            open_price = float(open_price_str)
            volume_24h  = float(volume_24h_str)
            high_24h    = float(high_24h_str)
            low_24h     = float(low_24h_str)
            pct_change  = ((last_price - open_price) / open_price) * 100.0
            wsname      = spot_pair_wsname_map[pair_code]

            return wsname, pct_change, volume_24h, last_price, high_24h, low_24h
        except Exception:
            return None, None, None, None, None, None

    def run(self):
        global spot_alerted_map, SCAN_INTERVAL_SEC

        while True:
            self.started_spot_scan.emit()
            all_tickers = []
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = {executor.submit(self.fetch_ticker, p): p for p in self.usd_pairs}
                for future in as_completed(futures):
                    wsname, pct, vol, price, ph, pl = future.result()
                    if wsname is None:
                        continue
                    all_tickers.append((wsname, pct, vol, price, ph, pl))

            if not all_tickers:
                time.sleep(SCAN_INTERVAL_SEC)
                continue

            all_tickers.sort(key=lambda x: x[2], reverse=True)
            top_tickers = all_tickers[:TOP_N_BY_VOLUME]

            filtered = [
                (sym, pct, vol, price, ph, pl)
                for (sym, pct, vol, price, ph, pl) in top_tickers
                if abs(pct) >= PERCENT_THRESHOLD or sym in spot_alerted_map
            ]

            current_map = {symbol: (pct, vol, price) for symbol, pct, vol, price, ph, pl in filtered}
            table_rows = []

            for symbol, new_pct, vol, price, prev_high, prev_low in filtered:
                record = spot_alerted_map.get(symbol)
                if record is None:
                    if abs(new_pct) >= PERCENT_THRESHOLD:
                        spot_alerted_map[symbol] = {'initial': new_pct, 'prev': new_pct}
                        init_str   = f"{new_pct:.2f}%"
                        prev_str   = init_str
                        now_str    = init_str
                        vol_str    = f"{vol*price:,.1f}"
                        price_str  = f"{price:.2f}"
                        table_rows.append((symbol, init_str, prev_str, now_str, vol_str, price_str, prev_high, prev_low))
                        notification.notify(
                            title="New Spot Alert",
                            message=f"{symbol} changed by {new_pct:.2f}% with volume ${vol*price:,.1f}",
                            timeout=5
                        )
                        self.log_message.emit(f"Spot coin added: {symbol} at {new_pct:.2f}%")
                else:
                    initial = record['initial']
                    prev_pct = record['prev']
                    # removal logic
                    if initial >= PERCENT_THRESHOLD and new_pct <= initial - DEVIATION_THRESHOLD:
                        spot_alerted_map.pop(symbol)
                        self.log_message.emit(f"Spot coin removed: {symbol} (dropped {initial:.2f}%→{new_pct:.2f}%)")
                        continue
                    if initial <= -PERCENT_THRESHOLD and new_pct >= initial + DEVIATION_THRESHOLD:
                        spot_alerted_map.pop(symbol)
                        self.log_message.emit(f"Spot coin removed: {symbol} (rose {initial:.2f}%→{new_pct:.2f}%)")
                        continue

                    # update and emit
                    record['prev'] = new_pct
                    init_str   = f"{initial:.2f}%"
                    prev_str   = f"{prev_pct:.2f}%"
                    now_str    = f"{new_pct:.2f}%"
                    vol_str    = f"{vol*price:,.1f}"
                    price_str  = f"{price:.2f}"
                    table_rows.append((symbol, init_str, prev_str, now_str, vol_str, price_str, prev_high, prev_low))

            # cleanup dropped
            for symbol in list(spot_alerted_map.keys()):
                if symbol not in current_map:
                    initial = spot_alerted_map[symbol]['initial']
                    prev_pct = spot_alerted_map[symbol]['prev']
                    if initial >= PERCENT_THRESHOLD and prev_pct <= initial - DEVIATION_THRESHOLD:
                        spot_alerted_map.pop(symbol, None)
                        self.log_message.emit(f"Spot coin removed: {symbol} (dropped {initial:.2f}%→{prev_pct:.2f}%)")
                    elif initial <= -PERCENT_THRESHOLD and prev_pct >= initial + DEVIATION_THRESHOLD:
                        spot_alerted_map.pop(symbol, None)
                        self.log_message.emit(f"Spot coin removed: {symbol} (rose {initial:.2f}%→{prev_pct:.2f}%)")

            self.update_spot_table.emit(table_rows)
            self.finished_spot_scan.emit()
            time.sleep(SCAN_INTERVAL_SEC)


# ─── FUTURES SCANNER WORKER ───────────────────────────────────────────────────────
class FuturesWorker(QObject):
    update_fut_table   = pyqtSignal(list)  # Emits rows: [(symbol, init, prev, now, vol, price, prev_high, prev_low), ...]
    started_fut_scan   = pyqtSignal()
    finished_fut_scan  = pyqtSignal()
    log_message        = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.symbols = self.fetch_all_symbols()
        if not self.symbols:
            self.log_message.emit("⚠️  No futures symbols found. Futures worker exiting.")

    def fetch_all_symbols(self):
        url = f"{FUTURES_API_BASE}/tickers"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
        except Exception as e:
            self.log_message.emit(f"Error fetching futures tickers: {e}")
            return []
        data = resp.json().get("tickers", [])
        return [entry.get("symbol") for entry in data if entry.get("symbol")]

    def fetch_symbol_details(self, symbol: str):
        """
        Fetch metadata for a symbol from /tickers/{symbol}.
        Returns (last_price, pct_change, volume24h, high24h, low24h, pair) or
        (None, None, None, None, None, None) on error.
        """
        url = f"{FUTURES_API_BASE}/tickers/{symbol}"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            info = resp.json().get("ticker", {})
            if info.get("tag") != "perpetual":
                return None, None, None, None, None, None

            last_price  = info.get("last")
            pct_change  = info.get("change24h")
            volume_24h  = info.get("vol24h")
            high_24h    = info.get("high24h")
            low_24h     = info.get("low24h")
            pair        = info.get("pair")
            return last_price, pct_change, volume_24h, high_24h, low_24h, pair
        except Exception:
            return None, None, None, None, None, None

    def run(self):
        global fut_alerted_map, SCAN_INTERVAL_SEC

        while True:
            self.started_fut_scan.emit()
            all_data = []
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = {executor.submit(self.fetch_symbol_details, s): s for s in self.symbols}
                for future in as_completed(futures):
                    lp, pct, vol, high24, low24, pair = future.result()
                    if None in (lp, pct, vol, high24, low24):
                        continue
                    all_data.append((pair, pct, vol, lp, high24, low24))

            if not all_data:
                time.sleep(SCAN_INTERVAL_SEC)
                continue

            filtered = []
            for symbol, pct, vol, price, prev_high, prev_low in all_data:
                if symbol in fut_alerted_map:
                    filtered.append((symbol, pct, vol, price, prev_high, prev_low))
                    continue
                if abs(pct) >= PERCENT_THRESHOLD:
                    if prev_high > 0 and abs(prev_high - price) / prev_high <= 0.01:
                        filtered.append((symbol, pct, vol, price, prev_high, prev_low))
                    elif prev_low > 0 and abs(price - prev_low) / prev_low <= 0.01:
                        filtered.append((symbol, pct, vol, price, prev_high, prev_low))

            current_map = {symbol: pct for symbol, pct, vol, price, ph, pl in filtered}
            table_rows = []

            for symbol, new_pct, vol, price, prev_high, prev_low in filtered:
                record = fut_alerted_map.get(symbol)
                if record is None:
                    fut_alerted_map[symbol] = {'initial': new_pct, 'prev': new_pct}
                    init_str   = f"{new_pct:.2f}%"
                    prev_str   = init_str
                    now_str    = init_str
                    vol_str    = f"{vol*price:,.1f}"
                    price_str  = f"{price:.2f}"
                    table_rows.append((symbol, init_str, prev_str, now_str, vol_str, price_str, prev_high, prev_low))
                    notification.notify(
                        title="New Futures Alert",
                        message=f"{symbol} at {new_pct:.2f}% (Vol: ${vol*price:,.1f})",
                        timeout=5,
                    )
                    self.log_message.emit(f"Futures added: {symbol} at {new_pct:.2f}%")
                else:
                    initial = record['initial']
                    prev_pct = record['prev']
                    if initial >= PERCENT_THRESHOLD and new_pct <= initial - DEVIATION_THRESHOLD:
                        fut_alerted_map.pop(symbol)
                        self.log_message.emit(f"Futures removed: {symbol} (dropped {initial:.2f}%→{new_pct:.2f}%)")
                        continue
                    if initial <= -PERCENT_THRESHOLD and new_pct >= initial + DEVIATION_THRESHOLD:
                        fut_alerted_map.pop(symbol)
                        self.log_message.emit(f"Futures removed: {symbol} (rose {initial:.2f}%→{new_pct:.2f}%)")
                        continue

                    record['prev'] = new_pct
                    init_str   = f"{initial:.2f}%"
                    prev_str   = f"{prev_pct:.2f}%"
                    now_str    = f"{new_pct:.2f}%"
                    vol_str    = f"{vol*price:,.1f}"
                    price_str  = f"{price:.2f}"
                    table_rows.append((symbol, init_str, prev_str, now_str, vol_str, price_str, prev_high, prev_low))

            for symbol in list(fut_alerted_map.keys()):
                if symbol not in current_map:
                    initial = fut_alerted_map[symbol]['initial']
                    prev_pct = fut_alerted_map[symbol]['prev']
                    if initial >= PERCENT_THRESHOLD and prev_pct <= initial - DEVIATION_THRESHOLD:
                        fut_alerted_map.pop(symbol, None)
                        self.log_message.emit(f"Futures removed: {symbol} (dropped {initial:.2f}%→{prev_pct:.2f}%)")
                    elif initial <= -PERCENT_THRESHOLD and prev_pct >= initial + DEVIATION_THRESHOLD:
                        fut_alerted_map.pop(symbol, None)
                        self.log_message.emit(f"Futures removed: {symbol} (rose {initial:.2f}%→{prev_pct:.2f}%)")

            self.update_fut_table.emit(table_rows)
            self.finished_fut_scan.emit()
            time.sleep(SCAN_INTERVAL_SEC)
