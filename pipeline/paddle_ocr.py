"""PaddleOCR 离线文字识别封装。"""

import numpy as np
from paddleocr import PaddleOCR

from config import OCR_LANG, OCR_USE_GPU


_ocr_instance = None


def get_ocr():
    global _ocr_instance
    if _ocr_instance is None:
        _ocr_instance = PaddleOCR(lang=OCR_LANG, use_gpu=OCR_USE_GPU)
    return _ocr_instance


def ocr_image(image: np.ndarray) -> list[tuple[str, float]]:
    """对整张图片做 OCR，返回 [(文字, 置信度), ...] 列表。"""
    ocr = get_ocr()
    results = ocr.ocr(image)
    if not results or not results[0]:
        return []
    # 按阅读顺序（从上到下、从左到右）排列
    items = []
    for line in results[0]:
        box, (text, score) = line
        y_center = (box[0][1] + box[2][1]) / 2
        items.append((y_center, text, score))
    items.sort(key=lambda x: x[0])
    return [(text, score) for _, text, score in items]
