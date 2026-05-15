"""百度图片爬虫 — 采集增值税发票图片用于 YOLO 训练。

用法：python scripts/crawl_invoices.py
输出：data/raw/ 目录下约 100 张发票图片。
"""

import os
import time
import requests
from pathlib import Path
from urllib.parse import quote

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "data" / "raw"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 搜索关键词（百度图片）
KEYWORDS = [
    "增值税发票",
    "增值税电子发票",
    "增值税专用发票",
    "增值税普通发票",
]

# 爬取参数
IMAGES_PER_KEYWORD = 25  # 每个关键词下 25 张，共 100 张
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def crawl_baidu_images(keyword: str, count: int) -> int:
    """从百度图片搜索爬取图片 URL 并下载。返回成功下载数。"""
    downloaded = 0
    page = 0

    while downloaded < count:
        # 百度图片搜索 API（非官方，页面结构可能变化时需要调整）
        url = (
            f"https://image.baidu.com/search/acjson"
            f"?tn=resultjson_com&ipn=rj&word={quote(keyword)}"
            f"&pn={page * 30}&rn=30"
        )
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            items = data.get("data", [])
            if not items:
                break

            for item in items:
                if downloaded >= count:
                    break
                img_url = item.get("thumbURL") or item.get("middleURL")
                if not img_url:
                    continue
                try:
                    img_resp = requests.get(img_url, headers=HEADERS, timeout=10)
                    if img_resp.status_code == 200 and len(img_resp.content) > 2000:
                        ext = _guess_ext(img_resp.headers.get("Content-Type", ""))
                        filepath = OUTPUT_DIR / f"{keyword}_{downloaded:03d}.{ext}"
                        filepath.write_bytes(img_resp.content)
                        downloaded += 1
                        print(f"  [{downloaded}/{count}] {filepath.name}")
                except Exception:
                    continue

            page += 1
            time.sleep(1.5)  # 礼貌爬取

        except Exception as e:
            print(f"  请求失败: {e}")
            break

    return downloaded


def _guess_ext(content_type: str) -> str:
    if "png" in content_type:
        return "png"
    if "gif" in content_type:
        return "gif"
    return "jpg"


def main():
    print(f"输出目录: {OUTPUT_DIR}")
    total = 0
    for kw in KEYWORDS:
        print(f"\n爬取关键词: {kw} (目标 {IMAGES_PER_KEYWORD} 张)")
        n = crawl_baidu_images(kw, IMAGES_PER_KEYWORD)
        total += n
        print(f"  实际下载: {n} 张")
    print(f"\n完成! 共下载 {total} 张图片到 {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
