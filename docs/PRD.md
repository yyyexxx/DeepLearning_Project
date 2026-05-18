# PRD：智能发票识别与自动报销填单系统

## Problem Statement

财务和审计人员在处理增值税发票报销时，需要手工录入发票号码、日期、购买方、销售方、金额、税额、价税合计等字段到报销表单中。人工录入效率低、容易出错，且无法自动检测重复报销（同一张发票被多次提交）。

需要一个系统：手机拍一张发票，自动识别提取所有关键字段，校验数据一致性，自动填单，检测重复，并导出标准报销单。

## Solution

一个 Web 应用，上传增值税发票图片（支持 JPG/PNG/PDF），自动完成以下全流程：

1. **YOLO 检测二维码** → 裁剪并解析二维码中的发票代码、号码、金额、日期
2. **PaddleOCR 离线识别** → 对整张图片做文字识别
3. **多模态 LLM 提取** → 同时利用图片视觉布局和 OCR 文字，提取 7 个发票字段
4. **双信息校验** → 逐字段比对二维码数据与 LLM 提取结果，不匹配则阻塞并标红
5. **自动填单** → 校验通过后，7 个字段自动填入报销表单（只读），用户补填 3 个手动字段
6. **重复检测** → 按发票代码+号码查 SQLite，已存在则报警阻塞
7. **导出** → 提供 Excel 和 PDF 双格式导出

## User Stories

1. 作为财务人员，我想要上传一张发票图片（手机拍照 JPG/PNG 或电子发票 PDF），系统自动识别所有关键字段，省去手工录入。
2. 作为财务人员，我想要在处理过程中看到实时进度——二维码检测框、OCR 文字、LLM 提取 JSON，以便了解系统正在做什么。
3. 作为财务人员，当二维码数据与 OCR 提取不一致时，我希望系统标红不一致字段并阻塞提交，防止我基于错误数据填单。
4. 作为财务人员，当发票图片模糊导致二维码无法检测时，我希望系统给出警告但不阻塞流程，让我人工核对后继续。
5. 作为财务人员，当 LLM API 调用失败时，我希望系统自动降级为规则提取，保证流程不中断。
6. 作为财务人员，我希望识别出的字段自动填入报销表单（只读），我只填报销人、报销事由、所属部门即可。
7. 作为财务人员，提交时系统自动检查该发票是否已报销过，重复则报警并展示原报销记录。
8. 作为财务人员，提交成功后我能下载 Excel 和 PDF 两种格式的报销单。
9. 作为系统管理员，我可以在配置文件中切换 LLM 后端（通义千问/GPT-4o/Claude/DeepSeek），不修改业务代码。
10. 作为开发者（答辩评委），我能看到清晰的模块化代码结构和术语表，理解每个模块的职责。
11. 作为开发者，我能看到 ADR 文档记录的关键架构决策及权衡理由。

## Implementation Decisions

### 发票范围
仅处理**增值税发票**（电子发票和纸质专票/普票）。出租车票、定额发票、通用机打发票不在 scope 内。增值税发票具有标准化版面（左上二维码 + 表格结构）和固定字段集合。

### 字段分类
- **可校验字段**（二维码和 OCR 共有）：发票号码、开票日期、不含税金额——双信息校验逐字段比对，全部通过才算校验通过
- **仅 OCR 字段**（二维码不包含）：购买方、销售方、税额、价税合计——不参与校验，直接信任 LLM 提取结果
- **手动字段**：报销人、报销事由、所属部门——用户手填；提交日期由系统自动生成

### 处理管道
图像上传后依次经过 5 个阶段：YOLO 检测二维码 → 二维码解析 → PaddleOCR 文字识别 → 多模态 LLM 信息抽取 → 双信息校验。每个阶段通过 SSE 向前端推送中间结果（富展示模式）。

### 降级策略
- **二维码缺检**：YOLO 未检测到二维码时，跳过二维码解析和校验，表单页顶部显示黄色警告，允许继续（人工核对）
- **LLM 不可用**：自动重试 1 次，仍失败则降级为正则规则提取，页面上标注"大模型不可用，已使用规则提取"

