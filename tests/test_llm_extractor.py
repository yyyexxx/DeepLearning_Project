"""测试 LLM JSON 解析逻辑（不调用真实 API）。"""

import json
import pytest

from pipeline.llm_extractor import _parse_json_response


class TestParseJSONResponse:
    def test_clean_json(self):
        text = '{"invoice_code": "123", "invoice_number": "456"}'
        result = _parse_json_response(text)
        assert result["invoice_code"] == "123"
        assert result["invoice_number"] == "456"

    def test_json_in_code_block(self):
        text = '```json\n{"invoice_code": "789"}\n```'
        result = _parse_json_response(text)
        assert result["invoice_code"] == "789"

    def test_json_in_generic_code_block(self):
        text = '```\n{"invoice_number": "000"}\n```'
        result = _parse_json_response(text)
        assert result["invoice_number"] == "000"

    def test_json_with_surrounding_text(self):
        text = '这是提取结果：\n{"invoice_code": "ABC", "amount": 100.5}\n以上为识别内容。'
        result = _parse_json_response(text)
        assert result["invoice_code"] == "ABC"
        assert result["amount"] == 100.5

    def test_null_values(self):
        text = '{"invoice_code": null, "invoice_number": "123", "amount": null}'
        result = _parse_json_response(text)
        assert result["invoice_code"] is None
        assert result["invoice_number"] == "123"
        assert result["amount"] is None

    def test_empty_input(self):
        result = _parse_json_response("")
        assert result == {}

    def test_non_json_text(self):
        result = _parse_json_response("这不是 JSON 文本")
        assert result == {}

    def test_malformed_json_in_braces(self):
        text = 'Some text {invoice_code: 123} more text'
        result = _parse_json_response(text)
        assert result == {}  # 不合法 JSON，返回空
