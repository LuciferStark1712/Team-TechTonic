from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from skimage.feature import local_binary_pattern


@dataclass
class VerificationResult:
    is_human: bool
    reasons: list[str]
    metrics: dict[str, float]


def _edge_density(gray: np.ndarray) -> float:
    edges = cv2.Canny(gray, 80, 180)
    return float(np.count_nonzero(edges)) / float(edges.size + 1e-6)


def _texture_variance(gray: np.ndarray) -> float:
    lbp = local_binary_pattern(gray, P=8, R=1, method="uniform")
    return float(np.var(lbp))


def verify_human(frame, bbox: tuple[int, int, int, int], cfg: dict) -> VerificationResult:
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = bbox
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(w - 1, x2)
    y2 = min(h - 1, y2)

    crop = frame[y1:y2, x1:x2]
    reasons: list[str] = []

    if crop.size == 0:
        return VerificationResult(False, ["empty_crop"], {})

    ch, cw = crop.shape[:2]
    aspect_ratio = ch / max(cw, 1)
    area_ratio = (ch * cw) / float(h * w)

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)

    edge = _edge_density(gray)
    texture_var = _texture_variance(gray)
    sat_mean = float(np.mean(hsv[:, :, 1]))
    val_std = float(np.std(hsv[:, :, 2]))

    is_shadow_like = (
        sat_mean <= cfg["shadow_max_saturation"]
        and val_std <= cfg["shadow_max_value_std"]
        and edge < cfg["min_edge_density"]
    )

    aspect_ok = cfg["min_aspect_ratio"] <= aspect_ratio <= cfg["max_aspect_ratio"]
    area_ok = area_ratio >= cfg["min_area_ratio"]
    edge_ok = edge >= cfg["min_edge_density"]
    texture_ok = texture_var >= cfg["min_texture_var"]
    shadow_ok = not is_shadow_like

    if not aspect_ok:
        reasons.append("aspect_ratio_out_of_range")
    if not area_ok:
        reasons.append("bbox_too_small")
    if not edge_ok:
        reasons.append("low_edge_density")
    if not texture_ok:
        reasons.append("low_texture_variance")
    if not shadow_ok:
        reasons.append("shadow_like_region")

    passed_checks = int(aspect_ok) + int(area_ok) + int(edge_ok) + int(texture_ok) + int(shadow_ok)
    min_human_score = float(cfg.get("min_human_score", 0.4))
    human_score = passed_checks / 5.0
    is_human = human_score >= min_human_score

    if is_human:
        reasons.append("passed_fusion_verification")

    metrics = {
        "aspect_ratio": round(aspect_ratio, 3),
        "area_ratio": round(area_ratio, 5),
        "edge_density": round(edge, 5),
        "texture_var": round(texture_var, 3),
        "sat_mean": round(sat_mean, 3),
        "val_std": round(val_std, 3),
        "human_score": round(human_score, 3),
    }

    return VerificationResult(is_human, reasons, metrics)
