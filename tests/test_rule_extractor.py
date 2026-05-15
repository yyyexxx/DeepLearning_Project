"""测试正则规则提取器。"""

import pytest
from pipeline.rule_extractor import extract_with_rules


SAMPLE_OCR = """增值税电子发票
发票代码: 123456789012
发票号码: 87654321
开票日期: 2024年01月15日
购买方名称: 北京测试科技有限公司
销售方名称: 上海数据服务有限公司
合计金额: ¥1234.56
税额: ¥160.49
价税合计 大写：壹仟叁佰玖拾伍元零伍分 小写: ¥1395.05"""


class TestRuleExtractor:
    def test_extract_all_fields(self):
        result = extract_with_rules([(SAMPLE_OCR, 1.0)])
        assert result["invoice_code"] == "123456789012"
        assert result["invoice_number"] == "87654321"
        assert result["invoice_date"] == "2024-01-15"
        assert result["purchaser"] == "北京测试科技有限公司"
        assert result["seller"] == "上海数据服务有限公司"
        assert result["amount"] == 1234.56
        assert result["tax"] == 160.49
        assert result["total"] == 1395.05

    def test_partial_fields(self):
        partial = "发票号码: 11111111\n开票日期: 2024-06-30"
        result = extract_with_rules([(partial, 1.0)])
        assert result["invoice_number"] == "11111111"
        assert result["invoice_date"] == "2024-06-30"
        assert result["invoice_code"] is None
        assert result["purchaser"] is None

    def test_empty_input(self):
        result = extract_with_rules([("", 1.0)])
        assert all(v is None for v in result.values())

    def test_date_formats(self):
        tests = [
            ("开票日期: 2024年1月5日", "2024-01-05"),
            ("2024-10-20", "2024-10-20"),
        ]
        for text, expected in tests:
            result = extract_with_rules([(text, 1.0)])
            assert result["invoice_date"] == expected

    def test_amount_with_yen_sign(self):
        text = "合计金额: ¥ 89.00\n税额: ￥11.57"
        result = extract_with_rules([(text, 1.0)])
        assert result["amount"] == 89.00
        assert result["tax"] == 11.57
