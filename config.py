"""集中配置管理。所有配置从环境变量读取，有合理默认值。"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent

# 加载 .env 文件
load_dotenv(BASE_DIR / ".env")

# ── LLM API 配置 ────────────────────────────────────────────
# 当前使用的后端: dashscope | openai | anthropic | deepseek
LLM_BACKEND = os.getenv("LLM_BACKEND", "dashscope")

# 各后端 API Key（从环境变量读取）
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

# DashScope 多模态模型名称
DASHSCOPE_MODEL = os.getenv("DASHSCOPE_MODEL", "qwen-vl-max")

# API 调用超时（秒）
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "30"))

# ── YOLO 配置 ───────────────────────────────────────────────
YOLO_MODEL_PATH = os.getenv("YOLO_MODEL_PATH", str(BASE_DIR / "data" / "model_weights" / "yolo_qr.pt"))
YOLO_CONFIDENCE = float(os.getenv("YOLO_CONFIDENCE", "0.5"))

# ── PaddleOCR 配置 ──────────────────────────────────────────
OCR_LANG = os.getenv("OCR_LANG", "ch")
OCR_USE_GPU = os.getenv("OCR_USE_GPU", "false").lower() == "true"

# ── 数据库配置 ──────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'invoice.db'}")

# ── 文件上传配置 ─────────────────────────────────────────────
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads")))
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "10"))
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "pdf"}

# 确保上传目录存在
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
