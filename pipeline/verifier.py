"""双信息校验。比对二维码与 LLM/规则提取结果。"""

from typing import Optional

from pipeline.qr_decoder import QRData


class VerificationResult:
    def __init__(self):
        self.passed = True
        self.mismatches: list[dict] = []  # [{"field": "invoice_number", "qr": "xxx", "extracted": "yyy"}, ...]

    def add_mismatch(self, field: str, qr_val, extracted_val):
        self.passed = False
        self.mismatches.append({
            "field": field,
            "qr": str(qr_val) if qr_val is not None else "",
            "extracted": str(extracted_val) if extracted_val is not None else "",
        })


def verify(qr_data: Optional[QRData], extracted: dict) -> VerificationResult:
    """比对可校验字段：发票号码、日期、金额。"""
    result = VerificationResult()

    if qr_data is None:
        result.passed = False
        result.mismatches.append({"field": "QR_CODE", "qr": "", "extracted": "未检测到二维码"})
        return result

    # 发票号码
    if qr_data.invoice_number and extracted.get("invoice_number"):
        if qr_data.invoice_number.strip() != str(extracted["invoice_number"]).strip():
            result.add_mismatch("invoice_number", qr_data.invoice_number, extracted["invoice_number"])

    # 开票日期
    if qr_data.date and extracted.get("invoice_date"):
        if qr_data.date.strip() != str(extracted["invoice_date"]).strip():
            result.add_mismatch("invoice_date", qr_data.date, extracted["invoice_date"])

    # 不含税金额（允许小数点差异）
    if qr_data.amount is not None and extracted.get("amount") is not None:
        try:
            if abs(qr_data.amount - float(extracted["amount"])) > 0.02:
                result.add_mismatch("amount", f"{qr_data.amount:.2f}", f"{float(extracted['amount']):.2f}")
        except (ValueError, TypeError):
            result.add_mismatch("amount", qr_data.amount, extracted["amount"])

    return result
