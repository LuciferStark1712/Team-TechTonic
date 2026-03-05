from __future__ import annotations

from pathlib import Path
from typing import Union

import cv2


def open_video(source: Union[str, int]):
    if isinstance(source, str):
        path = Path(source)
        if path.exists() and path.suffix.lower() in {".sh", ".py", ".md", ".txt", ".yaml", ".yml"}:
            raise RuntimeError(
                f"Source is not a video file: {source}\n"
                "Tip: run scripts separately, then pass a real video path to --source.\n"
                "Example: python src/main.py --config config/config.yaml --source data/sample_dataset/test_video.mp4"
            )

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError(
            f"Unable to open source: {source}\n"
            "Use a valid video path (e.g., .mp4/.avi/.mov) or webcam index if your setup supports it."
        )
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    return cap, fps, width, height


def create_video_writer(path: str, fps: float, width: int, height: int):
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    return cv2.VideoWriter(path, fourcc, fps, (width, height))
