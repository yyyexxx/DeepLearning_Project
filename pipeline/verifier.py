"""双信息校验。比对二维码与 LLM/规则提取结果。"""

import re
from typing import Optional

from pipeline.qr_decoder import QRData


class VerificationResult:
    def __init__(self):
        self.passed = True
        self.mismatches: list[dict] = []

    def add_mismatch(self, field: str, qr_val, extracted_val):
        self.passed = False
        self.mismatches.append({
            "field": field,
            "qr": str(qr_val) if qr_val is not None else "",
            "extracted": str(extracted_val) if extracted_val is not None else "",
        })


def verify(qr_data: Optional[QRData], extracted: dict) -> VerificationResult:
    result = VerificationResult()

    if qr_data is None:
        result.passed = False
        result.mismatches.append({"field": "QR_CODE", "qr": "", "extracted": "未检测到二维码"})
        return result

    # 发票号码
    if qr_data.invoice_number and extracted.get("invoice_number"):
        if qr_data.invoice_number.strip() != str(extracted["invoice_number"]).strip():
            result.add_mismatch("invoice_number", qr_data.invoice_number, extracted["invoice_number"])

    # 开票日期（统一转为 YYYY-MM-DD 格式）
    if qr_data.date and extracted.get("invoice_date"):
        qr_date = _normalize_date(qr_data.date)
        ext_date = _normalize_date(str(extracted["invoice_date"]))
        if qr_date and ext_date and qr_date != ext_date:
            result.add_mismatch("invoice_date", qr_date, ext_date)

    # 金额：QR 中存的可能是 不含税金额 或 价税合计
    # 优先比不含税金额，不匹配则试价税合计
    if qr_data.amount is not None:
        matched = False
        for key in ["amount", "total"]:
            ext_val = extracted.get(key)
            if ext_val is not None:
                try:
                    if abs(qr_data.amount - float(ext_val)) <= 0.02:
                        matched = True
                        break
                except (ValueError, TypeError):
                    pass
        if not matched:
            ext_show = f"amount={extracted.get('amount')}, total={extracted.get('total')}"
            result.add_mismatch("amount/total", f"{qr_data.amount:.2f}", ext_show)

    return result


def _normalize_date(val: str) -> Optional[str]:
    val = val.strip()
    # YYYY-MM-DD
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})$", val)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    # YYYYMMDD
    m = re.match(r"(\d{4})(\d{2})(\d{2})$", val)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    # YYYY年MM月DD日
    m = re.match(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", val)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return val
