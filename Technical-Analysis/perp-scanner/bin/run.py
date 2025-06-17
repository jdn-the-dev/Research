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
API_BASE_URL           = "https://api.kraken.com/0/public"
PERCENT_THRESHOLD      = 10.0            # only alert if |24h change| ≥ 10%
DEVIATION_THRESHOLD    = 5.0             # remove only if change from initial ≥ 5%
TOP_N_BY_VOLUME        = 100             # consider top 100 USD pairs by 24h volume
SCAN_INTERVAL_SEC      = 5               # default scan interval (seconds)
MAX_WORKERS            = 50              # max threads to fetch tickers concurrently

# ─── GLOBAL STATE ──────────────────────────────────────────────────────────────
# Track for each symbol: initial alerted pct and previous scan pct
# Structure: { wsname: {'initial': float, 'prev': float} }
alerted_map = {}

# Map from pair_code → wsname (e.g. "XXBTZUSD" → "BTC/USD")
pair_wsname_map = {}


# ─── QTHREAD WORKER ─────────────────────────────────────────────────────────────
class ScannerWorker(QObject):
    update_table   = pyqtSignal(list)  # Emits rows: [(symbol, init, prev, now, vol, price), ...]
    started_scan   = pyqtSignal()
    finished_scan  = pyqtSignal()
    log_message    = pyqtSignal(str)   # Emit log messages

    def __init__(self):
        super().__init__()
        self.usd_pairs = self.get_usd_pairs()
        if not self.usd_pairs:
            print("⚠️  No active USD pairs found. Exiting worker.")
            return

    def get_usd_pairs(self):
        url = f"{API_BASE_URL}/AssetPairs"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
        except Exception as e:
            self.log_message.emit(f"Error fetching AssetPairs: {e}")
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
            pair_wsname_map[pair_code] = wsname
            usd_pairs.append(pair_code)
        return usd_pairs

    def fetch_ticker(self, pair_code: str):
        """
        Fetch ticker info including last price, compute 24h pct change and 24h volume.
        Returns (wsname, pct_change, volume_24h, last_price) or (None, None, None, None) on error.
        """
        url = f"{API_BASE_URL}/Ticker?pair={pair_code}"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            result = resp.json().get("result", {})
            info = result.get(pair_code)
            if not info:
                return None, None, None, None

            last_price_str = info.get("c", [None])[0]
            open_price_str = info.get("o")
            volume_24h_str = info.get("v", [None, None])[1]

            if not last_price_str or not open_price_str or not volume_24h_str:
                return None, None, None, None

            last_price = float(last_price_str)
            open_price = float(open_price_str)
            volume_24h = float(volume_24h_str)

            pct_change = ((last_price - open_price) / open_price) * 100.0
            wsname = pair_wsname_map[pair_code]
            return wsname, pct_change, volume_24h, last_price
        except Exception:
            return None, None, None, None

    def run(self):
        global alerted_map, SCAN_INTERVAL_SEC

        while True:
            self.started_scan.emit()
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

            # Sort by 24h volume descending and keep top N
            all_tickers.sort(key=lambda x: x[2], reverse=True)
            top_tickers = all_tickers[:TOP_N_BY_VOLUME]

            # Filter for new alerts or existing alerts
            filtered = [
                (sym, pct, vol, price)
                for (sym, pct, vol, price) in top_tickers
                if abs(pct) >= PERCENT_THRESHOLD or sym in alerted_map
            ]

            current_map = {symbol: (pct, vol, price) for symbol, pct, vol, price in filtered}
            table_rows = []

            for symbol, new_pct, vol, price in filtered:
                record = alerted_map.get(symbol)
                if record is None:
                    if abs(new_pct) >= PERCENT_THRESHOLD:
                        alerted_map[symbol] = {'initial': new_pct, 'prev': new_pct}
                        init_str = f"{new_pct:.2f}%"
                        prev_str = f"{new_pct:.2f}%"
                        now_str = f"{new_pct:.2f}%"
                        vol_str = f"{vol:,.1f}"
                        price_str = f"{price:.2f}"
                        table_rows.append((symbol, init_str, prev_str, now_str, vol_str, price_str))
                        self.log_message.emit(f"Coin added: {symbol} at {new_pct:.2f}%")
                else:
                    initial = record['initial']
                    prev_pct = record['prev']
                    if initial >= PERCENT_THRESHOLD and new_pct <= initial - DEVIATION_THRESHOLD:
                        alerted_map.pop(symbol)
                        self.log_message.emit(f"Coin removed: {symbol} (dropped from {initial:.2f}% to {new_pct:.2f}%)")
                        continue
                    if initial <= -PERCENT_THRESHOLD and new_pct >= initial + DEVIATION_THRESHOLD:
                        alerted_map.pop(symbol)
                        self.log_message.emit(f"Coin removed: {symbol} (rose from {initial:.2f}% to {new_pct:.2f}%)")
                        continue
                    record['prev'] = new_pct
                    init_str = f"{initial:.2f}%"
                    prev_str = f"{prev_pct:.2f}%"
                    now_str = f"{new_pct:.2f}%"
                    vol_str = f"{vol:,.1f}"
                    price_str = f"{price:.2f}"
                    table_rows.append((symbol, init_str, prev_str, now_str, vol_str, price_str))

            # Clean up any symbols no longer in filtered but meeting removal
            for symbol in list(alerted_map.keys()):
                if symbol not in current_map:
                    initial = alerted_map[symbol]['initial']
                    prev_pct = alerted_map[symbol]['prev']
                    if initial >= PERCENT_THRESHOLD and prev_pct <= initial - DEVIATION_THRESHOLD:
                        alerted_map.pop(symbol, None)
                        self.log_message.emit(f"Coin removed: {symbol} (dropped from {initial:.2f}% to {prev_pct:.2f}%)")
                    elif initial <= -PERCENT_THRESHOLD and prev_pct >= initial + DEVIATION_THRESHOLD:
                        alerted_map.pop(symbol, None)
                        self.log_message.emit(f"Coin removed: {symbol} (rose from {initial:.2f}% to {prev_pct:.2f}%)")

            self.update_table.emit(table_rows)
            self.finished_scan.emit()
            time.sleep(SCAN_INTERVAL_SEC)


