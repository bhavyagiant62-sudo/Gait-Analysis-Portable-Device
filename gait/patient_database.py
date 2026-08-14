from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class PatientRecord:
    patient_id: str = ""
    name: str = ""
    age: int = 0
    gender: str = ""
    height_cm: float = 0.0
    weight_kg: float = 0.0
    affected_side: str = ""
    walking_condition: str = "Normal"
    trial_number: int = 1
    research_notes: str = ""
    # Free-text personal / clinical analysis for this patient. Kept
    # separate from research_notes so the Patients screen can offer a
    # dedicated "Personal Analysis" box without overloading one field.
    analysis_notes: str = ""
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not self.updated_at:
            self.updated_at = self.created_at


class PatientDatabase:
    """Stores patient metadata + personal analysis notes, with optional JSON persistence."""

    def __init__(self):
        self.records: Dict[str, PatientRecord] = {}

    # ------------------------------------------------------------- CRUD --
    def add_record(self, record: PatientRecord) -> str:
        patient_id = record.patient_id or f"P{len(self.records) + 1:03d}"
        record.patient_id = patient_id
        self.records[patient_id] = record
        return patient_id

    def update_record(self, record: PatientRecord) -> None:
        record.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.records[record.patient_id] = record

    def delete_record(self, patient_id: str) -> None:
        self.records.pop(patient_id, None)

    def get_record(self, patient_id: str) -> Optional[PatientRecord]:
        return self.records.get(patient_id)

    def list_records(self) -> List[PatientRecord]:
        return sorted(self.records.values(), key=lambda r: r.patient_id)

    def export_metadata(self) -> List[dict]:
        return [asdict(record) for record in self.records.values()]

    # ------------------------------------------------------------- FILE --
    def save_to_file(self, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(self.export_metadata(), handle, indent=2)

    def load_from_file(self, path: str) -> None:
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as handle:
            try:
                raw = json.load(handle)
            except json.JSONDecodeError:
                return
        self.records = {}
        known_fields = {f for f in PatientRecord.__dataclass_fields__.keys()}
        for item in raw:
            filtered = {k: v for k, v in item.items() if k in known_fields}
            record = PatientRecord(**filtered)
            self.records[record.patient_id] = record
