"""PDF 报销单导出。使用 reportlab 生成中文 PDF。"""

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


_FONT_REGISTERED = False


def _register_font():
    global _FONT_REGISTERED
    if _FONT_REGISTERED:
        return
    font_paths = [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simsun.ttc",
        "C:/Windows/Fonts/simhei.ttf",
    ]
    for fp in font_paths:
        try:
            pdfmetrics.registerFont(TTFont("ChineseFont", fp))
            _FONT_REGISTERED = True
            return
        except Exception:
            continue


EXPORT_FIELDS = [
    ("发票代码", "invoice_code"),
    ("发票号码", "invoice_number"),
    ("开票日期", "invoice_date"),
    ("购买方", "purchaser"),
    ("销售方", "seller"),
    ("不含税金额", "amount"),
    ("税额", "tax"),
    ("价税合计", "total"),
    ("报销人", "reimburser"),
    ("报销事由", "reason"),
    ("所属部门", "department"),
    ("提交日期", "submitted_date"),
]


def _fmt(val):
    if val is None:
        return ""
    if isinstance(val, (int, float)):
        return f"¥{val:,.2f}"
    return str(val)


def generate_pdf(data: dict) -> BytesIO:
    _register_font()

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=20*mm, rightMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm)

    title_style = ParagraphStyle("Title", fontName="ChineseFont",
                                 fontSize=18, leading=24, alignment=1)
    label_style = ParagraphStyle("Label", fontName="ChineseFont",
                                 fontSize=11, leading=16)
    value_style = ParagraphStyle("Value", fontName="ChineseFont",
                                 fontSize=11, leading=16)

    elements = [Paragraph("费用报销单", title_style), Spacer(1, 8*mm)]

    table_data = []
    for label, key in EXPORT_FIELDS:
        value = _fmt(data.get(key))
        table_data.append([
            Paragraph(f"<b>{label}</b>", label_style),
            Paragraph(value, value_style),
        ])

    table = Table(table_data, colWidths=[40*mm, 115*mm])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E8F0FE")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(table)

    doc.build(elements)
    buf.seek(0)
    return buf
