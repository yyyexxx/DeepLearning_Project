"""数据库模型。"""

from datetime import date, datetime

from sqlalchemy import Column, Integer, String, Float, Date, DateTime, create_engine
from sqlalchemy.orm import DeclarativeBase

from db.database import engine


class Base(DeclarativeBase):
    pass


class Invoice(Base):
    """已报销发票记录，用于重复检测和查询。"""

    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_code = Column(String(20), nullable=False, comment="发票代码")
    invoice_number = Column(String(20), nullable=False, comment="发票号码")
    invoice_date = Column(Date, nullable=True, comment="开票日期")
    purchaser = Column(String(200), nullable=True, comment="购买方名称")
    seller = Column(String(200), nullable=True, comment="销售方名称")
    amount = Column(Float, nullable=True, comment="不含税金额")
    tax = Column(Float, nullable=True, comment="税额")
    total = Column(Float, nullable=True, comment="价税合计")
    reimburser = Column(String(50), nullable=True, comment="报销人")
    reason = Column(String(200), nullable=True, comment="报销事由")
    department = Column(String(100), nullable=True, comment="所属部门")
    created_at = Column(DateTime, default=datetime.utcnow, comment="提交时间")


def init_db():
    Base.metadata.create_all(bind=engine)