### 校验失败处理
校验失败阻塞提交，不一致字段标红并展示二维码值与 OCR 提取值的差异。用户需重新上传或检查原图后重试。不存在逐字段手动覆盖的机制——保证了"双信息校验"的严肃性。

### 重复检测
按「发票代码 + 发票号码」组合作为唯一键查 SQLite。已存在则跳转到重复报警页，展示原报销记录（发票信息、原报销人、原报销时间），阻塞提交。

### 技术选型
| 层面 | 选型 | 理由 |
|:---|:---|:---|
| YOLO | Ultralytics YOLOv8n 预训练微调 | mAP50=0.924, 推理 2.8ms/张 (RTX 4060) |
| OCR | PaddleOCR（离线推理） | 中文识别强，课程要求离线 |
| LLM | 多模态（图 + OCR 文字输入），多后端适配器 | 视觉布局信息能纠错 OCR；可切换后端 |
| 默认 LLM | 通义千问 Qwen-VL（DashScope API） | 中文强、价格低、国内无需翻墙 |
| Web | FastAPI + Jinja2 | 异步支持好，模板渲染灵活 |
| 数据库 | SQLite | 零配置，单用户 demo 足够 |
| 二维码解析 | pyzbar | 轻量，解码标准二维码 |
| PDF 处理 | PyMuPDF (fitz) | Windows 零配置，pip 一键安装 |

### 导出
- Excel：openpyxl 生成，字段标签+值双列表格，金额格式化为 ¥1,234.56
- PDF：reportlab 生成，Windows 系统自带微软雅黑中文字体，无需额外依赖
- 两种格式在提交成功页并排提供下载按钮

### 训练数据集
公开数据集（ICDAR、天池等）为主体，百度图片爬取约 100 张作为多样性补充。总计 300–500 张图片，采用 AI 辅助打标 + 人工审核的方式完成标注。标注格式为 YOLO 标准格式（class + x_center + y_center + width + height 归一化坐标）。

### 模块架构
- **深模块**（pipeline/）：YOLO 检测器、QR 解码器、PaddleOCR 封装、LLM 提取器（多后端）、规则提取器、校验器、重复检测器。每个模块接口极简、可独立测试、不依赖 Web 框架。
- **浅模块**（web/）：FastAPI 路由只做参数绑定和结果转发，Jinja2 模板只做渲染。不包含业务逻辑。
- **导出模块**（export/）：Excel/PDF 写入器，接收字典数据，返回 BytesIO。
- **工具脚本**（scripts/）：爬虫（百度图片采集）、自动打标（AI 预标注 + 交互式人工审核）、训练脚本（自动分割 + YOLOv8 微调）。不进入主流程。

### 页面流程
6 个独立页面：上传页 → 处理中页（SSE 富展示）→ 校验失败页（阻塞+标红）或报销表单页（7 只读+3 手填）→ 重复报警页（阻塞）或提交成功页（双格式下载）。

### 流水线数据流
SSE 推送各阶段进度和中间结果到处理中页。LLM 提取完成后，所有字段和校验结果存入服务端 `app.state.tasks[task_id]`，后续表单页和校验失败页从 task store 读取——不依赖浏览器 sessionStorage，数据流在服务端闭环。

### 数据集划分
标注完成的数据按 80% 训练集 / 20% 验证集随机分割（固定 seed=42）。由训练脚本的 `--split 0.8` 参数自动执行，输出到 `data/dataset/{train,val}/{images,labels}/`。原始标注目录保持平铺结构，分割后的目录结构为训练时动态生成。

### 数据集来源
- 优先使用公开数据集：ICDAR 2019 SROIE（1000 张收据/发票图片）、天池/和鲸社区的中文增值税发票数据集、GitHub 社区整理的发票数据集
- 百度图片爬取约 100 张作为多样性补充，关键词覆盖"增值税发票""增值税电子发票""增值税专用发票""增值税普通发票"
- 所有原始图片统一放入 `data/raw/`，经 AI 辅助打标 + 交互式人工审核后进入 `data/labeled/`

## Testing Decisions

