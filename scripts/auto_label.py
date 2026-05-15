"""AI 辅助打标脚本 — 对发票图片中的二维码区域进行标注。

流程：
1. 用预训练 YOLO（或当前已训练的模型）初步检测二维码
2. 将检测结果写入 YOLO 标注文件
3. 人工审核：检查每张图片的检测框是否准确，修正偏差

输出 YOLO 格式标注文件（与图片同名的 .txt），格式：
  class_id center_x center_y width height  (归一化坐标)

用法：
  python scripts/auto_label.py                    # AI 预标注 + 交互式审核
  python scripts/auto_label.py --no-review        # 仅 AI 标注，不审核
"""

import os
import sys
from pathlib import Path

import cv2

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
LABELED_DIR = BASE_DIR / "data" / "labeled"
LABELED_DIR.mkdir(parents=True, exist_ok=True)

CLASS_ID = 0  # 只有一个类别: qr_code
CONFIDENCE_THRESHOLD = 0.3


def auto_label_one(image_path: Path, detector) -> tuple[bool, list[tuple]]:
    """对单张图片做 YOLO 检测，返回 (成功, [bbox列表])。bbox 为 (cx, cy, w, h) 归一化坐标。"""
    image = cv2.imread(str(image_path))
    if image is None:
        return False, []

    h, w = image.shape[:2]
    cropped, bbox = detector.detect(image)

    if bbox is None:
        return False, []

    x1, y1, x2, y2 = bbox
    # 转为 YOLO 归一化格式: center_x, center_y, width, height
    cx = ((x1 + x2) / 2) / w
    cy = ((y1 + y2) / 2) / h
    bw = (x2 - x1) / w
    bh = (y2 - y1) / h

    return True, [(cx, cy, bw, bh)]


def write_label(image_path: Path, boxes: list[tuple]):
    """将 bbox 写入 YOLO 格式 .txt 标注文件。"""
    label_path = LABELED_DIR / f"{image_path.stem}.txt"
    with open(label_path, "w") as f:
        for cx, cy, bw, bh in boxes:
            f.write(f"{CLASS_ID} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")

    # 复制图片到 labeled 目录
    import shutil
    dst_img = LABELED_DIR / image_path.name
    if not dst_img.exists():
        shutil.copy2(str(image_path), str(dst_img))


def review_mode():
    """交互式审核模式：逐张显示检测框，人工确认/修正。"""
    from pipeline.yolo_detector import YOLOQRDetector

    detector = YOLOQRDetector()
    images = sorted(RAW_DIR.glob("*.jpg")) + sorted(RAW_DIR.glob("*.png"))

    print(f"找到 {len(images)} 张图片")
    print("交互审核说明：")
    print("  y/Y = 确认（检测框正确）")
    print("  n/N = 跳过（放入 rejected/）")
    print("  其他 = 暂停，上一步的标注保留\n")

    rejected_dir = RAW_DIR / "rejected"
    rejected_dir.mkdir(exist_ok=True)

    ok_count = 0
    skip_count = 0

    for img_path in images:
        image = cv2.imread(str(img_path))
        if image is None:
            continue

        ok, boxes = auto_label_one(img_path, detector)
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

        # 缩放显示
        h, w = display.shape[:2]
        scale = min(1200 / max(h, w), 1.0)
        display = cv2.resize(display, (int(w * scale), int(h * scale)))

        cv2.imshow(f"Review: {img_path.name}  [y=确认 n=跳过 q=退出]", display)
        key = cv2.waitKey(0) & 0xFF

        if key == ord('y') or key == ord('Y'):
            if ok:
                write_label(img_path, boxes)
                ok_count += 1
                print(f"  ✓ {img_path.name}")
            else:
                print(f"  - {img_path.name} (无检测框，跳过)")
        elif key == ord('n') or key == ord('N'):
            img_path.rename(rejected_dir / img_path.name)
            skip_count += 1
            print(f"  ✗ {img_path.name} → rejected/")
        elif key == ord('q'):
            break

        cv2.destroyAllWindows()

    print(f"\n审核完成: 确认 {ok_count} 张, 拒绝 {skip_count} 张")

    # 统计标注文件
    labels = list(LABELED_DIR.glob("*.txt"))
    print(f"标注文件总数: {len(labels)}")
    print(f"标注目录: {LABELED_DIR}")


def auto_only():
    """无审核批量标注模式。"""
    from pipeline.yolo_detector import YOLOQRDetector

    detector = YOLOQRDetector()
    images = sorted(RAW_DIR.glob("*.jpg")) + sorted(RAW_DIR.glob("*.png"))

    ok_count = 0
    for img_path in images:
        ok, boxes = auto_label_one(img_path, detector)
        if ok:
            write_label(img_path, boxes)
            ok_count += 1
            print(f"  ✓ {img_path.name}")

    print(f"\n完成: {ok_count}/{len(images)} 张标注成功")
    print(f"标注目录: {LABELED_DIR}")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--no-review":
        print("模式: 纯 AI 标注（无审核）\n")
        auto_only()
    else:
        print("模式: AI 预标注 + 交互式审核\n")
        review_mode()


if __name__ == "__main__":
    main()
