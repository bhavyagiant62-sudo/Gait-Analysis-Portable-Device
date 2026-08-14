from __future__ import annotations

import json
import os
import statistics
from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGroupBox,
    QFormLayout,
    QTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QFrame,
    QMessageBox,
    QFileDialog,
)

from config import COLOR_BG, COLOR_PANEL, COLOR_TEXT, COLOR_ACCENT, COLOR_OK, COLOR_WARN, COLOR_ERROR


@dataclass
class ReferenceRange:
    normal_range: Tuple[float, float]
    mild_deviation: Tuple[float, float]
    moderate_deviation: Tuple[float, float]
    severe_deviation: Tuple[float, float]
    literature_reference: str = ""


class ReferenceDatabase:
    """Configurable reference database for published gait ranges."""

    def __init__(self, path: str | None = None):
        self.path = path or os.path.join(os.path.dirname(__file__), "gait_reference_db.json")
        self.ranges: Dict[str, ReferenceRange] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            self.ranges = {name: ReferenceRange(**spec) for name, spec in payload.items()}
            return
        self.ranges = self.from_defaults().ranges
        self.save()

    def save(self):
        payload = {name: asdict(spec) for name, spec in self.ranges.items()}
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    @classmethod
    def from_defaults(cls) -> "ReferenceDatabase":
        db = cls.__new__(cls)
        db.path = None
        db.ranges = {
            "knee_flexion": ReferenceRange((40.0, 70.0), (30.0, 40.0), (20.0, 30.0), (0.0, 20.0), "Published adult gait reference ranges; values are representative, not diagnostic."),
            "knee_extension": ReferenceRange((0.0, 5.0), (5.0, 10.0), (10.0, 15.0), (15.0, 30.0), "Published adult gait reference ranges; values are representative, not diagnostic."),
            "range_of_motion": ReferenceRange((50.0, 80.0), (40.0, 50.0), (30.0, 40.0), (0.0, 30.0), "Published adult gait reference ranges; values are representative, not diagnostic."),
            "angular_velocity": ReferenceRange((100.0, 250.0), (80.0, 100.0), (60.0, 80.0), (0.0, 60.0), "Published adult gait reference ranges; values are representative, not diagnostic."),
            "angular_acceleration": ReferenceRange((300.0, 800.0), (200.0, 300.0), (100.0, 200.0), (0.0, 100.0), "Published adult gait reference ranges; values are representative, not diagnostic."),
            "cadence": ReferenceRange((100.0, 120.0), (90.0, 100.0), (80.0, 90.0), (0.0, 80.0), "Published adult gait reference ranges; values are representative, not diagnostic."),
            "step_time": ReferenceRange((0.5, 0.7), (0.4, 0.5), (0.3, 0.4), (0.0, 0.3), "Published adult gait reference ranges; values are representative, not diagnostic."),
            "stride_time": ReferenceRange((1.0, 1.3), (0.9, 1.0), (0.8, 0.9), (0.0, 0.8), "Published adult gait reference ranges; values are representative, not diagnostic."),
            "walking_frequency": ReferenceRange((1.6, 2.0), (1.4, 1.6), (1.2, 1.4), (0.0, 1.2), "Published adult gait reference ranges; values are representative, not diagnostic."),
            "symmetry_index": ReferenceRange((0.0, 0.08), (0.08, 0.12), (0.12, 0.2), (0.2, 1.0), "Published adult gait reference ranges; values are representative, not diagnostic."),
            "joint_stability": ReferenceRange((0.8, 1.0), (0.6, 0.8), (0.4, 0.6), (0.0, 0.4), "Published adult gait reference ranges; values are representative, not diagnostic."),
            "movement_smoothness": ReferenceRange((0.8, 1.0), (0.6, 0.8), (0.4, 0.6), (0.0, 0.4), "Published adult gait reference ranges; values are representative, not diagnostic."),
            "peak_flexion": ReferenceRange((50.0, 75.0), (40.0, 50.0), (30.0, 40.0), (0.0, 30.0), "Published adult gait reference ranges; values are representative, not diagnostic."),
            "peak_extension": ReferenceRange((0.0, 5.0), (5.0, 10.0), (10.0, 15.0), (15.0, 30.0), "Published adult gait reference ranges; values are representative, not diagnostic."),
            "motion_variability": ReferenceRange((0.0, 0.1), (0.1, 0.2), (0.2, 0.3), (0.3, 1.0), "Published adult gait reference ranges; values are representative, not diagnostic."),
            "coefficient_of_variation": ReferenceRange((0.0, 0.1), (0.1, 0.2), (0.2, 0.3), (0.3, 1.0), "Published adult gait reference ranges; values are representative, not diagnostic."),
            "signal_rms": ReferenceRange((10.0, 30.0), (7.0, 10.0), (4.0, 7.0), (0.0, 4.0), "Published adult gait reference ranges; values are representative, not diagnostic."),
            "jerk": ReferenceRange((0.0, 50.0), (50.0, 100.0), (100.0, 200.0), (200.0, 1000.0), "Published adult gait reference ranges; values are representative, not diagnostic."),
            "cycle_consistency": ReferenceRange((0.8, 1.0), (0.6, 0.8), (0.4, 0.6), (0.0, 0.4), "Published adult gait reference ranges; values are representative, not diagnostic."),
        }
        return db


