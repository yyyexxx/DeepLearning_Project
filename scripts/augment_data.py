"""数据增强：对 labeled/ 中图片施加变换，模拟不同拍摄环境下的二维码。

变换类型（标签 bbox 同步更新）：
  1. 亮度/对比度       → 模拟强光/弱光
  2. 高斯模糊          → 模拟手抖/失焦
  3. 旋转 ±15°        → 模拟倾斜拍摄
  4. 透视变换          → 模拟侧角拍摄
  5. 缩放 (0.7x~1.3x)  → 模拟不同距离
  6. 椒盐噪声          → 模拟低光传感器噪声

用法：
  python scripts/augment_data.py              # 默认每张图生成 5 个变体
  python scripts/augment_data.py -n 3         # 每张图 3 个变体
"""

import random
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
LABELED_DIR = BASE_DIR / "data" / "labeled"
AUG_DIR = BASE_DIR / "data" / "augmented"
AUG_DIR.mkdir(parents=True, exist_ok=True)


def imread(path: Path):
    data = np.frombuffer(path.read_bytes(), np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def imwrite(path: Path, image):
    _, buf = cv2.imencode(path.suffix, image)
    path.write_bytes(buf)


def read_label(path: Path) -> list[tuple]:
    """读取 YOLO 格式标注: [(cx, cy, w, h), ...] 归一化坐标"""
    if not path.exists():
        return []
    boxes = []
    for line in path.read_text().strip().split("\n"):
        parts = line.split()
        if len(parts) >= 5:
            boxes.append(tuple(map(float, parts[1:5])))
    return boxes


def write_label(path: Path, boxes: list[tuple]):
    path.write_text("\n".join(f"0 {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}" for cx, cy, w, h in boxes))


# ═══════════════════════════════════════════════
# 变换函数（返回新图像 + 新 bbox 列表 或 None 表示 bbox 不变）
# ═══════════════════════════════════════════════

def augment_brightness_contrast(img, boxes):
    """随机亮度/对比度（bbox 不变——不改变几何形状）"""
    alpha = random.uniform(0.4, 1.6)  # 对比度
    beta = random.randint(-40, 40)     # 亮度
    return cv2.convertScaleAbs(img, alpha=alpha, beta=beta), boxes


def augment_blur(img, boxes):
    """随机高斯模糊（bbox 不变）"""
    k = random.choice([3, 5, 7])
    return cv2.GaussianBlur(img, (k, k), 0), boxes


def augment_noise(img, boxes):
    """随机椒盐噪声（bbox 不变）"""
    noisy = img.copy()
    amount = random.uniform(0.001, 0.008)
    h, w = img.shape[:2]
    num = int(h * w * amount)
    for _ in range(num):
        y, x = random.randint(0, h - 1), random.randint(0, w - 1)
        noisy[y, x] = (0, 0, 0) if random.random() < 0.5 else (255, 255, 255)
    return noisy, boxes


def _rotate_bbox(cx, cy, w, h, angle_deg, img_w, img_h):
    """绕图像中心旋转 bbox 后计算新的轴对齐外包框。返回 (new_cx, new_cy, new_w, new_h)"""
    rad = np.radians(-angle_deg)
    cos_a, sin_a = np.cos(rad), np.sin(rad)

    # 原始四角（归一化 → 像素）
    hw, hh = w * img_w / 2, h * img_h / 2
    corners = np.array([
        [-hw, -hh], [hw, -hh], [hw, hh], [-hw, hh]
    ])
    rotated = corners @ np.array([[cos_a, -sin_a], [sin_a, cos_a]])

    cx_px = cx * img_w
    cy_px = cy * img_h
    rotated[:, 0] += cx_px
    rotated[:, 1] += cy_px

    x1, y1 = rotated.min(axis=0)
    x2, y2 = rotated.max(axis=0)
    return ((x1 + x2) / 2 / img_w, (y1 + y2) / 2 / img_h,
            (x2 - x1) / img_w, (y2 - y1) / img_h)


def augment_rotate(img, boxes):
    """随机旋转 ±15°（bbox 同步旋转）"""
    h, w = img.shape[:2]
    angle = random.uniform(-15, 15)
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_REPLICATE)

    new_boxes = []
    for cx, cy, bw, bh in boxes:
        new_boxes.append(_rotate_bbox(cx, cy, bw, bh, angle, w, h))
    return rotated, new_boxes


