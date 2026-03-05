from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class AppConfig:
    raw: dict[str, Any]

    @staticmethod
    def load(path: str) -> "AppConfig":
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return AppConfig(raw=data)

    def ensure_dirs(self) -> None:
        log_cfg = self.raw["logging"]
        Path(log_cfg["snapshot_dir"]).mkdir(parents=True, exist_ok=True)
        Path(log_cfg["json_log_path"]).parent.mkdir(parents=True, exist_ok=True)
        Path(log_cfg["csv_log_path"]).parent.mkdir(parents=True, exist_ok=True)
        Path(self.raw["video"]["output_path"]).parent.mkdir(parents=True, exist_ok=True)
