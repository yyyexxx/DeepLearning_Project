"""AI 辅助打标脚本 — 对发票图片中的二维码区域进行标注。

先使用 OpenCV QRCodeDetector 做初始检测，训练出 YOLO 模型后可切换为 YOLO 检测器。

用法：
  python scripts/auto_label.py                    # 交互式审核
  python scripts/auto_label.py --no-review        # 仅检测，不审核
  python scripts/auto_label.py --use-yolo         # 使用已训练的 YOLO 模型检测
"""

import os
import sys
from pathlib import Path

import cv2

import sys
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
RAW_DIR = BASE_DIR / "data" / "raw"
LABELED_DIR = BASE_DIR / "data" / "labeled"
LABELED_DIR.mkdir(parents=True, exist_ok=True)

CLASS_ID = 0  # qr_code


def _imread(path: Path):
    """OpenCV imread 不支持中文路径，改用 numpy 读取。"""
    import numpy as np
    data = np.frombuffer(path.read_bytes(), np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def detect_with_opencv(image) -> tuple[bool, list[tuple]]:
    """使用 OpenCV 内置 QRCodeDetector 检测二维码。返回 (成功, [bbox列表])。"""
    qcd = cv2.QRCodeDetector()
    data, points, _ = qcd.detectAndDecode(image)
    if points is None:
        # 某些版本返回空 tuple 而非 None
        if isinstance(data, tuple) and not data:
            return False, []
        return False, []

    h, w = image.shape[:2]
    pts = points.reshape(-1, 2)
    x1, y1 = pts.min(axis=0)
    x2, y2 = pts.max(axis=0)
    cx = ((x1 + x2) / 2) / w
    cy = ((y1 + y2) / 2) / h
    bw = (x2 - x1) / w
    bh = (y2 - y1) / h
    return True, [(cx, cy, bw, bh)]


def detect_with_yolo(image, detector) -> tuple[bool, list[tuple]]:
    """使用 YOLO 模型检测。"""
    h, w = image.shape[:2]
    cropped, bbox = detector.detect(image)
    if bbox is None:
        return False, []
    x1, y1, x2, y2 = bbox
    cx = ((x1 + x2) / 2) / w
    cy = ((y1 + y2) / 2) / h
    bw = (x2 - x1) / w
    bh = (y2 - y1) / h
    return True, [(cx, cy, bw, bh)]


def write_label(image_path: Path, boxes: list[tuple]):
    label_path = LABELED_DIR / f"{image_path.stem}.txt"
    with open(label_path, "w") as f:
        for cx, cy, bw, bh in boxes:
            f.write(f"{CLASS_ID} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")

    import shutil
    dst_img = LABELED_DIR / image_path.name
    if not dst_img.exists():
        shutil.copy2(str(image_path), str(dst_img))


def review_mode(use_yolo=False):
    """交互式审核模式。"""
    if use_yolo:
        from pipeline.yolo_detector import YOLOQRDetector
        yolo = YOLOQRDetector()
        print("检测器: YOLO")
        detect_fn = lambda img: detect_with_yolo(img, yolo)
    else:
        print("检测器: OpenCV QRCodeDetector")
        detect_fn = detect_with_opencv

    images = sorted(RAW_DIR.glob("*.jpg")) + sorted(RAW_DIR.glob("*.png"))
    print(f"找到 {len(images)} 张图片\n")

    print("交互审核说明：")
    print("  y = 确认（检测框正确）")
    print("  n = 跳过（放入 rejected/）")
    print("  q = 退出\n")

    rejected_dir = RAW_DIR / "rejected"
    rejected_dir.mkdir(exist_ok=True)

    ok_count = 0
    skip_count = 0

    for img_path in images:
        image = _imread(img_path)
        if image is None:
            print(f"  - {img_path.name} (无法读取)")
            continue

        ok, boxes = detect_fn(image)
        display = image.copy()

        if ok:
            h, w = image.shape[:2]
            for cx, cy, bw, bh in boxes:
                x1 = int((cx - bw / 2) * w)
                y1 = int((cy - bh / 2) * h)
                x2 = int((cx + bw / 2) * w)
                y2 = int((cy + bh / 2) * h)
                cv2.rectangle(display, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(display, "QR_CODE", (x1, y1 - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        else:
            cv2.putText(display, "NO QR DETECTED", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        h, w = display.shape[:2]
        scale = min(1200 / max(h, w), 1.0)
        display = cv2.resize(display, (int(w * scale), int(h * scale)))

        cv2.imshow(f"Review [{ok_count+skip_count+1}/{len(images)}]: {img_path.name}  [y=ok n=skip q=quit]", display)
        key = cv2.waitKey(0) & 0xFF

        if key == ord('y') or key == ord('Y'):
            if ok:
                write_label(img_path, boxes)
                ok_count += 1
                print(f"  [OK] {img_path.name}")
            else:
                print(f"  - {img_path.name} (无检测框，跳过)")
        elif key == ord('n') or key == ord('N'):
            img_path.rename(rejected_dir / img_path.name)
            skip_count += 1
            print(f"  [SKIP] {img_path.name} → rejected/")
        elif key == ord('q'):
            break

        cv2.destroyAllWindows()

    print(f"\n审核完成: 确认 {ok_count} 张, 拒绝 {skip_count} 张")
    labels = list(LABELED_DIR.glob("*.txt"))
    print(f"标注文件总数: {len(labels)}")
    print(f"标注目录: {LABELED_DIR}")


def auto_only(use_yolo=False):
    """无审核批量标注模式。"""
    if use_yolo:
        from pipeline.yolo_detector import YOLOQRDetector
        yolo = YOLOQRDetector()
        detect_fn = lambda img: detect_with_yolo(img, yolo)
    else:
        detect_fn = detect_with_opencv

    images = sorted(RAW_DIR.glob("*.jpg")) + sorted(RAW_DIR.glob("*.png"))
    ok_count = 0

    for img_path in images:
        image = _imread(img_path)
        if image is None:
            continue
        ok, boxes = detect_fn(image)
        if ok:
            write_label(img_path, boxes)
            ok_count += 1
            print(f"  [OK] {img_path.name}")

    print(f"\n完成: {ok_count}/{len(images)} 张标注成功")
    print(f"标注目录: {LABELED_DIR}")


def main():
    use_yolo = "--use-yolo" in sys.argv
    if "--no-review" in sys.argv:
        print("模式: 纯检测标注（无审核）\n")
        auto_only(use_yolo=use_yolo)
    else:
        print("模式: 检测 + 交互式审核\n")
        review_mode(use_yolo=use_yolo)


if __name__ == "__main__":
    main()
