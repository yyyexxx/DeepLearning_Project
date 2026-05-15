"""数据库重复报销检测。"""

from sqlalchemy.orm import Session

from db.models import Invoice


def check_duplicate(db: Session, invoice_code: str, invoice_number: str) -> tuple[bool, Invoice | None]:
    """检查发票代码+号码是否已存在。返回 (是否重复, 已有记录或None)。"""
    existing = (
        db.query(Invoice)
        .filter(
            Invoice.invoice_code == invoice_code,
            Invoice.invoice_number == invoice_number,
        )
        .first()
    )
    if existing:
        return True, existing
    return False, None


def save_invoice(db: Session, data: dict) -> Invoice:
    """保存报销记录到数据库。"""
    from datetime import date as DateType

    invoice = Invoice(
        invoice_code=data.get("invoice_code"),
        invoice_number=data.get("invoice_number"),
        invoice_date=_parse_date(data.get("invoice_date")),
        purchaser=data.get("purchaser"),
        seller=data.get("seller"),
        amount=data.get("amount"),
        tax=data.get("tax"),
        total=data.get("total"),
        reimburser=data.get("reimburser"),
        reason=data.get("reason"),
        department=data.get("department"),
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def _parse_date(val: str | None):
    if not val:
        return None
    try:
        return DateType.fromisoformat(str(val))
    except (ValueError, TypeError):
        return None
