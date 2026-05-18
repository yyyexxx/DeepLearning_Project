"""FastAPI 路由。所有页面和 API 端点。"""

import asyncio
import base64
import json
import os
import uuid
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    RedirectResponse,
    StreamingResponse,
)
from sqlalchemy.orm import Session

from config import ALLOWED_EXTENSIONS, MAX_FILE_SIZE_MB, UPLOAD_DIR
from db.database import get_db
from db.models import init_db
from export.excel_writer import generate_excel
from export.pdf_writer import generate_pdf
from pipeline.duplicate_checker import check_duplicate, save_invoice
from pipeline.llm_extractor import extract_with_llm
from pipeline.paddle_ocr import ocr_image
from pipeline.qr_decoder import decode_qr, QRData
from pipeline.rule_extractor import extract_with_rules
from pipeline.verifier import VerificationResult, verify
from pipeline.yolo_detector import YOLOQRDetector

router = APIRouter()

# 全局 YOLO 检测器（惰性加载）
_yolo: Optional[YOLOQRDetector] = None


def get_yolo() -> YOLOQRDetector:
    global _yolo
    if _yolo is None:
        _yolo = YOLOQRDetector()
    return _yolo


# ── 页面路由 ─────────────────────────────────────────────────


@router.get("/", response_class=HTMLResponse)
async def page_upload(request: Request):
    """① 上传页。"""
    return request.app.state.templates.TemplateResponse(request, "upload.html", {"request": request})


@router.get("/process/{task_id}", response_class=HTMLResponse)
async def page_process(request: Request, task_id: str):
    """② 处理中页。"""
    return request.app.state.templates.TemplateResponse(request, 
        "process.html", {"request": request, "task_id": task_id}
    )


# ── API 路由 ─────────────────────────────────────────────────


@router.post("/api/upload")
async def api_upload(file: UploadFile = File(...)):
    """接收发票图片，返回 task_id。"""
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        return {"error": f"不支持的文件格式: {ext}，仅支持 {ALLOWED_EXTENSIONS}"}
    if ext == "jpeg":
        ext = "jpg"

    task_id = str(uuid.uuid4())
    filepath = UPLOAD_DIR / f"{task_id}.{ext}"
    content = await file.read()
    if len(content) > MAX_FILE_SIZE_MB * 1024 * 1024:
        return {"error": f"文件超过 {MAX_FILE_SIZE_MB}MB 限制"}
    filepath.write_bytes(content)

    # 处理 PDF → 提取第一页为 PNG
    if ext == "pdf":
        import pymupdf
        doc = pymupdf.open(str(filepath))
        page = doc.load_page(0)
        pix = page.get_pixmap(dpi=200)
        png_path = UPLOAD_DIR / f"{task_id}.png"
        pix.save(str(png_path))
        doc.close()
        filepath.unlink()  # 删原 PDF
        filepath = png_path
        ext = "png"

    return {"task_id": task_id, "ext": ext, "filename": file.filename}


