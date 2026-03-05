from __future__ import annotations

from dataclasses import dataclass

from ultralytics import YOLO


@dataclass
class Detection:
    cls_id: int
    cls_name: str
    conf: float
    x1: int
    y1: int
    x2: int
    y2: int


class YoloDetector:
    def __init__(self, weights: str, conf_threshold: float, iou_threshold: float) -> None:
        self.model = YOLO(weights)
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold

    def infer(self, frame):
        results = self.model.predict(
            frame,
            conf=self.conf_threshold,
            iou=self.iou_threshold,
            verbose=False,
        )
        detections: list[Detection] = []
        result = results[0]

        if result.boxes is None:
            return detections

        names = result.names
        for box in result.boxes:
            cls_id = int(box.cls.item())
            conf = float(box.conf.item())
            x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
            detections.append(
                Detection(
                    cls_id=cls_id,
                    cls_name=names[cls_id],
                    conf=conf,
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                )
            )
        return detections
