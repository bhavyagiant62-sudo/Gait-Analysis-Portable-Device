#!/usr/bin/env python3
"""
============================================================================
 KNEE GAIT ANALYSIS DASHBOARD
============================================================================
Platform    : Raspberry Pi 5, Python 3.13
Display     : Official Raspberry Pi Touch Display (800x480, fullscreen)
Input       : UDP JSON packets from ESP32 on port 5005
              {"time": 12345, "roll": 2.15, "pitch": 48.22, "yaw": -1.15}

ARCHITECTURE
----------------------------------------------------------------------------
- UDPReceiverThread   : dedicated QThread that owns the UDP socket and
                         blocks (with a timeout) only on recvfrom(). Never
                         touches the GUI directly - it communicates purely
                         via Qt signals, which are thread-safe by design
                         (Qt automatically marshals the signal onto the
                         receiving object's thread, i.e. the GUI thread).
- NetworkMonitorThread : dedicated QThread that periodically checks WiFi/
                         internet reachability without blocking the GUI.
- MainWindow            : owns all GUI construction and state. All slots
                         connected to the worker threads' signals execute
                         on the main (GUI) thread automatically, so no
                         manual locking of Qt widgets is required.
- CSVLogger             : thin wrapper around a csv.writer for the
                         continuous "Start/Stop Recording" session file.

THREAD SAFETY NOTES
----------------------------------------------------------------------------
- The only data shared across threads is passed through pyqtSignal
  payloads (dict / bool / str), which Qt copies safely across the
  thread boundary via its queued-connection mechanism.
- Both worker threads use a threading.Event as a cooperative stop flag
  and short socket/select timeouts so they shut down promptly and never
  block indefinitely, keeping the application fully responsive to close.
============================================================================
"""

import sys
import os
import socket
import json
import csv
import time
import threading
from collections import deque
from datetime import datetime

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QGridLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame, QMessageBox, QSizePolicy
)

import pyqtgraph as pg

from advanced_window import AdvancedGaitWindow
from intelligent_gait_interpretation import IntelligentGaitInterpretationWindow
from graphs import LiveAngleGraph
from viewer3d import KneeOrientationViewer
from status_panel import StatusPanel


# ============================================================================
#                               CONFIGURATION
# ============================================================================
UDP_PORT = 5005
UDP_BIND_ADDR = "0.0.0.0"
UDP_SOCKET_TIMEOUT_SEC = 0.5           # allows prompt thread shutdown

ESP32_TIMEOUT_SEC = 2.0                # no packet in this long -> "Disconnected"
WIFI_CHECK_INTERVAL_SEC = 3.0
WIFI_CHECK_TIMEOUT_SEC = 1.0
WIFI_PROBE_HOST = ("8.8.8.8", 53)      # reachability probe, no data sent

GUI_REFRESH_INTERVAL_MS = 100          # table refresh rate (~10 Hz)
PLOT_REFRESH_INTERVAL_MS = 66          # plot refresh rate (~15 Hz)
CLOCK_UPDATE_INTERVAL_MS = 1000
RATE_UPDATE_INTERVAL_MS = 1000

PLOT_MAX_POINTS = 300                  # rolling window shown on the graph
TABLE_MAX_ROWS = 500                   # cap to keep the widget responsive
EXPORT_BUFFER_MAX = 50000              # in-memory buffer for "Save CSV"

CSV_DIR = os.path.expanduser("~/GaitAnalysis/data/")

FULLSCREEN_MODE = True
WINDOW_SIZE = (800, 480)

# Color palette (medical / clinical dark theme)
COLOR_BG = "#101820"
COLOR_PANEL = "#1B2530"
COLOR_TEXT = "#E6EEF3"
COLOR_ACCENT = "#00B4D8"
COLOR_OK = "#2ECC71"
COLOR_WARN = "#F1C40F"
COLOR_ERROR = "#E74C3C"
COLOR_PITCH = "#00B4D8"
COLOR_ROLL = "#F39C12"
COLOR_YAW = "#9B59B6"