@router.get("/api/process-stream/{task_id}/{ext}")
async def api_process_stream(request: Request, task_id: str, ext: str):
    """SSE 推送处理进度和中间结果。"""
    app_state = request.app.state

    async def generate():
        filepath = UPLOAD_DIR / f"{task_id}.{ext}"
        # cv2.imread 不支持中文路径，用 numpy 读取
        image_data = np.frombuffer(filepath.read_bytes(), np.uint8)
        image = cv2.imdecode(image_data, cv2.IMREAD_COLOR)
        if image is None:
            yield _sse("error", {"message": "无法读取图片"})
            return

        # 阶段 1: YOLO 检测
        yield _sse("progress", {"stage": "yolo", "message": "正在检测二维码..."})
        try:
            loop = asyncio.get_event_loop()
            yolo = get_yolo()
            qr_cropped, bbox = await loop.run_in_executor(None, yolo.detect, image)
        except Exception as e:
            yield _sse("error", {"stage": "yolo", "message": f"YOLO 检测失败: {e}"})
            qr_cropped, bbox = None, None

        qr_with_box = _draw_bbox(image, bbox)
        yield _sse("yolo_result", {
            "detected": bbox is not None,
            "bbox": list(bbox) if bbox else None,
            "preview": _img_to_b64(qr_with_box) if qr_with_box is not None else None,
        })

        # 阶段 2: 二维码解析
        qr_data: Optional[QRData] = None
        qr_used = False
        if qr_cropped is not None:
            yield _sse("progress", {"stage": "qr", "message": "正在解析二维码..."})
            qr_data = decode_qr(qr_cropped)
            qr_used = qr_data is not None
            yield _sse("qr_result", {
                "parsed": qr_data is not None,
                "data": {
                    "invoice_code": qr_data.invoice_code if qr_data else None,
                    "invoice_number": qr_data.invoice_number if qr_data else None,
                    "amount": qr_data.amount if qr_data else None,
                    "date": qr_data.date if qr_data else None,
                } if qr_data else None,
            })
        else:
            yield _sse("qr_result", {"parsed": False, "data": None})

        # 阶段 3: OCR
        yield _sse("progress", {"stage": "ocr", "message": "正在进行 OCR 文字识别..."})
        try:
            ocr_results = await loop.run_in_executor(None, ocr_image, image)
        except Exception as e:
            yield _sse("error", {"stage": "ocr", "message": f"OCR 失败: {e}"})
            return
        yield _sse("ocr_result", {
            "text_lines": [{"text": t, "confidence": round(s, 2)} for t, s in ocr_results],
        })

        # 阶段 4: LLM 提取（含降级）
        yield _sse("progress", {"stage": "llm", "message": "正在调用大模型提取信息..."})
        extracted = None
        llm_used = True
        try:
            extracted = await loop.run_in_executor(None, extract_with_llm, ocr_results, filepath)
        except Exception as e:
            yield _sse("progress", {"stage": "llm_fallback", "message": f"大模型调用失败，降级为规则提取: {e}"})
            llm_used = False
            extracted = extract_with_rules(ocr_results)

        yield _sse("llm_result", {
            "source": "llm" if llm_used else "rules",
            "data": extracted,
        })

        # 阶段 5: 校验
        yield _sse("progress", {"stage": "verify", "message": "正在进行双信息校验..."})
        if qr_data is not None:
            vr = verify(qr_data, extracted)
        else:
            vr = VerificationResult()
            vr.passed = None  # type: ignore — 二维码缺失
            vr.mismatches.append({"field": "QR_CODE", "qr": "", "extracted": "未检测到二维码"})

        yield _sse("verify_result", {
            "passed": vr.passed,
            "qr_missing": qr_data is None,
            "mismatches": vr.mismatches,
        })

        # 将提取结果和校验结果存入 task store，供后续页面读取
        app_state.tasks[task_id] = {
            **extracted,
            "llm_source": "llm" if llm_used else "rules",
            "passed": vr.passed,
            "mismatches": vr.mismatches,
            "qr_missing": qr_data is None,
        }

        # 阶段 6: 重定向
        if vr.passed is True:
            yield _sse("redirect", {"url": f"/form/{task_id}/{ext}"})
        elif vr.passed is False:
            yield _sse("redirect", {"url": f"/verify-fail/{task_id}/{ext}"})
        else:
            # 二维码缺失，直接进表单但带警告
            yield _sse("redirect", {"url": f"/form/{task_id}/{ext}?qr_missing=1"})

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/form/{task_id}/{ext}", response_class=HTMLResponse)
async def page_form(request: Request, task_id: str, ext: str, qr_missing: str = "0"):
    """③b 报销表单页。"""
    data = request.app.state.tasks.get(task_id, {}) if hasattr(request.app.state, 'tasks') else {}
    return request.app.state.templates.TemplateResponse(request, "form.html", {
        "request": request,
        "task_id": task_id,
        "ext": ext,
        "qr_missing": qr_missing,
        "data": data,
    })


@router.get("/verify-fail/{task_id}/{ext}", response_class=HTMLResponse)
async def page_verify_fail(request: Request, task_id: str, ext: str):
    """③a 校验失败页。"""
    data = request.app.state.tasks.get(task_id, {}) if hasattr(request.app.state, 'tasks') else {}
    return request.app.state.templates.TemplateResponse(request, "verify_fail.html", {
        "request": request,
        "task_id": task_id,
        "ext": ext,
        "data": data,
    })


