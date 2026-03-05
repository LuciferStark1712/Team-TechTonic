from __future__ import annotations

import time
from pathlib import Path
from typing import Union

import cv2

from alerts import AlertLogger
from behavior import analyze_behavior, compute_risk_score
from detector import YoloDetector
from explainer import build_explanation
from io_utils import create_video_writer, open_video
from monitoring import MetricsTracker
from tracker import CentroidTracker
from verification import verify_human


class ThreatSensePipeline:
    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        self.camera_id = str(cfg.get("runtime", {}).get("camera_id", "camera_0"))
        self.source_name = str(cfg.get("runtime", {}).get("source_name", self.camera_id))

        self.detector = YoloDetector(
            cfg["model"]["weights"],
            cfg["model"]["conf_threshold"],
            cfg["model"]["iou_threshold"],
        )
        self.tracker = CentroidTracker(
            max_distance=float(cfg.get("tracker", {}).get("max_distance", 70.0)),
            max_missed_frames=int(cfg.get("tracker", {}).get("max_missed_frames", 25)),
            max_trace_length=int(cfg.get("tracker", {}).get("max_trace_length", 120)),
        )

        channels = AlertLogger.build_channels_from_config(cfg)
        self.logger = AlertLogger(
            cfg["logging"]["json_log_path"],
            cfg["logging"]["csv_log_path"],
            cfg["logging"]["snapshot_dir"],
            camera_id=self.camera_id,
            source_name=self.source_name,
            db_path=cfg.get("database", {}).get("sqlite_path", "outputs/db/events.db"),
            enable_csv=bool(cfg.get("logging", {}).get("enable_csv", True)),
            channels=channels,
        )

        metrics_path = cfg.get("monitoring", {}).get("metrics_path", f"outputs/metrics/{self.camera_id}.json")
        self.metrics = MetricsTracker(camera_id=self.camera_id, metrics_path=metrics_path)
        self.live_frame_path = Path(
            cfg.get("monitoring", {}).get("live_frame_path", f"outputs/live/{self.camera_id}.jpg")
        )
        self.live_frame_path.parent.mkdir(parents=True, exist_ok=True)

        self.alert_cooldown: dict[int, int] = {}

    def _write_live_frame(self, frame) -> None:
        cv2.imwrite(str(self.live_frame_path), frame)

    def _dump_frame_state(self, frame_idx: int, frame_max_risk: float, alerts_logged: int) -> None:
        self.metrics.dump_json(
            {
                "frame_idx": frame_idx,
                "frame_max_risk": round(frame_max_risk, 3),
                "alerts_logged": int(alerts_logged),
                "live_frame_path": str(self.live_frame_path),
            }
        )

    def run(self, source: Union[str, int], show_live: bool = False) -> None:
        cap, fps, width, height = open_video(source)
        writer = create_video_writer(self.cfg["video"]["output_path"], fps, width, height)

        frame_idx = 0
        max_frames = self.cfg["video"]["max_frames"]
        cooldown_frames = max(1, int(float(self.cfg.get("alerts", {}).get("cooldown_seconds", 3.0)) * fps))
        live_write_every = int(self.cfg.get("monitoring", {}).get("live_frame_every_n", 2))

        stats = {
            "frames": 0,
            "person_detections": 0,
            "verified_humans": 0,
            "discarded_by_verification": 0,
            "running_frames": 0,
            "loitering_frames": 0,
            "alerts_logged": 0,
            "dropped_frames": 0,
        }

        while True:
            loop_start = time.perf_counter()
            ok, frame = cap.read()
            if not ok:
                stats["dropped_frames"] += 1
                self.metrics.mark_dropped(1)
                break

            frame_idx += 1
            stats["frames"] += 1
            if max_frames and frame_idx > max_frames:
                break
            frame_max_risk = 0.0

            detections = self.detector.infer(frame)
            person_bboxes = []
            person_det_map = {}

            for det in detections:
                if det.cls_name != "person":
                    continue
                stats["person_detections"] += 1
                bbox = (det.x1, det.y1, det.x2, det.y2)
                person_bboxes.append(bbox)
                person_det_map[bbox] = det

            assigned = self.tracker.update(person_bboxes, frame_idx)

            for track_id, bbox in assigned.items():
                det = person_det_map[bbox]
                vr = verify_human(frame, bbox, self.cfg["human_verification"])
                if not vr.is_human:
                    stats["discarded_by_verification"] += 1
                    x1, y1, x2, y2 = bbox
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (50, 50, 255), 2)
                    cv2.putText(
                        frame,
                        f"discarded: {','.join(vr.reasons[:1])}",
                        (x1, max(20, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (50, 50, 255),
                        1,
                    )
                    continue

                stats["verified_humans"] += 1
                track = self.tracker.tracks[track_id]
                behavior = analyze_behavior(track.points, fps, self.cfg["behavior"])
                if behavior["is_running"]:
                    stats["running_frames"] += 1
                if behavior["is_loitering"]:
                    stats["loitering_frames"] += 1
                risk = compute_risk_score(det.conf, behavior, self.cfg["risk"])
                frame_max_risk = max(frame_max_risk, risk)
                explanation = build_explanation(
                    track_id,
                    det.conf,
                    vr.reasons,
                    vr.metrics,
                    behavior,
                    risk,
                )

                x1, y1, x2, y2 = bbox
                color = (0, 255, 0) if risk < self.cfg["risk"]["alert_threshold"] else (0, 0, 255)
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(
                    frame,
                    f"{self.camera_id} ID {track_id} risk={risk:.2f}",
                    (x1, max(20, y1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    color,
                    2,
                )

                is_alert = (
                    risk >= self.cfg["risk"]["alert_threshold"]
                    and track.frames_seen >= self.cfg["behavior"]["min_track_age_for_alert"]
                )

                if is_alert:
                    prev = self.alert_cooldown.get(track_id, 0)
                    if frame_idx - prev >= cooldown_frames:
                        event_type = (
                            "running"
                            if behavior["is_running"]
                            else "loitering"
                            if behavior["is_loitering"]
                            else "high_risk"
                        )
                        record = {
                            "timestamp_s": round(frame_idx / max(fps, 1e-6), 2),
                            "frame_idx": frame_idx,
                            "track_id": track_id,
                            "risk_score": risk,
                            "event_type": event_type,
                            "confidence": round(det.conf, 3),
                            "explanation": explanation,
                        }
                        self.logger.log_alert(record, frame)
                        stats["alerts_logged"] += 1
                        self.alert_cooldown[track_id] = frame_idx

            latency_ms = (time.perf_counter() - loop_start) * 1000.0
            metric = self.metrics.mark_frame(latency_ms)

            cv2.putText(
                frame,
                f"Cam: {self.camera_id}",
                (20, 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 0),
                2,
            )
            cv2.putText(
                frame,
                f"Frame Risk: {frame_max_risk:.2f} | FPS: {metric.fps:.1f} | Lat: {metric.inference_latency_ms:.1f} ms",
                (20, 52),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 255),
                2,
            )

            writer.write(frame)

            if frame_idx % max(live_write_every, 1) == 0:
                self._write_live_frame(frame)
                self._dump_frame_state(frame_idx=frame_idx, frame_max_risk=frame_max_risk, alerts_logged=stats["alerts_logged"])

            if show_live:
                cv2.imshow(f"ThreatSense Live - {self.camera_id}", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

        cap.release()
        writer.release()
        if show_live:
            cv2.destroyAllWindows()

        self._dump_frame_state(frame_idx=frame_idx, frame_max_risk=0.0, alerts_logged=stats["alerts_logged"])

        print(f"Done ({self.camera_id}). Output video: {self.cfg['video']['output_path']}")
        print(f"Alerts JSON: {self.cfg['logging']['json_log_path']}")
        if self.cfg.get("logging", {}).get("enable_csv", True):
            print(f"Alerts CSV:  {self.cfg['logging']['csv_log_path']}")
        print(f"Metrics: {self.cfg.get('monitoring', {}).get('metrics_path', 'outputs/metrics/<camera>.json')}")
        print(
            "Stats: "
            f"frames={stats['frames']}, "
            f"person_detections={stats['person_detections']}, "
            f"verified_humans={stats['verified_humans']}, "
            f"discarded_by_verification={stats['discarded_by_verification']}, "
            f"running_frames={stats['running_frames']}, "
            f"loitering_frames={stats['loitering_frames']}, "
            f"alerts_logged={stats['alerts_logged']}, "
            f"dropped_frames={stats['dropped_frames']}"
        )
