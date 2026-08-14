from __future__ import annotations

import os

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton, QCheckBox, QVBoxLayout,
    QHBoxLayout, QFormLayout, QFrame, QFileDialog, QMessageBox, QSpinBox,
)

from config import COLOR_PANEL, COLOR_PANEL_ALT, COLOR_TEXT, COLOR_ACCENT, COLOR_OK, COLOR_WARN, DEVICE_NAME


class SettingsPage(QWidget):
    """
    Functional settings screen. Every control here actually changes
    running application behaviour when 'Apply' is pressed - nothing is
    decorative.
    """

    csv_dir_changed = pyqtSignal(str)
    udp_port_changed = pyqtSignal(int)
    prefix_changed = pyqtSignal(str)
    fullscreen_toggled = pyqtSignal(bool)

    def __init__(self, current_csv_dir: str, current_udp_port: int,
                 current_prefix: str, current_fullscreen: bool, parent=None):
        super().__init__(parent)
        self._build_ui(current_csv_dir, current_udp_port, current_prefix, current_fullscreen)

    def _build_ui(self, csv_dir, udp_port, prefix, fullscreen):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        root.addWidget(self._build_recording_card(csv_dir, prefix))
        root.addWidget(self._build_network_card(udp_port))
        root.addWidget(self._build_display_card(fullscreen))
        root.addWidget(self._build_about_card())
        root.addStretch()

    def _card(self, title_text: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setStyleSheet(f"background-color: {COLOR_PANEL}; border-radius: 10px;")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        title = QLabel(title_text)
        title.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 13px; font-weight: 700; letter-spacing: 1px;")
        layout.addWidget(title)
        return card, layout

    # ------------------------------------------------------------ CARDS --
    def _build_recording_card(self, csv_dir, prefix) -> QWidget:
        card, layout = self._card("RECORDING")

        form = QFormLayout()
        row = QHBoxLayout()
        self.in_csv_dir = QLineEdit(csv_dir)
        self.in_csv_dir.setStyleSheet(f"background-color: {COLOR_PANEL_ALT}; color: {COLOR_TEXT}; padding: 4px; border-radius: 4px;")
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_csv_dir)
        browse_btn.setStyleSheet(f"background-color: {COLOR_ACCENT}; color: white; border-radius: 4px; padding: 4px 10px;")
        row.addWidget(self.in_csv_dir, stretch=1)
        row.addWidget(browse_btn)
        form.addRow(self._label("CSV Save Folder"), row)

        self.in_prefix = QLineEdit(prefix)
        self.in_prefix.setStyleSheet(f"background-color: {COLOR_PANEL_ALT}; color: {COLOR_TEXT}; padding: 4px; border-radius: 4px;")
        form.addRow(self._label("Recording Filename Prefix"), self.in_prefix)
        layout.addLayout(form)

        apply_btn = QPushButton("Apply Recording Settings")
        apply_btn.clicked.connect(self._apply_recording)
        apply_btn.setStyleSheet(f"background-color: {COLOR_OK}; color: white; font-weight: 700; border-radius: 6px; padding: 8px;")
        layout.addWidget(apply_btn)
        return card

    def _build_network_card(self, udp_port) -> QWidget:
        card, layout = self._card("DEVICE CONNECTION")

        form = QFormLayout()
        self.in_udp_port = QSpinBox()
        self.in_udp_port.setRange(1024, 65535)
        self.in_udp_port.setValue(udp_port)
        self.in_udp_port.setStyleSheet(f"background-color: {COLOR_PANEL_ALT}; color: {COLOR_TEXT}; padding: 4px; border-radius: 4px;")
        form.addRow(self._label("UDP Listen Port"), self.in_udp_port)
        layout.addLayout(form)

        note = QLabel(f"Device: {DEVICE_NAME}  •  Applying a new port restarts the UDP listener.")
        note.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 11px;")
        layout.addWidget(note)

        apply_btn = QPushButton("Apply & Restart Listener")
        apply_btn.clicked.connect(self._apply_network)
        apply_btn.setStyleSheet(f"background-color: {COLOR_WARN}; color: white; font-weight: 700; border-radius: 6px; padding: 8px;")
        layout.addWidget(apply_btn)
        return card

    def _build_display_card(self, fullscreen) -> QWidget:
        card, layout = self._card("DISPLAY")

        self.chk_fullscreen = QCheckBox("Fullscreen mode")
        self.chk_fullscreen.setChecked(fullscreen)
        self.chk_fullscreen.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 12px;")
        layout.addWidget(self.chk_fullscreen)

        apply_btn = QPushButton("Apply Display Setting")
        apply_btn.clicked.connect(lambda: self.fullscreen_toggled.emit(self.chk_fullscreen.isChecked()))
        apply_btn.setStyleSheet(f"background-color: {COLOR_ACCENT}; color: white; font-weight: 700; border-radius: 6px; padding: 8px;")
        layout.addWidget(apply_btn)
        return card

    def _build_about_card(self) -> QWidget:
        card, layout = self._card("ABOUT")
        info = QLabel(
            "Wearable 3D Knee Gait Analysis System\n"
            f"Sensor device: {DEVICE_NAME}\n"
            "UDP packet schema: {\"time\", \"roll\", \"pitch\", \"yaw\"}"
        )
        info.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 11px;")
        layout.addWidget(info)
        return card

    @staticmethod
    def _label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 12px;")
        return lbl

    # --------------------------------------------------------- ACTIONS --
    def _browse_csv_dir(self):
        chosen = QFileDialog.getExistingDirectory(self, "Select CSV Save Folder", self.in_csv_dir.text())
        if chosen:
            self.in_csv_dir.setText(chosen)

    def _apply_recording(self):
        directory = self.in_csv_dir.text().strip()
        prefix = self.in_prefix.text().strip()
        if not directory:
            QMessageBox.warning(self, "Invalid Folder", "Please choose a save folder.")
            return
        try:
            os.makedirs(directory, exist_ok=True)
        except OSError as exc:
            QMessageBox.critical(self, "Folder Error", f"Could not use this folder:\n{exc}")
            return
        self.csv_dir_changed.emit(directory)
        if prefix:
            self.prefix_changed.emit(prefix)
        QMessageBox.information(self, "Settings Applied", "Recording settings updated.")

    def _apply_network(self):
        port = self.in_udp_port.value()
        self.udp_port_changed.emit(port)
        QMessageBox.information(self, "Settings Applied", f"UDP listener restarted on port {port}.")