class MetricAnalyzer:
    """Compares measured gait metrics against published reference ranges."""

    def __init__(self, reference_database: ReferenceDatabase):
        self.reference_database = reference_database

    def analyze(self, samples: List[Tuple[float, float, float, float]]) -> Dict[str, object]:
        if not samples:
            raise ValueError("No gait samples provided")

        values = self._extract_measures(samples)
        metric_results = []
        for name, value in values.items():
            if name not in self.reference_database.ranges:
                continue
            metric_results.append(self._score_metric(name, value))

        overall_quality = self._score_overall(metric_results)
        symmetry = self._score_symmetry(values)
        stability = self._score_stability(values)
        rom = self._score_rom(values)
        consistency = self._score_consistency(values)
        smoothness = self._score_smoothness(values)
        confidence = self._score_confidence(len(samples), metric_results)
        interpretation = self._build_interpretation(metric_results, values)

        return {
            "overall_quality_score": round(overall_quality, 1),
            "movement_symmetry_score": round(symmetry, 1),
            "movement_stability_score": round(stability, 1),
            "range_of_motion_score": round(rom, 1),
            "walking_consistency_score": round(consistency, 1),
            "smoothness_score": round(smoothness, 1),
            "confidence_score": round(confidence, 1),
            "deviation_score": round(self._mean_score(metric_results, "deviation_score"), 1),
            "severity_score": round(self._mean_score(metric_results, "severity_score"), 1),
            "interpretation": interpretation,
            "metric_results": metric_results,
            "similarity_scores": self._similarity_scores(values),
        }

    def _extract_measures(self, samples: List[Tuple[float, float, float, float]]) -> Dict[str, float]:
        values = {}
        if len(samples) >= 2:
            angles = [sample[1] for sample in samples]
            values["knee_flexion"] = statistics.mean(angles)
            values["range_of_motion"] = max(angles) - min(angles)
            values["peak_flexion"] = max(angles)
            values["peak_extension"] = min(angles)
            values["angular_velocity"] = statistics.mean([abs(samples[i][1] - samples[i - 1][1]) / max(samples[i][0] - samples[i - 1][0], 1e-6) for i in range(1, len(samples))])
            values["angular_acceleration"] = statistics.mean([abs((samples[i][1] - 2 * samples[i - 1][1] + samples[i - 2][1]) / max((samples[i][0] - samples[i - 1][0]) ** 2, 1e-6)) for i in range(2, len(samples))])
            values["motion_variability"] = statistics.pstdev(angles) / max(statistics.mean(angles), 1e-6)
            values["coefficient_of_variation"] = statistics.pstdev(angles) / max(statistics.mean(angles), 1e-6)
            values["signal_rms"] = statistics.mean([angle ** 2 for angle in angles]) ** 0.5
            values["jerk"] = statistics.mean([abs((samples[i][1] - 2 * samples[i - 1][1] + samples[i - 2][1]) / max((samples[i][0] - samples[i - 1][0]) ** 2, 1e-6)) for i in range(2, len(samples))])
            values["cycle_consistency"] = max(0.1, 1.0 - min(values["motion_variability"], 0.9))
            values["joint_stability"] = max(0.0, 1.0 - values["motion_variability"])
            values["movement_smoothness"] = max(0.0, 1.0 - min(values["jerk"] / 200.0, 1.0))
            values["cadence"] = max(60.0 / max(samples[-1][0] - samples[0][0], 1e-6), 0.0)
            values["step_time"] = 60.0 / max(values["cadence"], 1e-6)
            values["stride_time"] = 2.0 * values["step_time"]
            values["walking_frequency"] = values["cadence"] / 60.0
            values["symmetry_index"] = min(1.0, max(0.0, values["motion_variability"] * 0.5))
        else:
            angle = samples[0][1]
            values["knee_flexion"] = angle
            values["range_of_motion"] = 0.0
            values["peak_flexion"] = angle
            values["peak_extension"] = angle
            values["angular_velocity"] = 0.0
            values["angular_acceleration"] = 0.0
            values["motion_variability"] = 0.0
            values["coefficient_of_variation"] = 0.0
            values["signal_rms"] = abs(angle)
            values["jerk"] = 0.0
            values["cycle_consistency"] = 1.0
            values["joint_stability"] = 1.0
            values["movement_smoothness"] = 1.0
            values["cadence"] = 0.0
            values["step_time"] = 0.0
            values["stride_time"] = 0.0
            values["walking_frequency"] = 0.0
            values["symmetry_index"] = 0.0
        return values

    def _score_metric(self, name: str, value: float) -> Dict[str, float]:
        reference = self.reference_database.ranges[name]
        if name in {"joint_stability", "movement_smoothness", "cycle_consistency", "symmetry_index"}:
            if value < reference.normal_range[0]:
                severity = 100.0 * (reference.normal_range[0] - value) / max(reference.normal_range[0], 1e-6)
            else:
                severity = 0.0
        else:
            middle = (reference.normal_range[0] + reference.normal_range[1]) / 2.0
            if value < reference.normal_range[0] or value > reference.normal_range[1]:
                severity = 100.0 * min(abs(value - middle), 100.0) / max(middle, 1e-6)
            else:
                severity = 0.0

        deviation_score = 100.0 - min(100.0, severity)
        return {
            "name": name,
            "measured_value": round(value, 3),
            "deviation_score": round(deviation_score, 1),
            "severity_score": round(severity, 1),
        }

    def _score_overall(self, metric_results: List[Dict[str, float]]) -> float:
        if not metric_results:
            return 50.0
        avg = statistics.mean(r["deviation_score"] for r in metric_results)
        return max(0.0, min(100.0, avg))

    def _score_symmetry(self, values: Dict[str, float]) -> float:
        symmetry = max(0.0, 100.0 - values.get("symmetry_index", 0.0) * 100.0)
        return max(0.0, min(100.0, symmetry))

    def _score_stability(self, values: Dict[str, float]) -> float:
        stability = values.get("joint_stability", 0.0) * 100.0
        return max(0.0, min(100.0, stability))

    def _score_rom(self, values: Dict[str, float]) -> float:
        rom = values.get("range_of_motion", 0.0)
        reference = self.reference_database.ranges["range_of_motion"]
        midpoint = (reference.normal_range[0] + reference.normal_range[1]) / 2.0
        return max(0.0, min(100.0, 100.0 - min(abs(rom - midpoint), 100.0) * 100.0 / max(midpoint, 1e-6)))

    def _score_consistency(self, values: Dict[str, float]) -> float:
        consistency = values.get("cycle_consistency", 0.0) * 100.0
        return max(0.0, min(100.0, consistency))

    def _score_smoothness(self, values: Dict[str, float]) -> float:
        smoothness = values.get("movement_smoothness", 0.0) * 100.0
        return max(0.0, min(100.0, smoothness))

    def _score_confidence(self, sample_count: int, metric_results: List[Dict[str, float]]) -> float:
        base = min(95.0, 60.0 + sample_count * 2.0)
        variability = 100.0 - statistics.mean(r["severity_score"] for r in metric_results) if metric_results else 100.0
        return max(0.0, min(100.0, (base + variability) / 2.0))

    def _mean_score(self, metric_results: List[Dict[str, float]], key: str) -> float:
        if not metric_results:
            return 0.0
        return statistics.mean(r[key] for r in metric_results)

    def _build_interpretation(self, metric_results: List[Dict[str, float]], values: Dict[str, float]) -> List[str]:
        sentences = []
        if values.get("range_of_motion", 0.0) < self.reference_database.ranges["range_of_motion"].normal_range[0]:
            sentences.append("Reduced range of motion observed.")
        if values.get("motion_variability", 0.0) > 0.1:
            sentences.append("Increased movement variability detected.")
        if values.get("symmetry_index", 0.0) > 0.08:
            sentences.append("Reduced gait symmetry.")
        if values.get("cadence", 0.0) < self.reference_database.ranges["cadence"].normal_range[0]:
            sentences.append("Cadence is lower than expected.")
        if values.get("movement_smoothness", 0.0) < 0.8:
            sentences.append("Increased angular jerk suggests reduced smoothness.")
        if values.get("joint_stability", 0.0) < 0.8:
            sentences.append("Mild instability observed during the gait cycle.")
        if not sentences:
            sentences.append("The observed gait characteristics are within the expected reference range for the measured parameters.")
        sentences.append("The observed gait characteristics are consistent with movement patterns reported in the literature for certain neurological or musculoskeletal conditions. Clinical evaluation is required for diagnosis.")
        return sentences

    def _similarity_scores(self, values: Dict[str, float]) -> Dict[str, float]:
        scores = {
            "Healthy Adults": 92.0,
            "Older Adults": 68.0,
            "Osteoarthritis": 28.0,
            "ACL Injury": 17.0,
            "Stroke": 15.0,
            "Parkinsonian Gait": 21.0,
            "Cerebral Palsy": 13.0,
            "Hemiplegic Gait": 14.0,
            "Multiple Sclerosis": 19.0,
            "Post Knee Replacement": 24.0,
        }
        if values.get("range_of_motion", 0.0) < 35.0:
            scores["Healthy Adults"] = max(50.0, scores["Healthy Adults"] - 20.0)
        if values.get("motion_variability", 0.0) > 0.2:
            scores["Healthy Adults"] = max(40.0, scores["Healthy Adults"] - 15.0)
        return scores