def augment_perspective(img, boxes):
    """随机透视变换（bbox 同步变换）"""
    h, w = img.shape[:2]
    margin = 0.1
    src = np.float32([[0, 0], [w, 0], [0, h], [w, h]])
    dst = np.float32([
        [random.randint(0, int(w * margin)), random.randint(0, int(h * margin))],
        [w - random.randint(0, int(w * margin)), random.randint(0, int(h * margin))],
        [random.randint(0, int(w * margin)), h - random.randint(0, int(h * margin))],
        [w - random.randint(0, int(w * margin)), h - random.randint(0, int(h * margin))],
    ])
    M = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(img, M, (w, h), borderMode=cv2.BORDER_REPLICATE)

    new_boxes = []
    for cx, cy, bw, bh in boxes:
        # 取 bbox 四角，过透视矩阵
        hw_px, hh_px = bw * w / 2, bh * h / 2
        corners_px = np.float32([
            [cx * w - hw_px, cy * h - hh_px],
            [cx * w + hw_px, cy * h - hh_px],
            [cx * w + hw_px, cy * h + hh_px],
            [cx * w - hw_px, cy * h + hh_px],
        ]).reshape(-1, 1, 2)

        # OpenCV 透视变换需要 3x3，用 perspectiveTransform
        transformed = cv2.perspectiveTransform(corners_px.reshape(1, -1, 2), M)[0]
        x1, y1 = transformed.min(axis=0)
        x2, y2 = transformed.max(axis=0)
        new_boxes.append(((x1 + x2) / 2 / w, (y1 + y2) / 2 / h,
                          (x2 - x1) / w, (y2 - y1) / h))
    return warped, new_boxes


def augment_scale(img, boxes):
    """随机缩放（0.7x~1.3x），填充/裁剪后 bbox 同步调整"""
    h, w = img.shape[:2]
    scale = random.uniform(0.7, 1.3)
    new_w, new_h = int(w * scale), int(h * scale)
    scaled = cv2.resize(img, (new_w, new_h))

    # 如果放大 → 中心裁剪回原始尺寸
    if scale > 1.0:
        x1 = (new_w - w) // 2
        y1 = (new_h - h) // 2
        cropped = scaled[y1:y1 + h, x1:x1 + w]

        new_boxes = []
        for cx, cy, bw, bh in boxes:
            # 缩放后坐标 → 裁剪后坐标
            px = cx * new_w - x1
            py = cy * new_h - y1
            new_boxes.append((px / w, py / h, bw * scale, bh * scale))
        return cropped, new_boxes

    # 如果缩小 → 填充黑边补回原始尺寸
    padded = np.zeros((h, w, 3), dtype=np.uint8)
    x1 = (w - new_w) // 2
    y1 = (h - new_h) // 2
    padded[y1:y1 + new_h, x1:x1 + new_w] = scaled

    new_boxes = []
    for cx, cy, bw, bh in boxes:
        px = cx * new_w + x1
        py = cy * new_h + y1
        new_boxes.append((px / w, py / h, bw * scale, bh * scale))
    return padded, new_boxes


# 变换列表（每个变换的名称 + 函数）
AUGMENTATIONS = [
    ("brightness", augment_brightness_contrast),
    ("blur", augment_blur),
    ("noise", augment_noise),
    ("rotate", augment_rotate),
    ("perspective", augment_perspective),
    ("scale", augment_scale),
]


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--num", type=int, default=5, help="每张图生成的增强变体数 (default: 5)")
    args = parser.parse_args()

    # 复制原始 labeled 数据到 augmented/
    src_imgs = sorted(LABELED_DIR.glob("*.jpg")) + sorted(LABELED_DIR.glob("*.jpeg")) + sorted(LABELED_DIR.glob("*.png"))
    print(f"原始图片: {len(src_imgs)} 张")

    for p in src_imgs:
        shutil.copy2(str(p), str(AUG_DIR / p.name))
        label = LABELED_DIR / f"{p.stem}.txt"
        if label.exists():
            shutil.copy2(str(label), str(AUG_DIR / f"{p.stem}.txt"))

    # 对每张图生成增强变体
    total = 0
    for img_path in src_imgs:
        label_path = LABELED_DIR / f"{img_path.stem}.txt"
        boxes = read_label(label_path)
        if not boxes:
            continue

        img = imread(img_path)
        if img is None:
            continue

        for i in range(args.num):
            aug_fn = random.choice(AUGMENTATIONS)
            try:
                aug_img, aug_boxes = aug_fn[1](img, boxes)
                if aug_boxes is None:
                    continue
                # 裁剪超出 [0,1] 的 bbox
                valid = []
                for cx, cy, bw, bh in aug_boxes:
                    cx = max(0, min(1, cx))
                    cy = max(0, min(1, cy))
                    bw = min(bw, 2 * min(cx, 1 - cx))
                    bh = min(bh, 2 * min(cy, 1 - cy))
                    if bw > 0.005 and bh > 0.005:
                        valid.append((cx, cy, bw, bh))

                if valid:
                    name = f"{img_path.stem}_aug{i:02d}_{aug_fn[0]}"
                    ext = img_path.suffix[1:]
                    imwrite(AUG_DIR / f"{name}.{ext}", aug_img)
                    write_label(AUG_DIR / f"{name}.txt", valid)
                    total += 1
            except Exception:
                continue

    all_files = list(AUG_DIR.glob("*"))
    imgs = [f for f in all_files if f.suffix in (".jpg", ".png")]
    labels = [f for f in all_files if f.suffix == ".txt"]
    print(f"增强后总数: {len(imgs)} 张图片, {len(labels)} 个标注")
    print(f"新增增强样本: {total} 张")
    print(f"输出目录: {AUG_DIR}")
    print(f"\n下一步: python scripts/train_yolo.py --data-dir {AUG_DIR.as_posix()}")


if __name__ == "__main__":
    main()
