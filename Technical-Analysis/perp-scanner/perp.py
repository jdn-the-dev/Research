import sys
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from PyQt5.QtCore import QObject, QThread, pyqtSignal, Qt
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QLabel,
    QSpinBox,
    QPushButton,
    QHeaderView,
    QTabWidget,
    QTextEdit,
)

# ─── CONFIGURATION ────────────────────────────────────────────────────────────
SPOT_API_BASE       = "https://api.kraken.com/0/public"
FUTURES_API_BASE    = "https://futures.kraken.com/derivatives/api/v3"
PERCENT_THRESHOLD   = 10.0            # only alert if |24h change| ≥ 10%
DEVIATION_THRESHOLD = 5.0             # remove only if change from initial ≥ 5%
TOP_N_BY_VOLUME     = 100             # consider top 100 USD pairs by 24h volume
SCAN_INTERVAL_SEC   = 60              # default scan interval (seconds)
MAX_WORKERS         = 50              # max threads to fetch tickers concurrently

# ─── GLOBAL STATE ──────────────────────────────────────────────────────────────
spot_alerted_map = {}   # { wsname: {'initial': float, 'prev': float} }
spot_pair_wsname_map = {}

fut_alerted_map = {}    # { symbol: {'initial': float, 'prev': float} }


# ─── SPOT SCANNER WORKER ─────────────────────────────────────────────────────────
class SpotWorker(QObject):
    update_spot_table   = pyqtSignal(list)  # Emits rows: [(symbol, init, prev, now, vol, price), ...]
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
                return None, None, None, None
            last_price_str   = info.get("c", [None])[0]
            open_price_str   = info.get("o")
            volume_24h_str   = info.get("v", [None, None])[1]
            if not last_price_str or not open_price_str or not volume_24h_str:
                return None, None, None, None
            last_price = float(last_price_str)
            open_price = float(open_price_str)
            volume_24h  = float(volume_24h_str)
            pct_change  = ((last_price - open_price) / open_price) * 100.0
            wsname = spot_pair_wsname_map[pair_code]
            return wsname, pct_change, volume_24h, last_price
        except Exception:
            return None, None, None, None

    def run(self):
        global spot_alerted_map, SCAN_INTERVAL_SEC

        while True:
            self.started_spot_scan.emit()
            all_tickers = []
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = {executor.submit(self.fetch_ticker, p): p for p in self.usd_pairs}
                for future in as_completed(futures):
                    wsname, pct, vol, price = future.result()
                    if wsname is None:
                        continue
                    all_tickers.append((wsname, pct, vol, price))

            if not all_tickers:
                time.sleep(SCAN_INTERVAL_SEC)
                continue

            all_tickers.sort(key=lambda x: x[2], reverse=True)
            top_tickers = all_tickers[:TOP_N_BY_VOLUME]

            filtered = [
                (sym, pct, vol, price)
                for (sym, pct, vol, price) in top_tickers
                if abs(pct) >= PERCENT_THRESHOLD or sym in spot_alerted_map
            ]

            current_map = {symbol: (pct, vol, price) for symbol, pct, vol, price in filtered}
            table_rows = []

            for symbol, new_pct, vol, price in filtered:
                record = spot_alerted_map.get(symbol)
                if record is None:
                    if abs(new_pct) >= PERCENT_THRESHOLD:
                        spot_alerted_map[symbol] = {'initial': new_pct, 'prev': new_pct}
                        init_str  = f"{new_pct:.2f}%"
                        prev_str  = f"{new_pct:.2f}%"
                        now_str   = f"{new_pct:.2f}%"
                        vol_str   = f"{vol*price:,.1f}"
                        price_str = f"{price:.2f}"
                        table_rows.append((symbol, init_str, prev_str, now_str, vol_str, price_str))
                        self.log_message.emit(f"Spot coin added: {symbol} at {new_pct:.2f}%")
                else:
                    initial = record['initial']
                    prev_pct = record['prev']
                    if initial >= PERCENT_THRESHOLD and new_pct <= initial - DEVIATION_THRESHOLD:
                        spot_alerted_map.pop(symbol)
                        self.log_message.emit(f"Spot coin removed: {symbol} (dropped {initial:.2f}%→{new_pct:.2f}%)")
                        continue
                    if initial <= -PERCENT_THRESHOLD and new_pct >= initial + DEVIATION_THRESHOLD:
                        spot_alerted_map.pop(symbol)
                        self.log_message.emit(f"Spot coin removed: {symbol} (rose {initial:.2f}%→{new_pct:.2f}%)")
                        continue
                    record['prev'] = new_pct
                    init_str  = f"{initial:.2f}%"
                    prev_str  = f"{prev_pct:.2f}%"
                    now_str   = f"{new_pct:.2f}%"
                    vol_str   = f"{vol*price:,.1f}"
                    price_str = f"{price:.2f}"
                    table_rows.append((symbol, init_str, prev_str, now_str, vol_str, price_str))

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


