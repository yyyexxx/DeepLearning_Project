"""YOLO 二维码检测模型训练脚本。

自动将标注数据按 80/20 分割为训练集和验证集，然后微调 YOLOv8。

前提：data/labeled/ 中已存在标注好的图片和同名 .txt 标注文件。

用法：
  python scripts/train_yolo.py --split 0.8 --epochs 50
  python scripts/train_yolo.py --split 0.8 --epochs 100 --batch 16 --imgsz 640

输出：data/model_weights/yolo_qr.pt
"""

import random
import shutil
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LABELED_DIR = BASE_DIR / "data" / "labeled"
DATASET_DIR = BASE_DIR / "data" / "dataset"
MODEL_DIR = BASE_DIR / "data" / "model_weights"
MODEL_DIR.mkdir(parents=True, exist_ok=True)


def split_dataset(train_ratio: float = 0.8):
    """将 data/labeled/ 中的图片和标注按比例分割到 data/dataset/train/ 和 data/dataset/val/。"""
    images = sorted(LABELED_DIR.glob("*.jpg")) + sorted(LABELED_DIR.glob("*.png"))
    if not images:
        print(f"错误: {LABELED_DIR} 中未找到图片文件。请先运行 auto_label.py 完成标注。")
        sys.exit(1)

    # 过滤：只保留有同名 .txt 标注的图片
    paired = []
    skipped = 0
    for img in images:
        label = LABELED_DIR / f"{img.stem}.txt"
        if label.exists():
            paired.append(img)
        else:
            skipped += 1

    if not paired:
        print("错误: 没有找到匹配的图片+标注文件对。")
        sys.exit(1)

    random.seed(42)
    random.shuffle(paired)
    split_idx = int(len(paired) * train_ratio)
    train_imgs = paired[:split_idx]
    val_imgs = paired[split_idx:]

    # 清理旧分割
    if DATASET_DIR.exists():
        shutil.rmtree(DATASET_DIR)

    for subset, img_list in [("train", train_imgs), ("val", val_imgs)]:
        img_dir = DATASET_DIR / subset / "images"
        lbl_dir = DATASET_DIR / subset / "labels"
        img_dir.mkdir(parents=True, exist_ok=True)
        lbl_dir.mkdir(parents=True, exist_ok=True)
        for img in img_list:
            shutil.copy2(str(img), str(img_dir / img.name))
            label_src = LABELED_DIR / f"{img.stem}.txt"
            shutil.copy2(str(label_src), str(lbl_dir / f"{img.stem}.txt"))

    print(f"标注图片总数: {len(paired)} (跳过 {skipped} 张无标注)")
    print(f"训练集: {len(train_imgs)} 张 → {DATASET_DIR / 'train'}")
    print(f"验证集: {len(val_imgs)} 张 → {DATASET_DIR / 'val'}")
    return len(train_imgs), len(val_imgs)


def create_data_yaml() -> str:
    """生成 YOLO 训练所需的 data.yaml。"""
    yaml_path = BASE_DIR / "data" / "data.yaml"
    yaml_content = f"""path: {DATASET_DIR.as_posix()}
train: train/images
val: val/images
nc: 1
names: ["qr_code"]
"""
    yaml_path.write_text(yaml_content, encoding="utf-8")
    return str(yaml_path)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="YOLO QR Code 检测训练")
    parser.add_argument("--split", type=float, default=0.8, help="训练集比例 (default: 0.8)")
    parser.add_argument("--epochs", type=int, default=50, help="训练轮数 (default: 50)")
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--skip-split", action="store_true", help="跳过分割，使用已有 data/dataset/ 目录")
    parser.add_argument("--data-dir", type=str, default=None, help="自定义标注目录 (默认: data/labeled)")
    args = parser.parse_args()

    if args.data_dir:
        global LABELED_DIR
        LABELED_DIR = Path(args.data_dir)

    if not args.skip_split:
        split_dataset(train_ratio=args.split)

    data_yaml = create_data_yaml()
    print(f"data.yaml: {data_yaml}")

    from ultralytics import YOLO

    print(f"\n开始训练 (epochs={args.epochs}, batch={args.batch}, imgsz={args.imgsz})...")
    model = YOLO("yolov8n.pt")
    model.train(
        data=data_yaml,
        epochs=args.epochs,
        batch=args.batch,
        imgsz=args.imgsz,
        verbose=True,
    )

    best_pt = MODEL_DIR / "yolo_qr.pt"
    saves = sorted(Path(model.trainer.save_dir).rglob("weights/best.pt"))
    if saves:
        shutil.copy(str(saves[0]), str(best_pt))
        print(f"\n权重已导出: {best_pt}")
    else:
        print("\n警告: 未找到 best.pt，请检查训练输出")


if __name__ == "__main__":
    main()
