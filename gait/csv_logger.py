import csv
import os
from datetime import datetime

from config import CSV_DIR, RECORDING_PREFIX


class CSVLogger:
    """Writes a continuous recording session to a timestamped CSV file."""

    def __init__(self, directory: str = CSV_DIR, prefix: str = RECORDING_PREFIX):
        self._directory = directory
        self._prefix = prefix
        self._file = None
        self._writer = None
        self._filepath = None
        self._row_count = 0

    def set_directory(self, directory: str):
        """Changes where the next recording session will be written.
        Safe to call any time except mid-recording (Settings screen
        disables the field while a session is active)."""
        self._directory = directory

    def set_prefix(self, prefix: str):
        """Changes the filename prefix used for the next recording session."""
        if prefix:
            self._prefix = prefix

    @property
    def directory(self) -> str:
        return self._directory

    def start(self) -> str:
        os.makedirs(self._directory, exist_ok=True)
        filename = f"{self._prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        self._filepath = os.path.join(self._directory, filename)
        self._file = open(self._filepath, mode="w", newline="", encoding="utf-8")
        self._writer = csv.writer(self._file)
        self._writer.writerow([
            "Packet",
            "Time",
            "Pitch",
            "Roll",
            "Yaw",
            "Calibration",
            "Timestamp",
            "SamplingFrequency",
        ])
        self._file.flush()
        self._row_count = 0
        return self._filepath

    def write_row(self, packet_id, packet_time, pitch, roll, yaw, calibration, sampling_frequency):
        if self._writer is None:
            return
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        self._writer.writerow([packet_id, packet_time, pitch, roll, yaw, calibration, timestamp, sampling_frequency])
        self._row_count += 1

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

    @property
    def row_count(self) -> int:
        return self._row_count