# ─── FUTURES SCANNER WORKER ─────────────────────────────────────────────────────────
class FuturesWorker(QObject):
    update_fut_table   = pyqtSignal(list)  # Emits rows: [(symbol, init, prev, now, vol, price), ...]
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
        symbols = [entry.get("symbol") for entry in data if entry.get("symbol")]
        return symbols

    def fetch_symbol_details(self, symbol: str):
        """
        Fetch metadata for a symbol from /tickers/{symbol}.
        Returns (last_price, pct_change, volume24h, high24h, low24h) or
        (None, None, None, None, None) on error.
        """
        url = f"{FUTURES_API_BASE}/tickers/{symbol}"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            info = resp.json().get("ticker", {})
            # Only perpetual contracts have tag="perpetual"
            if info.get("tag") != "perpetual":
                return None, None, None, None, None, None
            last_price  = info.get("last")
            pct_change  = info.get("change24h")
            volume_24h  = info.get("vol24h")
            high_24h    = info.get("high24h")
            low_24h     = info.get("low24h")
            pair = info.get("pair")
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
                    last_price, pct_change, volume_24h, high_24h, low_24h, pair = future.result()
                    if last_price is None or pct_change is None or volume_24h is None or high_24h is None or low_24h is None:
                        continue
                    all_data.append((pair, pct_change, volume_24h, last_price, high_24h, low_24h))

            if not all_data:
                time.sleep(SCAN_INTERVAL_SEC)
                continue

            filtered = []
            for symbol, pct, vol, price, high24, low24 in all_data:
                # If first time alert or already tracking:
                if symbol in fut_alerted_map:
                    filtered.append((symbol, pct, vol, price, high24, low24))
                    continue

                # Otherwise, only alert if |pct| ≥ threshold AND current price is within 1% of high24 or low24
                if abs(pct) >= PERCENT_THRESHOLD:
                    if high24 > 0 and abs(high24 - price) / high24 <= 0.01:
                        filtered.append((symbol, pct, vol, price, high24, low24))
                    elif low24 > 0 and abs(price - low24) / low24 <= 0.01:
                        filtered.append((symbol, pct, vol, price, high24, low24))

            current_map = {symbol: pct for symbol, pct, vol, price, h, l in filtered}
            table_rows = []

            for symbol, new_pct, vol, price, high24, low24 in filtered:
                record = fut_alerted_map.get(symbol)
                if record is None:
                    # First-time alert
                    fut_alerted_map[symbol] = {'initial': new_pct, 'prev': new_pct}
                    init_str  = f"{new_pct:.2f}%"
                    prev_str  = f"{new_pct:.2f}%"
                    now_str   = f"{new_pct:.2f}%"
                    vol_str   = f"{vol*price:,.1f}"
                    price_str = f"{price:.2f}"
                    table_rows.append((symbol, init_str, prev_str, now_str, vol_str, price_str))
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
                    init_str  = f"{initial:.2f}%"
                    prev_str  = f"{prev_pct:.2f}%"
                    now_str   = f"{new_pct:.2f}%"
                    vol_str   = f"{vol*price:,.1f}"
                    price_str = f"{price:.2f}"
                    table_rows.append((symbol, init_str, prev_str, now_str, vol_str, price_str))

            for symbol in list(fut_alerted_map.keys()):
                if symbol not in current_map:
                    initial = fut_alerted_map[symbol]['initial']
                    prev_pct  = fut_alerted_map[symbol]['prev']
                    if initial >= PERCENT_THRESHOLD and prev_pct <= initial - DEVIATION_THRESHOLD:
                        fut_alerted_map.pop(symbol, None)
                        self.log_message.emit(f"Futures removed: {symbol} (dropped {initial:.2f}%→{prev_pct:.2f}%)")
                    elif initial <= -PERCENT_THRESHOLD and prev_pct >= initial + DEVIATION_THRESHOLD:
                        fut_alerted_map.pop(symbol, None)
                        self.log_message.emit(f"Futures removed: {symbol} (rose {initial:.2f}%→{prev_pct:.2f}%)")

            self.update_fut_table.emit(table_rows)
            self.finished_fut_scan.emit()
            time.sleep(SCAN_INTERVAL_SEC)


