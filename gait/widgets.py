from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QLabel, QHBoxLayout, QVBoxLayout, QSizePolicy

from config import COLOR_TEXT, COLOR_WARN, COLOR_OK, COLOR_ERROR


class StatusIndicator(QWidget):
    """Colored indicator with a short label."""

    def __init__(self, label_text: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(8)

        self._dot = QLabel()
        self._dot.setFixedSize(14, 14)
        self._set_dot_color(COLOR_WARN)

        self._text = QLabel(label_text)
        self._text.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 12px;")

        layout.addWidget(self._dot)
        layout.addWidget(self._text)
        layout.addStretch()

    def _set_dot_color(self, hex_color: str):
        self._dot.setStyleSheet(f"background-color: {hex_color}; border-radius: 7px;")

    def set_state(self, ok: bool, text_ok: str, text_bad: str, warn: bool = False):
        if warn:
            self._set_dot_color(COLOR_WARN)
        else:
            self._set_dot_color(COLOR_OK if ok else COLOR_ERROR)
        self._text.setText(text_ok if ok else text_bad)


class DigitalReadout(QWidget):
    """Compact digital angle readout for the small live-value strip."""

    def __init__(self, title: str, color: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)

        self.title = QLabel(title)
        self.title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.title.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 10px; letter-spacing: 1px;")

        self.value = QLabel("0.00°")
        self.value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.value.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.value.setStyleSheet(
            f"color: {color}; font-size: 18px; font-weight: 700;"
            f"font-family: 'DejaVu Sans Mono', monospace;"
        )

        layout.addWidget(self.title)
        layout.addWidget(self.value)

    def set_value(self, value: float):
        self.value.setText(f"{value:6.2f}°")
