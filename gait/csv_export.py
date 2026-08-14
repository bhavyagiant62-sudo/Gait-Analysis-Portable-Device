import csv
import os
from datetime import datetime


class CSVExporter:
    """Exports gait metrics and patient metadata to CSV."""

    def __init__(self, output_dir: str):
        self.output_dir = output_dir

    def export(self, filename: str, rows: list, metadata: dict | None = None) -> str:
        os.makedirs(self.output_dir, exist_ok=True)
        path = os.path.join(self.output_dir, filename)
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            if metadata:
                writer.writerow(["metadata", "value"])
                for key, value in metadata.items():
                    writer.writerow([key, value])
                writer.writerow([])
            writer.writerow(["metric", "value"])
            for key, value in rows:
                writer.writerow([key, value])
        return path
