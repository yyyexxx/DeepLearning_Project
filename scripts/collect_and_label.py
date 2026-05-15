"""集成数据采集管线：爬虫 → 去重 → 500张 → 打标。

用法：
  python scripts/collect_and_label.py              # 完整管线
  python scripts/collect_and_label.py --skip-crawl # 跳过爬取，只做去重+打标
  python scripts/collect_and_label.py -n 300       # 目标 300 张
"""

import hashlib
import sys
import time
import requests
import numpy as np
import cv2
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
DEDUP_DIR = BASE_DIR / "data" / "dedup"
LABELED_DIR = BASE_DIR / "data" / "labeled"
RAW_DIR.mkdir(parents=True, exist_ok=True)
DEDUP_DIR.mkdir(parents=True, exist_ok=True)
LABELED_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

BAIDU_URL = "https://image.baidu.com/search/acjson"
CLASS_ID = 0
HAMMING_THRESHOLD = 5  # 汉明距离 <= 5 视为重复

KEYWORDS = [
    "电子发票",
    "增值税电子普通发票",
    "电子发票 打印",
    "增值税发票 高清",
    "发票图片 二维码",
    "增值税普通发票",
    "电子发票 截图",
    "增值税发票 电子",
    "全电发票",
    "电子发票 样式",
    "增值税专用发票 电子",
    "发票 二维码",
    "电子发票样本",
]


# ═══════════════════════════════════════════════════════════
# 图片读写（兼容中文路径）
# ═══════════════════════════════════════════════════════════

def imread(path: Path):
    data = np.frombuffer(path.read_bytes(), np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def imwrite(path: Path, image):
    _, buf = cv2.imencode(path.suffix, image)
    path.write_bytes(buf)


# ═══════════════════════════════════════════════════════════
# 阶段 1：爬虫
# ═══════════════════════════════════════════════════════════

def crawl_baidu(keyword: str, count: int) -> int:
    """爬取百度图片，存入 RAW_DIR。返回本次下载数。"""
    downloaded = 0
    page = 0
    while downloaded < count and page < 15:
        url = (
            f"{BAIDU_URL}"
            f"?tn=resultjson_com&ipn=rj"
            f"&word={requests.utils.quote(keyword)}"
            f"&pn={page * 30}&rn=30"
        )
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            data = resp.json()
            items = data.get("data", [])
            if not items:
                break
            for item in items:
                if downloaded >= count:
                    break
                img_url = item.get("thumbURL") or item.get("middleURL") or item.get("hoverURL")
                if not img_url:
                    continue
                try:
                    r = requests.get(img_url, headers=HEADERS, timeout=10)
                    if r.status_code == 200 and len(r.content) > 5000:
                        ct = r.headers.get("Content-Type", "")
                        ext = "png" if "png" in ct else ("gif" if "gif" in ct else "jpg")
                        # 用内容 hash 做文件名，防止同一下载任务中重复
                        fhash = hashlib.md5(r.content).hexdigest()[:12]
                        filepath = RAW_DIR / f"raw_{fhash}.{ext}"
                        if not filepath.exists():
                            filepath.write_bytes(r.content)
                            downloaded += 1
                except Exception:
                    continue
            page += 1
            time.sleep(0.6)
        except Exception:
            break
    return downloaded


def crawl_sogou(keyword: str, count: int) -> int:
    """搜狗图片搜索备用源。返回下载数。"""
    downloaded = 0
    page = 0
    while downloaded < count and page < 5:
        url = (
            f"https://pic.sogou.com/pics"
            f"?query={requests.utils.quote(keyword)}"
            f"&mode=1&start={page * 48}&reqType=ajax"
        )
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            try:
                data = resp.json()
                items = data.get("items", [])
                for item in items:
                    if downloaded >= count:
                        break
                    img_url = item.get("picUrl") or item.get("thumbUrl")
                    if not img_url:
                        continue
                    try:
                        r = requests.get(img_url, headers=HEADERS, timeout=10)
                        if r.status_code == 200 and len(r.content) > 5000:
                            ext = "jpg"
                            if "png" in (r.headers.get("Content-Type", "")):
                                ext = "png"
                            fhash = hashlib.md5(r.content).hexdigest()[:12]
                            filepath = RAW_DIR / f"raw_{fhash}.{ext}"
                            if not filepath.exists():
                                filepath.write_bytes(r.content)
                                downloaded += 1
                    except Exception:
                        continue
            except Exception:
                pass
            page += 1
            time.sleep(0.8)
        except Exception:
            break
    return downloaded


# ═══════════════════════════════════════════════════════════
# 阶段 2：感知哈希去重
# ═══════════════════════════════════════════════════════════

def dhash(image, hash_size=8):
    """计算图片的差异哈希 (dHash)。返回 64-bit 整数。"""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (hash_size + 1, hash_size))
    diff = resized[:, 1:] > resized[:, :-1]
    # 转为 64-bit 整数
    h = 0
    for bit in diff.flatten():
        h = (h << 1) | int(bit)
    return h


def hamming_distance(h1: int, h2: int) -> int:
    """计算两个 64-bit hash 的汉明距离。"""
    return (h1 ^ h2).bit_count()