# ─── MAIN WINDOW ───────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kraken USD Alerts")
        self.resize(920, 600)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout()
        central.setLayout(main_layout)

        # Tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # ─ Spot Alerts Tab ─────────────────────────────────────────────────────────
        self.spot_tab = QWidget()
        spot_layout = QVBoxLayout()
        self.spot_tab.setLayout(spot_layout)

        # Interval control + status for spot
        spot_interval_layout = QHBoxLayout()
        spot_interval_label = QLabel("Spot Scan Interval (s):")
        self.spot_interval_spin = QSpinBox()
        self.spot_interval_spin.setRange(1, 300)
        self.spot_interval_spin.setValue(SCAN_INTERVAL_SEC)
        self.spot_apply_button = QPushButton("Apply Spot Interval")
        self.spot_apply_button.clicked.connect(self.apply_spot_interval)
        spot_interval_layout.addWidget(spot_interval_label)
        spot_interval_layout.addWidget(self.spot_interval_spin)
        spot_interval_layout.addWidget(self.spot_apply_button)
        spot_interval_layout.addStretch()
        self.spot_status_label = QLabel("Status: Idle")
        spot_interval_layout.addWidget(self.spot_status_label)
        spot_layout.addLayout(spot_interval_layout)

        # Spot table
        self.spot_table = QTableWidget()
        self.spot_table.setColumnCount(6)
        self.spot_table.setHorizontalHeaderLabels(
            ["Symbol", "Initial %", "Prev %", "Now %", "Volume ($)", "Price"]
        )
        self.spot_table.setSortingEnabled(True)
        self.spot_table.setAlternatingRowColors(True)
        font = QFont("Arial", 10)
        self.spot_table.setFont(font)
        header = self.spot_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setDefaultAlignment(Qt.AlignCenter)
        spot_layout.addWidget(self.spot_table)

        self.tabs.addTab(self.spot_tab, "Spot Alerts")

        # ─ Futures Alerts Tab ───────────────────────────────────────────────────────
        self.fut_tab = QWidget()
        fut_layout = QVBoxLayout()
        self.fut_tab.setLayout(fut_layout)

        # Interval control + status for futures
        fut_interval_layout = QHBoxLayout()
        fut_interval_label = QLabel("Futures Scan Interval (s):")
        self.fut_interval_spin = QSpinBox()
        self.fut_interval_spin.setRange(1, 300)
        self.fut_interval_spin.setValue(SCAN_INTERVAL_SEC)
        self.fut_apply_button = QPushButton("Apply Futures Interval")
        self.fut_apply_button.clicked.connect(self.apply_fut_interval)
        fut_interval_layout.addWidget(fut_interval_label)
        fut_interval_layout.addWidget(self.fut_interval_spin)
        fut_interval_layout.addWidget(self.fut_apply_button)
        fut_interval_layout.addStretch()
        self.fut_status_label = QLabel("Status: Idle")
        fut_interval_layout.addWidget(self.fut_status_label)
        fut_layout.addLayout(fut_interval_layout)

        # Futures table
        self.fut_table = QTableWidget()
        self.fut_table.setColumnCount(6)
        self.fut_table.setHorizontalHeaderLabels(
            ["Symbol", "Initial %", "Prev %", "Now %", "Volume ($)", "Price"]
        )
        self.fut_table.setSortingEnabled(True)
        self.fut_table.setAlternatingRowColors(True)
        self.fut_table.setFont(font)
        fut_header = self.fut_table.horizontalHeader()
        fut_header.setSectionResizeMode(QHeaderView.Stretch)
        fut_header.setDefaultAlignment(Qt.AlignCenter)
        fut_layout.addWidget(self.fut_table)

        self.tabs.addTab(self.fut_tab, "Futures Alerts")

        # ─ Log Tab ─────────────────────────────────────────────────────────────────
        self.log_tab = QWidget()
        log_layout = QVBoxLayout()
        self.log_tab.setLayout(log_layout)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("Courier", 9))
        log_layout.addWidget(self.log_view)

        self.tabs.addTab(self.log_tab, "Log")

        # Start spot worker thread
        self.spot_worker = SpotWorker()
        self.spot_thread = QThread()
        self.spot_worker.moveToThread(self.spot_thread)
        self.spot_worker.update_spot_table.connect(self.populate_spot_table)
        self.spot_worker.log_message.connect(self.log)
        self.spot_worker.started_spot_scan.connect(self.on_spot_started)
        self.spot_worker.finished_spot_scan.connect(self.on_spot_finished)
        self.spot_thread.started.connect(self.spot_worker.run)
        self.spot_thread.start()

        # Start futures worker thread
        self.fut_worker = FuturesWorker()
        self.fut_thread = QThread()
        self.fut_worker.moveToThread(self.fut_thread)
        self.fut_worker.update_fut_table.connect(self.populate_fut_table)
        self.fut_worker.log_message.connect(self.log)
        self.fut_worker.started_fut_scan.connect(self.on_fut_started)
        self.fut_worker.finished_fut_scan.connect(self.on_fut_finished)
        self.fut_thread.started.connect(self.fut_worker.run)
        self.fut_thread.start()

    def log(self, message: str):
        """Append a line to the log view with timestamp."""
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        self.log_view.append(f"[{ts}] {message}")

    def apply_spot_interval(self):
        global SCAN_INTERVAL_SEC
        new_interval = self.spot_interval_spin.value()
        SCAN_INTERVAL_SEC = new_interval
        self.log(f"Spot interval changed to {new_interval} seconds")
        self.spot_status_label.setText(f"Status: Interval set to {new_interval}s")

    def apply_fut_interval(self):
        global SCAN_INTERVAL_SEC
        new_interval = self.fut_interval_spin.value()
        SCAN_INTERVAL_SEC = new_interval
        self.log(f"Futures interval changed to {new_interval} seconds")
        self.fut_status_label.setText(f"Status: Interval set to {new_interval}s")

    def on_spot_started(self):
        self.spot_status_label.setText("Status: Loading...")

    def on_spot_finished(self):
        ts = time.strftime("%H:%M:%S", time.localtime())
        self.spot_status_label.setText(f"Status: Last spot update at {ts}")

    def on_fut_started(self):
        self.fut_status_label.setText("Status: Loading...")

    def on_fut_finished(self):
        ts = time.strftime("%H:%M:%S", time.localtime())
        self.fut_status_label.setText(f"Status: Last futures update at {ts}")

    def populate_spot_table(self, rows):
        self.spot_table.setRowCount(len(rows))
        for idx, (symbol, init_s, prev_s, now_s, vol_s, price_s) in enumerate(rows):
            items = []
            for text in (symbol, init_s, prev_s, now_s, vol_s, price_s):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignCenter)
                item.setFont(QFont("Arial", 9))
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                items.append(item)

            color = None
            try:
                prev_pct = float(prev_s.strip("%"))
                now_pct = float(now_s.strip("%"))
            except ValueError:
                color = None
            else:
                if prev_pct == float(init_s.strip("%")):
                    color = QColor(173, 216, 230)  # light blue for new
                else:
                    if now_pct > 0:
                        color = QColor(144, 238, 144)  # light green for positive
                    elif now_pct < 0:
                        color = QColor(250, 128, 114)  # light red for negative

            if color:
                for item in items:
                    item.setBackground(color)
                    

            for col, item in enumerate(items):
                self.spot_table.setItem(idx, col, item)

        self.spot_table.resizeRowsToContents()

    def populate_fut_table(self, rows):
        self.fut_table.setRowCount(len(rows))
        for idx, (symbol, init_s, prev_s, now_s, vol_s, price_s) in enumerate(rows):
            items = []
            for text in (symbol, init_s, prev_s, now_s, vol_s, price_s):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignCenter)
                item.setFont(QFont("Arial", 9))
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                items.append(item)

            color = None
            try:
                prev_pct = float(prev_s.strip("%"))
                now_pct = float(now_s.strip("%"))
            except ValueError:
                color = None
            else:
                if prev_pct == float(init_s.strip("%")):
                    color = QColor(173, 216, 230)  # light blue for new
                else:
                    if now_pct > 0:
                        color = QColor(144, 238, 144)  # light green for positive
                    elif now_pct < 0:
                        color = QColor(250, 128, 114)  # light red for negative

            if color:
                for item in items:
                    item.setBackground(color)

            for col, item in enumerate(items):
                self.fut_table.setItem(idx, col, item)

        self.fut_table.resizeRowsToContents()


# ─── ENTRY POINT ───────────────────────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