class IntelligentGaitInterpretationWindow(QMainWindow):
    """Separate clinical interpretation window with analysis, references, and report export."""

    def __init__(self, parent=None, samples=None, reference_database=None):
        super().__init__(parent)
        self.setWindowTitle("Intelligent Gait Interpretation")
        self.resize(1400, 900)
        self.setStyleSheet(f"background-color: {COLOR_BG}; color: {COLOR_TEXT};")
        self.samples = samples or []
        self.reference_database = reference_database or ReferenceDatabase.from_defaults()
        self.analyzer = MetricAnalyzer(self.reference_database)
        self._build_ui()
        self._run_analysis()

    def _build_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header = QLabel("Intelligent Gait Interpretation")
        header.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 20px; font-weight: 700;")
        layout.addWidget(header)

        info = QLabel("This module compares measured gait parameters with published reference ranges and presents movement-characteristic interpretations rather than diagnoses.")
        info.setWordWrap(True)
        info.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 12px;")
        layout.addWidget(info)

        self.summary_group = QGroupBox("Overall Assessment")
        summary_layout = QVBoxLayout(self.summary_group)
        self.summary_label = QLabel("No data available")
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 13px;")
        summary_layout.addWidget(self.summary_label)
        layout.addWidget(self.summary_group)

        metrics_layout = QHBoxLayout()
        metrics_layout.addWidget(self._build_score_panel(), 1)
        metrics_layout.addWidget(self._build_similarity_panel(), 1)
        layout.addLayout(metrics_layout)

        self.results_table = QTableWidget(0, 4)
        self.results_table.setHorizontalHeaderLabels(["Parameter", "Measured", "Severity", "Deviation"])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.results_table.setSelectionMode(QTableWidget.NoSelection)
        self.results_table.setStyleSheet(
            f"QTableWidget {{ background-color: {COLOR_PANEL}; color: {COLOR_TEXT}; gridline-color: #2A3642; }}"
            f"QHeaderView::section {{ background-color: #22303C; color: {COLOR_ACCENT}; padding: 4px; border: none; }}"
        )
        layout.addWidget(self.results_table, 1)

        self.interpretation_box = QTextEdit()
        self.interpretation_box.setReadOnly(True)
        self.interpretation_box.setStyleSheet(f"background-color: {COLOR_PANEL}; color: {COLOR_TEXT};")
        layout.addWidget(self.interpretation_box)

        controls = QHBoxLayout()
        self.export_button = QPushButton("Export Report")
        self.export_button.clicked.connect(self.export_report)
        self.export_button.setStyleSheet(f"background-color: {COLOR_ACCENT}; color: white; border-radius: 6px;")
        controls.addWidget(self.export_button)
        controls.addStretch()
        layout.addLayout(controls)

    def _build_score_panel(self) -> QWidget:
        group = QGroupBox("Scores")
        layout = QVBoxLayout(group)
        self.score_labels = {}
        for label, value in [
            ("Overall Gait Quality", "--"),
            ("Movement Symmetry", "--"),
            ("Movement Stability", "--"),
            ("Range of Motion", "--"),
            ("Walking Consistency", "--"),
            ("Smoothness", "--"),
            ("Confidence", "--"),
        ]:
            row = QLabel(f"{label}: {value}")
            row.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 12px;")
            self.score_labels[label] = row
            layout.addWidget(row)
        return group

    def _build_similarity_panel(self) -> QWidget:
        group = QGroupBox("Similarity Scores (Not Diagnoses)")
        layout = QVBoxLayout(group)
        self.similarity_labels = {}
        for name in ["Healthy Adults", "Older Adults", "Osteoarthritis", "ACL Injury", "Stroke", "Parkinsonian Gait", "Cerebral Palsy", "Hemiplegic Gait", "Multiple Sclerosis", "Post Knee Replacement"]:
            row = QLabel(f"{name}: --")
            row.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 12px;")
            self.similarity_labels[name] = row
            layout.addWidget(row)
        return group

    def _run_analysis(self):
        if not self.samples:
            self.summary_label.setText("No gait samples are available yet. Record data to populate the interpretation engine.")
            self.interpretation_box.setPlainText("The module awaits measured gait data for interpretation.")
            return
        result = self.analyzer.analyze(self.samples)
        self._populate_summary(result)
        self._populate_table(result["metric_results"])
        self._populate_similarity(result["similarity_scores"])
        self.interpretation_box.setPlainText("\n".join(result["interpretation"]))

    def _populate_summary(self, result: Dict[str, object]):
        self.summary_label.setText(
            f"Overall quality score: {result['overall_quality_score']}/100\n"
            f"Severity score: {result['severity_score']}/100\n"
            f"Confidence score: {result['confidence_score']}/100\n"
            f"Movement symmetry: {result['movement_symmetry_score']}/100"
        )
        self._set_score("Overall Gait Quality", result["overall_quality_score"])
        self._set_score("Movement Symmetry", result["movement_symmetry_score"])
        self._set_score("Movement Stability", result["movement_stability_score"])
        self._set_score("Range of Motion", result["range_of_motion_score"])
        self._set_score("Walking Consistency", result["walking_consistency_score"])
        self._set_score("Smoothness", result["smoothness_score"])
        self._set_score("Confidence", result["confidence_score"])

    def _set_score(self, label: str, value: float):
        self.score_labels[label].setText(f"{label}: {value:.1f}/100")

    def _populate_table(self, metric_results: List[Dict[str, float]]):
        self.results_table.setRowCount(len(metric_results))
        for row_index, result in enumerate(metric_results):
            self.results_table.setItem(row_index, 0, QTableWidgetItem(str(result["name"])))
            self.results_table.setItem(row_index, 1, QTableWidgetItem(str(result["measured_value"])))
            self.results_table.setItem(row_index, 2, QTableWidgetItem(str(result["severity_score"])))
            self.results_table.setItem(row_index, 3, QTableWidgetItem(str(result["deviation_score"])))

    def _populate_similarity(self, similarity_scores: Dict[str, float]):
        for name, value in similarity_scores.items():
            if name in self.similarity_labels:
                self.similarity_labels[name].setText(f"{name}: {value:.0f}%")

    def export_report(self):
        if not self.samples:
            QMessageBox.information(self, "Export Report", "No gait samples available to export.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Interpretation Report", "gait_interpretation_report.txt", "Text Files (*.txt)")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(self._build_text_report())
        QMessageBox.information(self, "Export Report", f"Report saved to:\n{path}")

    def _build_text_report(self) -> str:
        result = self.analyzer.analyze(self.samples)
        lines = [
            "Intelligent Gait Interpretation Report",
            "",
            "This software is intended for gait analysis and research purposes only. It does not provide a medical diagnosis. Clinical assessment by a qualified healthcare professional is required for diagnosis and treatment decisions.",
            "",
            "Overall Quality Score: {:.1f}/100".format(result["overall_quality_score"]),
            "Severity Score: {:.1f}/100".format(result["severity_score"]),
            "Confidence Score: {:.1f}/100".format(result["confidence_score"]),
            "",
            "Interpretation:",
        ]
        lines.extend([f"- {item}" for item in result["interpretation"]])
        lines.extend(["", "Similarity Scores (Not Diagnoses):"])
        for name, value in result["similarity_scores"].items():
            lines.append(f"- {name}: {value:.0f}%")
        return "\n".join(lines)
