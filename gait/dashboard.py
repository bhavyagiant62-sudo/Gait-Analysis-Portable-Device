#!/usr/bin/env python3
import os
import sys
import time
import platform
from collections import deque
from datetime import datetime

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QFrame,
    QMessageBox,
    QSizePolicy,
    QStackedWidget,
    QScrollArea,
)

import pyqtgraph as pg

from config import (
    APP_TITLE,
    CSV_DIR,
    PATIENTS_FILE,
    DEVICE_NAME,
    COLOR_ACCENT,
    COLOR_BG,
    COLOR_ERROR,
    COLOR_OK,
    COLOR_PANEL,
    COLOR_PANEL_ALT,
    COLOR_PITCH,
    COLOR_ROLL,
    COLOR_TEXT,
    COLOR_WARN,
    COLOR_YAW,
    ESP32_TIMEOUT_SEC,
    FULLSCREEN_MODE,
    GUI_REFRESH_INTERVAL_MS,
    PLOT_REFRESH_INTERVAL_MS,
    RATE_UPDATE_INTERVAL_MS,
    RECORDING_PREFIX,
    TABLE_MAX_ROWS,
    UDP_PORT,
    WINDOW_SIZE,
)
from csv_logger import CSVLogger
from graphs import LiveAngleGraph
from status_panel import StatusPanel
from udp_receiver import UDPReceiverThread, NetworkMonitorThread
from viewer3d import KneeOrientationViewer
from widgets import DigitalReadout, StatusIndicator
from advanced_window import AdvancedGaitWindow
from intelligent_gait_interpretation import IntelligentGaitInterpretationWindow
from patient_database import PatientDatabase
from patients_page import PatientsPage
from settings_page import SettingsPage


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)

        self.recording = False
        self.last_packet_time = None
        self.packet_count_this_second = 0
        self.esp32_connected = False
        self.wifi_connected = False
        self.reconnect_count = 0
        self.packet_counter = 0
        self.packets_lost = 0
        self.packet_frequency = 0.0
        self.average_frequency = 0.0
        self.latency_ms = 0.0
        self.jitter_ms = 0.0
        self.connection_time_sec = 0.0
        self.last_packet_timestamp = None
        self.last_packet_sequence = None
        self._pending_rows = []
        self._export_buffer = deque(maxlen=100000)
        # (time_ms, pitch, roll, yaw) tuples feeding Advanced Analysis /
        # Clinical Interpretation - capped so those windows stay responsive
        # while still covering several minutes of walking at ~50-100 Hz.
        self._sample_buffer = deque(maxlen=6000)

        # Runtime-configurable settings (Settings screen changes these).
        self._csv_dir = CSV_DIR
        self._udp_port = UDP_PORT
        self._recording_prefix = RECORDING_PREFIX
        self._fullscreen = FULLSCREEN_MODE

        # Last live reading, used for "Insert Live Reading" on the
        # Patients screen and for the header connection badge.
        self._last_pitch = None
        self._last_roll = None
        self._last_yaw = None

        self.csv_logger = CSVLogger(self._csv_dir, self._recording_prefix)
        self.advanced_window = None
        self.interpretation_window = None

        self.patient_db = PatientDatabase()
        self.patient_db.load_from_file(PATIENTS_FILE)

        self._build_ui()
        self._start_threads()
        self._start_timers()

    # ------------------------------------------------------------ BUILD --
    def _build_ui(self):
        central = QWidget()
        central.setStyleSheet(f"background-color: {COLOR_BG};")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        root.addWidget(self._build_nav_bar())

        self.stack = QStackedWidget()
        self.home_page = self._build_home_page()
        self.patients_page = self._build_patients_page()
        self.settings_page = self._build_settings_page()
        self.stack.addWidget(self.home_page)     # index 0 - first interface
        self.stack.addWidget(self.patients_page)  # index 1
        self.stack.addWidget(self.settings_page)  # index 2

        # A scroll area around the page stack means the *window* can always
        # be shrunk to fit the screen - if a page's content still wants
        # more room than that, it scrolls instead of forcing the window
        # to grow past the display.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"QScrollArea {{ background-color: {COLOR_BG}; border: none; }}")
        scroll.setWidget(self.stack)
        root.addWidget(scroll, stretch=1)

        self.setMinimumSize(640, 480)

        if self._fullscreen:
            self.showFullScreen()
        else:
            self._fit_to_screen()

    def _fit_to_screen(self):
        """Sizes the window to fit the real available screen space, so it
        never overflows a smaller monitor/laptop regardless of the
        configured WINDOW_SIZE default."""
        screen = QApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None
        if available is not None:
            margin = 40
            width = min(WINDOW_SIZE[0], available.width() - margin)
            height = min(WINDOW_SIZE[1], available.height() - margin)
            width = max(width, 640)
            height = max(height, 480)
            self.resize(width, height)
            frame = self.frameGeometry()
            frame.moveCenter(available.center())
            self.move(frame.topLeft())
        else:
            self.resize(*WINDOW_SIZE)

    # -- Persistent top bar: title, clock, connection status, navigation --
    def _build_nav_bar(self) -> QWidget:
        panel = QFrame()
        panel.setStyleSheet(f"background-color: {COLOR_PANEL}; border-radius: 10px;")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(10)

        title = QLabel(APP_TITLE)
        title.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 18px; font-weight: 700;")
        layout.addWidget(title)
        layout.addSpacing(16)

        self.lbl_date = QLabel("--")
        self.lbl_date.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 13px;")
        layout.addWidget(self.lbl_date)

        self.lbl_time = QLabel("--")
        self.lbl_time.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 13px;")
        layout.addWidget(self.lbl_time)

        layout.addSpacing(16)

        self.lbl_wifi = QLabel("WiFi: --")
        self.lbl_wifi.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 13px;")
        layout.addWidget(self.lbl_wifi)

        # Prominent wearable-device connection indicator - this is the
        # single clearest place in the app to check "is the sensor on?".
        self.device_badge = QLabel(f"● {DEVICE_NAME}: Disconnected")
        self.device_badge.setStyleSheet(
            f"color: white; background-color: {COLOR_ERROR}; font-size: 13px; "
            f"font-weight: 700; border-radius: 6px; padding: 6px 12px;"
        )
        layout.addWidget(self.device_badge)

        self.lbl_rate = QLabel("Rate: 0 Hz")
        self.lbl_rate.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 13px;")
        layout.addWidget(self.lbl_rate)

        layout.addStretch()

        self.btn_nav_home = self._make_nav_button("Home", self.show_home)
        self.btn_nav_patients = self._make_nav_button("Patients", self.show_patients)
        self.btn_nav_settings = self._make_nav_button("Settings", self.show_settings)
        layout.addWidget(self.btn_nav_home)
        layout.addWidget(self.btn_nav_patients)
        layout.addWidget(self.btn_nav_settings)

        layout.addSpacing(12)
        self.btn_exit = self._make_button("Exit", "#4D5E6F", self.exit_app)
        layout.addWidget(self.btn_exit)

        return panel

    @staticmethod
    def _make_nav_button(text: str, slot) -> QPushButton:
        btn = QPushButton(text)
        btn.setMinimumHeight(34)
        btn.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_PANEL_ALT}; color: {COLOR_TEXT}; "
            f"font-size: 12px; font-weight: 600; border-radius: 6px; padding: 6px 14px; }}"
            f"QPushButton:pressed {{ background-color: #3B82F6; }}"
        )
        btn.clicked.connect(slot)
        return btn

    # -- Home page: 3 live graphs, small live readouts, 3D knee viewer,
    #    live table and recording controls. This is the app's first screen.
    def _build_home_page(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        left = QVBoxLayout()
        left.setSpacing(10)
        left.addWidget(self._build_live_readouts(), stretch=0)
        left.addWidget(self._build_middle_section(), stretch=4)
        left.addWidget(self._build_table(), stretch=1)
        layout.addLayout(left, stretch=3)
        layout.addWidget(self._build_right_panel(), stretch=1)
        return page

    def _build_patients_page(self) -> QWidget:
        return PatientsPage(
            self.patient_db,
            save_callback=self._save_patients,
            live_snapshot_callback=self._get_live_snapshot,
        )

    def _build_settings_page(self) -> QWidget:
        page = SettingsPage(
            current_csv_dir=self._csv_dir,
            current_udp_port=self._udp_port,
            current_prefix=self._recording_prefix,
            current_fullscreen=self._fullscreen,
        )
        page.csv_dir_changed.connect(self._on_csv_dir_changed)
        page.udp_port_changed.connect(self._on_udp_port_changed)
        page.prefix_changed.connect(self._on_prefix_changed)
        page.fullscreen_toggled.connect(self._on_fullscreen_toggled)
        return page

    def _build_live_readouts(self):
        panel = QFrame()
        panel.setStyleSheet(f"background-color: {COLOR_PANEL}; border-radius: 10px;")
        panel.setMaximumHeight(48)
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(16)

        self.readout_pitch = DigitalReadout("KNEE PITCH", COLOR_PITCH)
        self.readout_roll = DigitalReadout("KNEE ROLL", COLOR_ROLL)
        self.readout_yaw = DigitalReadout("KNEE YAW", COLOR_YAW)
        layout.addWidget(self.readout_pitch)
        layout.addWidget(self.readout_roll)
        layout.addWidget(self.readout_yaw)
        return panel

    def _build_middle_section(self):
        panel = QFrame()
        panel.setStyleSheet(f"background-color: {COLOR_PANEL}; border-radius: 10px;")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.graphs = LiveAngleGraph()
        self.viewer = KneeOrientationViewer()
        layout.addWidget(self.graphs, stretch=3)
        layout.addWidget(self.viewer, stretch=1)
        return panel

    def _build_table(self):
        panel = QFrame()
        panel.setStyleSheet(f"background-color: {COLOR_PANEL}; border-radius: 10px;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)

        title = QLabel("LIVE DATA TABLE")
        title.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 12px; font-weight: 700; letter-spacing: 1px;")
        layout.addWidget(title)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["Packet", "Time", "Pitch", "Roll", "Yaw", "Calibration", "Timestamp", "Sampling Freq"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setStyleSheet(
            f"QTableWidget {{ background-color: {COLOR_PANEL_ALT}; color: {COLOR_TEXT}; gridline-color: #2E3F53; font-size: 11px; }}"
            f"QHeaderView::section {{ background-color: #22303C; color: {COLOR_ACCENT}; padding: 4px; border: none; font-weight: 600; }}"
        )
        layout.addWidget(self.table)
        return panel

    def _build_right_panel(self):
        panel = QFrame()
        panel.setFixedWidth(260)
        panel.setStyleSheet(f"background-color: {COLOR_PANEL}; border-radius: 10px;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.ind_connection = StatusIndicator("Connection: --")
        self.ind_recording = StatusIndicator("Recording: OFF")
        self.ind_calibration = StatusIndicator("Calibration: Unknown")
        layout.addWidget(self.ind_connection)
        layout.addWidget(self.ind_recording)
        layout.addWidget(self.ind_calibration)

        self.status_panel = StatusPanel()
        layout.addWidget(self.status_panel)

        self._build_controls(layout)
        layout.addStretch()
        return panel

    def _build_controls(self, layout):
        controls = QFrame()
        controls.setStyleSheet(f"background-color: {COLOR_PANEL_ALT}; border-radius: 8px;")
        box = QVBoxLayout(controls)
        box.setContentsMargins(8, 8, 8, 8)
        box.setSpacing(6)

        title = QLabel("RECORDING / EXPORT")
        title.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 12px; font-weight: 700; letter-spacing: 1px;")
        box.addWidget(title)

        self.btn_start = self._make_button("Start Recording", COLOR_OK, self.start_recording)
        self.btn_stop = self._make_button("Stop Recording", COLOR_ERROR, self.stop_recording)
        self.btn_save = self._make_button("Save CSV", COLOR_ACCENT, self.save_csv)
        self.btn_export = self._make_button("Export CSV", COLOR_WARN, self.export_csv)
        self.btn_advanced = self._make_button("Advanced Analysis", COLOR_ACCENT, self.open_advanced_window)
        self.btn_clinical = self._make_button("Clinical Interpretation", COLOR_ACCENT, self.open_interpretation_window)
        for button in (self.btn_start, self.btn_stop, self.btn_save, self.btn_export, self.btn_advanced, self.btn_clinical):
            box.addWidget(button)
        self.btn_stop.setEnabled(False)
        layout.addWidget(controls)

    @staticmethod
    def _make_button(text: str, color: str, slot):
        button = QPushButton(text)
        button.setMinimumHeight(40)
        button.setStyleSheet(
            f"QPushButton {{ background-color: {color}; color: white; font-size: 12px; font-weight: 600; border-radius: 6px; }}"
            f"QPushButton:pressed {{ background-color: #555555; }}"
            f"QPushButton:disabled {{ background-color: #3A3A3A; color: #888888; }}"
        )
        button.clicked.connect(slot)
        return button

    # ------------------------------------------------------- NAVIGATION --
    def show_home(self):
        self.stack.setCurrentWidget(self.home_page)

    def show_patients(self):
        self.stack.setCurrentWidget(self.patients_page)

    def show_settings(self):
        self.stack.setCurrentWidget(self.settings_page)

    # ------------------------------------------------------------ PATIENTS --
    def _save_patients(self):
        try:
            self.patient_db.save_to_file(PATIENTS_FILE)
        except OSError as exc:
            QMessageBox.critical(self, "Save Error", f"Could not save patient data:\n{exc}")

    def _get_live_snapshot(self) -> str:
        if self._last_pitch is None:
            return ""
        connection = "Connected" if self.esp32_connected else "Disconnected"
        recording = "ON" if self.recording else "OFF"
        return (
            f"Pitch: {self._last_pitch:.2f}°  Roll: {self._last_roll:.2f}°  "
            f"Yaw: {self._last_yaw:.2f}°  |  Device: {connection}  |  Recording: {recording}"
        )

    # ------------------------------------------------------------ SETTINGS --
    def _on_csv_dir_changed(self, directory: str):
        self._csv_dir = directory
        self.csv_logger.set_directory(directory)

    def _on_prefix_changed(self, prefix: str):
        self._recording_prefix = prefix
        self.csv_logger.set_prefix(prefix)

    def _on_udp_port_changed(self, port: int):
        if port == self._udp_port and self.udp_thread.isRunning():
            return
        self._udp_port = port
        self.udp_thread.stop()
        self.udp_thread = UDPReceiverThread(port=port)
        self.udp_thread.packet_received.connect(self.on_packet_received)
        self.udp_thread.error_occurred.connect(self.on_udp_error)
        self.udp_thread.start()
        # A new listener means the device hasn't been heard from yet.
        self.last_packet_time = None

    def _on_fullscreen_toggled(self, enabled: bool):
        self._fullscreen = enabled
        if enabled:
            self.showFullScreen()
        else:
            self.showNormal()
            self._fit_to_screen()

    # ------------------------------------------------------------- THREADS --
    def _start_threads(self):
        self.udp_thread = UDPReceiverThread(port=self._udp_port)
        self.udp_thread.packet_received.connect(self.on_packet_received)
        self.udp_thread.error_occurred.connect(self.on_udp_error)
        self.udp_thread.start()

        self.net_thread = NetworkMonitorThread()
        self.net_thread.wifi_status_changed.connect(self.on_wifi_status_changed)
        self.net_thread.start()

    def _start_timers(self):
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(1000)

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

    # ------------------------------------------------------------- SLOTS ----
    def on_packet_received(self, data: dict):
        try:
            packet_time = int(data["time"])
            pitch = float(data["pitch"])
            roll = float(data["roll"])
            yaw = float(data["yaw"])
        except (KeyError, TypeError, ValueError):
            return

        self.last_packet_time = time.monotonic()
        self.packet_count_this_second += 1
        self.packet_counter += 1
        self.packet_frequency = self.packet_count_this_second

        if self.last_packet_sequence is None:
            self.last_packet_sequence = packet_time
        else:
            self.packets_lost += max(0, int(packet_time) - self.last_packet_sequence - 1)
            self.last_packet_sequence = packet_time

        if self.last_packet_timestamp is not None:
            delta = (time.monotonic() - self.last_packet_timestamp) * 1000.0
            self.latency_ms = delta
            self.jitter_ms = abs(delta - self.latency_ms)
        self.last_packet_timestamp = time.monotonic()
        self.connection_time_sec += 0.1

        calibration = bool(data.get("calibrated", False))
        self.ind_calibration.set_state(
            calibration,
            "Calibration: Ready",
            "Calibration: Needed",
            warn=not calibration,
        )
        self._last_pitch, self._last_roll, self._last_yaw = pitch, roll, yaw
        self.readout_pitch.set_value(pitch)
        self.readout_roll.set_value(roll)
        self.readout_yaw.set_value(yaw)

        self.graphs.append_sample(self.packet_counter, pitch, roll, yaw)
        self.viewer.update_orientation(pitch, roll, yaw)

        row = (self.packet_counter, packet_time, pitch, roll, yaw, calibration, datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3], self.packet_frequency)
        self._pending_rows.append(row)
        self._export_buffer.append(row)
        self._sample_buffer.append((packet_time, pitch, roll, yaw))

        if self.recording and self.csv_logger.is_active:
            self.csv_logger.write_row(self.packet_counter, packet_time, pitch, roll, yaw, calibration, self.packet_frequency)

        self._refresh_status_panel()

    def on_udp_error(self, message: str):
        print(f"[UDP] {message}")

    def on_wifi_status_changed(self, connected: bool):
        self.wifi_connected = connected
        self.lbl_wifi.setText(f"WiFi: {'Connected' if connected else 'Disconnected'}")
        self.lbl_wifi.setStyleSheet(f"color: {COLOR_OK if connected else COLOR_ERROR}; font-size: 13px;")

    def _update_clock(self):
        now = datetime.now()
        self.lbl_date.setText(now.strftime("%Y-%m-%d"))
        self.lbl_time.setText(now.strftime("%H:%M:%S"))

    def _update_packet_rate(self):
        rate = self.packet_count_this_second
        self.packet_count_this_second = 0
        self.packet_frequency = rate
        self.lbl_rate.setText(f"Rate: {rate} Hz")
        self._refresh_status_panel()

    def _check_esp32_timeout(self):
        if self.last_packet_time is None:
            connected = False
        else:
            connected = (time.monotonic() - self.last_packet_time) <= ESP32_TIMEOUT_SEC

        if connected != self.esp32_connected:
            self.esp32_connected = connected
            self.ind_connection.set_state(connected, "Connection: Live", "Connection: Lost")
            self.device_badge.setText(f"● {DEVICE_NAME}: {'Connected' if connected else 'Disconnected'}")
            self.device_badge.setStyleSheet(
                f"color: white; background-color: {COLOR_OK if connected else COLOR_ERROR}; "
                f"font-size: 13px; font-weight: 700; border-radius: 6px; padding: 6px 12px;"
            )
            if not connected and self.last_packet_time is not None:
                self.reconnect_count += 1
                QMessageBox.warning(self, "Connection Lost", "Wearable device disconnected. Reconnect attempts will continue automatically.")

    def _flush_pending_rows(self):
        if not self._pending_rows:
            return

        rows = self._pending_rows
        self._pending_rows = []
        self.table.setUpdatesEnabled(False)
        try:
            for row in reversed(rows):
                self.table.insertRow(0)
                for col_idx, value in enumerate(row):
                    self.table.setItem(0, col_idx, QTableWidgetItem(str(value)))
            while self.table.rowCount() > TABLE_MAX_ROWS:
                self.table.removeRow(self.table.rowCount() - 1)
        finally:
            self.table.setUpdatesEnabled(True)

    def _refresh_status_panel(self):
        self.status_panel.set_metric("packet_counter", f"{self.packet_counter}", COLOR_ACCENT)
        self.status_panel.set_metric("packets_lost", f"{self.packets_lost}", COLOR_WARN if self.packets_lost else COLOR_ACCENT)
        self.status_panel.set_metric("packet_freq", f"{self.packet_frequency:.1f} Hz", COLOR_ACCENT)
        self.status_panel.set_metric("avg_freq", f"{self.average_frequency:.1f} Hz", COLOR_ACCENT)
        self.status_panel.set_metric("latency", f"{self.latency_ms:.1f} ms", COLOR_OK if self.latency_ms < 50 else COLOR_WARN)
        self.status_panel.set_metric("jitter", f"{self.jitter_ms:.1f} ms", COLOR_OK if self.jitter_ms < 10 else COLOR_WARN)
        self.status_panel.set_metric("connection_time", f"{self.connection_time_sec:.1f} s", COLOR_ACCENT)
        self.status_panel.set_metric("reconnect_count", f"{self.reconnect_count}", COLOR_WARN if self.reconnect_count else COLOR_ACCENT)

    def start_recording(self):
        if self.recording:
            return
        try:
            filepath = self.csv_logger.start()
        except OSError as exc:
            QMessageBox.critical(self, "Recording Error", f"Could not create CSV file:\n{exc}")
            return

        self.recording = True
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.ind_recording.set_state(True, "Recording: ON", "Recording: OFF")
        self._refresh_status_panel()
        print(f"[REC] Recording started -> {filepath}")

    def stop_recording(self):
        if not self.recording:
            return
        self.recording = False
        self.csv_logger.stop()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.ind_recording.set_state(False, "Recording: ON", "Recording: OFF")

    def save_csv(self):
        if not self._export_buffer:
            QMessageBox.information(self, "Save CSV", "No data available to save yet.")
            return
        try:
            os.makedirs(self._csv_dir, exist_ok=True)
            filename = f"gait_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            filepath = os.path.join(self._csv_dir, filename)
            with open(filepath, mode="w", newline="", encoding="utf-8") as handle:
                handle.write("Packet,Time,Pitch,Roll,Yaw,Calibration,Timestamp,SamplingFrequency\n")
                for row in self._export_buffer:
                    handle.write(",".join(str(v) for v in row) + "\n")
            QMessageBox.information(self, "Save CSV", f"Saved {len(self._export_buffer)} rows to:\n{filepath}")
        except OSError as exc:
            QMessageBox.critical(self, "Save CSV Error", f"Could not write CSV file:\n{exc}")

    def export_csv(self):
        self.save_csv()

    def clear_graph(self):
        self.graphs.clear()

    def open_advanced_window(self):
        if self.advanced_window is None or not self.advanced_window.isVisible():
            self.advanced_window = AdvancedGaitWindow(self, samples=list(self._sample_buffer))
            self.advanced_window.show()
        else:
            self.advanced_window.recalculate()
            self.advanced_window.raise_()
            self.advanced_window.activateWindow()

    def open_interpretation_window(self):
        if self.interpretation_window is None or not self.interpretation_window.isVisible():
            self.interpretation_window = IntelligentGaitInterpretationWindow(self, samples=list(self._sample_buffer))
            self.interpretation_window.show()
        else:
            self.interpretation_window.raise_()
            self.interpretation_window.activateWindow()

    def exit_app(self):
        reply = QMessageBox.question(self, "Exit", "Exit the gait dashboard?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.close()

    def closeEvent(self, event):
        try:
            if self.recording:
                self.stop_recording()
            self._save_patients()
            self.udp_thread.stop()
            self.net_thread.stop()
        except Exception as exc:
            print(f"[SHUTDOWN WARNING] {exc}")
        finally:
            event.accept()


def main():
    os.makedirs(CSV_DIR, exist_ok=True)

    if platform.machine().startswith("arm") or "raspberry" in platform.platform().lower():
        os.environ.setdefault("QT_QPA_PLATFORM", "eglfs")

    app = QApplication(sys.argv)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[FATAL] {exc}")
        raise
