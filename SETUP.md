# 环境配置指南

在新电脑上复现本项目的完整开发环境。

---

## 前置条件

- Git（克隆仓库）
- Anaconda / Miniconda（管理 Python 环境）
- 推荐：NVIDIA 显卡 + CUDA 12.4（YOLO 训练加速，非必须）

---

## 步骤 1：克隆项目

```bash
git clone <你的GitHub仓库地址>
cd 智能发票识别与自动报销填单系统
```

---

## 步骤 2：创建 conda 环境

```bash
conda create -n invoice-recognition python=3.10 -y
conda activate invoice-recognition
```

---

## 步骤 3：安装 PyTorch

**有 NVIDIA 显卡（推荐，国内网络用 conda）**：
```bash
conda install -n invoice-recognition pytorch torchvision pytorch-cuda=12.4 -c pytorch -c nvidia -y
```

**有 NVIDIA 显卡（海外网络，pip 更快）**：
```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
```

**无显卡 / macOS**：
```bash
pip install torch torchvision
```

验证 CUDA 是否可用：
```bash
python -c "import torch; print(torch.cuda.is_available())"
```

---

## 步骤 4：安装其余依赖

```bash
pip install -r requirements_minimal.txt
```

`requirements_minimal.txt` 只列直接依赖（~20 个包），传递依赖由 pip 自动解析。

> 如果某些包安装失败，也可用 `requirements.txt`（完整冻结版，110 个包），但版本兼容性更严格。

---

## 步骤 5：配置 API Key

创建 `.env` 文件（项目根目录），填入通义千问 API Key：

```
DASHSCOPE_API_KEY=sk-你的密钥

# 如需切换 LLM 后端，取消注释并填入：
# LLM_BACKEND=openai
# OPENAI_API_KEY=sk-xxx
```

> 通义千问 Key 获取：https://bailian.console.aliyun.com/ → API-KEY 管理

---

## 步骤 6：验证安装

```bash
python -c "
from app import app
from pipeline.yolo_detector import YOLOQRDetector
from pipeline.paddle_ocr import ocr_image
from pipeline.llm_extractor import extract_with_llm
from pipeline.verifier import verify
from export.excel_writer import generate_excel
print('All OK')
"
```

---

## 步骤 7：启动

```bash
python app.py
# 浏览器打开 http://127.0.0.1:8000
```

---

## 目录结构

```
.
├── .env                    ← API Key（需手动创建，不上传 git）
├── config.py               ← 配置集中管理
├── app.py                  ← 启动入口
├── requirements_minimal.txt ← 精简依赖
├── requirements.txt        ← 完整冻结依赖
├── SETUP.md                ← 本文件
│
├── pipeline/               ← 7 个深模块（核心 DL 逻辑）
├── web/                    ← FastAPI 路由 + Jinja2 模板
├── db/                     ← SQLite ORM 模型
├── export/                 ← Excel / PDF 导出
├── scripts/                ← 爬虫 / 打标 / 训练 脚本
├── data/                   ← 数据集和模型权重
├── docs/                   ← 文档（PRD + ADR + CONTEXT）
└── uploads/                ← 上传文件存储（运行时生成）
```

---

## 常见问题

**Q: Windows 下 `conda run` 报 `chcp` 错误？**
不影响 Python 运行。改用 `conda activate invoice-recognition` 后直接执行 `python` 即可。

**Q: PaddlePaddle 安装失败？**
Windows 上 PaddlePaddle 仅支持 Python 3.8-3.10。本项目锁定 Python 3.10 就是为了兼容。

**Q: WeasyPrint 报 GTK 错误？**
Windows 上 WeasyPrint ≥60 版本已移除 GTK 依赖，pip 安装即可直接用。如果仍报错，检查版本 `pip install weasyprint>=60`。
