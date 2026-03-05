from __future__ import annotations

from dataclasses import dataclass, field
from math import hypot


@dataclass
class Track:
    track_id: int
    points: list[tuple[float, float]] = field(default_factory=list)
    bboxes: list[tuple[int, int, int, int]] = field(default_factory=list)
    frames_seen: int = 0
    last_frame_idx: int = 0
    missed_frames: int = 0


class CentroidTracker:
    def __init__(
        self,
        max_distance: float = 70.0,
        max_missed_frames: int = 25,
        max_trace_length: int = 120,
    ) -> None:
        self.max_distance = max_distance
        self.max_missed_frames = max_missed_frames
        self.max_trace_length = max_trace_length
        self.tracks: dict[int, Track] = {}
        self.next_id = 1

    @staticmethod
    def _centroid(bbox: tuple[int, int, int, int]) -> tuple[float, float]:
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    def _append_observation(self, track: Track, centroid: tuple[float, float], bbox: tuple[int, int, int, int], frame_idx: int) -> None:
        track.points.append(centroid)
        track.bboxes.append(bbox)
        if len(track.points) > self.max_trace_length:
            track.points = track.points[-self.max_trace_length :]
        if len(track.bboxes) > self.max_trace_length:
            track.bboxes = track.bboxes[-self.max_trace_length :]
        track.frames_seen += 1
        track.last_frame_idx = frame_idx
        track.missed_frames = 0

    def update(self, bboxes: list[tuple[int, int, int, int]], frame_idx: int) -> dict[int, tuple[int, int, int, int]]:
        assigned: dict[int, tuple[int, int, int, int]] = {}
        available_track_ids = set(self.tracks.keys())
        matched_track_ids: set[int] = set()

        for bbox in bboxes:
            c = self._centroid(bbox)
            best_tid = None
            best_dist = 1e9

            for tid in available_track_ids:
                last = self.tracks[tid].points[-1]
                d = hypot(c[0] - last[0], c[1] - last[1])
                if d < best_dist and d <= self.max_distance:
                    best_dist = d
                    best_tid = tid

            if best_tid is None:
                tid = self.next_id
                self.next_id += 1
                tr = Track(track_id=tid, points=[], bboxes=[], frames_seen=0, last_frame_idx=frame_idx)
                self._append_observation(tr, c, bbox, frame_idx)
                self.tracks[tid] = tr
                assigned[tid] = bbox
                matched_track_ids.add(tid)
            else:
                tr = self.tracks[best_tid]
                self._append_observation(tr, c, bbox, frame_idx)
                assigned[best_tid] = bbox
                available_track_ids.remove(best_tid)
                matched_track_ids.add(best_tid)

        stale_ids: list[int] = []
        for tid, tr in self.tracks.items():
            if tid not in matched_track_ids:
                tr.missed_frames += 1
                if tr.missed_frames > self.max_missed_frames:
                    stale_ids.append(tid)

        for tid in stale_ids:
            self.tracks.pop(tid, None)

        return assigned