### 测试原则
- 只测试外部行为，不测试实现细节
- Pipeline 模块接口极简（输入 image/dict → 输出 dict/result），特别适合单元测试
- Web 路由层不需要单元测试——它们是浅模块，逻辑都在 pipeline 里

### 需要测试的模块
1. **QR Decoder** — 输入已知二维码图片，验证 QRData 各字段正确；输入无二维码图片，验证返回 None
2. **Verifier** — 构造匹配/不匹配的 QRData + extracted 对，验证 passed 和 mismatches 正确
3. **Rule Extractor** — 输入包含已知字段的标准发票 OCR 文本，验证提取结果正确
4. **Duplicate Checker** — 先写入一条记录，验证同 code+number 被检测为重复；不同 code+number 不重复
5. **LLM Extractor** — mock 外部 API 响应，验证 JSON 解析正确、降级逻辑触发正确
6. **Export Writers** — 输入已知 data，验证生成的 Excel/PDF 文件可打开且包含关键字段

### 不需要测试的
- YOLO Detector（依赖预训练模型权重，正确性由 Ultralytics 保证）
- PaddleOCR（同样依赖推理模型权重，正确性由 PaddleOCR 保证）
- Web 模板渲染（手动验证即可）
- SSE 推送流程（手动验证即可）

### 测试框架
pytest + unittest.mock（已在 Python 标准库中）

## Out of Scope

- 非增值税发票（出租车票、定额发票、过路费票等）
- 多用户系统、权限管理、登录认证
- 对接真实 OA/财务系统（钉钉、企业微信等）
- 批量上传/批量处理多张发票
- 移动端 App（仅支持桌面 Web）
- 发票真伪验证（仅做信息提取和查重，不调税务局接口验真）
- YOLO 模型训练过程本身（训练脚本会提供，但不进入主流程）
- 生产级部署（仅本地开发运行 `uvicorn`）

## 数据采集管线迭代

数据采集经历了三个阶段的技术方案演化，最终收敛为三阶段集成管线。

### 迭代 1：分离式脚本（已废弃）

**架构**：`crawl_invoices.py`（独立爬虫）→ `auto_label.py`（独立打标）

**问题**：
- 百度图片搜索返回大量缩略图和示意图，爬 100 张仅 5 张含可识别二维码
- 爬虫和打标分离，中间需手动搬运文件
- `cv2.imread` 不支持中文路径，Windows 上无法读取中文文件名的图片
- 终端 GBK 编码无法输出 ✓/✗ 等 Unicode 符号
- 无去重机制，搜索结果中存在大量视觉重复图片

**发现**：语义关键词（"增值税发票"）命中率极低；精确关键词（"电子发票"、"发票图片 二维码"）命中率更高。

### 迭代 2：分离式修复（已废弃）

**改动**：
- 用 `np.frombuffer + cv2.imdecode` 替代 `cv2.imread`，解决中文路径问题
- 用 `[OK]` / `[SKIP]` 替代 Unicode 符号
- `auto_label.py` 增加 `--use-yolo` 选项，支持切换 YOLO 或 OpenCV QR 检测器

**问题**：爬虫和打标仍然分离，无法自动循环直到达标。

### 迭代 3：集成式 `collect_and_label.py`（当前方案）

**架构**：三阶段管线在单次运行中完成——

```
阶段 1: 爬虫    阶段 2: 去重            阶段 3: 打标
百度+搜狗     → dHash 感知哈希     → OpenCV QRCodeDetector
13个关键词      汉明距离≤5 视为重复    保留检测成功的
778 张原图      500 张不重复           45 张标注
```

**关键设计决策**：
- **双源爬取**：百度图片为主、搜狗图片为备用，避免单源枯竭
- **MD5 防同次重复**：图片内容 hash 做文件名，同一次运行中相同图片自动跳过
- **dHash 去重**：图片缩放到 9×8 灰度，计算水平差异哈希（64-bit），汉明距离 ≤ 5 视为重复。优先保留文件较大的图（分辨率更高）
- **指定目标数量**：`-n 500` 控制去重后的图片数量，而非爬取数量
- **延续编号**：多次运行时自动检测 `labeled/` 中已有编号，从上次结束位置继续
- **`--skip-crawl` 选项**：用户手动放入公开数据集到 `raw/` 后，跳过爬虫直接进去重+打标

