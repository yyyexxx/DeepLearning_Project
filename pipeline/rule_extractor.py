"""正则规则提取。LLM 不可用时的降级方案。"""

import re
from datetime import date as DateType


def extract_with_rules(ocr_results: list[tuple[str, float]]) -> dict:
    """从 OCR 文本中用正则匹配提取增值税发票字段。"""
    ocr_text = "\n".join([text for text, _ in ocr_results])

    return {
        "invoice_code": _match_first(ocr_text, r"发票代码[：:\s]*([A-Za-z0-9]{10,14})"),
        "invoice_number": _match_first(ocr_text, r"发票号码[：:\s]*([A-Za-z0-9]{6,10})"),
        "invoice_date": _match_date(ocr_text),
        "purchaser": _match_first(ocr_text, r"(?:购买方|名称)[：:\s]*([一-龥\(\)（）\w]{2,40})"),
        "seller": _match_first(ocr_text, r"销售方[：:\s]*([一-龥\(\)（）\w]{2,40})"),
        "amount": _match_amount(ocr_text, r"(?:金额|不含税金额|合计金额)[：:\s]*"),
        "tax": _match_amount(ocr_text, r"(?:税额|税款)[：:\s]*"),
        "total": _match_amount(ocr_text, r"(?:价税合计|大写.*?小写)[：:\s]*"),
    }


def _match_first(text: str, pattern: str) -> str | None:
    m = re.search(pattern, text)
    return m.group(1).strip() if m else None


def _match_date(text: str) -> str | None:
    patterns = [
        r"开票日期[：:\s]*(\d{4})\D+(\d{1,2})\D+(\d{1,2})",
        r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            try:
                y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                DateType(y, mo, d)  # 验证合法性
                return f"{y:04d}-{mo:02d}-{d:02d}"
            except ValueError:
                continue
    return None


def _match_amount(text: str, prefix_pattern: str) -> float | None:
    """匹配金额字段，支持 ¥123.45 和 123.45 格式。"""
    m = re.search(prefix_pattern + r"[¥￥]?\s*(\d+\.?\d*)", text)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return None
