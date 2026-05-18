"""PaddleOCR 离线文字识别封装。"""

import os
import numpy as np

# PaddlePaddle 3.3.1 oneDNN bug → 锁定 3.2.0
# OMP 库与 PyTorch 冲突修复
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

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

    # PaddleOCR 3.x 返回 OCRResult (dict-like)，字段名为 rec_* 前缀
    items = []
    for result in results:
        for poly, text, score in zip(result["rec_polys"], result["rec_texts"], result["rec_scores"]):
            # poly 是四点坐标 [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
            y_center = (poly[0][1] + poly[2][1]) / 2
            items.append((y_center, text, score))

    items.sort(key=lambda x: x[0])
    return [(text, score) for _, text, score in items]