@router.post("/api/submit/{task_id}/{ext}")
async def api_submit(
    request: Request,
    task_id: str,
    ext: str,
    invoice_code: str = Form(""),
    invoice_number: str = Form(""),
    invoice_date: str = Form(""),
    purchaser: str = Form(""),
    seller: str = Form(""),
    amount: str = Form(""),
    tax: str = Form(""),
    total: str = Form(""),
    reimburser: str = Form(...),
    reason: str = Form(...),
    department: str = Form(...),
    db: Session = Depends(get_db),
):
    """提交报销单。自动字段以表单值为准（用户可修改），fallback 到 task store。"""
    task_data = request.app.state.tasks.get(task_id, {})

    data = {
        "invoice_code": invoice_code or task_data.get("invoice_code", ""),
        "invoice_number": invoice_number or task_data.get("invoice_number", ""),
        "invoice_date": invoice_date or task_data.get("invoice_date", ""),
        "purchaser": purchaser or task_data.get("purchaser", ""),
        "seller": seller or task_data.get("seller", ""),
        "amount": _safe_float(amount) or task_data.get("amount"),
        "tax": _safe_float(tax) or task_data.get("tax"),
        "total": _safe_float(total) or task_data.get("total"),
        "reimburser": reimburser,
        "reason": reason,
        "department": department,
        "submitted_date": str(date.today()),
    }

    # 重复检测
    is_dup, existing = check_duplicate(db, data["invoice_code"], data["invoice_number"])
    if is_dup:
        return {"error": "duplicate", "existing_id": existing.id,
                "message": f"发票 {data['invoice_code']}-{data['invoice_number']} 已在 {existing.created_at} 报销"}

    invoice = save_invoice(db, data)

    # 清理 task 数据
    request.app.state.tasks.pop(task_id, None)

    return {"ok": True, "invoice_id": invoice.id}


@router.get("/success/{invoice_id}", response_class=HTMLResponse)
async def page_success(request: Request, invoice_id: int, db: Session = Depends(get_db)):
    """④b 提交成功页。"""
    from db.models import Invoice
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    return request.app.state.templates.TemplateResponse(request, "success.html", {
        "request": request,
        "invoice": invoice,
    })


@router.get("/duplicate/{invoice_id}", response_class=HTMLResponse)
async def page_duplicate(request: Request, invoice_id: int, db: Session = Depends(get_db)):
    """④a 重复报警页。"""
    from db.models import Invoice
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    return request.app.state.templates.TemplateResponse(request, "duplicate.html", {
        "request": request,
        "invoice": invoice,
    })


@router.get("/api/export/excel/{invoice_id}")
async def api_export_excel(invoice_id: int, db: Session = Depends(get_db)):
    """导出 Excel。"""
    from db.models import Invoice
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        return {"error": "not found"}

    data = _invoice_to_dict(invoice)
    excel_bytes = generate_excel(data)
    return StreamingResponse(
        excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=报销单_{invoice.invoice_number}.xlsx"},
    )


@router.get("/api/export/pdf/{invoice_id}")
async def api_export_pdf(invoice_id: int, db: Session = Depends(get_db)):
    """导出 PDF。"""
    from db.models import Invoice
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        return {"error": "not found"}

    data = _invoice_to_dict(invoice)
    pdf_bytes = generate_pdf(data)
    return StreamingResponse(
        pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=报销单_{invoice.invoice_number}.pdf"},
    )


# ── 辅助函数 ─────────────────────────────────────────────────


def _safe_float(val: str):
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _draw_bbox(image: np.ndarray, bbox):
    """在图片上绘制检测框。"""
    if image is None:
        return None
    img = image.copy()
    if bbox:
        x1, y1, x2, y2 = bbox
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 3)
    return img


def _img_to_b64(image: np.ndarray) -> str:
    """numpy 图片转 base64 data URL。"""
    _, buf = cv2.imencode(".png", image)
    b64 = base64.b64encode(buf).decode()
    return f"data:image/png;base64,{b64}"


def _invoice_to_dict(invoice) -> dict:
    return {c.name: getattr(invoice, c.name) for c in invoice.__table__.columns}