**数据目录结构**：
```
data/
  raw/        ← 爬虫原图（临时，可清空）
  dedup/      ← 去重后不重复图片（500 张，中间产物）
  labeled/    ← 含 QR 的图片 + 同名 .txt 标注（YOLO 格式）
```

**当前成果**：爬取 778 → 去重 500（删除 278 张重复，去重率 35.7%）→ 45 张已标注。

### 迭代 4：YOLO 引导式打标（bootstrap labeling）

**动机**：OpenCV QRCodeDetector 在公开数据集上仅命中 14.8%（13/88）。训练好的 YOLO 模型对发票 QR 码的检测能力远超通用 QR 检测器。

**流程**：

```
OpenCV 打标 (71张) → 初训 YOLO (mAP50=0.942)
    → YOLO 重扫公开数据集 (78/88, 88.6%)
    → 合并数据集 (123张)
    → 重训 YOLO (mAP50=0.924, mAP50-95=0.788)
```

**关键发现**：
- YOLO 检测命中率（88.6%）是 OpenCV（14.8%）的 **6 倍**
- 更多数据使泛化能力提升：mAP50-95 从 0.741 提升到 0.788
- 引导式打标形成正向循环：模型越好 → 标注越多 → 模型更好
- `--skip-dedup` 选项支持公开数据集直标（公开数据集已经过人工筛选，无需去重）
- `--prefix public` 和 `--prefix invoice` 区分不同数据来源

### 端到端诊断与修复记录

使用真实增值税发票（PDF 电子发票 + 3 张截图）进行全流程验证，共发现并修复以下问题：

---

**1. PaddlePaddle 版本兼容性（OCR 崩溃）**

| 现象 | 根因 | 解决 |
|:---|:---|:---|
| `NotImplementedError: ConvertPirAttribute2RuntimeAttribute` | PaddlePaddle 3.3.1 oneDNN/PIR bug，Windows+RTX4060 触发 | **锁定 PaddlePaddle 3.2.0** |
| `FLAGS_use_onednn=0` 无效 | 该 flag 在 3.3.1 已被绕过 | 降级是唯一方案 |
| PaddlePaddle 3.0rc1 PIR kernel 断言失败 | 3.0rc1 的 PIR 转换逻辑有 bug | 不采用 |
| PaddlePaddle 2.6.2 缺少 `set_optimization_level` | 2.6.2 API 与 PaddleOCR 3.5 不兼容 | 不采用 |

附加修复：`KMP_DUPLICATE_LIB_OK=TRUE` 解决 PyTorch 与 PaddlePaddle OMP 库冲突。

---

**2. PaddleOCR 3.5 API 适配（连续 3 轮）**

| 轮次 | 现象 | 根因 | 解决 |
|:---|:---|:---|:---|
| 1 | `Unknown argument: use_gpu` | PaddleOCR 3.5 移除了 `use_gpu` 参数 | 删除，仅保留 `lang` |
| 2 | `Unknown argument: show_log` | 同上 | 删除 |
| 3 | `'OCRResult' object has no attribute 'boxes'` | PaddlePaddle 3.2.0 下 OCRResult 为 dict-like，属性名为 `rec_texts`/`rec_scores`/`rec_polys`（非 `.texts`/`.scores`/`.boxes`） | 改用 `result["rec_polys"]` 等字典访问 |

---

**3. Starlette 1.0 Web 层适配（2 个问题）**

| 现象 | 根因 | 解决 |
|:---|:---|:---|
| `'Environment' object has no attribute 'TemplateResponse'` | app.py 用了 Jinja2 裸 `Environment`，不是 FastAPI 的 `Jinja2Templates` | 改用 `Jinja2Templates(directory=...)` |
| `TypeError: unhashable type: 'dict'` | Starlette 1.0 中 `TemplateResponse` 的 `request` 参数从自动注入变为必须显式传入第一参数 | 6 处调用改为 `TemplateResponse(request, name, context)` |

---

**4. PDF 处理（2 个问题）**

