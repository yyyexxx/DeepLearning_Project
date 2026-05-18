"""端到端自动化测试：上传测试图片，追踪 SSE 全流程，汇总错误。"""
import json
import requests
from pathlib import Path

BASE = "http://127.0.0.1:8000"
TEST_DIR = Path(r"E:\Codes\深度学习大作业\智能发票识别与自动报销填单系统\网站测试用图片")
IMAGES = sorted(TEST_DIR.glob("*.*"))

print(f"找到 {len(IMAGES)} 张测试图片\n")

all_results = []

for idx, img_path in enumerate(IMAGES):
    print(f"{'='*60}")
    print(f"测试 {idx+1}/{len(IMAGES)}: {img_path.name} ({img_path.stat().st_size/1024:.0f}KB)")
    print(f"{'='*60}")

    report = {"file": img_path.name, "events": {}, "errors": []}

    # ── 上传 ──
    print("  [上传] ...", end=" ", flush=True)
    with open(img_path, "rb") as f:
        resp = requests.post(f"{BASE}/api/upload", files={"file": (img_path.name, f)}, timeout=30)
    data = resp.json()
    if "error" in data:
        print(f"FAIL: {data['error']}")
        report["errors"].append({"stage": "upload", "msg": data["error"]})
        all_results.append(report)
        continue
    print(f"OK (id={data['task_id'][:8]}...)")

    # ── SSE 流 ──
    print("  [SSE] 跟踪处理流...")
    events_seen = []

    try:
        resp = requests.get(
            f"{BASE}/api/process-stream/{data['task_id']}/{data['ext']}",
            stream=True, timeout=120
        )
        current_event = None
        buf = ""
        for chunk in resp.iter_content(chunk_size=1, decode_unicode=True):
            if chunk is None:
                continue
            buf += chunk
            while "\n\n" in buf:
                block, buf = buf.split("\n\n", 1)
                lines = block.strip().split("\n")
                event_name = None
                event_data = None
                for line in lines:
                    if line.startswith("event:"):
                        event_name = line[6:].strip()
                    elif line.startswith("data:"):
                        try:
                            event_data = json.loads(line[5:].strip())
                        except Exception:
                            event_data = line[5:].strip()
                if event_name:
                    events_seen.append((event_name, event_data))
                    report["events"][event_name] = event_data

                    # 简短打印
                    if event_name == "progress":
                        print(f"    [{event_data.get('stage','?')}] {event_data.get('message','')}")
                    elif event_name == "error":
                        print(f"    [ERROR] {event_data.get('message','')}")
                        report["errors"].append({"stage": event_data.get("stage","?"), "msg": event_data.get("message","")})
                    elif event_name == "yolo_result":
                        print(f"    [YOLO] detected={event_data.get('detected')}")
                    elif event_name == "qr_result":
                        print(f"    [QR] parsed={event_data.get('parsed')}")
                    elif event_name == "ocr_result":
                        lines_count = len(event_data.get("text_lines", []))
                        print(f"    [OCR] {lines_count} lines")
                    elif event_name == "llm_result":
                        print(f"    [LLM] source={event_data.get('source')}, fields={len(event_data.get('data',{}))}")
                    elif event_name == "verify_result":
                        print(f"    [校验] passed={event_data.get('passed')}, qr_missing={event_data.get('qr_missing')}")
                    elif event_name == "redirect":
                        print(f"    [REDIRECT] {event_data.get('url')}")
    except Exception as e:
        print(f"    SSE 异常: {e}")
        report["errors"].append({"stage": "sse", "msg": str(e)})

    all_results.append(report)

# ── 汇总 ──
print(f"\n\n{'='*60}")
print("汇总报告")
print(f"{'='*60}")

for r in all_results:
    errors = r.get("errors", [])
    events = r.get("events", {})
    status = "PASS" if not errors else "FAIL"
    print(f"\n  {r['file']}  [{status}]")
    if errors:
        for e in errors:
            print(f"    错误 [{e['stage']}]: {e['msg']}")
    if not errors:
        for name in ["yolo_result", "qr_result", "ocr_result", "llm_result", "verify_result", "redirect"]:
            if name in events:
                v = events[name]
                print(f"    {name}: {json.dumps(v, ensure_ascii=False)[:100]}")
