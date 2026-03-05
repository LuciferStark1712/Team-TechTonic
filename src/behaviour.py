from __future__ import annotations

from math import hypot


def analyze_behavior(track_points: list[tuple[float, float]], fps: float, cfg: dict) -> dict:
    if len(track_points) < 2:
        return {
            "speed_px_s": 0.0,
            "is_running": False,
            "is_loitering": False,
            "loiter_duration_s": 0.0,
            "radius_px": 0.0,
        }

    total_dist = 0.0
    for i in range(1, len(track_points)):
        total_dist += hypot(
            track_points[i][0] - track_points[i - 1][0],
            track_points[i][1] - track_points[i - 1][1],
        )

    duration_s = max((len(track_points) - 1) / max(fps, 1e-6), 1e-6)
    speed = total_dist / duration_s

    xs = [p[0] for p in track_points]
    ys = [p[1] for p in track_points]
    center = (sum(xs) / len(xs), sum(ys) / len(ys))
    radius = max(hypot(x - center[0], y - center[1]) for x, y in track_points)

    loiter_duration = len(track_points) / max(fps, 1e-6)
    is_loitering = loiter_duration >= cfg["loitering_seconds"] and radius <= cfg["loitering_max_radius_px"]
    is_running = speed >= cfg["running_speed_threshold_px_s"]

    return {
        "speed_px_s": round(speed, 2),
        "is_running": is_running,
        "is_loitering": is_loitering,
        "loiter_duration_s": round(loiter_duration, 2),
        "radius_px": round(radius, 2),
    }


def compute_risk_score(det_conf: float, behavior: dict, cfg: dict) -> float:
    score = 0.0
    score += cfg["confidence_weight"] * det_conf
    score += cfg["running_weight"] * float(behavior["is_running"])
    score += cfg["loitering_weight"] * float(behavior["is_loitering"])
    return round(min(score, 1.0), 3)
