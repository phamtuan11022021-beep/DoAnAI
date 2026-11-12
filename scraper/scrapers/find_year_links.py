import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


URL = (
    "https://thongtintuyensinh.vn/"
    "Tong-hop-diem-chuan-tuyen-sinh-DHCD-cac-nam_C309_D13729.htm"
)

TARGET_YEARS = ("2023", "2024", "2025", "2026")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/153.0.0.0 Safari/537.36"
    )
}

# Những cụm này không phải trang điểm chuẩn đại học chính mà dự án cần.
EXCLUDE_TEXT = (
    "lớp 10",
    "học bạ",
    "đánh giá năng lực",
    "đgnl",
    "xét tuyển sớm",
    "điểm sàn",
    "nhận hồ sơ",
    "ngưỡng đầu vào",
)


def clean_text(value):
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\xa0", " ")).strip()


def score_year_link(text, year):
    """
    Chấm điểm để mỗi năm chỉ chọn đúng trang tổng hợp phù hợp nhất.
    2023/2024 ưu tiên trang ghi rõ điểm thi TN THPT.
    2025/2026 ưu tiên trang tổng hợp điểm chuẩn của toàn quốc.
    """
    low = clean_text(text).lower()

    if year not in low:
        return -10_000

    if "điểm chuẩn" not in low and "điểm trúng tuyển" not in low:
        return -10_000

    if any(bad in low for bad in EXCLUDE_TEXT):
        return -10_000

    score = 0

    if "tổng hợp" in low:
        score += 40

    if "điểm chuẩn" in low:
        score += 30

    if "điểm trúng tuyển" in low:
        score += 25

    if "đại học" in low or "đh" in low:
        score += 15

    if year in {"2023", "2024"}:
        if "tn thpt" in low or "tốt nghiệp thpt" in low:
            score += 100
        else:
            score -= 20

    if year in {"2025", "2026"}:
        if "các trường" in low or "toàn quốc" in low:
            score += 30

    return score


def find_year_links():
    response = requests.get(
        URL,
        headers=HEADERS,
        timeout=20,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")

    candidates = {year: [] for year in TARGET_YEARS}

    for anchor in soup.find_all("a", href=True):
        text = clean_text(anchor.get_text(" ", strip=True))
        href = urljoin(URL, anchor["href"])

        for year in TARGET_YEARS:
            score = score_year_link(text, year)

            if score > -10_000:
                candidates[year].append(
                    {
                        "year": int(year),
                        "text": text,
                        "url": href,
                        "score": score,
                    }
                )

    result = {}

    for year in TARGET_YEARS:
        rows = candidates[year]

        if not rows:
            result[int(year)] = None
            continue

        rows.sort(
            key=lambda item: (
                item["score"],
                len(item["text"]),
            ),
            reverse=True,
        )

        result[int(year)] = rows[0]

    return result


def main():
    links = find_year_links()

    print("=== LINK ĐIỂM CHUẨN DÙNG CHO ĐỒ ÁN 2023-2026 ===")
    print()

    for year in map(int, TARGET_YEARS):
        item = links.get(year)

        if item is None:
            print(f"{year}: ❌ Chưa tìm thấy link phù hợp")
            print("-" * 90)
            continue

        print(f"{year}:")
        print("Tên:", item["text"])
        print("URL :", item["url"])
        print("-" * 90)


if __name__ == "__main__":
    main()
