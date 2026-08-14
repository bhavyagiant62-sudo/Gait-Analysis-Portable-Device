from __future__ import annotations

from datetime import datetime
from typing import List, Tuple

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QTabWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGroupBox,
    QGridLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QTextEdit,
    QFrame,
    QPushButton,
    QFileDialog,
    QMessageBox,
)

from config import COLOR_BG, COLOR_PANEL, COLOR_TEXT, COLOR_ACCENT, COLOR_OK, COLOR_WARN, COLOR_ERROR
from kinematics import KinematicsAnalyzer
from gait_parameters import GaitParameterCalculator
from spatiotemporal import SpatiotemporalAnalyzer
from clinical_summary import ClinicalSummaryGenerator
from intelligent_gait_interpretation import ReferenceDatabase, MetricAnalyzer

Sample = Tuple[float, float, float, float]  # (time_ms, pitch, roll, yaw)


class AdvancedGaitWindow(QMainWindow):
    """
    Clinical / research gait analysis workspace. Every tab shows the
    parameter name, the formula used, and the value computed live from
    the wearable's actual pitch/roll/yaw stream - not placeholder text.
    Parameters this single-IMU wearable cannot measure (needing distance,
    pressure, or a second limb sensor) are stated as such rather than
    guessed.
    """

    def __init__(self, parent=None, samples: List[Sample] | None = None):
        super().__init__(parent)
        self.setWindowTitle("Advanced Gait Analysis")
        self.resize(1400, 900)
        self.setStyleSheet(f"background-color: {COLOR_BG}; color: {COLOR_TEXT};")

        self._explicit_samples = samples
        self.kinematics = KinematicsAnalyzer()
        self.gait_params = GaitParameterCalculator()
        self.spatiotemporal = SpatiotemporalAnalyzer()
        self.clinical = ClinicalSummaryGenerator()
        self.reference_db = ReferenceDatabase.from_defaults()
        self.reference_analyzer = MetricAnalyzer(self.reference_db)

        self._build_ui()
        self.recalculate()

    # ------------------------------------------------------------ helpers --
    def _current_samples(self) -> List[Sample]:
        """Prefers live data pulled from the parent MainWindow, falls back
        to whatever was passed in explicitly at construction time."""
        parent = self.parent()
        if parent is not None and hasattr(parent, "_sample_buffer") and parent._sample_buffer:
            return list(parent._sample_buffer)
        return self._explicit_samples or []

    # ---------------------------------------------------------------- UI ---
    def _build_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("Clinical Gait Analysis Workspace")
        title.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 20px; font-weight: 700;")
        header.addWidget(title)
        header.addStretch()
        self.sample_count_label = QLabel("0 samples")
        self.sample_count_label.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 12px;")
        header.addWidget(self.sample_count_label)
        refresh_btn = QPushButton("Recalculate")
        refresh_btn.setStyleSheet(f"background-color: {COLOR_ACCENT}; color: white; border-radius: 6px; padding: 6px 14px; font-weight: 600;")
        refresh_btn.clicked.connect(self.recalculate)
        header.addWidget(refresh_btn)
        layout.addLayout(header)

        self.tabs = QTabWidget()
        self.kinematics_tab = self._make_metrics_tab()
        self.spatiotemporal_tab = self._make_metrics_tab()
        self.clinical_tab = self._make_clinical_tab()
        self.unavailable_tab = self._build_unavailable_tab()
        self.conclusion_tab = self._make_conclusion_tab()

        self.tabs.addTab(self.kinematics_tab["widget"], "Kinematics")
        self.tabs.addTab(self.spatiotemporal_tab["widget"], "Spatiotemporal")
        self.tabs.addTab(self.clinical_tab["widget"], "Clinical Analysis")
        self.tabs.addTab(self.unavailable_tab, "Not Available on This Hardware")
        self.tabs.addTab(self.conclusion_tab["widget"], "Conclusion")
        self.tabs.addTab(self._build_export_tab(), "Export")
        layout.addWidget(self.tabs)

    def _make_metrics_tab(self) -> dict:
        """A tab holding a 3-column table: Parameter | Formula | Value."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        table = QTableWidget(0, 3)
        table.setHorizontalHeaderLabels(["Parameter", "Formula", "Computed Value"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionMode(QTableWidget.NoSelection)
        table.setStyleSheet(
            f"QTableWidget {{ background-color: {COLOR_PANEL}; color: {COLOR_TEXT}; gridline-color: #2A3642; font-size: 12px; }}"
            f"QHeaderView::section {{ background-color: #22303C; color: {COLOR_ACCENT}; padding: 4px; border: none; font-weight: 600; }}"
        )
        layout.addWidget(table)
        return {"widget": panel, "table": table}

    def _make_clinical_tab(self) -> dict:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        summary = QTextEdit()
        summary.setReadOnly(True)
        summary.setStyleSheet(f"background-color: {COLOR_PANEL}; color: {COLOR_TEXT};")
        layout.addWidget(summary, 1)
        table = QTableWidget(0, 3)
        table.setHorizontalHeaderLabels(["Parameter", "Formula / Basis", "Computed Value"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionMode(QTableWidget.NoSelection)
        table.setStyleSheet(
            f"QTableWidget {{ background-color: {COLOR_PANEL}; color: {COLOR_TEXT}; gridline-color: #2A3642; font-size: 12px; }}"
            f"QHeaderView::section {{ background-color: #22303C; color: {COLOR_ACCENT}; padding: 4px; border: none; font-weight: 600; }}"
        )
        layout.addWidget(table, 1)
        return {"widget": panel, "summary": summary, "table": table}

    def _build_unavailable_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        note = QLabel(
            "These parameters appear in gait-analysis literature but require sensing "
            "hardware this wearable does not have (distance/position reference, foot "
            "pressure, or a second synchronized limb sensor). They are listed here for "
            "completeness, not calculated from guesses."
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 12px;")
        layout.addWidget(note)
        for title, reason in [
            ("Walking Velocity", "Needs a distance/position reference (e.g. stereo camera, UWB, GPS)."),
            ("Step Length / Stride Length", "Needs a distance reference or calibrated stride integration."),
            ("Step Width", "Needs a lateral position reference between the two feet."),
            ("Foot Progression Angle", "Needs a foot-mounted IMU or camera tracking foot orientation."),
            ("Single/Double Support Time", "Needs foot-contact (pressure/force) sensing."),
            ("Stance Time / Swing Time", "Needs foot-contact (pressure/force) sensing."),
            ("True Left/Right Symmetry Index", "Needs a second, time-synchronized IMU on the other leg."),
            ("Pelvic Tilt / Rotation / Obliquity", "Sensor not connected - would need a pelvis-mounted IMU."),
            ("Hip Flexion", "Sensor not connected - would need a thigh-relative-to-pelvis IMU pair."),
            ("Ankle Motion", "Sensor not connected - would need a foot/shank IMU pair."),
        ]:
            layout.addWidget(self._make_summary_card(title, reason))
        layout.addStretch()
        return panel

    def _make_conclusion_tab(self) -> dict:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        scores_group = QGroupBox("Overall Scores")
        scores_layout = QGridLayout(scores_group)
        score_labels = {}
        names = [
            "Overall Gait Quality", "Movement Symmetry", "Movement Stability",
            "Range of Motion", "Walking Consistency", "Smoothness", "Confidence",
        ]
        for i, name in enumerate(names):
            lbl = QLabel(f"{name}: --")
            lbl.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 13px;")
            score_labels[name] = lbl
            scores_layout.addWidget(lbl, i // 2, i % 2)
        layout.addWidget(scores_group)

        conclusion_text = QTextEdit()
        conclusion_text.setReadOnly(True)
        conclusion_text.setStyleSheet(f"background-color: {COLOR_PANEL}; color: {COLOR_TEXT}; font-size: 13px;")
        layout.addWidget(conclusion_text, 1)

        master_table = QTableWidget(0, 3)
        master_table.setHorizontalHeaderLabels(["Parameter", "Formula", "Computed Value"])
        master_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        master_table.verticalHeader().setVisible(False)
        master_table.setEditTriggers(QTableWidget.NoEditTriggers)
        master_table.setSelectionMode(QTableWidget.NoSelection)
        master_table.setStyleSheet(
            f"QTableWidget {{ background-color: {COLOR_PANEL}; color: {COLOR_TEXT}; gridline-color: #2A3642; font-size: 11px; }}"
            f"QHeaderView::section {{ background-color: #22303C; color: {COLOR_ACCENT}; padding: 4px; border: none; font-weight: 600; }}"
        )
        layout.addWidget(master_table, 2)

        return {
            "widget": panel,
            "score_labels": score_labels,
            "conclusion_text": conclusion_text,
            "master_table": master_table,
        }

    def _build_export_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.addWidget(self._make_summary_card("CSV Export", "Use the main dashboard's Save/Export CSV buttons for raw packet data."))
        export_btn = QPushButton("Export Full Calculation Report (.txt)")
        export_btn.setStyleSheet(f"background-color: {COLOR_ACCENT}; color: white; border-radius: 6px; padding: 8px;")
        export_btn.clicked.connect(self.export_report)
        layout.addWidget(export_btn)
        layout.addStretch()
        return panel

    def _make_summary_card(self, title: str, detail: str) -> QWidget:
        frame = QFrame()
        frame.setStyleSheet(f"background-color: {COLOR_PANEL}; border-radius: 8px;")
        layout = QVBoxLayout(frame)
        title_label = QLabel(title)
        title_label.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 14px; font-weight: 700;")
        detail_label = QLabel(detail)
        detail_label.setWordWrap(True)
        detail_label.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 12px;")
        layout.addWidget(title_label)
        layout.addWidget(detail_label)
        return frame

    # ------------------------------------------------------ calculation ----
    def recalculate(self):
        samples = self._current_samples()
        self.sample_count_label.setText(f"{len(samples)} samples")

        if len(samples) < 3:
            self._show_insufficient_data()
            return

        angles = [s[1] for s in samples]
        time_angle_pairs = [(s[0], s[1]) for s in samples]

        kin = self.kinematics.update(time_angle_pairs)
        gait = self.gait_params.update(time_angle_pairs)
        spatio = self.spatiotemporal.update(gait)
        clinical = self.clinical.update(
            rom=kin["rom"],
            cadence=gait["cadence"],
            joint_stability=kin["joint_stability"],
            movement_smoothness=kin["movement_smoothness"],
            cycle_time_variability=gait["cycle_time_variability"],
        )

        self._populate_kinematics(kin)
        self._populate_spatiotemporal(gait, spatio)
        self._populate_clinical(clinical, kin, gait)
        self._populate_conclusion(samples, kin, gait, clinical)

    def _show_insufficient_data(self):
        for tab in (self.kinematics_tab, self.spatiotemporal_tab):
            tab["table"].setRowCount(1)
            tab["table"].setItem(0, 0, QTableWidgetItem("--"))
            tab["table"].setItem(0, 1, QTableWidgetItem("--"))
            tab["table"].setItem(0, 2, QTableWidgetItem("Waiting for at least 3 samples of live data"))
        self.clinical_tab["summary"].setPlainText("Waiting for gait data. Start walking with the sensor connected, then press Recalculate.")
        self.conclusion_tab["conclusion_text"].setPlainText("Not enough data yet to generate a conclusion.")

    def _fill_rows(self, table: QTableWidget, rows: List[Tuple[str, str, str]]):
        table.setRowCount(len(rows))
        for r, (name, formula, value) in enumerate(rows):
            table.setItem(r, 0, QTableWidgetItem(name))
            table.setItem(r, 1, QTableWidgetItem(formula))
            table.setItem(r, 2, QTableWidgetItem(value))

    def _populate_kinematics(self, kin: dict):
        rows = [
            ("Max Knee Flexion", "max(theta)", f"{kin['max_flexion']:.2f} deg"),
            ("Max Knee Extension", "min(theta)", f"{kin['max_extension']:.2f} deg"),
            ("Range of Motion (ROM)", "max(theta) - min(theta)", f"{kin['rom']:.2f} deg"),
            ("Average Knee Angle", "mean(theta)", f"{kin['average_knee_angle']:.2f} deg"),
            ("Angular Velocity (mean |w|)", "|d(theta)/dt|, averaged", f"{kin['angular_velocity']:.2f} deg/s"),
            ("Peak Angular Velocity", "max |d(theta)/dt|", f"{kin['peak_angular_velocity']:.2f} deg/s"),
            ("Angular Acceleration (mean |a|)", "|d(omega)/dt|, averaged", f"{kin['angular_acceleration']:.2f} deg/s^2"),
            ("Peak Angular Acceleration", "max |d(omega)/dt|", f"{kin['peak_angular_acceleration']:.2f} deg/s^2"),
            ("Jerk (mean |d(a)/dt|)", "d(alpha)/dt, averaged", f"{kin['jerk']:.2f} deg/s^3"),
            ("Signal RMS", "sqrt(mean(theta^2))", f"{kin['signal_rms']:.2f} deg"),
            ("Coefficient of Variation", "stdev(theta) / |mean(theta)|", f"{kin['coefficient_of_variation']:.3f}"),
            ("Joint Stability Index", "1 - motion_variability", f"{kin['joint_stability']:.3f}"),
            ("Movement Smoothness Index", "1 - min(mean|jerk| / 2000, 1)", f"{kin['movement_smoothness']:.3f}"),
        ]
        self._fill_rows(self.kinematics_tab["table"], rows)

    def _populate_spatiotemporal(self, gait: dict, spatio: dict):
        rows = [
            ("Step Count (this sensor)", "count of detected flexion peaks", f"{gait['step_count']}"),
            ("Cadence (single-limb)", "detected_peaks / elapsed_minutes", f"{gait['cadence']:.1f} steps/min"),
            ("Walking Frequency", "cadence / 60", f"{gait['walking_frequency']:.3f} Hz"),
            ("Stride Frequency", "walking_frequency / 2", f"{spatio['stride_frequency']:.3f} Hz"),
            ("Step Time", "60 / cadence", f"{spatio['step_time']:.3f} s"),
            ("Gait Cycle Time (Stride Time)", "mean(time between consecutive flexion peaks)", f"{gait['gait_cycle_duration']:.3f} s"),
            ("Cycle Time Variability (CV)", "stdev(cycle times) / mean(cycle times)", f"{gait['cycle_time_variability']:.3f}"),
            ("Observation Window", "last_sample_time - first_sample_time", f"{gait['observation_duration_s']:.1f} s"),
            ("Walking Velocity", "-", str(spatio["walking_velocity"])),
            ("Step Length / Stride Length", "-", str(spatio["step_length"])),
            ("Step Width", "-", str(spatio["step_width"])),
            ("Single / Double Support Time", "-", str(spatio["single_support_time"])),
            ("True Walking Symmetry Index (L/R)", "-", str(spatio["walking_symmetry_index"])),
        ]
        self._fill_rows(self.spatiotemporal_tab["table"], rows)

    def _populate_clinical(self, clinical: dict, kin: dict, gait: dict):
        text = (
            f"{clinical['clinical_summary']}\n\n"
            f"- Walking Pattern: {clinical['walking_pattern']} (cadence = {gait['cadence']:.1f} steps/min)\n"
            f"- Joint Excursion: {clinical['joint_stiffness']} (ROM = {kin['rom']:.1f} deg)\n"
            f"- Joint Stability: {clinical['stability_note']} (stability index = {kin['joint_stability']:.2f})\n"
            f"- Movement Smoothness: {clinical['smoothness_note']} (smoothness index = {kin['movement_smoothness']:.2f})\n"
            f"- Step Rhythm: {clinical['rhythm_note']} (cycle time CV = {gait['cycle_time_variability']:.2f})\n"
            f"- Asymmetry: {clinical['asymmetry']}\n\n"
            f"{clinical['possible_gait_abnormality']}\n\n"
            "This is a descriptive summary of the measured signal, not a medical diagnosis. "
            "Clinical evaluation by a qualified healthcare professional is required for diagnosis "
            "and treatment decisions."
        )
        self.clinical_tab["summary"].setPlainText(text)

        rows = [
            ("Walking Pattern", "cadence thresholds: <80 slow, 80-120 normal, >120 fast", clinical["walking_pattern"]),
            ("Joint Excursion", "ROM thresholds: <20 reduced, 20-70 moderate, >70 increased", clinical["joint_stiffness"]),
            ("Joint Stability", "joint_stability >=0.8 stable, >=0.6 mild, <0.6 notable", clinical["stability_note"]),
            ("Movement Smoothness", "smoothness >=0.8 smooth, >=0.6 some jerk, <0.6 high jerk", clinical["smoothness_note"]),
            ("Step Rhythm", "cycle time CV <=0.1 consistent, <=0.2 mild, >0.2 high variability", clinical["rhythm_note"]),
        ]
        self._fill_rows(self.clinical_tab["table"], rows)

    def _populate_conclusion(self, samples: List[Sample], kin: dict, gait: dict, clinical: dict):
        try:
            result = self.reference_analyzer.analyze(samples)
        except ValueError:
            result = None

        labels = self.conclusion_tab["score_labels"]
        if result:
            labels["Overall Gait Quality"].setText(f"Overall Gait Quality: {result['overall_quality_score']:.1f}/100")
            labels["Movement Symmetry"].setText(f"Movement Symmetry: {result['movement_symmetry_score']:.1f}/100")
            labels["Movement Stability"].setText(f"Movement Stability: {result['movement_stability_score']:.1f}/100")
            labels["Range of Motion"].setText(f"Range of Motion: {result['range_of_motion_score']:.1f}/100")
            labels["Walking Consistency"].setText(f"Walking Consistency: {result['walking_consistency_score']:.1f}/100")
            labels["Smoothness"].setText(f"Smoothness: {result['smoothness_score']:.1f}/100")
            labels["Confidence"].setText(f"Confidence: {result['confidence_score']:.1f}/100")

        lines = [
            f"CONCLUSION - generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f"Based on {len(samples)} samples spanning {gait['observation_duration_s']:.1f} s, "
            f"{gait['step_count']} gait cycles were detected on this limb at a cadence of "
            f"{gait['cadence']:.1f} steps/min (walking frequency {gait['walking_frequency']:.2f} Hz).",
            "",
            f"Knee range of motion measured {kin['rom']:.1f} deg (flexion peak {kin['max_flexion']:.1f} deg, "
            f"extension trough {kin['max_extension']:.1f} deg), with a mean angular velocity of "
            f"{kin['angular_velocity']:.1f} deg/s and peak {kin['peak_angular_velocity']:.1f} deg/s.",
            "",
            f"Movement quality indicators: joint stability index {kin['joint_stability']:.2f}, "
            f"smoothness index {kin['movement_smoothness']:.2f}, cycle-to-cycle timing variability "
            f"{gait['cycle_time_variability']:.2f}.",
            "",
            f"Interpretation: {clinical['walking_pattern']}. {clinical['joint_stiffness']}. "
            f"{clinical['stability_note']}. {clinical['smoothness_note']}. {clinical['rhythm_note']}.",
        ]
        if result:
            lines.append("")
            lines.append("Reference-range comparison:")
            lines.extend(f"- {sentence}" for sentence in result["interpretation"])

        lines.append("")
        lines.append(
            "Note: this device measures a single limb's knee flexion/extension only. "
            "True bilateral symmetry, stance/swing timing, and spatial parameters (step length, "
            "walking velocity, step width) require additional sensors and are not fabricated here."
        )
        lines.append("")
        lines.append(
            "This is a descriptive summary of the measured signal, not a medical diagnosis. "
            "Clinical evaluation by a qualified healthcare professional is required for diagnosis "
            "and treatment decisions."
        )
        self.conclusion_tab["conclusion_text"].setPlainText("\n".join(lines))

        master_rows = [
            ("Max Knee Flexion", "max(theta)", f"{kin['max_flexion']:.2f} deg"),
            ("Max Knee Extension", "min(theta)", f"{kin['max_extension']:.2f} deg"),
            ("Range of Motion", "max(theta) - min(theta)", f"{kin['rom']:.2f} deg"),
            ("Average Knee Angle", "mean(theta)", f"{kin['average_knee_angle']:.2f} deg"),
            ("Angular Velocity (mean)", "|d(theta)/dt|, averaged", f"{kin['angular_velocity']:.2f} deg/s"),
            ("Peak Angular Velocity", "max |d(theta)/dt|", f"{kin['peak_angular_velocity']:.2f} deg/s"),
            ("Angular Acceleration (mean)", "|d(omega)/dt|, averaged", f"{kin['angular_acceleration']:.2f} deg/s^2"),
            ("Jerk (mean)", "d(alpha)/dt, averaged", f"{kin['jerk']:.2f} deg/s^3"),
            ("Signal RMS", "sqrt(mean(theta^2))", f"{kin['signal_rms']:.2f} deg"),
            ("Coefficient of Variation", "stdev(theta)/|mean(theta)|", f"{kin['coefficient_of_variation']:.3f}"),
            ("Joint Stability Index", "1 - motion_variability", f"{kin['joint_stability']:.3f}"),
            ("Movement Smoothness Index", "1 - min(mean|jerk|/2000, 1)", f"{kin['movement_smoothness']:.3f}"),
            ("Step Count", "detected flexion peaks", f"{gait['step_count']}"),
            ("Cadence (single-limb)", "peaks / elapsed_minutes", f"{gait['cadence']:.1f} steps/min"),
            ("Walking Frequency", "cadence / 60", f"{gait['walking_frequency']:.3f} Hz"),
            ("Gait Cycle Time", "mean(inter-peak interval)", f"{gait['gait_cycle_duration']:.3f} s"),
            ("Cycle Time Variability", "stdev/mean of inter-peak intervals", f"{gait['cycle_time_variability']:.3f}"),
        ]
        if result:
            master_rows.append(("Overall Gait Quality Score", "mean(deviation_score) vs reference ranges", f"{result['overall_quality_score']:.1f}/100"))
            master_rows.append(("Confidence Score", "f(sample_count, mean severity)", f"{result['confidence_score']:.1f}/100"))
        self._fill_rows(self.conclusion_tab["master_table"], master_rows)

    # ----------------------------------------------------------- export ----
    def export_report(self):
        samples = self._current_samples()
        if len(samples) < 3:
            QMessageBox.information(self, "Export Report", "Not enough data yet to export a report.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Calculation Report", "gait_calculation_report.txt", "Text Files (*.txt)")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(self.conclusion_tab["conclusion_text"].toPlainText())
        QMessageBox.information(self, "Export Report", f"Report saved to:\n{path}")
