from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock


@dataclass
class FrameMetrics:
    inference_latency_ms: float
    fps: float
    dropped_frames: int
    uptime_s: float


class MetricsTracker:
    def __init__(self, camera_id: str, metrics_path: str, ema_alpha: float = 0.2) -> None:
        self.camera_id = camera_id
        self.metrics_path = Path(metrics_path)
        self.metrics_path.parent.mkdir(parents=True, exist_ok=True)

        self.start_ts = time.time()
        self.last_frame_ts: float | None = None
        self.ema_latency_ms = 0.0
        self.ema_fps = 0.0
        self.frames_processed = 0
        self.frames_dropped = 0
        self.ema_alpha = ema_alpha
        self._lock = Lock()

    def mark_frame(self, latency_ms: float) -> FrameMetrics:
        now = time.time()
        with self._lock:
            self.frames_processed += 1
            if self.frames_processed == 1:
                self.ema_latency_ms = latency_ms
            else:
                self.ema_latency_ms = self.ema_alpha * latency_ms + (1 - self.ema_alpha) * self.ema_latency_ms

            inst_fps = 0.0
            if self.last_frame_ts is not None:
                delta = max(now - self.last_frame_ts, 1e-6)
                inst_fps = 1.0 / delta

            if self.frames_processed <= 2:
                self.ema_fps = inst_fps
            else:
                self.ema_fps = self.ema_alpha * inst_fps + (1 - self.ema_alpha) * self.ema_fps

            self.last_frame_ts = now
            return self.snapshot()

    def mark_dropped(self, count: int = 1) -> None:
        with self._lock:
            self.frames_dropped += max(0, int(count))

    def snapshot(self) -> FrameMetrics:
        uptime = max(time.time() - self.start_ts, 0.0)
        return FrameMetrics(
            inference_latency_ms=round(self.ema_latency_ms, 2),
            fps=round(self.ema_fps, 2),
            dropped_frames=int(self.frames_dropped),
            uptime_s=round(uptime, 2),
        )

    def dump_json(self, extra: dict | None = None) -> None:
        payload = {
            "camera_id": self.camera_id,
            "frames_processed": self.frames_processed,
            "inference_latency_ms": self.snapshot().inference_latency_ms,
            "fps": self.snapshot().fps,
            "dropped_frames": self.frames_dropped,
            "uptime_s": self.snapshot().uptime_s,
            "updated_ts": time.time(),
        }
        if extra:
            payload.update(extra)
        self.metrics_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