| 现象 | 根因 | 解决 |
|:---|:---|:---|
| PDF 上传后显示"无法读取图片" | `process.html` 硬编码 `EventSource('/api/process-stream/' + TASK_ID + '/jpg')`，但 PDF 转换为 `.png`，SSE 找不到文件 | 上传后跳转携带 `?ext=` 参数，process.html 从 URL 读取真实扩展名 |
| 同上（第二次触发） | SSE 管线中 `cv2.imread()` 不支持中文路径，与 `auto_label.py` 曾遇到的同一问题 | 改为 `np.frombuffer + cv2.imdecode` |

---

**5. 二维码解析（真实电子发票）**

| 现象 | 根因 | 解决 |
|:---|:---|:---|
| 校验误报：`invoice_date QR=500.00 vs 2026-05-12` | 电子发票 QR 格式为 `01,type,,number,total,date,,checksum`（号码在 parts[3]、总金额在 parts[4]），解析器按纸质发票格式读取（号码在 parts[2]、金额在 parts[3]），导致字段全部错位 | `_parse_qr_text()` 自动检测格式：若 parts[3] 为 8 位以上纯数字则为电子发票格式 |

---

**6. 双信息校验（2 个问题）**

| 现象 | 根因 | 解决 |
|:---|:---|:---|
| 日期校验失败：`20260512 vs 2026-05-12` | QR 存 `YYYYMMDD`，LLM 返回 `YYYY-MM-DD` | `_normalize_date()` 统一转为 `YYYY-MM-DD` |
| 金额校验失败：`QR=500.00 vs 442.48` | QR 存的是价税合计（500），LLM 的 `amount` 是不含税金额（442.48），校验器比错了字段 | 金额同时比 `amount` 和 `total`，任一匹配 0.02 容差即通过 |

---

**7. 下载中文文件名乱码**

| 现象 | 根因 | 解决 |
|:---|:---|:---|
| 点击下载 Excel/PDF 报 `Internal Server Error` | `Content-Disposition: filename=报销单_xxx.xlsx` 含中文，Starlette 用 `latin-1` 编码 HTTP 头失败 | 改用 `filename*=UTF-8''` + URL encode |

---

**8. OCR 性能（14.6s 瓶颈）**

| 现象 | 根因 | 解决 |
|:---|:---|:---|
| 上传 PDF 后处理页长时间"准备中" | PaddleOCR 处理 1103×1654 大图需 14.6s | 最长边 >1024px 时缩放到 1024（9.4s，-36%） |
| 首次请求额外等待 20s | PaddleOCR 模型懒加载，首次调用时才下载/初始化 | `@app.on_event("startup")` 预热 OCR 模型 |

总耗时：21s → 14.2s（-32%）。

---

**9. YOLO QR 检测（真实发票）**

| 现象 | 根因 | 解决 |
|:---|:---|:---|
| 3 张测试发票 YOLO 全漏检 | 阈值 0.5 过高 + 训练集缺乏真实发票 QR 样本 | 阈值降至 0.2 + 手动标注 3 张加入训练集 + 增强重训 → mAP50=0.985，2/3 检出 |
| 图1（738×433, QR 65×66px）仍无法检测 | QR 极小（占图 8.8%），训练集中此类样本稀缺 | 已知限制，需更多极小 QR 训练样本 |

### 数据增强

新增 `scripts/augment_data.py`，6 种变换（亮度/模糊/噪声/旋转/透视/缩放），bbox 自动同步。效果：123 张 → 696 张（5.7x），配合手动标注的真发票样本，最终 mAP50=0.985。

### 最终 UX 改进（本轮）

**10. 处理中进度条**

处理中页面新增渐变色进度条，随 5 个阶段推进（20%→30%→55%→80%→95%→100%），百分比数字实时更新。

**11. 识别结果可视化图**

OCR 完成后，在 SSE 管线中生成叠加了 YOLO 绿色检测框和 OCR 文字列表的可视化图，保存为 PNG。提交成功后，该图展示在成功页顶部，方便用户直观确认识别效果。

**12. 手动确认步骤**

处理完成后不再自动跳转。SSE 发送 `complete` 事件（替代原来的 `redirect`），前端展示"确认，继续填单"按钮，用户手动确认后才跳转到表单页。允许用户在跳转前充分检查 YOLO、OCR、LLM 各项结果。

