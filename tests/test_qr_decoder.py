"""测试 QR 解码器：解析、空输入、边界情况。"""

import cv2
import numpy as np
import pytest

from pipeline.qr_decoder import decode_qr, _parse_qr_text, QRData


class TestParseQRText:
    def test_standard_format(self):
        text = "01,123456789012,87654321,1234.56,20240115,CHECKSUM123"
        result = _parse_qr_text(text)
        assert result is not None
        assert result.invoice_code == "123456789012"
        assert result.invoice_number == "87654321"
        assert result.amount == 1234.56
        assert result.date == "20240115"

    def test_minimal_parts(self):
        text = "01,CODE123,NUM456"
        result = _parse_qr_text(text)
        assert result is None  # 少于 5 段

    def test_empty_text(self):
        assert _parse_qr_text("") is None

    def test_non_numeric_amount(self):
        text = "01,CODE123,NUM456,NOT_A_NUM,20240115,CHK"
        result = _parse_qr_text(text)
        assert result is not None
        assert result.amount is None

    def test_partial_data(self):
        text = "01,CODE123,NUM456,,20240115,CHK"
        result = _parse_qr_text(text)
        assert result is not None
        assert result.amount is None


class TestDecodeQR:
    def test_no_qr_in_image(self):
        """纯白图片不含二维码，应返回 None。"""
        img = np.ones((200, 200), dtype=np.uint8) * 255
        result = decode_qr(img)
        assert result is None

    def test_garbage_image(self):
        """随机噪声图片，应返回 None。"""
        img = np.random.randint(0, 255, (200, 200), dtype=np.uint8)
        result = decode_qr(img)
        assert result is None
