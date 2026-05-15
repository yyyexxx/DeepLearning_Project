"""YOLO 二维码检测模型训练脚本。

前提：data/labeled/ 中已存在标注好的图片和 .txt 标注文件。

用法：
  python scripts/train_yolo.py
  python scripts/train_yolo.py --epochs 100 --batch 16

输出：data/model_weights/yolo_qr.pt
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LABELED_DIR = BASE_DIR / "data" / "labeled"
MODEL_DIR = BASE_DIR / "data" / "model_weights"
MODEL_DIR.mkdir(parents=True, exist_ok=True)


def create_data_yaml() -> str:
    """生成 YOLO 训练所需的 data.yaml 配置文件。"""
    yaml_path = BASE_DIR / "data" / "data.yaml"
    yaml_content = f"""path: {LABELED_DIR.as_posix()}
train: {LABELED_DIR.as_posix()}
val: {LABELED_DIR.as_posix()}
nc: 1
names: ["qr_code"]
"""
    yaml_path.write_text(yaml_content, encoding="utf-8")
    return str(yaml_path)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--imgsz", type=int, default=640)
    args = parser.parse_args()

    labels = list(LABELED_DIR.glob("*.txt"))
    if not labels:
        print(f"错误: {LABELED_DIR} 中未找到标注文件。请先运行 auto_label.py 完成标注。")
        sys.exit(1)
    print(f"数据集: {len(labels)} 张标注图片")

    data_yaml = create_data_yaml()

    # Ultralytics 会在训练前自动下载 yolov8n.pt 预训练权重
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

    # 导出最佳权重
    best_pt = MODEL_DIR / "yolo_qr.pt"
    model_path = Path(model.trainer.save_dir) / "weights" / "best.pt"
    if model_path.exists():
        import shutil
        shutil.copy(str(model_path), str(best_pt))
        print(f"\n权重已导出: {best_pt}")
    else:
        print(f"\n警告: 未找到最佳权重文件 {model_path}")


if __name__ == "__main__":
    main()
