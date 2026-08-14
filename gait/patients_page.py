from __future__ import annotations

from datetime import datetime

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QLabel, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
    QTextEdit, QPushButton, QVBoxLayout, QHBoxLayout, QFormLayout,
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QSizePolicy,
)

from config import COLOR_PANEL, COLOR_PANEL_ALT, COLOR_TEXT, COLOR_ACCENT, COLOR_OK, COLOR_WARN, COLOR_ERROR
from patient_database import PatientDatabase, PatientRecord


class PatientsPage(QWidget):
    """
    Patient roster + personal analysis screen.

    - Left: list of all patients (click a row to load it into the form).
    - Right: personal-information form (add new / edit selected) and a
      free-text "Personal Analysis" box that can be saved per patient,
      optionally pre-filled with a live snapshot of the current reading.
    """

    patients_changed = pyqtSignal()

    def __init__(self, database: PatientDatabase, save_callback=None,
                 live_snapshot_callback=None, parent=None):
        super().__init__(parent)
        self.database = database
        self._save_callback = save_callback              # persists DB to disk
        self._live_snapshot_callback = live_snapshot_callback  # returns str
        self._selected_id = None
        self._build_ui()
        self.refresh_table()

    # ------------------------------------------------------------- UI --
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        root.addWidget(self._build_list_panel(), stretch=1)
        root.addWidget(self._build_form_panel(), stretch=1)

    def _build_list_panel(self) -> QWidget:
        panel = QFrame()
        panel.setStyleSheet(f"background-color: {COLOR_PANEL}; border-radius: 10px;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("PATIENTS")
        title.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 14px; font-weight: 700; letter-spacing: 1px;")
        layout.addWidget(title)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["ID", "Name", "Age", "Condition"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setStyleSheet(
            f"QTableWidget {{ background-color: {COLOR_PANEL_ALT}; color: {COLOR_TEXT}; gridline-color: #2E3F53; font-size: 12px; }}"
            f"QHeaderView::section {{ background-color: #22303C; color: {COLOR_ACCENT}; padding: 4px; border: none; font-weight: 600; }}"
            f"QTableWidget::item:selected {{ background-color: #2A4A5C; }}"
        )
        self.table.itemSelectionChanged.connect(self._on_row_selected)
        layout.addWidget(self.table, stretch=1)

        btn_row = QHBoxLayout()
        self.btn_new = QPushButton("New Patient")
        self.btn_new.clicked.connect(self.clear_form)
        self.btn_delete = QPushButton("Delete Selected")
        self.btn_delete.clicked.connect(self.delete_selected)
        for b, color in ((self.btn_new, COLOR_ACCENT), (self.btn_delete, COLOR_ERROR)):
            b.setStyleSheet(
                f"QPushButton {{ background-color: {color}; color: white; font-weight: 600; "
                f"border-radius: 6px; padding: 8px; }}"
                f"QPushButton:pressed {{ background-color: #555555; }}"
            )
            btn_row.addWidget(b)
        layout.addLayout(btn_row)
        return panel

    def _build_form_panel(self) -> QWidget:
        panel = QFrame()
        panel.setStyleSheet(f"background-color: {COLOR_PANEL}; border-radius: 10px;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("PERSONAL INFORMATION")
        title.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 14px; font-weight: 700; letter-spacing: 1px;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(6)

        self.in_id = QLineEdit()
        self.in_id.setPlaceholderText("auto-generated if left blank")
        self.in_name = QLineEdit()
        self.in_age = QSpinBox()
        self.in_age.setRange(0, 120)
        self.in_gender = QComboBox()
        self.in_gender.addItems(["", "Female", "Male", "Other"])
        self.in_height = QDoubleSpinBox()
        self.in_height.setRange(0, 250)
        self.in_height.setSuffix(" cm")
        self.in_weight = QDoubleSpinBox()
        self.in_weight.setRange(0, 300)
        self.in_weight.setSuffix(" kg")
        self.in_side = QComboBox()
        self.in_side.addItems(["", "Left", "Right", "Bilateral", "None"])
        self.in_condition = QLineEdit()
        self.in_condition.setText("Normal")
        self.in_trial = QSpinBox()
        self.in_trial.setRange(1, 999)

        for w in (self.in_id, self.in_name, self.in_age, self.in_gender, self.in_height,
                   self.in_weight, self.in_side, self.in_condition, self.in_trial):
            w.setStyleSheet(f"background-color: {COLOR_PANEL_ALT}; color: {COLOR_TEXT}; padding: 4px; border-radius: 4px;")

        form.addRow(self._label("Patient ID"), self.in_id)
        form.addRow(self._label("Name"), self.in_name)
        form.addRow(self._label("Age"), self.in_age)
        form.addRow(self._label("Gender"), self.in_gender)
        form.addRow(self._label("Height"), self.in_height)
        form.addRow(self._label("Weight"), self.in_weight)
        form.addRow(self._label("Affected Side"), self.in_side)
        form.addRow(self._label("Walking Condition"), self.in_condition)
        form.addRow(self._label("Trial Number"), self.in_trial)
        layout.addLayout(form)

        self.in_research_notes = QTextEdit()
        self.in_research_notes.setPlaceholderText("Research / intake notes...")
        self.in_research_notes.setMaximumHeight(70)
        self.in_research_notes.setStyleSheet(f"background-color: {COLOR_PANEL_ALT}; color: {COLOR_TEXT}; border-radius: 4px;")
        layout.addWidget(self._label("Research Notes"))
        layout.addWidget(self.in_research_notes)

        analysis_title = QLabel("PERSONAL ANALYSIS")
        analysis_title.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 13px; font-weight: 700; letter-spacing: 1px; margin-top: 6px;")
        layout.addWidget(analysis_title)

        self.in_analysis = QTextEdit()
        self.in_analysis.setPlaceholderText("Clinical / personal analysis for this patient...")
        self.in_analysis.setStyleSheet(f"background-color: {COLOR_PANEL_ALT}; color: {COLOR_TEXT}; border-radius: 4px;")
        layout.addWidget(self.in_analysis, stretch=1)

        self.lbl_meta = QLabel("")
        self.lbl_meta.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 11px;")
        layout.addWidget(self.lbl_meta)

        btn_row = QHBoxLayout()
        self.btn_snapshot = QPushButton("Insert Live Reading")
        self.btn_snapshot.clicked.connect(self._insert_live_snapshot)
        self.btn_save = QPushButton("Save Patient")
        self.btn_save.clicked.connect(self.save_form)
        for b, color in ((self.btn_snapshot, COLOR_WARN), (self.btn_save, COLOR_OK)):
            b.setStyleSheet(
                f"QPushButton {{ background-color: {color}; color: white; font-weight: 700; "
                f"border-radius: 6px; padding: 10px; }}"
                f"QPushButton:pressed {{ background-color: #555555; }}"
            )
            btn_row.addWidget(b)
        layout.addLayout(btn_row)
        return panel

    @staticmethod
    def _label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 12px;")
        return lbl

    # --------------------------------------------------------- ACTIONS --
    def refresh_table(self):
        records = self.database.list_records()
        self.table.setRowCount(0)
        for record in records:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(record.patient_id))
            self.table.setItem(row, 1, QTableWidgetItem(record.name))
            self.table.setItem(row, 2, QTableWidgetItem(str(record.age)))
            self.table.setItem(row, 3, QTableWidgetItem(record.walking_condition))

    def _on_row_selected(self):
        selected = self.table.selectedItems()
        if not selected:
            return
        row = selected[0].row()
        patient_id = self.table.item(row, 0).text()
        record = self.database.get_record(patient_id)
        if record:
            self._load_into_form(record)

    def _load_into_form(self, record: PatientRecord):
        self._selected_id = record.patient_id
        self.in_id.setText(record.patient_id)
        self.in_id.setEnabled(False)
        self.in_name.setText(record.name)
        self.in_age.setValue(record.age)
        idx = self.in_gender.findText(record.gender)
        self.in_gender.setCurrentIndex(idx if idx >= 0 else 0)
        self.in_height.setValue(record.height_cm)
        self.in_weight.setValue(record.weight_kg)
        idx = self.in_side.findText(record.affected_side)
        self.in_side.setCurrentIndex(idx if idx >= 0 else 0)
        self.in_condition.setText(record.walking_condition)
        self.in_trial.setValue(record.trial_number or 1)
        self.in_research_notes.setPlainText(record.research_notes)
        self.in_analysis.setPlainText(record.analysis_notes)
        self.lbl_meta.setText(f"Created {record.created_at}  •  Last updated {record.updated_at}")

    def clear_form(self):
        self._selected_id = None
        self.table.clearSelection()
        self.in_id.clear()
        self.in_id.setEnabled(True)
        self.in_name.clear()
        self.in_age.setValue(0)
        self.in_gender.setCurrentIndex(0)
        self.in_height.setValue(0)
        self.in_weight.setValue(0)
        self.in_side.setCurrentIndex(0)
        self.in_condition.setText("Normal")
        self.in_trial.setValue(1)
        self.in_research_notes.clear()
        self.in_analysis.clear()
        self.lbl_meta.setText("")

    def save_form(self):
        name = self.in_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing Name", "Please enter the patient's name before saving.")
            return

        record = PatientRecord(
            patient_id=self._selected_id or self.in_id.text().strip(),
            name=name,
            age=self.in_age.value(),
            gender=self.in_gender.currentText(),
            height_cm=self.in_height.value(),
            weight_kg=self.in_weight.value(),
            affected_side=self.in_side.currentText(),
            walking_condition=self.in_condition.text().strip() or "Normal",
            trial_number=self.in_trial.value(),
            research_notes=self.in_research_notes.toPlainText(),
            analysis_notes=self.in_analysis.toPlainText(),
        )

        if self._selected_id:
            self.database.update_record(record)
        else:
            new_id = self.database.add_record(record)
            self._selected_id = new_id

        if self._save_callback:
            self._save_callback()

        self.refresh_table()
        self._load_into_form(self.database.get_record(self._selected_id))
        self.patients_changed.emit()
        QMessageBox.information(self, "Saved", f"Patient '{name}' saved.")

    def delete_selected(self):
        if not self._selected_id:
            QMessageBox.information(self, "Delete Patient", "Select a patient from the list first.")
            return
        reply = QMessageBox.question(
            self, "Delete Patient",
            f"Delete patient '{self._selected_id}'? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.database.delete_record(self._selected_id)
            if self._save_callback:
                self._save_callback()
            self.clear_form()
            self.refresh_table()
            self.patients_changed.emit()

    def _insert_live_snapshot(self):
        if not self._live_snapshot_callback:
            return
        snapshot = self._live_snapshot_callback()
        if not snapshot:
            QMessageBox.information(self, "Live Reading", "No live data available yet.")
            return
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        existing = self.in_analysis.toPlainText()
        addition = f"[{timestamp}] {snapshot}"
        self.in_analysis.setPlainText((existing + "\n" + addition) if existing else addition)
