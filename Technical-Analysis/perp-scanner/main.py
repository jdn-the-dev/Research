import sys
import time
import workers
from workers import SpotWorker, FuturesWorker
from utils.screenshot.chart_api.get_charts import fetch_chart_bytes
import os
from settings import load_settings, save_settings
from PyQt5.QtCore import QThread, Qt, QSize, QSettings
from PyQt5.QtGui import QColor, QFont, QCursor, QPixmap
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
    QGridLayout,
    QToolButton,
    QStyle,
    QPushButton,
    QHeaderView,
    QTabWidget,
    QTextEdit,
    QDialog,
    QDialogButtonBox,
    QLineEdit,
    QCheckBox,
    QFileDialog,
    QDoubleSpinBox,
    QFormLayout,
)

import io
from PIL import Image
from PIL.ImageQt import toqpixmap

from concurrent.futures import ThreadPoolExecutor
from utils.indicators.rsi import fetch_rsi_intervals

# ─── CONFIGURATION ────────────────────────────────────────────────────────────
SCAN_INTERVAL_SEC = 60  # default scan interval (seconds)

# ─── COLOR CONSTANTS ──────────────────────────────────────────────────────────
NEW_COLOR = QColor(173, 216, 230)      # light blue
POS_COLOR = QColor(144, 238, 144)      # light green
NEG_COLOR = QColor(250, 128, 114)      # light red
RANGE_BREAK_COLOR = QColor(142, 68, 191)  # light purple

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kraken USD Alerts")
        self.resize(920, 600)
        self.setWindowFlags(Qt.WindowStaysOnTopHint)

        # Load persisted Telegram settings
        self.settings = QSettings("TotalDev", "KrakenUSDAlerts")
        # Load persisted settings from JSON
        config = load_settings()
        self.telegram_token = config.get("telegram_token", "")
        self.telegram_chat_id = config.get("telegram_chat_id", "")
        self.alert_threshold = config.get("alert_threshold", 10.0)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # Top controls
        ctrl = QHBoxLayout()
        ctrl.addStretch()

        # Mute button
        self.mute_button = QToolButton()
        self.mute_button.setIcon(self.style().standardIcon(QStyle.SP_MediaVolumeMuted))
        self.mute_button.setCheckable(True)
        self.mute_button.setChecked(False)
        self.mute_button.toggled.connect(self.toggle_mute)
        ctrl.addWidget(self.mute_button)

        # Settings button for Telegram alerts
        self.settings_button = QToolButton()
        self.settings_button.setText("Settings")
        self.settings_button.clicked.connect(self.on_settings_clicked)
        ctrl.addWidget(self.settings_button)

        workers.MUTE_NOTIFICATIONS = True
        main_layout.addLayout(ctrl)

        # Tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        self._init_spot_tab()
        self._init_fut_tab()
        self._init_screenshots_tab()
        self._init_log_tab()
        self._start_workers()

    def on_settings_clicked(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Telegram Alert Settings")
        dialog.setModal(True)
        form = QFormLayout(dialog)

        token_input = QLineEdit()
        token_input.setText(self.telegram_token)
        form.addRow("Bot Token:", token_input)

        chat_input = QLineEdit()
        chat_input.setText(self.telegram_chat_id)
        form.addRow("Chat ID:", chat_input)

        threshold_input = QDoubleSpinBox()
        threshold_input.setRange(0.1, 100.0)
        threshold_input.setSuffix(" %")
        threshold_input.setValue(self.alert_threshold)
        form.addRow("Change Threshold:", threshold_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)

        if dialog.exec_() == QDialog.Accepted:
            self.telegram_token = token_input.text().strip()
            self.telegram_chat_id = chat_input.text().strip()
            self.alert_threshold = threshold_input.value()
            # Persist to JSON
            save_settings({
                "telegram_token": self.telegram_token,
                "telegram_chat_id": self.telegram_chat_id,
                "alert_threshold": self.alert_threshold
            })
            self.log(f"Telegram settings updated (threshold: {self.alert_threshold}%)")

    def _init_screenshots_tab(self):
        self.screenshots_tab = QWidget()
        layout = QVBoxLayout(self.screenshots_tab)

        row = QHBoxLayout()
        row.addWidget(QLabel("Pair:"))
        self.pair_input = QLineEdit()
        self.pair_input.setPlaceholderText("e.g. BTCUSDT")
        row.addWidget(self.pair_input)

        btn = QPushButton("Capture")
        btn.clicked.connect(self.on_capture_clicked)
        row.addWidget(btn)
        row.addStretch()
        layout.addLayout(row)

        status_row = QHBoxLayout()
        self.status_label = QLabel("Status: Idle")
        status_row.addWidget(self.status_label)
        status_row.addStretch()
        layout.addLayout(status_row)

        save_row = QHBoxLayout()
        self.save_checkbox = QCheckBox("Save Images")
        save_row.addWidget(self.save_checkbox)
        self.save_dir_input = QLineEdit()
        self.save_dir_input.setPlaceholderText("Output folder (optional)")
        self.save_dir_input.setReadOnly(True)
        save_row.addWidget(self.save_dir_input)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self.on_browse_folder)
        save_row.addWidget(browse_btn)
        save_row.addStretch()
        layout.addLayout(save_row)

        self.chart_label = QLabel(alignment=Qt.AlignCenter)
        self.chart_label.setFixedSize(QSize(800, 400))
        layout.addWidget(self.chart_label, stretch=1)

        self.tabs.addTab(self.screenshots_tab, "Screenshots")

    def on_browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select folder", os.getcwd())
        if folder:
            self.save_dir_input.setText(folder)

    def on_capture_clicked(self):
        base = self.pair_input.text().strip().upper()
        if not base:
            self.status_label.setText("Status: Please enter a valid pair")
            self.log("⚠️ Please enter a pair like BTCUSDT")
            return

        pair = f"BINANCE:{base}"
        self.status_label.setText(f"Status: Capturing charts for {pair}…")
        self.log(f"Capturing charts for {pair}…")
        
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        
        try:
            
            intervals = ["1h", "4h", "1D"]
            first_pix = None
            out_dir = self.save_dir_input.text() or "charts"
            if self.save_checkbox.isChecked():
                os.makedirs(out_dir, exist_ok=True)

            for idx, interval in enumerate(intervals):
                raw_png = fetch_chart_bytes(pair, interval=interval)
                if idx == 0:
                    img = Image.open(io.BytesIO(raw_png)).convert("RGBA")
                    try:
                        first_pix = toqpixmap(img)
                    except Exception:
                        import tempfile
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                            img.save(tmp, format="PNG")
                            tmp_path = tmp.name
                        first_pix = QPixmap(tmp_path)
                        os.unlink(tmp_path)
                if self.save_checkbox.isChecked():
                    fname = f"{pair.replace(':','_')}_{interval}.png"
                    path = os.path.join(out_dir, fname)
                    with open(path, "wb") as f:
                        f.write(raw_png)
                    self.status_label.setText(f"Status: Saved {interval} chart: {path}")
                    self.log(f"Saved {interval} chart: {path}")

            if first_pix:
                self.chart_label.setPixmap(
                    first_pix.scaled(
                        self.chart_label.size(),
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )
                )
                self.status_label.setText(f"Status: Screenshot updated for {pair}")
                self.log(f"Screenshot updated for {pair} (1h)")
        except Exception as e:
            self.status_label.setText(f"Status: Error capturing charts: {pair}")
            self.log(f"Error capturing chart: {e}")
        finally:
            QApplication.restoreOverrideCursor()

    def _init_spot_tab(self):
        self.spot_tab = QWidget()
        layout = QVBoxLayout(self.spot_tab)
        # Spot interval controls
        h = QHBoxLayout()
        h.addWidget(QLabel("Spot Scan Interval (s):"))
        self.spot_interval_spin = QSpinBox()
        self.spot_interval_spin.setRange(1, 300)
        self.spot_interval_spin.setValue(SCAN_INTERVAL_SEC)
        h.addWidget(self.spot_interval_spin)
        btn = QPushButton("Apply Spot Interval")
        btn.clicked.connect(self.apply_spot_interval)
        h.addWidget(btn)
        h.addStretch()
        self.spot_status_label = QLabel("Status: Idle")
        h.addWidget(self.spot_status_label)
        layout.addLayout(h)
        # Spot table
        self.spot_table = QTableWidget()
        self.spot_table.setColumnCount(7)
        self.spot_table.setHorizontalHeaderLabels([
            "Symbol", "Initial %", "Prev %", "Now %", "Volume ($)", "Price", "Prev Day Range"
        ])
        self._format_table(self.spot_table)
        self.spot_table.cellDoubleClicked.connect(lambda r, c: self.show_rsi_popup(r, c, is_future=False))
        layout.addWidget(self.spot_table)
        self.tabs.addTab(self.spot_tab, "Spot Alerts")

    def _init_fut_tab(self):
        self.fut_tab = QWidget()
        layout = QVBoxLayout(self.fut_tab)
        # Futures interval controls
        h = QHBoxLayout()
        h.addWidget(QLabel("Futures Scan Interval (s):"))
        self.fut_interval_spin = QSpinBox()
        self.fut_interval_spin.setRange(1, 300)
        self.fut_interval_spin.setValue(SCAN_INTERVAL_SEC)
        h.addWidget(self.fut_interval_spin)
        btn = QPushButton("Apply Futures Interval")
        btn.clicked.connect(self.apply_fut_interval)
        h.addWidget(btn)
        h.addStretch()
        self.fut_status_label = QLabel("Status: Idle")
        h.addWidget(self.fut_status_label)
        layout.addLayout(h)
        # Futures table
        self.fut_table = QTableWidget()
        self.fut_table.setColumnCount(7)
        self.fut_table.setHorizontalHeaderLabels([
            "Symbol", "Initial %", "Prev %", "Now %", "Volume ($)", "Price", "Prev Day Range"
        ])
        self._format_table(self.fut_table)
        self.fut_table.cellDoubleClicked.connect(lambda r, c: self.show_rsi_popup(r, c, is_future=True))
        layout.addWidget(self.fut_table)
        self.tabs.addTab(self.fut_tab, "Futures Alerts")

    def _init_log_tab(self):
        self.log_tab = QWidget()
        layout = QVBoxLayout(self.log_tab)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("Arial", 9))
        layout.addWidget(self.log_view)
        self.tabs.addTab(self.log_tab, "Log")

    def _format_table(self, table: QTableWidget):
        table.setSortingEnabled(True)
        table.setAlternatingRowColors(True)
        table.setFont(QFont("Arial", 10))
        hdr = table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.Stretch)
        hdr.setDefaultAlignment(Qt.AlignCenter)

    def _start_workers(self):
        # Spot worker
        self.spot_worker = SpotWorker()
        self.spot_thread = QThread()
        self.spot_worker.moveToThread(self.spot_thread)
        self.spot_worker.update_spot_table.connect(self.populate_spot_table)
        self.spot_worker.log_message.connect(self.log)
        self.spot_worker.started_spot_scan.connect(self.on_spot_started)
        self.spot_worker.finished_spot_scan.connect(self.on_spot_finished)
        self.spot_thread.started.connect(self.spot_worker.run)
        self.spot_thread.start()
        # Futures worker
        self.fut_worker = FuturesWorker()
        self.fut_thread = QThread()
        self.fut_worker.moveToThread(self.fut_thread)
        self.fut_worker.update_fut_table.connect(self.populate_fut_table)
        self.fut_worker.log_message.connect(self.log)
        self.fut_worker.started_fut_scan.connect(self.on_fut_started)
        self.fut_worker.finished_fut_scan.connect(self.on_fut_finished)
        self.fut_thread.started.connect(self.fut_worker.run)
        self.fut_thread.start()

    def log(self, msg: str):
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        self.log_view.append(f"[{ts}] {msg}")

    def apply_spot_interval(self):
        global SCAN_INTERVAL_SEC
        SCAN_INTERVAL_SEC = self.spot_interval_spin.value()
        self.log(f"Spot interval changed to {SCAN_INTERVAL_SEC} seconds")
        self.spot_status_label.setText(f"Status: Interval set to {SCAN_INTERVAL_SEC}s")

    def apply_fut_interval(self):
        global SCAN_INTERVAL_SEC
        SCAN_INTERVAL_SEC = self.fut_interval_spin.value()
        self.log(f"Futures interval changed to {SCAN_INTERVAL_SEC} seconds")
        self.fut_status_label.setText(f"Status: Interval set to {SCAN_INTERVAL_SEC}s")

    def toggle_mute(self, checked: bool):
        icon = QStyle.SP_MediaVolume if checked else QStyle.SP_MediaVolumeMuted
        self.mute_button.setIcon(self.style().standardIcon(icon))
        self.log("Notifications unmuted" if checked else "Notifications muted")
        workers.MUTE_NOTIFICATIONS = not checked


    def on_spot_started(self):
        self.spot_status_label.setText("Status: Loading...")

    def on_spot_finished(self):
        self.spot_status_label.setText(f"Status: Last spot update at {time.strftime('%H:%M:%S')}")

    def on_fut_started(self):
        self.fut_status_label.setText("Status: Loading...")

    def on_fut_finished(self):
        self.fut_status_label.setText(f"Status: Last futures update at {time.strftime('%H:%M:%S')}")

    def show_rsi_popup(self, row: int, column: int, is_future: bool):
        # Replace self.setOverrideCursor with QApplication.setOverrideCursor
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        table = self.fut_table if is_future else self.spot_table
        token_item = table.item(row, 0)
        token = token_item.text().replace(':', '/') if token_item else "Unknown"
        self.log(f"Fetching RSI for {token}…")
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(fetch_rsi_intervals, token)
            rsis = future.result()
        QApplication.restoreOverrideCursor()  # Restore cursor after fetching RSI
        r1 = rsis.get('1h') or float('nan')
        r4 = rsis.get('4h') or float('nan')
        rD = rsis.get('1d') or float('nan')

        # Build dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"RSI for {token}")
        dialog.setModal(True)
        dialog.resize(350, 220)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        # Header label
        header = QLabel(f"Relative Strength Index")
        header.setFont(QFont("Arial", 14, QFont.Bold))
        header.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(header)

        # Grid: Interval | Value | Status
        grid = QGridLayout()
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(8)

        # Column titles
        grid.addWidget(QLabel("Interval"), 0, 0)
        grid.addWidget(QLabel("Value"),    0, 1)
        grid.addWidget(QLabel("Status"),   0, 2)

        # Helper to color-code
        def styled_label(value: float):
            lbl = QLabel(f"{value:.2f}")
            if value < 30:
                color = "green"
                status = "Oversold"
            elif value > 70:
                color = "red"
                status = "Overbought"
            else:
                color = "lightblue"
                status = "Neutral"
            lbl.setStyleSheet(f"color: {color}; font-weight: bold;")
            return lbl, status

        # Populate rows for each timeframe
        for i, tf in enumerate(["1h", "4h", "1d"], start=1):
            val = {"1h": r1, "4h": r4, "1d": rD}[tf]
            # Interval cell
            tf_lbl = QLabel(tf)
            tf_lbl.setFont(QFont("Arial", 12, QFont.Bold))
            grid.addWidget(tf_lbl, i, 0)

            # Value + Status
            val_lbl, status = styled_label(val)
            grid.addWidget(val_lbl, i, 1)
            grid.addWidget(QLabel(status), i, 2)

        main_layout.addLayout(grid)

        # OK button
        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(dialog.accept)
        main_layout.addWidget(buttons)

        dialog.setLayout(main_layout)
        dialog.exec_()

    def populate_spot_table(self, rows):
        self._populate_table(self.spot_table, rows)

    def populate_fut_table(self, rows):
        self._populate_table(self.fut_table, rows)

    def _populate_table(self, table: QTableWidget, rows):
        unique = {}
        for r in rows:
            sym = r[0]
            if sym not in unique:
                unique[sym] = r
        deduped = list(unique.values())
        table.setRowCount(len(deduped))
        for i, (sym, init_s, prev_s, now_s, vol_s, price_s, ph, pl) in enumerate(deduped):
            items = [self._make_item(sym),
                     self._make_item(init_s, True),
                     self._make_item(prev_s, True),
                     self._make_item(now_s, True),
                     self._make_item(vol_s, True),
                     self._make_item(price_s, True),
                     self._make_item(f"{ph:.2f}-{pl:.2f}")]
            color = None
            try:
                prev_pct = float(prev_s.rstrip("%"))
                now_pct = float(now_s.rstrip("%"))
                price_val = float(str(price_s).replace(",", ""))
            except:
                pass
            else:
                if prev_pct == float(init_s.rstrip("%")):
                    color = NEW_COLOR
                elif now_pct > 0:
                    color = POS_COLOR
                elif now_pct < 0:
                    color = NEG_COLOR
                if price_val > ph or price_val < pl:
                    color = RANGE_BREAK_COLOR
            if color:
                for it in items:
                    it.setBackground(color)
            for col, it in enumerate(items):
                table.setItem(i, col, it)
        table.resizeRowsToContents()

    def _make_item(self, text, numeric=False):
        it = QTableWidgetItem(str(text))
        it.setTextAlignment(Qt.AlignCenter)
        it.setFont(QFont("Courier", 9))
        it.setFlags(it.flags() & ~Qt.ItemIsEditable)
        if numeric:
            try:
                it.setData(Qt.DisplayRole, float(str(text).replace(",", "")))
            except:
                pass
        return it


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
