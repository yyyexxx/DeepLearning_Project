"""手动标注脚本：鼠标拖拽画出 QR bbox，输出 YOLO 格式标注。

用法：
  python scripts/manual_label.py <图片路径>

操作：
  鼠标拖拽 → 画框
  y → 确认保存
  n → 重画
  q → 退出不保存
"""

import sys
import cv2
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LABELED_DIR = BASE_DIR / "data" / "labeled"
LABELED_DIR.mkdir(parents=True, exist_ok=True)

drawing = False
start_x, start_y = -1, -1
end_x, end_y = -1, -1
bbox_saved = None


def imread(path: Path):
    data = np.frombuffer(path.read_bytes(), np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def draw_bbox(img, x1, y1, x2, y2):
    disp = img.copy()
    cv2.rectangle(disp, (x1, y1), (x2, y2), (0, 255, 0), 2)
    cv2.putText(disp, "QR_CODE", (x1, y1 - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    return disp


def mouse_callback(event, x, y, flags, param):
    global drawing, start_x, start_y, end_x, end_y, bbox_saved
    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        start_x, start_y = x, y
        bbox_saved = None
    elif event == cv2.EVENT_MOUSEMOVE and drawing:
        end_x, end_y = x, y
    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        end_x, end_y = x, y


def main():
    if len(sys.argv) < 2:
        print("用法: python scripts/manual_label.py <图片路径>")
        print("示例: python scripts/manual_label.py 网站测试用图片/xxx.jpeg")
        sys.exit(1)

    img_path = Path(sys.argv[1])
    if not img_path.exists():
        print(f"文件不存在: {img_path}")
        sys.exit(1)

    img = imread(img_path)
    if img is None:
        print(f"无法读取图片: {img_path}")
        sys.exit(1)

    h, w = img.shape[:2]
    print(f"图片: {w}x{h}")
    print("操作: 鼠标拖拽画框 → y确认保存 → n重画 → q退出")

    # 缩放显示（最大 1400px 宽）
    scale = min(1400 / w, 1.0)
    disp_w, disp_h = int(w * scale), int(h * scale)

    global drawing, start_x, start_y, end_x, end_y, bbox_saved

    cv2.namedWindow("Manual Label")
    cv2.setMouseCallback("Manual Label", mouse_callback)

    while True:
        display = img.copy()

        # 缩放回原始坐标
        if drawing:
            x1, y1 = int(min(start_x, end_x) / scale), int(min(start_y, end_y) / scale)
            x2, y2 = int(max(start_x, end_x) / scale), int(max(start_y, end_y) / scale)
            display = draw_bbox(display, x1, y1, x2, y2)
        elif bbox_saved:
            x1, y1, x2, y2 = bbox_saved
            display = draw_bbox(display, x1, y1, x2, y2)
        else:
            cv2.putText(display, "drag mouse to draw QR bbox", (20, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

        display = cv2.resize(display, (disp_w, disp_h))
        cv2.imshow("Manual Label", display)

        key = cv2.waitKey(20) & 0xFF

        if key == ord('y') or key == ord('Y'):
            if not drawing and end_x >= 0:
                x1 = int(min(start_x, end_x) / scale)
                y1 = int(min(start_y, end_y) / scale)
                x2 = int(max(start_x, end_x) / scale)
                y2 = int(max(start_y, end_y) / scale)

                if x2 - x1 < 5 or y2 - y1 < 5:
                    print("框太小，请重画")
                    continue

                # 转为 YOLO 归一化坐标
                cx = ((x1 + x2) / 2) / w
                cy = ((y1 + y2) / 2) / h
                bw = (x2 - x1) / w
                bh = (y2 - y1) / h

                # 保存图片到 labeled/
                import shutil
                dst_img = LABELED_DIR / img_path.name
                shutil.copy2(str(img_path), str(dst_img))

                # 保存标注
                label_path = LABELED_DIR / f"{dst_img.stem}.txt"
                label_path.write_text(f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")

                print(f"\n已保存:")
                print(f"  图片: {dst_img}")
                print(f"  标注: {label_path}")
                print(f"  bbox: ({x1},{y1})-({x2},{y2}) → cx={cx:.4f} cy={cy:.4f} w={bw:.4f} h={bh:.4f}")
                break
            else:
                print("请先画框再按 y")

        elif key == ord('n') or key == ord('N'):
            start_x = start_y = end_x = end_y = -1
            bbox_saved = None
            print("已清除，请重画")

        elif key == ord('q') or key == ord('Q'):
            print("取消")
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