def deduplicate(raw_dir: Path, dedup_dir: Path, target: int) -> int:
    """对 raw_dir 中所有图片做感知哈希去重，结果写入 dedup_dir。
    返回去重后的图片数量。
    """
    images = sorted(raw_dir.glob("*.jpg")) + sorted(raw_dir.glob("*.png"))
    if not images:
        print("  raw/ 目录为空，跳过去重。")
        return 0

    print(f"  原始图片: {len(images)} 张，计算哈希...")

    # 计算所有图片的 dHash
    hashes = {}  # path -> hash
    for p in images:
        img = imread(p)
        if img is not None:
            hashes[p] = dhash(img)

    print(f"  成功计算 {len(hashes)} 个哈希，聚类去重...")

    # 贪心聚类：按图片尺寸降序（优先保留大图），逐一检查
    paths = sorted(hashes.keys(), key=lambda p: p.stat().st_size, reverse=True)
    kept_paths = []
    kept_hashes = []

    for p in paths:
        h = hashes[p]
        is_dup = False
        for kh in kept_hashes:
            if hamming_distance(h, kh) <= HAMMING_THRESHOLD:
                is_dup = True
                break
        if not is_dup:
            kept_paths.append(p)
            kept_hashes.append(h)
            # 达到目标数量即停止
            if len(kept_paths) >= target:
                break

    # 复制到 dedup 目录
    for f in dedup_dir.glob("*"):
        f.unlink()
    for i, p in enumerate(kept_paths):
        dst = dedup_dir / p.name
        dst.write_bytes(p.read_bytes())

    dup_count = len(images) - len(kept_paths)
    print(f"  去重: {len(images)} → {len(kept_paths)} (删除 {dup_count} 张重复)")
    return len(kept_paths)


# ═══════════════════════════════════════════════════════════
# 阶段 3：QR 检测打标
# ═══════════════════════════════════════════════════════════

def detect_qr(image) -> tuple[bool, list[float]]:
    qcd = cv2.QRCodeDetector()
    data, points, _ = qcd.detectAndDecode(image)
    if points is None or (isinstance(data, tuple) and not data):
        return False, []
    h, w = image.shape[:2]
    pts = points.reshape(-1, 2)
    x1, y1 = pts.min(axis=0)
    x2, y2 = pts.max(axis=0)
    cx = ((x1 + x2) / 2) / w
    cy = ((y1 + y2) / 2) / h
    bw = (x2 - x1) / w
    bh = (y2 - y1) / h
    return True, [cx, cy, bw, bh]


def label_images(src_dir: Path, labeled_dir: Path):
    """对 src_dir 中所有图片做 QR 检测，成功的写入 labeled_dir。"""
    images = sorted(src_dir.glob("*.jpg")) + sorted(src_dir.glob("*.png"))
    if not images:
        print("  无图片可标注。")
        return 0

    # 获取已有标注数量，延续编号
    existing_labels = len(list(labeled_dir.glob("*.txt")))
    cnt = existing_labels

    kept = 0
    for p in images:
        img = imread(p)
        if img is None:
            continue
        ok, bbox = detect_qr(img)
        if ok:
            ext = p.suffix[1:]  # 去掉点号
            img_dst = labeled_dir / f"invoice_{cnt:04d}.{ext}"
            label_dst = labeled_dir / f"invoice_{cnt:04d}.txt"
            imwrite(img_dst, img)
            label_dst.write_text(
                f"{CLASS_ID} {bbox[0]:.6f} {bbox[1]:.6f} {bbox[2]:.6f} {bbox[3]:.6f}")
            cnt += 1
            kept += 1
            print(f"  [OK] {img_dst.name}")

    print(f"  打标: {len(images)} 张扫描 → {kept} 张含二维码")
    return kept


# ═══════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="爬虫 → 去重 → 500张 → 打标")
    parser.add_argument("-n", "--target", type=int, default=500, help="目标不重复图片数 (default: 500)")
    parser.add_argument("--skip-crawl", action="store_true", help="跳过爬取阶段")
    args = parser.parse_args()

    # ── 阶段 1：爬虫 ─────────────────────────────────
    if not args.skip_crawl:
        print("═" * 50)
        print("阶段 1/3：爬取图片")
        print("═" * 50)
        current_raw = len(list(RAW_DIR.glob("*")))
        # 爬足够的原始图片（经验：去重和 QR 检测会筛掉约 90%）
        raw_target = args.target * 12  # 爬 ~6000 张来保证去重后有 500
        to_fetch = max(0, raw_target - current_raw)

        if to_fetch > 0:
            total_dl = 0
            cycle = 0
            while total_dl < to_fetch:
                kw = KEYWORDS[cycle % len(KEYWORDS)]
                batch = min(50, to_fetch - total_dl)
                n = crawl_baidu(kw, batch)
                if n < 5:
                    n2 = crawl_sogou(kw, batch - n)
                    n += n2
                total_dl += n
                cycle += 1
                print(f"  [{kw}] +{n} | 累计 raw: {len(list(RAW_DIR.glob('*')))}")
                if n == 0 and cycle >= 5:
                    break
                time.sleep(0.5)
        else:
            print(f"  raw/ 已有 {current_raw} 张，跳过爬取。")

    # ── 阶段 2：去重 ─────────────────────────────────
    print("\n" + "═" * 50)
    print("阶段 2/3：感知哈希去重")
    print("═" * 50)
    dedup_count = deduplicate(RAW_DIR, DEDUP_DIR, args.target)

    # ── 阶段 3：打标 ─────────────────────────────────
    print("\n" + "═" * 50)
    print("阶段 3/3：QR 检测打标")
    print("═" * 50)
    label_kept = label_images(DEDUP_DIR, LABELED_DIR)

    # ── 汇总 ────────────────────────────────────────
    total_labels = len(list(LABELED_DIR.glob("*.txt")))
    print("\n" + "═" * 50)
    print(f"管线完成")
    print(f"  raw/      原始爬取")
    print(f"  dedup/    去重后: {dedup_count} 张")
    print(f"  labeled/  已标注: {total_labels} 张")
    print("═" * 50)

    if total_labels < 50:
        print("警告: 标注数据不足 50 张，YOLO 训练效果可能较差。")


if __name__ == "__main__":
    main()
