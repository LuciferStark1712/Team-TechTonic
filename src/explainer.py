from __future__ import annotations


def build_explanation(track_id: int, det_conf: float, verification_reasons: list[str], metrics: dict, behavior: dict, risk_score: float) -> str:
    behavior_tags = []
    if behavior["is_running"]:
        behavior_tags.append(f"running(speed={behavior['speed_px_s']} px/s)")
    if behavior["is_loitering"]:
        behavior_tags.append(
            f"loitering(duration={behavior['loiter_duration_s']}s, radius={behavior['radius_px']}px)"
        )
    if not behavior_tags:
        behavior_tags.append("normal_movement")

    verification_text = ", ".join(verification_reasons)
    metrics_text = ", ".join([f"{k}={v}" for k, v in metrics.items()])

    return (
        f"Track {track_id}: conf={det_conf:.2f}; behavior={'; '.join(behavior_tags)}; "
        f"verification={verification_text}; metrics[{metrics_text}]; risk={risk_score:.2f}"
    )