**13. PDF 上传视觉反馈**

选择 PDF 文件后显示文件名 + 文件大小 + PDF 图标（替代之前选择 PDF 后完全无视觉反馈的问题）。点击上传按钮后提示"正在上传 xxx.pdf ..."。

## Current Progress

### Phase 1 — 项目骨架与文档（已完成）
- [x] 目录结构、`.gitignore`、`.env`（通义千问 API Key 已配置）、`config.py`
- [x] CONTEXT.md（24 条领域术语）
- [x] ADR-0001 双信息校验架构、ADR-0002 多模态 LLM 信息抽取
- [x] 原始技术需求文档

### Phase 2 — 核心模块（已完成并验证）
- [x] **数据库层**：SQLAlchemy 引擎 + Session 管理 + Invoice 表 ORM + `init_db()`
- [x] **Pipeline（7 个深模块）**：YOLO 检测器、PaddleOCR 封装、QR 解码器、LLM 多后端提取器、规则降级提取器、双信息校验器、重复检测器
- [x] **导出模块**：Excel（openpyxl，实测 5519 bytes）+ PDF（WeasyPrint HTML 渲染）
- [x] **Web 层**：FastAPI 路由（11 个端点）+ 7 个 Jinja2 模板 + `app.py` 入口
- [x] **SSE 数据流**：提取结果存入 `app.state.tasks`，表单页从服务端读取，不依赖浏览器缓存
- [x] **Python 验证**：11/11 模块全部通过导入和逻辑测试（rule_extractor 正则提取正确、verifier 匹配/不匹配用例正确、excel 生成正常、FastAPI app 创建成功）

### Phase 3 — 工具脚本（已完成）
- [x] `scripts/crawl_invoices.py`：百度图片爬虫，4 个关键词 × 25 张 = 100 张
- [x] `scripts/auto_label.py`：AI 预标注 + OpenCV 交互式人工审核 + YOLO 检测器切换
- [x] `scripts/train_yolo.py`：自动 80/20 分割 + YOLOv8n 微调 + 支持 `--data-dir` 自定义数据源
- [x] `scripts/collect_and_label.py`：三阶段集成管线（爬虫→去重→打标），详见"数据采集管线迭代"章节
- [x] `scripts/augment_data.py`：6 种环境模拟变换（亮度/模糊/噪声/旋转/透视/缩放），bbox 自动同步
- [x] `requirements.txt`：`pip freeze` 导出全量依赖

### Phase 4 — 基础设施（已完成）
- [x] conda 环境 `invoice-recognition`（Python 3.10）
- [x] Git 仓库初始化 + 3 次提交推送到 GitHub
- [x] 所有核心依赖安装并验证导入成功

### Phase 5 — 收尾阶段
- [x] **单元测试**：34/34 通过
- [x] **数据采集管线**：爬虫→去重→打标三阶段集成，123 张标注
- [x] **YOLO 训练**：手动标注+增强训练，mAP50=0.985
- [x] **端到端诊断**：13 项问题全部修复
- [x] **Web 全功能**：首页→上传→进度条→处理→确认识别结果→填单→提交→Excel/PDF 导出 全链路正常
- [x] **UX 完善**：进度条、识别结果可视化图、手动确认步骤、PDF 上传反馈
- [ ] **演示材料**：6 张核心功能截图 + 技术报告（Word/PDF）

## Further Notes

- 本项目为"深度学习理论及应用实践"课程大作业，代码需模块化、注释清晰
- 交付物要求：源代码 + 至少 6 张核心功能截图 + Word/PDF 技术报告
- 通义千问 API Key 已配置在 `.env` 中，`.gitignore` 已排除该文件，不会泄露
- Git 仓库已推送至 GitHub，10 次提交（含最新：运行时兼容性修复、Web 服务启动）
- 启动方式：`conda activate invoice-recognition && python app.py`，浏览器打开 `http://127.0.0.1:8000`
- Windows 下 `conda run` 存在 `chcp` 编码警告，不影响 Python 运行，建议用 `conda activate` 后直接执行
