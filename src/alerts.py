from __future__ import annotations

import csv
import json
from pathlib import Path

import cv2


class AlertLogger:
    def __init__(self, json_path: str, csv_path: str, snapshot_dir: str) -> None:
        self.json_path = Path(json_path)
        self.csv_path = Path(csv_path)
        self.snapshot_dir = Path(snapshot_dir)

        self.json_path.parent.mkdir(parents=True, exist_ok=True)
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

        if not self.csv_path.exists():
            with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "timestamp_s",
                        "frame_idx",
                        "track_id",
                        "risk_score",
                        "event_type",
                        "confidence",
                        "explanation",
                        "snapshot_path",
                    ],
                )
                writer.writeheader()

    def log_alert(self, record: dict, frame) -> None:
        snapshot_name = f"alert_f{record['frame_idx']}_t{record['track_id']}.jpg"
        snapshot_path = self.snapshot_dir / snapshot_name
        cv2.imwrite(str(snapshot_path), frame)
        record["snapshot_path"] = str(snapshot_path)

        with open(self.json_path, "a", encoding="utf-8") as jf:
            jf.write(json.dumps(record, ensure_ascii=False) + "\n")

        with open(self.csv_path, "a", newline="", encoding="utf-8") as cf:
            writer = csv.DictWriter(cf, fieldnames=record.keys())
            writer.writerow(record)
