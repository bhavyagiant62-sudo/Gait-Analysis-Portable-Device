import math
import os
import time
from collections import deque

import numpy as np
import pyqtgraph as pg
import pyqtgraph.exporters
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from config import (
    COLOR_ACCENT,
    COLOR_BG,
    COLOR_OK,
    COLOR_PANEL,
    COLOR_PANEL_ALT,
    COLOR_PITCH,
    COLOR_ROLL,
    COLOR_TEXT,
    COLOR_WARN,
    COLOR_YAW,
    PLOT_MAX_POINTS,
)


class LiveAngleGraph(QWidget):
    """Single synchronized knee-angle chart for pitch, roll and yaw."""

    AXES = (
        ("pitch", "Pitch", "Flexion / Extension", COLOR_PITCH),
        ("roll", "Roll", "Abduction / Adduction", COLOR_ROLL),
        ("yaw", "Yaw", "Internal / External Rotation", COLOR_YAW),
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        try:
            pg.setConfigOptions(antialias=True, useOpenGL=True)
        except Exception:
            pg.setConfigOptions(antialias=True)

        self._buffers = {key: deque(maxlen=PLOT_MAX_POINTS) for key, *_ in self.AXES}
        self._time = deque(maxlen=PLOT_MAX_POINTS)
        self._start_time = None
        self._paused = False
        self._dirty = False
        self._auto_scale = True
        self._region_user_controlled = False
        self._visible = {key: True for key, *_ in self.AXES}
        self._last_values = {key: None for key, *_ in self.AXES}
        self._last_refresh = time.perf_counter()

        self._build_ui()
        self._plot_timer = QTimer(self)
        self._plot_timer.timeout.connect(self._refresh_plot)
        self._plot_timer.start(20)

    def _build_ui(self):
        self.setStyleSheet(f"background-color: {COLOR_PANEL}; color: {COLOR_TEXT};")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("Knee Joint Angle")
        title.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 15px; font-weight: 700;")
        header.addWidget(title)
        header.addStretch()
        self.cursor_label = QLabel("Cursor: --")
        self.cursor_label.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 11px;")
        header.addWidget(self.cursor_label)
        root.addLayout(header)

        controls = QHBoxLayout()
        controls.setSpacing(6)
        self.axis_buttons = {}
        for key, label, _desc, color in self.AXES:
            button = self._make_button(f"Hide {label}", color, checkable=True)
            button.setChecked(True)
            button.clicked.connect(lambda checked, axis=key: self._toggle_axis(axis, checked))
            self.axis_buttons[key] = button
            controls.addWidget(button)

        self.btn_reset = self._make_button("Reset Zoom", COLOR_ACCENT)
        self.btn_pause = self._make_button("Pause Graph", COLOR_WARN)
        self.btn_resume = self._make_button("Resume Graph", COLOR_OK)
        self.btn_clear = self._make_button("Clear Graph", "#607D8B")
        self.btn_png = self._make_button("Export PNG", COLOR_ACCENT)
        self.btn_svg = self._make_button("Export SVG", COLOR_ACCENT)
        self.btn_auto = self._make_button("Auto Scale", COLOR_OK, checkable=True)
        self.btn_auto.setChecked(True)

        self.btn_reset.clicked.connect(self.reset_zoom)
        self.btn_pause.clicked.connect(self.pause_graph)
        self.btn_resume.clicked.connect(self.resume_graph)
        self.btn_clear.clicked.connect(self.clear)
        self.btn_png.clicked.connect(lambda: self.export_graph("png"))
        self.btn_svg.clicked.connect(lambda: self.export_graph("svg"))
        self.btn_auto.clicked.connect(self._toggle_auto_scale)

        for button in (
            self.btn_reset,
            self.btn_pause,
            self.btn_resume,
            self.btn_clear,
            self.btn_png,
            self.btn_svg,
            self.btn_auto,
        ):
            controls.addWidget(button)
        controls.addStretch()
        root.addLayout(controls)

        body = QHBoxLayout()
        body.setSpacing(10)
        self.plot = pg.PlotWidget()
        self.plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.plot.setBackground(COLOR_BG)
        self.plot.showGrid(x=True, y=True, alpha=0.25)
        self.plot.setLabel("bottom", "Time", units="seconds")
        self.plot.setLabel("left", "Angle", units="degrees")
        self.plot.setMouseEnabled(x=True, y=True)
        self.plot.setMenuEnabled(True)
        self.plot.addLegend(offset=(10, 10))
        self.plot.getViewBox().setMouseMode(pg.ViewBox.PanMode)
        self.plot.getViewBox().setLimits(xMin=0)
        self.plot.getAxis("left").setPen(pg.mkPen(COLOR_TEXT))
        self.plot.getAxis("bottom").setPen(pg.mkPen(COLOR_TEXT))
        self.plot.getAxis("left").setTextPen(pg.mkPen(COLOR_TEXT))
        self.plot.getAxis("bottom").setTextPen(pg.mkPen(COLOR_TEXT))

        self.zero_line = pg.InfiniteLine(pos=0, angle=0, pen=pg.mkPen("#8AA0B8", width=1, style=Qt.DashLine))
        self.crosshair_x = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("#9FB6C8", width=1))
        self.crosshair_y = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen("#9FB6C8", width=1))
        self.region = pg.LinearRegionItem(values=(0, 2), brush=pg.mkBrush(38, 198, 218, 35), movable=True)
        self.region.setZValue(10)
        self.region.sigRegionChanged.connect(self._update_region_statistics)
        self.region.sigRegionChangeFinished.connect(self._mark_region_user_controlled)
        self.plot.addItem(self.zero_line)
        self.plot.addItem(self.region)
        self.plot.addItem(self.crosshair_x, ignoreBounds=True)
        self.plot.addItem(self.crosshair_y, ignoreBounds=True)

        self.curves = {}
        for key, label, desc, color in self.AXES:
            curve = self.plot.plot(
                [],
                [],
                pen=pg.mkPen(color, width=2.4),
                name=f"{label} ({desc})",
                antialias=True,
                connect="finite",
            )
            curve.setClipToView(True)
            curve.setDownsampling(auto=True, method="peak")
            self.curves[key] = curve

        self.curve_pitch = self.curves["pitch"]
        self.curve_roll = self.curves["roll"]
        self.curve_yaw = self.curves["yaw"]

        self._mouse_proxy = pg.SignalProxy(self.plot.scene().sigMouseMoved, rateLimit=50, slot=self._on_mouse_moved)
        body.addWidget(self.plot, stretch=5)
        body.addWidget(self._build_statistics_panel(), stretch=2)
        root.addLayout(body, stretch=1)

    def _build_statistics_panel(self):
        panel = QFrame()
        panel.setStyleSheet(f"background-color: {COLOR_PANEL_ALT}; border-radius: 8px;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel("GRAPH STATISTICS")
        title.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 12px; font-weight: 700;")
        layout.addWidget(title)

        self.stat_labels = {}
        stat_grid = QGridLayout()
        stat_grid.setHorizontalSpacing(8)
        stat_grid.setVerticalSpacing(4)
        headers = ("Axis", "Current", "Max", "Min", "Avg", "Std", "ROM")
        for col, header in enumerate(headers):
            stat_grid.addWidget(self._small_label(header, COLOR_TEXT, bold=True), 0, col)
        for row, (key, label, _desc, color) in enumerate(self.AXES, start=1):
            stat_grid.addWidget(self._small_label(label, color, bold=True), row, 0)
            self.stat_labels[key] = {}
            for col, metric in enumerate(("current", "max", "min", "avg", "std", "rom"), start=1):
                value = self._small_label("--", COLOR_TEXT)
                stat_grid.addWidget(value, row, col)
                self.stat_labels[key][metric] = value
        layout.addLayout(stat_grid)

        region_title = QLabel("SELECTED INTERVAL")
        region_title.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 12px; font-weight: 700;")
        layout.addWidget(region_title)

        self.region_summary = QLabel("Drag the highlighted time region to analyze.")
        self.region_summary.setWordWrap(True)
        self.region_summary.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 10px;")
        layout.addWidget(self.region_summary)

        self.region_labels = {}
        region_grid = QGridLayout()
        region_grid.setHorizontalSpacing(8)
        region_grid.setVerticalSpacing(4)
        for col, header in enumerate(("Metric", "Pitch", "Roll", "Yaw")):
            region_grid.addWidget(self._small_label(header, COLOR_TEXT, bold=True), 0, col)
        for row, metric in enumerate(("Max", "Min", "Average", "Peak", "Peak-to-Peak", "Mean", "RMS"), start=1):
            region_grid.addWidget(self._small_label(metric, COLOR_TEXT), row, 0)
            self.region_labels[metric] = {}
            for col, key in enumerate(("pitch", "roll", "yaw"), start=1):
                value = self._small_label("--", COLOR_TEXT)
                region_grid.addWidget(value, row, col)
                self.region_labels[metric][key] = value
        layout.addLayout(region_grid)
        layout.addStretch()
        return panel

    def _small_label(self, text, color, bold=False):
        label = QLabel(text)
        label.setStyleSheet(f"color: {color}; font-size: 10px; font-weight: {'700' if bold else '400'};")
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        return label

    def _make_button(self, text, color, checkable=False):
        button = QPushButton(text)
        button.setCheckable(checkable)
        button.setMinimumHeight(28)
        button.setStyleSheet(
            f"QPushButton {{ background-color: {color}; color: white; font-size: 10px; "
            f"font-weight: 700; border: none; border-radius: 6px; padding: 4px 8px; }}"
            f"QPushButton:checked {{ border: 1px solid {COLOR_TEXT}; }}"
            f"QPushButton:pressed {{ background-color: #455A64; }}"
        )
        return button

    def append_sample(self, sample_index: int, pitch: float, roll: float, yaw: float):
        if self._start_time is None:
            self._start_time = time.perf_counter()

        elapsed = time.perf_counter() - self._start_time
        self._time.append(elapsed)
        for key, value in (("pitch", pitch), ("roll", roll), ("yaw", yaw)):
            self._buffers[key].append(float(value))
            self._last_values[key] = float(value)

        self._dirty = True
        self._update_live_statistics()

    def _smooth(self, values):
        if len(values) < 5:
            return np.asarray(values, dtype=float)
        data = np.asarray(values, dtype=float)
        kernel = np.ones(3, dtype=float) / 3.0
        return np.convolve(data, kernel, mode="same")

    def _refresh_plot(self):
        if self._paused or not self._dirty or not self._time:
            return

        x = np.asarray(self._time, dtype=float)
        for key, *_ in self.AXES:
            y = self._smooth(self._buffers[key])
            self.curves[key].setData(x, y)
            self.curves[key].setVisible(self._visible[key])

        if self._auto_scale:
            self.plot.enableAutoRange(axis=pg.ViewBox.YAxis, enable=True)
        else:
            self.plot.enableAutoRange(axis=pg.ViewBox.YAxis, enable=False)

        if len(x):
            right = float(x[-1])
            left = max(0.0, right - max(8.0, len(x) / 50.0))
            self.plot.setXRange(left, max(right, 8.0), padding=0)
            if not self._region_user_controlled and right > 2.0:
                self.region.setRegion((max(0.0, right - 2.0), right))

        self._dirty = False
        self._update_region_statistics()

    def _toggle_axis(self, axis, visible):
        self._visible[axis] = visible
        self.curves[axis].setVisible(visible)
        label = axis.capitalize()
        self.axis_buttons[axis].setText(f"Hide {label}" if visible else f"Show {label}")

    def _toggle_auto_scale(self, enabled):
        self._auto_scale = enabled
        self.btn_auto.setText("Auto Scale" if enabled else "Manual Scale")
        self.plot.enableAutoRange(axis=pg.ViewBox.YAxis, enable=enabled)

    def reset_zoom(self):
        self._auto_scale = True
        self.btn_auto.setChecked(True)
        self.btn_auto.setText("Auto Scale")
        self.plot.enableAutoRange(axis=pg.ViewBox.XAxis, enable=True)
        self.plot.enableAutoRange(axis=pg.ViewBox.YAxis, enable=True)

    def pause_graph(self):
        self._paused = True

    def resume_graph(self):
        self._paused = False
        self._dirty = True

    def clear(self):
        for values in self._buffers.values():
            values.clear()
        self._time.clear()
        self._start_time = None
        self._last_values = {key: None for key, *_ in self.AXES}
        self._region_user_controlled = False
        self.region.setRegion((0, 2))
        for curve in self.curves.values():
            curve.clear()
        self._dirty = False
        self.cursor_label.setText("Cursor: --")
        self._update_live_statistics()
        self._update_region_statistics()

    def _mark_region_user_controlled(self):
        self._region_user_controlled = True

    def export_graph(self, file_type):
        suffix = "png" if file_type == "png" else "svg"
        default_name = os.path.join(os.path.expanduser("~"), f"knee_joint_angle.{suffix}")
        caption = "Export Graph as PNG" if suffix == "png" else "Export Graph as SVG"
        filters = "PNG Image (*.png)" if suffix == "png" else "SVG Vector (*.svg)"
        filename, _selected = QFileDialog.getSaveFileName(self, caption, default_name, filters)
        if not filename:
            return
        if not filename.lower().endswith(f".{suffix}"):
            filename = f"{filename}.{suffix}"

        exporter_cls = pg.exporters.ImageExporter if suffix == "png" else pg.exporters.SVGExporter
        exporter = exporter_cls(self.plot.plotItem)
        if suffix == "png":
            exporter.parameters()["width"] = 1600
        exporter.export(filename)

    def _update_live_statistics(self):
        for key, label, _desc, _color in self.AXES:
            values = np.asarray(self._buffers[key], dtype=float)
            if values.size == 0:
                stats = {metric: "--" for metric in ("current", "max", "min", "avg", "std", "rom")}
            else:
                stats = {
                    "current": f"{values[-1]:.2f}",
                    "max": f"{np.max(values):.2f}",
                    "min": f"{np.min(values):.2f}",
                    "avg": f"{np.mean(values):.2f}",
                    "std": f"{np.std(values):.2f}",
                    "rom": f"{(np.max(values) - np.min(values)):.2f}",
                }
            for metric, text in stats.items():
                self.stat_labels[key][metric].setText(text)

    def _update_region_statistics(self):
        if not self._time:
            self.region_summary.setText("No interval data available.")
            for metric_values in self.region_labels.values():
                for label in metric_values.values():
                    label.setText("--")
            return

        low, high = self.region.getRegion()
        x = np.asarray(self._time, dtype=float)
        mask = (x >= low) & (x <= high)
        duration = max(0.0, high - low)
        self.region_summary.setText(f"Duration: {duration:.2f} s")

        for key, *_ in self.AXES:
            values = np.asarray(self._buffers[key], dtype=float)[mask]
            if values.size == 0:
                computed = {metric: "--" for metric in self.region_labels}
            else:
                max_value = float(np.max(values))
                min_value = float(np.min(values))
                mean_value = float(np.mean(values))
                peak_value = float(values[np.argmax(np.abs(values))])
                rms_value = math.sqrt(float(np.mean(np.square(values))))
                computed = {
                    "Max": f"{max_value:.2f}",
                    "Min": f"{min_value:.2f}",
                    "Average": f"{mean_value:.2f}",
                    "Peak": f"{peak_value:.2f}",
                    "Peak-to-Peak": f"{(max_value - min_value):.2f}",
                    "Mean": f"{mean_value:.2f}",
                    "RMS": f"{rms_value:.2f}",
                }
            for metric, value in computed.items():
                self.region_labels[metric][key].setText(value)

    def _on_mouse_moved(self, event):
        pos = event[0]
        if not self.plot.sceneBoundingRect().contains(pos) or not self._time:
            return

        point = self.plot.getViewBox().mapSceneToView(pos)
        x_value = point.x()
        y_value = point.y()
        self.crosshair_x.setPos(x_value)
        self.crosshair_y.setPos(y_value)

        x = np.asarray(self._time, dtype=float)
        index = int(np.argmin(np.abs(x - x_value)))
        tooltip_parts = [f"t={x[index]:.2f}s"]
        for key, label, _desc, _color in self.AXES:
            values = self._buffers[key]
            if len(values) > index:
                tooltip_parts.append(f"{label}={values[index]:.2f} deg")
        text = " | ".join(tooltip_parts)
        self.cursor_label.setText(f"Cursor: {text}")
        QToolTip.showText(self.plot.mapToGlobal(pos.toPoint()), text, self.plot)
