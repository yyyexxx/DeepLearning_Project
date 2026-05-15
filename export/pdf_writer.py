"""PDF 报销单导出。从 HTML 模板渲染。"""

from io import BytesIO
from datetime import date

from jinja2 import Template

PDF_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>
  body { font-family: "Microsoft YaHei", "SimSun", sans-serif; padding: 40px; }
  h1 { text-align: center; font-size: 22px; margin-bottom: 24px; }
  table { width: 100%; border-collapse: collapse; }
  td { border: 1px solid #333; padding: 8px 12px; font-size: 13px; }
  td.label { background: #e8f0fe; font-weight: bold; width: 18%; text-align: right; }
  td.value { width: 32%; }
</style>
</head>
<body>
<h1>费用报销单</h1>
<table>
  {% for label, value in rows %}
  <tr>
    <td class="label">{{ label }}</td>
    <td class="value">{{ value }}</td>
    <td class="label">{{ rows2[loop.index0][0] if loop.index0 < rows2|length else '' }}</td>
    <td class="value">{{ rows2[loop.index0][1] if loop.index0 < rows2|length else '' }}</td>
  </tr>
  {% endfor %}
</table>
</body>
</html>"""


def generate_pdf(data: dict) -> BytesIO:
    """从报销数据生成 PDF，返回 BytesIO。"""
    from weasyprint import HTML

    left_fields = [
        ("发票代码", data.get("invoice_code") or ""),
        ("发票号码", data.get("invoice_number") or ""),
        ("开票日期", data.get("invoice_date") or ""),
        ("购买方", data.get("purchaser") or ""),
        ("销售方", data.get("seller") or ""),
        ("不含税金额", _fmt(data.get("amount"))),
    ]
    right_fields = [
        ("税额", _fmt(data.get("tax"))),
        ("价税合计", _fmt(data.get("total"))),
        ("报销人", data.get("reimburser") or ""),
        ("报销事由", data.get("reason") or ""),
        ("所属部门", data.get("department") or ""),
        ("提交日期", data.get("submitted_date", str(date.today()))),
    ]

    template = Template(PDF_TEMPLATE)
    html_str = template.render(rows=left_fields, rows2=right_fields)

    pdf_bytes = HTML(string=html_str).write_pdf()
    output = BytesIO(pdf_bytes)
    output.seek(0)
    return output


def _fmt(val) -> str:
    if val is None:
        return ""
    if isinstance(val, (int, float)):
        return f"¥{val:,.2f}"
    return str(val)
