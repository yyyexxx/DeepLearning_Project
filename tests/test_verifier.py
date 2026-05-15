"""测试双信息校验器：匹配、不匹配、边界情况。"""

import pytest

from pipeline.verifier import verify
from pipeline.qr_decoder import QRData


class TestVerifyPass:
    def test_all_fields_match(self):
        qr = QRData(invoice_code="123", invoice_number="456", amount=100.0,
                     date="2024-01-15", checksum="CHK")
        extracted = {"invoice_code": "123", "invoice_number": "456",
                     "amount": 100.0, "invoice_date": "2024-01-15"}
        result = verify(qr, extracted)
        assert result.passed is True
        assert len(result.mismatches) == 0

    def test_amount_tiny_difference(self):
        """金额差异 ≤ 0.02 视为通过（浮点容忍）。"""
        qr = QRData(invoice_code="123", invoice_number="456", amount=100.0,
                     date="2024-01-15")
        extracted = {"invoice_code": "123", "invoice_number": "456",
                     "amount": 100.01, "invoice_date": "2024-01-15"}
        result = verify(qr, extracted)
        assert result.passed is True


class TestVerifyFail:
    def test_invoice_number_mismatch(self):
        qr = QRData(invoice_code="123", invoice_number="456", amount=100.0,
                     date="2024-01-15")
        extracted = {"invoice_code": "123", "invoice_number": "999",
                     "amount": 100.0, "invoice_date": "2024-01-15"}
        result = verify(qr, extracted)
        assert result.passed is False
        assert any(m["field"] == "invoice_number" for m in result.mismatches)

    def test_date_mismatch(self):
        qr = QRData(invoice_code="123", invoice_number="456", amount=100.0,
                     date="2024-01-15")
        extracted = {"invoice_code": "123", "invoice_number": "456",
                     "amount": 100.0, "invoice_date": "2024-02-20"}
        result = verify(qr, extracted)
        assert result.passed is False
        assert any(m["field"] == "invoice_date" for m in result.mismatches)

    def test_amount_large_difference(self):
        qr = QRData(invoice_code="123", invoice_number="456", amount=100.0,
                     date="2024-01-15")
        extracted = {"invoice_code": "123", "invoice_number": "456",
                     "amount": 200.0, "invoice_date": "2024-01-15"}
        result = verify(qr, extracted)
        assert result.passed is False
        assert any(m["field"] == "amount" for m in result.mismatches)


class TestVerifyQRMissing:
    def test_qr_none(self):
        result = verify(None, {"invoice_number": "456"})
        # QR 为 None 时 passed=False，mismatches 中包含 QR_CODE 标记
        assert result.passed is False
        assert any("QR" in m["field"] for m in result.mismatches)