# ─── MAIN WINDOW ───────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kraken USD Alerts")
        self.resize(900, 550)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout()
        central.setLayout(main_layout)

        # Tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # ─ Alerts Tab ───────────────────────────────────────────────────────────────
        self.alerts_tab = QWidget()
        alerts_layout = QVBoxLayout()
        self.alerts_tab.setLayout(alerts_layout)

        # Interval control + status
        interval_layout = QHBoxLayout()
        interval_label = QLabel("Scan Interval (s):")
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 300)
        self.interval_spin.setValue(SCAN_INTERVAL_SEC)
        self.apply_button = QPushButton("Apply Interval")
        self.apply_button.clicked.connect(self.apply_interval)
        interval_layout.addWidget(interval_label)
        interval_layout.addWidget(self.interval_spin)
        interval_layout.addWidget(self.apply_button)
        interval_layout.addStretch()

        # Loading status label
        self.status_label = QLabel("Status: Idle")
        interval_layout.addWidget(self.status_label)

        alerts_layout.addLayout(interval_layout)

        # Table: Symbol | Initial % | Prev % | Now % | Volume | Price
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["Symbol", "Initial %", "Prev %", "Now %", "Volume", "Price"]
        )
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        font = QFont("Arial", 10)
        self.table.setFont(font)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setDefaultAlignment(Qt.AlignCenter)
        alerts_layout.addWidget(self.table)

        self.tabs.addTab(self.alerts_tab, "Alerts")

        # ─ Log Tab ─────────────────────────────────────────────────────────────────
        self.log_tab = QWidget()
        log_layout = QVBoxLayout()
        self.log_tab.setLayout(log_layout)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("Courier", 9))
        log_layout.addWidget(self.log_view)

        self.tabs.addTab(self.log_tab, "Log")

        # Start worker thread
        self.worker = ScannerWorker()
        self.thread = QThread()
        self.worker.moveToThread(self.thread)
        self.worker.update_table.connect(self.populate_table)
        self.worker.log_message.connect(self.log)
        self.worker.started_scan.connect(self.on_scan_started)
        self.worker.finished_scan.connect(self.on_scan_finished)
        self.thread.started.connect(self.worker.run)
        self.thread.start()

    def log(self, message: str):
        """Append a line to the log view with timestamp."""
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        self.log_view.append(f"[{ts}] {message}")

    def apply_interval(self):
        global SCAN_INTERVAL_SEC
        new_interval = self.interval_spin.value()
        SCAN_INTERVAL_SEC = new_interval
        self.log(f"Scan interval changed to {new_interval} seconds")
        self.status_label.setText(f"Status: Interval set to {new_interval}s")

    def on_scan_started(self):
        self.status_label.setText("Status: Loading...")

    def on_scan_finished(self):
        ts = time.strftime("%H:%M:%S", time.localtime())
        self.status_label.setText(f"Status: Last update at {ts}")

    def populate_table(self, rows):
        """
        Update the QTableWidget with rows and color-code:
        - Light blue if Prev % == Initial %
        - Light green if Now % > 0
        - Light red if Now % < 0
        """
        self.table.setRowCount(len(rows))
        for idx, (symbol, init_s, prev_s, now_s, vol_s, price_s) in enumerate(rows):
            items = []
            for text in (symbol, init_s, prev_s, now_s, vol_s, price_s):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignCenter)
                item.setFont(QFont("Arial", 9))
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                items.append(item)

            # Determine color based on now_s
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
                self.table.setItem(idx, col, item)

        self.table.resizeRowsToContents()


# ─── ENTRY POINT ───────────────────────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
