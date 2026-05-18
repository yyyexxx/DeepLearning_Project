"""二维码解码。使用 pyzbar 解析二维码内容。"""

from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np
from pyzbar.pyzbar import decode


@dataclass
class QRData:
    invoice_code: str      # 发票代码 (12位)
    invoice_number: str    # 发票号码 (8位)
    amount: Optional[float] = None     # 不含税金额
    date: Optional[str] = None         # 开票日期
    checksum: Optional[str] = None     # 校验码


def decode_qr(image: np.ndarray) -> Optional[QRData]:
    """解码二维码图片，成功返回 QRData，失败返回 None。"""
    decoded = decode(image)
    if not decoded:
        return None

    raw_text = decoded[0].data.decode("utf-8", errors="ignore")
    return _parse_qr_text(raw_text)


def _parse_qr_text(text: str) -> Optional[QRData]:
    """解析增值税发票二维码文本（逗号分隔格式）。

    增值税发票 QR 码有两种常见格式：
      - 格式A（纸质）: version, invoice_code, invoice_number, amount, date, checksum
      - 格式B（电子）: version, type, ?, invoice_number, total, date, ?, checksum

    通过检查各字段的形态自动判断格式。
    """
    parts = [p.strip() for p in text.split(",")]
    if len(parts) < 6:
        return None

    # 判断格式：如果 parts[3] 是纯数字长串（发票号码特征），则为电子发票格式
    if len(parts) > 4 and parts[3].isdigit() and len(parts[3]) >= 8:
        # 电子发票格式
        invoice_code = parts[1] if len(parts[1]) >= 10 and parts[1].isdigit() else None
        invoice_number = parts[3]
        amount = _safe_float(parts[4])
        date = parts[5] if len(parts) > 5 else None
        checksum = parts[-1] if len(parts[-1]) <= 6 else None
    else:
        # 传统纸质发票格式
        invoice_code = parts[1] if len(parts) > 1 else parts[0]
        invoice_number = parts[2] if len(parts) > 2 else parts[1]
        amount = _safe_float(parts[3]) if len(parts) > 3 else None
        date = parts[4] if len(parts) > 4 else None
        checksum = parts[5] if len(parts) > 5 else None

    return QRData(
        invoice_code=invoice_code,
        invoice_number=invoice_number,
        amount=amount,
        date=date,
        checksum=checksum,
    )


def _safe_float(s: str) -> Optional[float]:
    try:
        return float(s)
    except ValueError:
        return None
