import sys
import time
from workers import SpotWorker, FuturesWorker

from PyQt5.QtCore import QThread, Qt
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
SCAN_INTERVAL_SEC   = 60              # default scan interval (seconds)



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