# ============================================================================
#                          UDP RECEIVER (BACKGROUND THREAD)
# ============================================================================
class UDPReceiverThread(QThread):
    """
    Owns the UDP socket on its own thread so that blocking network I/O
    never touches the GUI event loop. Emits one signal per valid JSON
    packet received; malformed packets are logged and skipped rather
    than crashing the thread.
    """
    packet_received = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    status_message = pyqtSignal(str)

    def __init__(self, port: int, parent=None):
        super().__init__(parent)
        self._port = port
        self._stop_event = threading.Event()
        self._sock = None

    def run(self):
        """Thread entry point. Binds the socket and loops until stopped."""
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.settimeout(UDP_SOCKET_TIMEOUT_SEC)
            self._sock.bind((UDP_BIND_ADDR, self._port))
            self.status_message.emit(f"UDP listener bound on port {self._port}")
        except OSError as exc:
            self.error_occurred.emit(f"Failed to bind UDP socket: {exc}")
            return

        while not self._stop_event.is_set():
            try:
                raw_bytes, _addr = self._sock.recvfrom(1024)
            except socket.timeout:
                # Expected periodically; lets us re-check the stop flag.
                continue
            except OSError as exc:
                if not self._stop_event.is_set():
                    self.error_occurred.emit(f"UDP socket error: {exc}")
                break

            try:
                data = json.loads(raw_bytes.decode("utf-8"))
                # Basic schema validation - skip malformed packets gracefully.
                if all(k in data for k in ("time", "roll", "pitch", "yaw")):
                    self.packet_received.emit(data)
                else:
                    self.error_occurred.emit("Packet missing required fields")
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                self.error_occurred.emit(f"Malformed packet ignored: {exc}")

        if self._sock:
            self._sock.close()

    def stop(self):
        """Requests a graceful shutdown; safe to call from the GUI thread."""
        self._stop_event.set()
        self.wait(2000)


# ============================================================================
#                       NETWORK / WIFI MONITOR (BACKGROUND THREAD)
# ============================================================================
class NetworkMonitorThread(QThread):
    """
    Periodically checks internet/WiFi reachability using a lightweight
    TCP connect probe (no data exchanged). Runs on its own thread so the
    short connect timeout never stalls the GUI.
    """
    wifi_status_changed = pyqtSignal(bool)

    def __init__(self, interval_sec: float = WIFI_CHECK_INTERVAL_SEC, parent=None):
        super().__init__(parent)
        self._interval = interval_sec
        self._stop_event = threading.Event()

    def run(self):
        while not self._stop_event.is_set():
            connected = self._probe_connectivity()
            self.wifi_status_changed.emit(connected)
            # Sleep in small increments via Event.wait() so stop() is prompt.
            self._stop_event.wait(self._interval)

    @staticmethod
    def _probe_connectivity() -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(WIFI_CHECK_TIMEOUT_SEC)
                s.connect(WIFI_PROBE_HOST)
            return True
        except OSError:
            return False

    def stop(self):
        self._stop_event.set()
        self.wait(2000)


# ============================================================================
#                              CSV LOGGER (SESSION FILE)
# ============================================================================
class CSVLogger:
    """
    Manages a single continuous recording session's CSV file. A new,
    timestamped file is created automatically each time recording starts.
    Not thread-safe by itself - by design it is only ever written from
    the GUI thread (inside MainWindow's packet-received slot), so no
    additional locking is required.
    """

    def __init__(self, directory: str):
        self._directory = directory
        self._file = None
        self._writer = None
        self._filepath = None

    def start(self) -> str:
        """Creates a new timestamped CSV file and writes the header row."""
        os.makedirs(self._directory, exist_ok=True)
        filename = f"gait_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        self._filepath = os.path.join(self._directory, filename)

        self._file = open(self._filepath, mode="w", newline="", encoding="utf-8")
        self._writer = csv.writer(self._file)
        self._writer.writerow(["Time", "Pitch", "Roll", "Yaw", "Timestamp"])
        self._file.flush()
        return self._filepath

    def write_row(self, packet_time, pitch, roll, yaw):
        if self._writer is None:
            return
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        self._writer.writerow([packet_time, pitch, roll, yaw, timestamp])

    def flush(self):
        if self._file:
            self._file.flush()

    def stop(self):
        if self._file:
            self._file.flush()
            self._file.close()
        self._file = None
        self._writer = None

    @property
    def is_active(self) -> bool:
        return self._writer is not None

    @property
    def filepath(self):
        return self._filepath


