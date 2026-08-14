from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QGridLayout, QFrame

from config import COLOR_PANEL, COLOR_TEXT, COLOR_ACCENT, COLOR_OK, COLOR_WARN, COLOR_ERROR


class StatusPanel(QWidget):
    """Compact diagnostics, recording info, calibration, and gait metrics panel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet(f"background-color: {COLOR_PANEL}; border-radius: 10px;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel("DIAGNOSTICS")
        title.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 12px; font-weight: 700; letter-spacing: 1px;")
        layout.addWidget(title)

        self.metrics = {}
        grid = QGridLayout()
        grid.setSpacing(8)
        self._add_metric(grid, 0, 0, "Packet Counter", "0")
        self._add_metric(grid, 0, 1, "Packets Lost", "0")
        self._add_metric(grid, 1, 0, "Packet Freq", "0 Hz")
        self._add_metric(grid, 1, 1, "Avg Freq", "0 Hz")
        self._add_metric(grid, 2, 0, "Latency", "0 ms")
        self._add_metric(grid, 2, 1, "Jitter", "0 ms")
        self._add_metric(grid, 3, 0, "Connection", "0 s")
        self._add_metric(grid, 3, 1, "Reconnects", "0")
        layout.addLayout(grid)

        layout.addSpacing(8)
        rec_title = QLabel("RECORDING")
        rec_title.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 12px; font-weight: 700; letter-spacing: 1px;")
        layout.addWidget(rec_title)
        self.rec_status = self._make_value_label("Status", "Idle")
        self.rec_duration = self._make_value_label("Duration", "00:00")
        self.rec_file = self._make_value_label("CSV File", "-")
        self.rec_rows = self._make_value_label("Rows", "0")
        for widget in (self.rec_status, self.rec_duration, self.rec_file, self.rec_rows):
            layout.addWidget(widget)

        layout.addSpacing(8)
        cal_title = QLabel("CALIBRATION")
        cal_title.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 12px; font-weight: 700; letter-spacing: 1px;")
        layout.addWidget(cal_title)

        self.calib_labels = {
            "overall": self._make_calibration_box("Overall"),
            "thigh": self._make_calibration_box("Thigh"),
            "calf": self._make_calibration_box("Calf"),
        }
        for widget in self.calib_labels.values():
            layout.addWidget(widget)

        layout.addSpacing(8)
        gait_title = QLabel("GAIT PARAMETERS")
        gait_title.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 12px; font-weight: 700; letter-spacing: 1px;")
        layout.addWidget(gait_title)
        self.gait_metrics = {}
        self._add_gait_metric("Max Flexion", "0.0°")
        self._add_gait_metric("Max Extension", "0.0°")
        self._add_gait_metric("ROM", "0.0°")
        self._add_gait_metric("Avg Angle", "0.0°")
        self._add_gait_metric("Cadence", "0 spm")
        self._add_gait_metric("Steps", "0")

    def _add_metric(self, grid, row, col, name, value):
        frame = QFrame()
        frame.setStyleSheet(f"background-color: #1A2735; border-radius: 6px;")
        box = QVBoxLayout(frame)
        box.setContentsMargins(8, 6, 8, 6)
        label = QLabel(name)
        label.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 11px;")
        value_label = QLabel(value)
        value_label.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 15px; font-weight: 600;")
        box.addWidget(label)
        box.addWidget(value_label)
        grid.addWidget(frame, row, col)
        self.metrics[(row, col)] = value_label

    def _make_value_label(self, title: str, value: str) -> QWidget:
        frame = QFrame()
        frame.setStyleSheet(f"background-color: #1A2735; border-radius: 6px;")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 6, 8, 6)
        title_label = QLabel(title)
        title_label.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 11px;")
        value_label = QLabel(value)
        value_label.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 13px; font-weight: 600;")
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        return frame

    def _add_gait_metric(self, title: str, value: str):
        frame = QFrame()
        frame.setStyleSheet(f"background-color: #1A2735; border-radius: 6px;")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 6, 8, 6)
        title_label = QLabel(title)
        title_label.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 11px;")
        value_label = QLabel(value)
        value_label.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 13px; font-weight: 600;")
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        self.gait_metrics[title] = value_label
        self.layout().addWidget(frame)

    def _make_calibration_box(self, name: str) -> QWidget:
        frame = QFrame()
        frame.setStyleSheet(f"background-color: #1A2735; border-radius: 6px;")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 6, 8, 6)
        title = QLabel(name)
        title.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 12px;")
        self._indicator = QLabel("●")
        self._indicator.setStyleSheet(f"color: {COLOR_WARN}; font-size: 18px;")
        self._value = QLabel("0")
        self._value.setStyleSheet(f"color: {COLOR_WARN}; font-size: 14px; font-weight: 700;")
        layout.addWidget(title)
        layout.addWidget(self._indicator)
        layout.addWidget(self._value)
        return frame

    def set_metric(self, key: str, value: str, color: str = COLOR_ACCENT):
        if key in {"packet_counter", "packets_lost", "packet_freq", "avg_freq", "latency", "jitter", "connection_time", "reconnect_count"}:
            mapping = {
                "packet_counter": (0, 0),
                "packets_lost": (0, 1),
                "packet_freq": (1, 0),
                "avg_freq": (1, 1),
                "latency": (2, 0),
                "jitter": (2, 1),
                "connection_time": (3, 0),
                "reconnect_count": (3, 1),
            }
            self.metrics[mapping[key]].setText(value)
            self.metrics[mapping[key]].setStyleSheet(f"color: {color}; font-size: 15px; font-weight: 600;")

    def set_recording_info(self, status: str, duration: str, csv_file: str, rows: int):
        self.rec_status.findChildren(QLabel)[1].setText(status)
        self.rec_duration.findChildren(QLabel)[1].setText(duration)
        self.rec_file.findChildren(QLabel)[1].setText(csv_file)
        self.rec_rows.findChildren(QLabel)[1].setText(str(rows))

    def set_gait_metric(self, name: str, value: str):
        if name in self.gait_metrics:
            self.gait_metrics[name].setText(value)

    def set_calibration(self, overall: int, thigh: int, calf: int):
        for key, value in (("overall", overall), ("thigh", thigh), ("calf", calf)):
            widget = self.calib_labels[key]
            if value >= 3:
                color = COLOR_OK
                text = "3 - Fully Calibrated"
            elif value == 2:
                color = COLOR_WARN
                text = "2 - Partial"
            else:
                color = COLOR_ERROR
                text = "0/1 - Not Calibrated"
            widget.findChildren(QLabel)[1].setStyleSheet(f"color: {color}; font-size: 18px;")
            widget.findChildren(QLabel)[2].setText(text)
            widget.findChildren(QLabel)[2].setStyleSheet(f"color: {color}; font-size: 14px; font-weight: 700;")
