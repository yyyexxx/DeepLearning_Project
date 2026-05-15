"""PaddleOCR 离线文字识别封装。"""

import os
import numpy as np

# 禁用 oneDNN 避免 PaddlePaddle 3.x 兼容性问题
os.environ["FLAGS_use_onednn"] = "0"

from paddleocr import PaddleOCR  # noqa: E402
from config import OCR_LANG  # noqa: E402


_ocr_instance = None


def get_ocr():
    global _ocr_instance
    if _ocr_instance is None:
        _ocr_instance = PaddleOCR(lang=OCR_LANG)
    return _ocr_instance


def ocr_image(image: np.ndarray) -> list[tuple[str, float]]:
    """对整张图片做 OCR，返回 [(文字, 置信度), ...] 列表。"""
    ocr = get_ocr()
    # PaddleOCR 3.x: predict() 替代废弃的 ocr()
    results = list(ocr.predict(image))
    if not results:
        return []

    # PaddleOCR 3.x 返回 OCRResult 对象
    items = []
    for result in results:
        for box, text, score in zip(result.boxes, result.texts, result.scores):
            y_center = (box[0][1] + box[2][1]) / 2
            items.append((y_center, text, score))

    items.sort(key=lambda x: x[0])
    return [(text, score) for _, text, score in items]
