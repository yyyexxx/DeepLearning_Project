"""YOLO 二维码检测与裁剪。基于 Ultralytics YOLO。"""

import cv2
import numpy as np
from ultralytics import YOLO

from config import YOLO_MODEL_PATH, YOLO_CONFIDENCE


class YOLOQRDetector:
    def __init__(self, model_path: str = YOLO_MODEL_PATH):
        self.model = YOLO(model_path)

    def detect(self, image: np.ndarray):
        """在图片上检测二维码区域，返回 (裁剪图, 检测框坐标) 或 (None, None)。"""
        results = self.model(image, conf=YOLO_CONFIDENCE, verbose=False)
        if not results or len(results[0].boxes) == 0:
            return None, None

        # 取置信度最高的检测框
        boxes = results[0].boxes
        best = boxes[boxes.conf.argmax()]
        x1, y1, x2, y2 = map(int, best.xyxy[0].tolist())

        cropped = image[y1:y2, x1:x2]
        return cropped, (x1, y1, x2, y2)
