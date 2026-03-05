from __future__ import annotations

import argparse
import copy
from datetime import datetime
from pathlib import Path

from config import AppConfig
from pipeline import ThreatSensePipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ThreatSense AI-DVR")
    parser.add_argument("--config", type=str, default="config/config.yaml")
    parser.add_argument("--source", type=str, help="Path to one input video")
    parser.add_argument("--webcam", action="store_true", help="Use webcam as live input source")
    parser.add_argument("--camera-index", type=int, default=0, help="Webcam index (default: 0)")
    parser.add_argument("--show-live", action="store_true", help="Show live preview window (press q to quit)")
    parser.add_argument(
        "--source-dir",
        type=str,
        help="Directory containing multiple videos for batch processing",
    )
    parser.add_argument(
        "--pattern",
        type=str,
        default="*",
        help="Glob pattern for --source-dir (default: *)",
    )
    return parser.parse_args()


def _is_video_file(path: Path) -> bool:
    return path.suffix.lower() in {".mp4", ".avi", ".mov", ".mkv", ".m4v", ".webm"}


def _cfg_for_video(base_cfg: dict, source_path: Path) -> dict:
    cfg = copy.deepcopy(base_cfg)
    stem = source_path.stem

    cfg["video"]["output_path"] = f"outputs/annotated_{stem}.mp4"
    cfg["logging"]["json_log_path"] = f"outputs/logs/alerts_{stem}.jsonl"
    cfg["logging"]["csv_log_path"] = f"outputs/logs/alerts_{stem}.csv"
    cfg["logging"]["snapshot_dir"] = f"outputs/snapshots/{stem}"
    return cfg


def _cfg_for_webcam(base_cfg: dict, camera_index: int) -> dict:
    cfg = copy.deepcopy(base_cfg)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = f"webcam_{camera_index}_{ts}"
    cfg["video"]["output_path"] = f"outputs/annotated_{stem}.mp4"
    cfg["logging"]["json_log_path"] = f"outputs/logs/alerts_{stem}.jsonl"
    cfg["logging"]["csv_log_path"] = f"outputs/logs/alerts_{stem}.csv"
    cfg["logging"]["snapshot_dir"] = f"outputs/snapshots/{stem}"
    return cfg


def main() -> None:
    args = parse_args()
    sources_selected = int(bool(args.source)) + int(bool(args.source_dir)) + int(bool(args.webcam))
    if sources_selected == 0:
        raise ValueError("Provide one input mode: --source, --source-dir, or --webcam.")
    if sources_selected > 1:
        raise ValueError("Choose only one input mode at a time: --source OR --source-dir OR --webcam.")

    app_cfg = AppConfig.load(args.config)
    base_cfg = app_cfg.raw

    if args.webcam:
        cfg = _cfg_for_webcam(base_cfg, args.camera_index)
        Path(cfg["logging"]["snapshot_dir"]).mkdir(parents=True, exist_ok=True)
        Path(cfg["logging"]["json_log_path"]).parent.mkdir(parents=True, exist_ok=True)
        Path(cfg["logging"]["csv_log_path"]).parent.mkdir(parents=True, exist_ok=True)
        Path(cfg["video"]["output_path"]).parent.mkdir(parents=True, exist_ok=True)
        pipeline = ThreatSensePipeline(cfg)
        pipeline.run(args.camera_index, show_live=args.show_live)
        return

    if args.source:
        source_path = Path(args.source)
        cfg = _cfg_for_video(base_cfg, source_path)
        Path(cfg["logging"]["snapshot_dir"]).mkdir(parents=True, exist_ok=True)
        Path(cfg["logging"]["json_log_path"]).parent.mkdir(parents=True, exist_ok=True)
        Path(cfg["logging"]["csv_log_path"]).parent.mkdir(parents=True, exist_ok=True)
        Path(cfg["video"]["output_path"]).parent.mkdir(parents=True, exist_ok=True)
        pipeline = ThreatSensePipeline(cfg)
        pipeline.run(str(source_path), show_live=args.show_live)
        return

    source_dir = Path(args.source_dir)
    if not source_dir.exists() or not source_dir.is_dir():
        raise ValueError(f"Invalid --source-dir: {source_dir}")

    candidates = sorted(source_dir.glob(args.pattern))
    videos = [p for p in candidates if p.is_file() and _is_video_file(p)]
    if not videos:
        raise ValueError(f"No video files found in {source_dir} with pattern '{args.pattern}'.")

    print(f"Found {len(videos)} video(s). Starting batch run...")
    for idx, video_path in enumerate(videos, start=1):
        cfg = _cfg_for_video(base_cfg, video_path)
        print(f"[{idx}/{len(videos)}] Processing: {video_path}")
        Path(cfg["logging"]["snapshot_dir"]).mkdir(parents=True, exist_ok=True)
        Path(cfg["logging"]["json_log_path"]).parent.mkdir(parents=True, exist_ok=True)
        Path(cfg["logging"]["csv_log_path"]).parent.mkdir(parents=True, exist_ok=True)
        Path(cfg["video"]["output_path"]).parent.mkdir(parents=True, exist_ok=True)
        pipeline = ThreatSensePipeline(cfg)
        pipeline.run(str(video_path), show_live=args.show_live)
    print("Batch run completed.")


if __name__ == "__main__":
    main()