# ============================================================================
#                         SMALL REUSABLE STATUS INDICATOR WIDGET
# ============================================================================
class StatusIndicator(QWidget):
    """A colored dot + text label pair used for the right-hand status panel."""

    def __init__(self, label_text: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(8)

        self._dot = QLabel()
        self._dot.setFixedSize(16, 16)
        self._set_dot_color(COLOR_WARN)

        self._text = QLabel(label_text)
        self._text.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 13px;")

        layout.addWidget(self._dot)
        layout.addWidget(self._text)
        layout.addStretch()

    def _set_dot_color(self, hex_color: str):
        self._dot.setStyleSheet(
            f"background-color: {hex_color}; border-radius: 8px;"
        )

    def set_state(self, ok: bool, text_ok: str, text_bad: str, warn: bool = False):
        """Updates dot color and label text based on a boolean status."""
        if warn:
            self._set_dot_color(COLOR_WARN)
        else:
            self._set_dot_color(COLOR_OK if ok else COLOR_ERROR)
        self._text.setText(text_ok if ok else text_bad)


# ============================================================================
#                                  MAIN WINDOW
# ============================================================================
class MainWindow(QMainWindow):
    """
    Top-level application window. Builds the full dashboard UI and wires
    it to the UDP receiver / network monitor worker threads.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Knee Gait Analysis Dashboard")

        # ---- Runtime state -------------------------------------------------
        self.recording = False
        self.last_packet_time = None      # monotonic time of last UDP packet
        self.packet_count_this_second = 0
        self.esp32_connected = False
        self.wifi_connected = False

        # Rolling buffers for the live plot (fast, append-only)
        self._t_buf = deque(maxlen=PLOT_MAX_POINTS)
        self._pitch_buf = deque(maxlen=PLOT_MAX_POINTS)
        self._roll_buf = deque(maxlen=PLOT_MAX_POINTS)
        self._yaw_buf = deque(maxlen=PLOT_MAX_POINTS)

        # Buffer of packets waiting to be inserted into the table on the
        # next throttled GUI refresh tick (keeps table updates off the
        # 50 Hz hot path while still feeling real-time to the user).
        self._pending_rows = []

        # Full-session in-memory buffer backing the manual "Save CSV" button.
        self._export_buffer = deque(maxlen=EXPORT_BUFFER_MAX)

        self.csv_logger = CSVLogger(CSV_DIR)

        self.advanced_window = None
        self.interpretation_window = None
        self._sample_buffer = []
        self._fps_frame_count = 0
        self._fps_last_second = 0

        self._build_ui()
        self._start_threads()
        self._start_timers()

    # ------------------------------------------------------------------ UI --
    def _build_ui(self):
        central = QWidget()
        central.setStyleSheet(f"background-color: {COLOR_BG};")
        self.setCentralWidget(central)

        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.sidebar = self._build_sidebar()
        root_layout.addWidget(self.sidebar)

        content = QWidget()
        content.setStyleSheet(f"background-color: {COLOR_BG};")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(12, 12, 12, 12)
        content_layout.setSpacing(10)

        content_layout.addWidget(self._build_header())
        content_layout.addLayout(self._build_center_column(), stretch=1)

        root_layout.addWidget(content, stretch=1)

        if FULLSCREEN_MODE:
            self.showFullScreen()
        else:
            self.resize(*WINDOW_SIZE)

    # -- Header: project name, clock, WiFi, ESP32 status, packet rate --------
    def _build_header(self) -> QWidget:
        panel = QFrame()
        panel.setStyleSheet(
            f"background-color: {COLOR_PANEL}; border-radius: 14px;"
        )
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(16, 10, 16, 10)

        title = QLabel("KNEE GAIT ANALYSIS SYSTEM")
        title.setStyleSheet(
            f"color: {COLOR_ACCENT}; font-size: 18px; font-weight: 700; letter-spacing: 1px;"
        )
        layout.addWidget(title)
        layout.addStretch()

        self.lbl_clock = QLabel("--:--:--")
        self.lbl_clock.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 13px;")
        layout.addWidget(self.lbl_clock)
        layout.addSpacing(16)

        self.lbl_wifi = QLabel("WiFi: --")
        self.lbl_wifi.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 13px;")
        layout.addWidget(self.lbl_wifi)
        layout.addSpacing(16)

        self.lbl_esp32 = QLabel("ESP32: --")
        self.lbl_esp32.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 13px;")
        layout.addWidget(self.lbl_esp32)
        layout.addSpacing(16)

        self.lbl_rate = QLabel("Rate: 0 Hz")
        self.lbl_rate.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 13px;")
        layout.addWidget(self.lbl_rate)
        layout.addSpacing(16)

        self.lbl_sampling = QLabel("Sampling: 0 Hz")
        self.lbl_sampling.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 13px;")
        layout.addWidget(self.lbl_sampling)
        layout.addSpacing(16)

        self.lbl_recording = QLabel("Recording: OFF")
        self.lbl_recording.setStyleSheet(f"color: {COLOR_ERROR}; font-size: 13px; font-weight: 700;")
        layout.addWidget(self.lbl_recording)
        layout.addSpacing(16)

        self.lbl_quality = QLabel("Quality: --")
        self.lbl_quality.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 13px;")
        layout.addWidget(self.lbl_quality)
        layout.addSpacing(16)

        self.lbl_fps = QLabel("FPS: 0")
        self.lbl_fps.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 13px;")
        layout.addWidget(self.lbl_fps)

        return panel

    def _build_sidebar(self) -> QWidget:
        panel = QFrame()
        panel.setFixedWidth(210)
        panel.setStyleSheet(f"background-color: #111827; border: none;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        title = QLabel("MEDICAL VIEW")
        title.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 12px; font-weight: 700; letter-spacing: 2px;")
        layout.addWidget(title)

        layout.addWidget(QLabel("Clinical Gait Suite"))
        layout.addSpacing(12)

        nav_items = [
            ("Home", self._noop),
            ("Live Analysis", self._noop),
            ("Advanced Analysis", self.open_advanced_window),
            ("3D Viewer", self._noop),
            ("Patient", self._noop),
            ("Reports", self._noop),
            ("Research", self._noop),
            ("Clinical Interpretation", self.open_interpretation_window),
            ("Settings", self._noop),
            ("Help", self._noop),
            ("About", self._noop),
        ]
        for text, slot in nav_items:
            button = self._make_nav_button(text, slot)
            layout.addWidget(button)

        layout.addStretch()
        return panel

    def _build_center_column(self) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(10)

        col.addLayout(self._build_metrics_row(), stretch=0)
        col.addLayout(self._build_middle_row(), stretch=1)
        col.addWidget(self._build_table_card(), stretch=1)
        return col

    def _build_metrics_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)
        pitch_card, pitch_value, pitch_min, pitch_max, pitch_avg, pitch_trend = self._build_metric_card("Knee Pitch", COLOR_PITCH, "PITCH", "0.00°")
        roll_card, roll_value, roll_min, roll_max, roll_avg, roll_trend = self._build_metric_card("Knee Roll", COLOR_ROLL, "ROLL", "0.00°")
        yaw_card, yaw_value, yaw_min, yaw_max, yaw_avg, yaw_trend = self._build_metric_card("Knee Yaw", COLOR_YAW, "YAW", "0.00°")
        self.lbl_pitch_val = pitch_value
        self.lbl_roll_val = roll_value
        self.lbl_yaw_val = yaw_value
        self.metric_cards = {
            "pitch": (pitch_value, pitch_min, pitch_max, pitch_avg, pitch_trend, COLOR_PITCH),
            "roll": (roll_value, roll_min, roll_max, roll_avg, roll_trend, COLOR_ROLL),
            "yaw": (yaw_value, yaw_min, yaw_max, yaw_avg, yaw_trend, COLOR_YAW),
        }
        row.addWidget(pitch_card)
        row.addWidget(roll_card)
        row.addWidget(yaw_card)
        return row

    def _build_metric_card(self, title: str, color: str, caption: str, value_text: str):
        card = QFrame()
        card.setStyleSheet(f"background-color: {COLOR_PANEL}; border-radius: 14px;")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 12px; font-weight: 700; letter-spacing: 1px;")
        layout.addWidget(title_label)

        value = QLabel(value_text)
        value.setStyleSheet(f"color: {color}; font-size: 30px; font-weight: 700; font-family: 'DejaVu Sans Mono', monospace;")
        layout.addWidget(value)

        subtitle = QLabel(caption)
        subtitle.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 11px;")
        layout.addWidget(subtitle)

        stat_row = QHBoxLayout()
        stat_row.setSpacing(6)
        min_label = QLabel("Min: --")
        min_label.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 10px;")
        max_label = QLabel("Max: --")
        max_label.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 10px;")
        avg_label = QLabel("Avg: --")
        avg_label.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 10px;")
        stat_row.addWidget(min_label)
        stat_row.addWidget(max_label)
        stat_row.addWidget(avg_label)
        layout.addLayout(stat_row)

        trend = QLabel("●")
        trend.setStyleSheet(f"color: {color}; font-size: 20px;")
        layout.addWidget(trend)
        return card, value, min_label, max_label, avg_label, trend

    def _build_middle_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(self._build_graph_card(), stretch=2)
        row.addWidget(self._build_3d_card(), stretch=1)
        return row

    def _build_graph_card(self) -> QWidget:
        card = QFrame()
        card.setStyleSheet(f"background-color: {COLOR_PANEL}; border-radius: 14px;")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        top = QHBoxLayout()
        title = QLabel("Live Angle Signals")
        title.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 13px; font-weight: 700; letter-spacing: 1px;")
        top.addWidget(title)
        top.addStretch()
        top.addWidget(self._make_icon_button("⏯"))
        top.addWidget(self._make_icon_button("↕"))
        top.addWidget(self._make_icon_button("⤢"))
        layout.addLayout(top)

        self.graph_widget = LiveAngleGraph(self)
        layout.addWidget(self.graph_widget, stretch=1)
        return card

    def _build_3d_card(self) -> QWidget:
        card = QFrame()
        card.setStyleSheet(f"background-color: {COLOR_PANEL}; border-radius: 14px;")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        top = QHBoxLayout()
        title = QLabel("3D Orientation")
        title.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 13px; font-weight: 700; letter-spacing: 1px;")
        top.addWidget(title)
        top.addStretch()
        reset_btn = self._make_icon_button("↺")
        top.addWidget(reset_btn)
        layout.addLayout(top)

        self.viewer3d = KneeOrientationViewer(self)
        layout.addWidget(self.viewer3d, stretch=1)
        return card

    def _build_table_card(self) -> QWidget:
        card = QFrame()
        card.setStyleSheet(f"background-color: {COLOR_PANEL}; border-radius: 14px;")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("Live Packet Log")
        title.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 13px; font-weight: 700; letter-spacing: 1px;")
        header.addWidget(title)
        header.addStretch()
        self.btn_start = self._make_button("Start", COLOR_OK, self.start_recording)
        self.btn_stop = self._make_button("Stop", COLOR_ERROR, self.stop_recording)
        self.btn_save = self._make_button("Export", COLOR_ACCENT, self.save_csv)
        self.btn_clear = self._make_button("Clear", "#7F8C8D", self.clear_graph)
        self.btn_advanced = self._make_button("Advanced", COLOR_WARN, self.open_advanced_window)
        self.btn_clinical = self._make_button("Clinical", COLOR_ACCENT, self.open_interpretation_window)
        self.btn_exit = self._make_button("Exit", "#34495E", self.exit_app)
        for b in (self.btn_start, self.btn_stop, self.btn_save, self.btn_clear, self.btn_advanced, self.btn_clinical, self.btn_exit):
            header.addWidget(b)
        layout.addLayout(header)

        table = QTableWidget(0, 4)
        table.setHorizontalHeaderLabels(["Time", "Pitch", "Roll", "Yaw"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionMode(QTableWidget.NoSelection)
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(True)
        table.setStyleSheet(
            f"QTableWidget {{ background-color: #0F172A; color: {COLOR_TEXT}; gridline-color: #2A3642; font-size: 11px; }}"
            f"QTableWidget::item:alternate {{ background-color: #142033; }}"
            f"QHeaderView::section {{ background-color: #1E293B; color: {COLOR_ACCENT}; padding: 4px; border: none; font-weight: 600; }}"
        )
        layout.addWidget(table, stretch=1)
        self.table = table

        self.status_panel = StatusPanel(self)
        self.status_panel.setFixedWidth(240)
        layout.addWidget(self.status_panel)
        return card

    def _make_nav_button(self, text: str, slot) -> QPushButton:
        btn = QPushButton(text)
        btn.setMinimumHeight(36)
        btn.setStyleSheet(
            f"QPushButton {{ background-color: transparent; color: {COLOR_TEXT}; text-align: left; padding-left: 10px; border-radius: 8px; font-size: 12px; }}"
            f"QPushButton:hover {{ background-color: #1E293B; }}"
            f"QPushButton:pressed {{ background-color: #3B82F6; }}"
        )
        btn.clicked.connect(slot)
        return btn

    @staticmethod
    def _make_icon_button(text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedSize(28, 28)
        btn.setStyleSheet(f"background-color: #1E293B; color: {COLOR_TEXT}; border-radius: 8px;")
        return btn

    @staticmethod
    def _make_button(text: str, color: str, slot) -> QPushButton:
        btn = QPushButton(text)
        btn.setMinimumHeight(28)
        btn.setStyleSheet(
            f"QPushButton {{ background-color: {color}; color: white; font-size: 11px; font-weight: 600; border-radius: 6px; padding: 4px 8px; }}"
            f"QPushButton:pressed {{ background-color: #555555; }}"
            f"QPushButton:disabled {{ background-color: #3A3A3A; color: #888888; }}"
        )
        btn.clicked.connect(slot)
        return btn

    def _noop(self):
        return None

    def _update_live_card(self, key: str, value: float, samples):
        if key not in self.metric_cards or not samples:
            return

        value_label, min_label, max_label, avg_label, trend_label, color = self.metric_cards[key]
        numeric_samples = [float(sample) for sample in samples]
        average = sum(numeric_samples) / len(numeric_samples)
        previous = numeric_samples[-2] if len(numeric_samples) > 1 else value
        delta = value - previous
        if delta > 0.05:
            trend = "^ rising"
            trend_color = COLOR_OK
        elif delta < -0.05:
            trend = "v falling"
            trend_color = COLOR_WARN
        else:
            trend = "- steady"
            trend_color = COLOR_TEXT

        value_label.setText(f"{value:6.2f}°")
        value_label.setStyleSheet(f"color: {color}; font-size: 30px; font-weight: 700; font-family: 'DejaVu Sans Mono', monospace;")
        min_label.setText(f"Min: {min(numeric_samples):.1f}")
        max_label.setText(f"Max: {max(numeric_samples):.1f}")
        avg_label.setText(f"Avg: {average:.1f}")
        trend_label.setText(trend)
        trend_label.setStyleSheet(f"color: {trend_color}; font-size: 13px; font-weight: 700;")

    # ------------------------------------------------------------- THREADS --
    def _start_threads(self):
        self.udp_thread = UDPReceiverThread(UDP_PORT)
        self.udp_thread.packet_received.connect(self.on_packet_received)
        self.udp_thread.error_occurred.connect(self.on_udp_error)
        self.udp_thread.status_message.connect(lambda msg: print(f"[UDP] {msg}"))
        self.udp_thread.start()

        self.net_thread = NetworkMonitorThread()
        self.net_thread.wifi_status_changed.connect(self.on_wifi_status_changed)
        self.net_thread.start()

    # -------------------------------------------------------------- TIMERS --
    def _start_timers(self):
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(CLOCK_UPDATE_INTERVAL_MS)

        self.rate_timer = QTimer(self)
        self.rate_timer.timeout.connect(self._update_packet_rate)
        self.rate_timer.start(RATE_UPDATE_INTERVAL_MS)

        self.esp32_timer = QTimer(self)
        self.esp32_timer.timeout.connect(self._check_esp32_timeout)
        self.esp32_timer.start(RATE_UPDATE_INTERVAL_MS)

        self.table_timer = QTimer(self)
        self.table_timer.timeout.connect(self._flush_pending_rows)
        self.table_timer.start(GUI_REFRESH_INTERVAL_MS)

        self._update_clock()
        self.status_panel.set_metric("packet_counter", "0")
        self.status_panel.set_metric("packet_freq", "0 Hz")
        self.status_panel.set_recording_info("Idle", "00:00", "-", 0)
        self.status_panel.set_calibration(0, 0, 0)

    # ------------------------------------------------------------- SLOTS ----
    def on_packet_received(self, data: dict):
        """
        Executes on the GUI thread (Qt marshals the cross-thread signal
        automatically). Kept intentionally lightweight: buffer updates,
        optional CSV write, and bookkeeping only - no widget rebuilding.
        """
        try:
            t = data["time"]
            pitch = float(data["pitch"])
            roll = float(data["roll"])
            yaw = float(data["yaw"])
        except (KeyError, TypeError, ValueError):
            return  # already validated upstream, but stay defensive

        self.last_packet_time = time.monotonic()
        self.packet_count_this_second += 1

        # Optional forward-compatible calibration flag from firmware.
        if "calibrated" in data:
            is_cal = bool(data["calibrated"])
            self.status_panel.set_calibration(3 if is_cal else 0, 3 if is_cal else 0, 3 if is_cal else 0)

        # Update the big digital readout immediately (cheap widget updates).
        self.lbl_pitch_val.setText(f"{pitch:6.2f}°")
        self.lbl_roll_val.setText(f"{roll:6.2f}°")
        self.lbl_yaw_val.setText(f"{yaw:6.2f}°")

        # Fast append-only buffers for the plot.
        self._t_buf.append(t)
        self._pitch_buf.append(pitch)
        self._roll_buf.append(roll)
        self._yaw_buf.append(yaw)
        self._update_live_card("pitch", pitch, self._pitch_buf)
        self._update_live_card("roll", roll, self._roll_buf)
        self._update_live_card("yaw", yaw, self._yaw_buf)

        # Queue for the throttled table refresh.
        row = (t, pitch, roll, yaw)
        self._pending_rows.append(row)
        self._export_buffer.append(row)
        self._sample_buffer.append((t, pitch, roll, yaw))
        if len(self._sample_buffer) > 200:
            self._sample_buffer = self._sample_buffer[-200:]

        self.graph_widget.append_sample(int(t), pitch, roll, yaw)
        self.viewer3d.update_orientation(pitch, roll, yaw)
        self.status_panel.set_gait_metric("Max Flexion", f"{max(pitch, 0):.1f}°")
        self.status_panel.set_gait_metric("Max Extension", f"{min(pitch, 0):.1f}°")
        self.status_panel.set_gait_metric("ROM", f"{max(0.0, pitch):.1f}°")
        self.status_panel.set_gait_metric("Avg Angle", f"{pitch:.1f}°")

        # Continuous CSV logging while a recording session is active.
        if self.recording and self.csv_logger.is_active:
            self.csv_logger.write_row(t, pitch, roll, yaw)

    def on_udp_error(self, message: str):
        # Non-fatal - log to console so a bad packet never disrupts the UI.
        print(f"[UDP WARNING] {message}")

    def on_wifi_status_changed(self, connected: bool):
        self.wifi_connected = connected
        self.lbl_wifi.setText(f"WiFi: {'Connected' if connected else 'Disconnected'}")
        self.lbl_wifi.setStyleSheet(
            f"color: {COLOR_OK if connected else COLOR_ERROR}; font-size: 14px;"
        )

    # ---------------------------------------------------------- TIMER TICKS -
    def _update_clock(self):
        self.lbl_clock.setText(datetime.now().strftime("%Y-%m-%d  %H:%M:%S"))

    def _update_packet_rate(self):
        rate = self.packet_count_this_second
        self.packet_count_this_second = 0
        self.lbl_rate.setText(f"Rate: {rate} Hz")
        self.lbl_sampling.setText(f"Sampling: {rate} Hz")
        if rate >= 45:
            quality_text = "Quality: Excellent"
            quality_color = COLOR_OK
        elif rate >= 25:
            quality_text = "Quality: Fair"
            quality_color = COLOR_WARN
        else:
            quality_text = "Quality: Low"
            quality_color = COLOR_ERROR
        self.lbl_quality.setText(quality_text)
        self.lbl_quality.setStyleSheet(f"color: {quality_color}; font-size: 13px; font-weight: 700;")
        self.status_panel.set_metric("packet_counter", str(rate))
        self.status_panel.set_metric("packet_freq", f"{rate} Hz")

    def _check_esp32_timeout(self):
        if self.last_packet_time is None:
            connected = False
        else:
            connected = (time.monotonic() - self.last_packet_time) <= ESP32_TIMEOUT_SEC

        if connected != self.esp32_connected:
            self.esp32_connected = connected
            self.lbl_esp32.setText(f"ESP32: {'Connected' if connected else 'Disconnected'}")
            self.lbl_esp32.setStyleSheet(
                f"color: {COLOR_OK if connected else COLOR_ERROR}; font-size: 14px;"
            )
            if hasattr(self, "ind_connection"):
                self.ind_connection.set_state(
                    connected, "Connection: Live", "Connection: Lost"
                )

    def _flush_pending_rows(self):
        """Moves buffered packets into the QTableWidget, newest on top."""
        if not self._pending_rows:
            return

        rows = self._pending_rows
        self._pending_rows = []

        self.table.setUpdatesEnabled(False)
        try:
            # Insert in reverse so the most recent packet ends up at row 0.
            for (t, pitch, roll, yaw) in reversed(rows):
                self.table.insertRow(0)
                self.table.setItem(0, 0, QTableWidgetItem(str(t)))
                self.table.setItem(0, 1, QTableWidgetItem(f"{pitch:.2f}"))
                self.table.setItem(0, 2, QTableWidgetItem(f"{roll:.2f}"))
                self.table.setItem(0, 3, QTableWidgetItem(f"{yaw:.2f}"))

            # Trim from the bottom (oldest) to keep the widget responsive.
            while self.table.rowCount() > TABLE_MAX_ROWS:
                self.table.removeRow(self.table.rowCount() - 1)
        finally:
            self.table.setUpdatesEnabled(True)

    # ------------------------------------------------------- BUTTON ACTIONS -
    def start_recording(self):
        if self.recording:
            return
        try:
            filepath = self.csv_logger.start()
        except OSError as exc:
            QMessageBox.critical(self, "Recording Error",
                                  f"Could not create CSV file:\n{exc}")
            return

        self.recording = True
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.lbl_recording.setText("Recording: ON")
        self.lbl_recording.setStyleSheet(f"color: {COLOR_OK}; font-size: 13px; font-weight: 700;")
        self.status_panel.set_recording_info("Recording", "00:00", filepath, 0)
        print(f"[REC] Recording started -> {filepath}")

    def stop_recording(self):
        if not self.recording:
            return
        self.recording = False
        self.csv_logger.stop()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.lbl_recording.setText("Recording: OFF")
        self.lbl_recording.setStyleSheet(f"color: {COLOR_ERROR}; font-size: 13px; font-weight: 700;")
        self.status_panel.set_recording_info("Idle", "00:00", self.csv_logger.filepath or "-", len(self._export_buffer))
        print("[REC] Recording stopped.")

    def save_csv(self):
        """
        Exports the full in-memory session buffer to a new timestamped
        CSV file. Independent of Start/Stop Recording - useful for a
        quick manual snapshot at any time.
        """
        if not self._export_buffer:
            QMessageBox.information(self, "Save CSV", "No data available to save yet.")
            return

        try:
            os.makedirs(CSV_DIR, exist_ok=True)
            filename = f"gait_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            filepath = os.path.join(CSV_DIR, filename)

            with open(filepath, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Time", "Pitch", "Roll", "Yaw", "Timestamp"])
                snapshot_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                for (t, pitch, roll, yaw) in self._export_buffer:
                    writer.writerow([t, f"{pitch:.2f}", f"{roll:.2f}", f"{yaw:.2f}", snapshot_ts])

            QMessageBox.information(self, "Save CSV", f"Saved {len(self._export_buffer)} rows to:\n{filepath}")
        except OSError as exc:
            QMessageBox.critical(self, "Save CSV Error", f"Could not write CSV file:\n{exc}")

    def clear_graph(self):
        self._t_buf.clear()
        self._pitch_buf.clear()
        self._roll_buf.clear()
        self._yaw_buf.clear()
        self.graph_widget.clear()

    def open_advanced_window(self):
        if self.advanced_window is None or not self.advanced_window.isVisible():
            self.advanced_window = AdvancedGaitWindow(self)
            self.advanced_window.show()
        else:
            self.advanced_window.raise_()
            self.advanced_window.activateWindow()

    def open_interpretation_window(self):
        if self.interpretation_window is None or not self.interpretation_window.isVisible():
            samples = [(sample[0], sample[1], sample[2], sample[3]) for sample in self._sample_buffer]
            self.interpretation_window = IntelligentGaitInterpretationWindow(self, samples=samples)
            self.interpretation_window.show()
        else:
            self.interpretation_window.raise_()
            self.interpretation_window.activateWindow()

    def exit_app(self):
        reply = QMessageBox.question(
            self, "Exit", "Exit the Gait Analysis Dashboard?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.close()

    # ------------------------------------------------------------ SHUTDOWN --
    def closeEvent(self, event):
        """Ensures background threads and any open file handle are cleaned up."""
        try:
            if self.recording:
                self.stop_recording()
            self.udp_thread.stop()
            self.net_thread.stop()
        except Exception as exc:
            print(f"[SHUTDOWN WARNING] {exc}")
        finally:
            event.accept()


# ============================================================================
#                                    ENTRY POINT
# ============================================================================
def main():
    os.makedirs(CSV_DIR, exist_ok=True)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # top-level safety net - never crash silently
        print(f"[FATAL] Unhandled exception: {exc}")
        raise
