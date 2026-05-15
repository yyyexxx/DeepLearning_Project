"""测试重复检测器。"""

import pytest

from db.database import SessionLocal, engine
from db.models import Base, Invoice
from pipeline.duplicate_checker import check_duplicate, save_invoice


@pytest.fixture(autouse=True)
def setup_db():
    """每个测试前创建表，测试后清理。"""
    Base.metadata.create_all(bind=engine)
    yield
    # 清理测试数据
    db = SessionLocal()
    db.query(Invoice).delete()
    db.commit()
    db.close()


class TestDuplicateChecker:
    def test_no_duplicate(self):
        db = SessionLocal()
        is_dup, existing = check_duplicate(db, "NEW_CODE", "NEW_NUM")
        assert is_dup is False
        assert existing is None
        db.close()

    def test_duplicate_detected(self):
        db = SessionLocal()
        data = {
            "invoice_code": "DUP_CODE", "invoice_number": "DUP_NUM",
            "amount": 100.0, "reimburser": "测试",
        }
        save_invoice(db, data)
        db.close()

        db2 = SessionLocal()
        is_dup, existing = check_duplicate(db2, "DUP_CODE", "DUP_NUM")
        assert is_dup is True
        assert existing.invoice_code == "DUP_CODE"
        db2.close()

    def test_different_code_same_number(self):
        """不同发票代码、相同号码不视为重复。"""
        db = SessionLocal()
        save_invoice(db, {"invoice_code": "CODE_A", "invoice_number": "123",
                          "amount": 100.0})
        db.close()

        db2 = SessionLocal()
        is_dup, existing = check_duplicate(db2, "CODE_B", "123")
        assert is_dup is False
        db2.close()

    def test_save_and_retrieve(self):
        db = SessionLocal()
        data = {
            "invoice_code": "SAVE_TEST", "invoice_number": "001",
            "amount": 200.0, "tax": 26.0, "total": 226.0,
            "invoice_date": "2024-03-15",
            "purchaser": "购买方", "seller": "销售方",
            "reimburser": "张三", "reason": "差旅", "department": "技术部",
        }
        invoice = save_invoice(db, data)
        assert invoice.id is not None
        assert invoice.amount == 200.0
        assert invoice.reimburser == "张三"
        db.close()
