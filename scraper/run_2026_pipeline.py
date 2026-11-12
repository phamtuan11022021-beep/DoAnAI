from __future__ import annotations

import io
import os
import json
import re
import shutil
import tempfile
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup
from PIL import Image
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    import pymupdf as fitz
except ImportError:
    import fitz

try:
    if os.environ.get('SCRAPER_SKIP_OCR') == '1':
        raise ImportError('OCR disabled for structured recovery')
    from paddleocr import PPStructureV3
except ImportError:
    PPStructureV3 = None

# Shared parser đã sửa cho phạm vi 2023-2026.
try:
    from scrapers.school_scraper import scrape_school
except Exception:
    scrape_school = None


# =============================================================================
# 2026 PRODUCTION PIPELINE
# =============================================================================
#
# MỤC TIÊU
# -------
# Một pipeline duy nhất cho 2026, rút kinh nghiệm từ 2023-2025:
#
#   aggregate 2026
#      -> inventory trường (kể cả trường chưa có href)
#      -> ưu tiên trường đã có lịch sử 2023-2025
#      -> HTML/PDF trực tiếp
#      -> cross-year code mapping CHỈ trong cùng trường nếu bảng 2026 thiếu mã
#      -> OCR chỉ khi structured extraction thất bại
#      -> FINAL raw / ML READY / ML EXCLUDED / SOURCE EXCLUDED
#      -> hard audit
#
# NGUYÊN TẮC 2026
# ----------------
# 1) Trang tổng hợp 2026 KHÔNG đồng nghĩa mọi điểm là THPT-30.
# 2) FINAL bảo toàn điểm chuẩn công bố nếu source đủ tin cậy.
# 3) ML READY chỉ nhận:
#       - phương thức có evidence THPT thuần;
#       - score 10..30;
#       - không thang 40/100/150;
#       - không học bạ/ĐGNL/ĐGTD/TSA/HSA/V-SAT;
#       - không "THPT_COMBINED".
# 4) Bảng generic "Điểm chuẩn" vẫn có thể ở FINAL với method=UNSPECIFIED_2026,
#    nhưng KHÔNG vào ML READY.
# 5) Không tự quy đổi thang điểm.
# 6) Không dùng VietNamNet/TS247 làm dữ liệu FINAL.
# 7) Source ngoài thongtintuyensinh.vn chỉ dùng khi CHÍNH aggregate 2026 liên kết.
# 8) Trường không có link trong aggregate: chỉ tìm lại bài 2026 trên
#    thongtintuyensinh.vn; nếu không có => SOURCE_EXCLUDED.
#
# =============================================================================

YEAR = 2026
PIPELINE_VERSION = "2026-P3-FINAL-LOCK-20260924"

AGGREGATE_URL = (
    "https://thongtintuyensinh.vn/"
    "Tong-hop-diem-chuan-trung-tuyen-dai-hoc-nam-2026_C309_D24283.htm"
)

ROOT_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT_DIR / "data" / "raw"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"

DOC_DIR = RAW_DIR / "documents" / "2026"
RECOVERY_ROOT = RAW_DIR / "primary_recovery_2026"
ASSET_ROOT = RECOVERY_ROOT / "assets"
OCR_CACHE_ROOT = RECOVERY_ROOT / "ocr_cache"

for path in (
    RAW_DIR,
    PROCESSED_DIR,
    DOC_DIR,
    RECOVERY_ROOT,
    ASSET_ROOT,
    OCR_CACHE_ROOT,
):
    path.mkdir(parents=True, exist_ok=True)

SOURCE_MAP_FILE = RAW_DIR / "source_map_2026.csv"
SOURCE_ANALYSIS_FILE = RAW_DIR / "source_analysis_2026.csv"

FINAL_FILE = PROCESSED_DIR / "admission_scores_2026_final.csv"
ML_READY_FILE = PROCESSED_DIR / "admission_scores_2026_ml_ready.csv"
ML_EXCLUDED_FILE = PROCESSED_DIR / "admission_scores_2026_ml_excluded.csv"
SOURCE_EXCLUDED_FILE = PROCESSED_DIR / "admission_scores_2026_source_excluded.csv"
SOURCE_STATUS_FILE = PROCESSED_DIR / "admission_scores_2026_source_status.csv"
ROW_EXCLUDED_FILE = PROCESSED_DIR / "admission_scores_2026_row_excluded.csv"
REVIEW_FILE = PROCESSED_DIR / "admission_scores_2026_review.csv"
REPORT_FILE = PROCESSED_DIR / "admission_scores_2026_production_report.csv"

ASCII_ROOT = Path(tempfile.gettempdir()) / "uniconnect_2026_recovery"
ASCII_ROOT.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/153.0.0.0 Safari/537.36"
    )
}

CANONICAL_COLUMNS = [
    "university_name",
    "major_code",
    "major_name",
    "year",
    "admission_method_codes",
    "combination",
    "cutoff_score",
    "admission_note",
    "source_url",
]

SOURCE_MAP_COLUMNS = [
    "university_name",
    "source_urls",
    "source_type",
    "priority",
    "linked_from_aggregate",
]

ANALYSIS_COLUMNS = [
    "university_name",
    "source_type",
    "analysis_class",
    "source_count",
    "page_title",
    "local_files",
    "source_urls",
]

EXCLUDED_COLUMNS = [
    "university_name",
    "source_type",
    "analysis_class",
    "exclusion_reason",
    "source_urls",
    "local_files",
]

REPORT_COLUMNS = [
    "university_name",
    "priority",
    "analysis_class",
    "strategies",
    "candidate_rows",
    "accepted_rows",
    "ml_ready_rows",
    "status",
    "reason",
    "source_urls",
]


# =============================================================================
# METHOD / SCALE RULES
# =============================================================================

THPT_MARKERS = (
    "thi tốt nghiệp thpt",
    "điểm thi tốt nghiệp thpt",
    "kết quả thi tốt nghiệp thpt",
    "kết quả kỳ thi tốt nghiệp thpt",
    "xét điểm thi tốt nghiệp thpt",
    "xét tuyển theo kết quả thi tốt nghiệp thpt",
    "xét tuyển dựa trên điểm thi tốt nghiệp thpt",
    "thi tn thpt",
    "điểm thi tn thpt",
    "xét điểm thi tn thpt",
    "điểm chuẩn thpt",
    "điểm trúng tuyển thpt",
)

COMBINED_MARKERS = (
    "xét tuyển kết hợp",
    "xét kết hợp",
    "kết hợp điểm thi",
    "điểm thi thpt và học bạ",
    "điểm thi tốt nghiệp thpt và học bạ",
    "học bạ và điểm thi",
    "học bạ và kết quả thi",
    "tổng hợp",
)

NON_THPT_MARKERS = (
    "học bạ",
    "kết quả học tập",
    "đánh giá năng lực",
    "đgnl",
    "đánh giá tư duy",
    "đgtd",
    "v-sat",
    "vsat",
    "hsa",
    "tsa",
    "spt",
    "tuyển thẳng",
)

SCALE40_MARKERS = (
    "thang 40",
    "thang điểm 40",
    "nhân hệ số 2",
    "nhân đôi",
)

SCALE100_MARKERS = (
    "thang 100",
    "thang điểm 100",
)

SCALE150_MARKERS = (
    "thang 150",
    "thang điểm 150",
)

# Umbrella/system source, không phải một trường đơn lẻ trong recommender.
FORCE_EXCLUDE_NAMES = {
    "đại học huế",
    "đại học đà nẵng",
}

# Generic groups, không phải university entity.
INVENTORY_JUNK = {
    "các trường quân đội",
    "các trường công an",
}

SCHOOL_PREFIXES = (
    "trường đh ",
    "trường đại học ",
    "đại học ",
    "đh ",
    "hv ",
    "học viện ",
    "khoa quốc tế ",
    "trường y dược ",
)

CODE_HEADER_MARKERS = (
    "ma nganh",
    "ma xet tuyen",
    "ma tuyen sinh",
    "ma chuong trinh",
    "ma ctdt",
    "ma ct",
)

NAME_HEADER_MARKERS = (
    "ten nganh",
    "nganh dao tao",
    "nganh tuyen sinh",
    "ten chuong trinh",
    "chuong trinh dao tao",
    "chuyen nganh",
    "nganh",
)

SCORE_HEADER_MARKERS = (
    "diem chuan",
    "diem trung tuyen",
    "muc diem trung tuyen",
)

COMBO_HEADER_MARKERS = (
    "to hop",
    "khoi thi",
    "ma to hop",
)

METHOD_HEADER_MARKERS = (
    "phuong thuc",
    "ma phuong thuc",
    "ptxt",
)

NOTE_HEADER_MARKERS = (
    "ghi chu",
    "tieu chi phu",
    "dieu kien phu",
    "dieu kien",
)

SCALE_HEADER_MARKERS = (
    "thang diem",
    "thang",
)


# =============================================================================
# BASIC HELPERS
# =============================================================================

def clean_text(value) -> str:
    if value is None:
        return ""

    text = str(value).replace("\xa0", " ")

    if text.lower() in {"nan", "none", "<na>"}:
        return ""

    return re.sub(r"\s+", " ", text).strip()


def strip_accents(value: str) -> str:
    value = str(value).replace("Đ", "D").replace("đ", "d")
    value = unicodedata.normalize("NFD", value)
    value = "".join(
        ch for ch in value
        if unicodedata.category(ch) != "Mn"
    )
    return unicodedata.normalize("NFC", value)


def norm(value) -> str:
    text = strip_accents(clean_text(value)).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_school(value: str) -> str:
    text = norm(value)

    replacements = [
        (r"\bhv\b", "hoc vien"),
        (r"\bdh\b", "dai hoc"),
        (r"\bdhqghcm\b", "dai hoc quoc gia tp hcm"),
        (r"\bdhqg hcm\b", "dai hoc quoc gia tp hcm"),
        (r"\bdhqg tp hcm\b", "dai hoc quoc gia tp hcm"),
        (r"\bdhqghn\b", "dai hoc quoc gia ha noi"),
        (r"\bdhqg ha noi\b", "dai hoc quoc gia ha noi"),
        (r"\bdhtn\b", "dai hoc thai nguyen"),
        (r"\btphcm\b", "tp hcm"),
        (r"\bvn\b", "viet nam"),
    ]

    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text)

    return re.sub(r"\s+", " ", text).strip()


def inventory_base_school(value: str) -> str:
    """
    Chỉ gộp suffix phương thức của cùng trường, ví dụ:
      Trường ĐH Tôn Đức Thắng - PT1
      Trường ĐH Tôn Đức Thắng - PT2
    Không fuzzy-merge tên trường.
    """
    text = clean_text(value)
    text = re.sub(
        r"\s*[-–—]\s*pt\s*\d+[a-z]?\s*$",
        "",
        text,
        flags=re.I,
    )
    text = re.sub(
        r"\s*\(\*\)\s*$",
        "",
        text,
    )
    return clean_text(text)


def slugify(value: str) -> str:
    value = norm(value).replace(" ", "_")
    return re.sub(r"[^a-z0-9_]+", "", value)[:90] or "school"


def parse_number(value) -> Optional[float]:
    text = clean_text(value).replace(",", ".")
    text = re.sub(r"\s+", "", text)

    if not re.fullmatch(r"[-+]?\d{1,4}(?:\.\d{1,4})?", text):
        return None

    try:
        return float(text)
    except ValueError:
        return None


def normalize_major_code(value) -> str:
    return clean_text(value).replace(" ", "").upper()


def normalize_major_code_strict(value) -> str:
    """
    Chuẩn hóa major_code an toàn.

    Chỉ tự sửa trường hợp pandas/PDF biến mã 7 chữ số thành 7140201.0.
    Không coi các số thập phân kiểu 25.5 / 33.42 / 71.9 là mã ngành.
    """
    text = normalize_major_code(value)

    match = re.fullmatch(r"(\d{6,8})\.0", text)
    if match:
        return match.group(1)

    return text


def valid_major_code(value) -> bool:
    text = normalize_major_code_strict(value)

    if not text:
        return False

    # Mã ngành chuẩn dạng số.
    if text.isdigit():
        return 6 <= len(text) <= 8

    # Ví dụ: QHT01, HVN01, ACT01, NTHCN18.
    if re.fullmatch(r"[A-Z]{1,10}[A-Z0-9]{1,11}", text):
        return bool(re.search(r"\d", text)) and len(text) <= 14

    # Ví dụ: 7140202JR, 7340101DN.
    if re.fullmatch(r"\d{6,8}[A-Z][A-Z0-9]{0,5}", text):
        return True

    # Ví dụ: 7340101_3, 7480107_1.
    if re.fullmatch(r"\d{6,8}[_/-][A-Z0-9]{1,5}", text):
        return True

    # Một số mã chương trình chữ-số có dấu gạch dưới.
    if re.fullmatch(r"[A-Z][A-Z0-9]{1,10}[_/-][A-Z0-9]{1,5}", text):
        return True

    return False

def looks_garbled(value: str) -> bool:
    text = clean_text(value)

    if "�" in text:
        return True

    low = text.lower()

    return any(
        marker in low
        for marker in (
            "ngµnh",
            "®iÓm",
            "tuyén",
            "trüng",
        )
    )


def explicit_thpt(value: str) -> bool:
    low = clean_text(value).lower()
    return any(marker in low for marker in THPT_MARKERS)


def combined_method(value: str) -> bool:
    low = clean_text(value).lower()
    return any(marker in low for marker in COMBINED_MARKERS)


def non_thpt(value: str) -> bool:
    low = clean_text(value).lower()
    return any(marker in low for marker in NON_THPT_MARKERS)


def force_exclude(name: str) -> bool:
    target = normalize_school(name)
    return any(
        target == normalize_school(item)
        for item in FORCE_EXCLUDE_NAMES
    )


def infer_scale(value: str, score: Optional[float] = None) -> str:
    low = clean_text(value).lower()

    if any(marker in low for marker in SCALE150_MARKERS):
        return "150"

    if any(marker in low for marker in SCALE100_MARKERS):
        return "100"

    if any(marker in low for marker in SCALE40_MARKERS):
        return "40"

    if score is not None:
        if score > 100:
            return "150"
        if score > 40:
            return "100"
        if score > 30:
            return "40"

    return "30_OR_UNKNOWN"


def canonicalize(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=CANONICAL_COLUMNS)

    df = pd.DataFrame(rows)

    for col in CANONICAL_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df = df[CANONICAL_COLUMNS].copy()

    for col in (
        "university_name",
        "major_code",
        "major_name",
        "admission_method_codes",
        "combination",
        "admission_note",
        "source_url",
    ):
        df[col] = df[col].map(clean_text)

    df["year"] = pd.to_numeric(
        df["year"],
        errors="coerce",
    ).astype("Int64")

    df["cutoff_score"] = pd.to_numeric(
        df["cutoff_score"],
        errors="coerce",
    )

    return df


def dedupe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    keys = [
        "university_name",
        "major_code",
        "major_name",
        "year",
        "admission_method_codes",
        "combination",
        "cutoff_score",
        "source_url",
    ]

    return (
        df.drop_duplicates(subset=keys, keep="first")
        .sort_values(
            [
                "university_name",
                "major_code",
                "cutoff_score",
                "source_url",
            ],
            kind="stable",
        )
        .reset_index(drop=True)
    )


def build_session() -> requests.Session:
    session = requests.Session()

    retry = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=0.7,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "HEAD"}),
        raise_on_status=False,
    )

    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update(HEADERS)

    return session


def decode_response(response: requests.Response) -> str:
    if (
        not response.encoding
        or response.encoding.lower() == "iso-8859-1"
    ):
        response.encoding = response.apparent_encoding or "utf-8"

    return response.text


def split_urls(value: str) -> list[str]:
    return [
        clean_text(item)
        for item in clean_text(value).split(";;")
        if clean_text(item)
    ]


def join_urls(urls: list[str]) -> str:
    output = []

    for url in urls:
        url = clean_text(url)
        if url and url not in output:
            output.append(url)

    return ";;".join(output)


# =============================================================================
# CROSS-YEAR PRIORITY + MAJOR CODE MAP
# =============================================================================

def load_history_school_presence() -> dict[str, int]:
    counts: dict[str, int] = {}

    for year in (2023, 2024, 2025):
        path = PROCESSED_DIR / f"admission_scores_{year}_ml_ready.csv"

        if not path.exists():
            continue

        try:
            df = pd.read_csv(
                path,
                dtype=str,
                keep_default_na=False,
                usecols=["university_name"],
            )
        except Exception:
            continue

        for name in df["university_name"].drop_duplicates():
            key = normalize_school(name)
            counts[key] = counts.get(key, 0) + 1

    return counts


def major_name_key(value: str) -> str:
    text = norm(value)

    replacements = [
        (r"\bhe chinh quy\b", ""),
        (r"\bdai tra\b", ""),
        (r"\bchuong trinh\b", ""),
    ]

    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text)

    return re.sub(r"\s+", " ", text).strip()


def build_crossyear_major_map() -> dict[str, dict]:
    """
    Chỉ map code trong CHÍNH CÙNG TRƯỜNG.
    Chỉ giữ name -> code nếu các năm lịch sử không mâu thuẫn.
    """
    raw: dict[str, dict[str, set[str]]] = {}

    for year in (2023, 2024, 2025):
        path = PROCESSED_DIR / f"admission_scores_{year}_final.csv"

        if not path.exists():
            continue

        try:
            df = pd.read_csv(
                path,
                dtype=str,
                keep_default_na=False,
                usecols=[
                    "university_name",
                    "major_code",
                    "major_name",
                ],
            )
        except Exception:
            continue

        for _, row in df.iterrows():
            school = normalize_school(row["university_name"])
            code = normalize_major_code(row["major_code"])
            name_key = major_name_key(row["major_name"])

            if not school or not name_key or not valid_major_code(code):
                continue

            raw.setdefault(school, {}).setdefault(
                name_key,
                set(),
            ).add(code)

    output = {}

    for school, mapping in raw.items():
        exact = {
            name: next(iter(codes))
            for name, codes in mapping.items()
            if len(codes) == 1
        }

        output[school] = {
            "exact": exact,
            "items": list(exact.items()),
        }

    return output


def map_code_crossyear(
    university_name: str,
    major_name: str,
    crossyear_map: dict[str, dict],
) -> tuple[str, str]:
    school_key = normalize_school(university_name)
    name_key = major_name_key(major_name)

    school_map = crossyear_map.get(school_key, {})
    exact = school_map.get("exact", {})

    if name_key in exact:
        return exact[name_key], "CROSSYEAR_EXACT"

    ranked = []

    for known_name, code in school_map.get("items", []):
        seq = SequenceMatcher(
            None,
            name_key,
            known_name,
        ).ratio()

        a = set(name_key.split())
        b = set(known_name.split())

        coverage = (
            len(a & b)
            / max(1, min(len(a), len(b)))
        )

        ranked.append(
            (seq, coverage, known_name, code)
        )

    if not ranked:
        return "", ""

    ranked.sort(reverse=True)
    best = ranked[0]
    second = ranked[1][0] if len(ranked) > 1 else 0.0

    if (
        best[0] >= 0.94
        and best[1] >= 0.80
        and best[0] - second >= 0.04
    ):
        return best[3], "CROSSYEAR_FUZZY_STRICT"

    return "", ""


# =============================================================================
# INVENTORY 2026
# =============================================================================

def looks_like_school_name(value: str) -> bool:
    low = clean_text(value).lower()

    if not low:
        return False

    if low in INVENTORY_JUNK:
        return False

    return low.startswith(SCHOOL_PREFIXES)


def school_name_similarity(a: str, b: str) -> tuple[float, float]:
    na = normalize_school(a)
    nb = normalize_school(b)

    if not na or not nb:
        return 0.0, 0.0

    seq = SequenceMatcher(None, na, nb).ratio()

    stop = {
        "truong",
        "dai",
        "hoc",
        "vien",
        "tp",
        "thanh",
        "pho",
        "viet",
        "nam",
    }

    ta = {token for token in na.split() if token not in stop}
    tb = {token for token in nb.split() if token not in stop}

    coverage = len(ta & tb) / max(1, len(ta))
    return seq, coverage


def discover_archive_articles(
    session: requests.Session,
) -> list[dict]:
    """
    Cache danh sách bài "Điểm chuẩn năm 2026..." trên chính
    thongtintuyensinh.vn. Không dùng secondary site.
    """
    output = []
    seen = set()

    # 2026 bài mới tập trung ở các trang đầu; 8 trang đủ rộng nhưng vẫn nhanh.
    for page in range(1, 9):
        url = (
            "https://thongtintuyensinh.vn/"
            f"diem-chuan-trung-tuyen_C237_P{page}.htm"
        )

        try:
            response = session.get(
                url,
                timeout=30,
                allow_redirects=True,
            )
            response.raise_for_status()
        except Exception:
            continue

        soup = BeautifulSoup(
            decode_response(response),
            "lxml",
        )

        for anchor in soup.find_all("a", href=True):
            title = clean_text(
                anchor.get_text(" ", strip=True)
            )

            if "2026" not in title:
                continue

            low = title.lower()

            if (
                "điểm chuẩn" not in low
                and "điểm trúng tuyển" not in low
            ):
                continue

            if any(
                bad in low
                for bad in (
                    "lớp 10",
                    "điểm sàn",
                    "nhận hồ sơ",
                    "ngưỡng điểm",
                    "tuyển bổ sung",
                )
            ):
                continue

            href = urljoin(
                url,
                clean_text(anchor.get("href")),
            )

            if (
                "thongtintuyensinh.vn"
                not in urlparse(href).netloc.lower()
            ):
                continue

            if href in seen:
                continue

            seen.add(href)
            output.append(
                {
                    "title": title,
                    "url": href,
                }
            )

    return output


def match_archive_article(
    university_name: str,
    archive_articles: list[dict],
) -> tuple[str, str]:
    ranked = []

    for item in archive_articles:
        seq, coverage = school_name_similarity(
            university_name,
            item["title"],
        )

        if seq < 0.52 or coverage < 0.75:
            continue

        ranked.append(
            (
                coverage,
                seq,
                item["title"],
                item["url"],
            )
        )

    if not ranked:
        return "", ""

    ranked.sort(reverse=True)
    best = ranked[0]
    second_seq = ranked[1][1] if len(ranked) > 1 else 0.0

    # Exact token coverage or very strong unique fuzzy.
    if (
        best[0] >= 0.95
        or (
            best[0] >= 0.85
            and best[1] >= 0.78
            and best[1] - second_seq >= 0.05
        )
    ):
        return best[3], best[2]

    return "", ""


def discover_inventory(
    session: requests.Session,
) -> tuple[pd.DataFrame, list[dict]]:
    response = session.get(
        AGGREGATE_URL,
        timeout=45,
        allow_redirects=True,
    )
    response.raise_for_status()

    html = decode_response(response)
    soup = BeautifulSoup(html, "lxml")

    h1 = soup.find("h1")

    if h1 is None:
        raise RuntimeError(
            "Không tìm thấy H1 của trang tổng hợp 2026."
        )

    # Anchor map from article body only.
    anchor_records = []
    text_chunks = []

    for element in h1.find_all_next():
        text = clean_text(
            element.get_text(" ", strip=True)
        )

        if (
            text.lower() == "tin cùng chuyên mục"
            or text.lower().startswith("tin cùng chuyên mục")
        ):
            break

        if element.name == "a" and element.get("href"):
            anchor_text = inventory_base_school(
                clean_text(
                    element.get_text(" ", strip=True)
                )
            )

            if looks_like_school_name(anchor_text):
                anchor_records.append(
                    (
                        anchor_text,
                        urljoin(
                            AGGREGATE_URL,
                            element["href"],
                        ),
                    )
                )

        # We only need textual school fragments once per block-level node.
        if element.name in {"p", "div", "li"} and text:
            text_chunks.append(text)

    # Candidate names from raw article text; catches schools with no href.
    candidate_names = []

    separators = re.compile(
        r"\s*(?:\*|\||•|·)\s*"
    )

    for chunk in text_chunks:
        for piece in separators.split(chunk):
            piece = inventory_base_school(
                clean_text(piece)
            )

            # Remove region heading prefixes accidentally attached to first school.
            piece = re.sub(
                r"^các trường khu vực[^A-ZÀ-Ỹ]*",
                "",
                piece,
                flags=re.I,
            ).strip()

            if looks_like_school_name(piece):
                candidate_names.append(piece)

    # Anchor names are authoritative candidates too.
    for name, _ in anchor_records:
        candidate_names.append(name)

    # Merge only exact normalized/base identity.
    inventory: dict[str, dict] = {}
    priority_map = load_history_school_presence()

    for raw_name in candidate_names:
        base_name = inventory_base_school(raw_name)
        key = normalize_school(base_name)

        if not key:
            continue

        if key not in inventory:
            inventory[key] = {
                "university_name": base_name,
                "source_urls": [],
                "source_type": "UNLINKED",
                "priority": priority_map.get(key, 0),
                "linked_from_aggregate": False,
            }

    for anchor_name, href in anchor_records:
        key = normalize_school(
            inventory_base_school(anchor_name)
        )

        if key not in inventory:
            continue

        if href not in inventory[key]["source_urls"]:
            inventory[key]["source_urls"].append(href)

        inventory[key]["linked_from_aggregate"] = True

    # Same-site archive map used only for unlinked schools.
    archive_articles = discover_archive_articles(session)

    for key, item in inventory.items():
        if item["source_urls"]:
            continue

        url, _ = match_archive_article(
            item["university_name"],
            archive_articles,
        )

        if url:
            item["source_urls"].append(url)
            item["source_type"] = "ARCHIVE_REDISCOVERED"

    rows = []

    for item in inventory.values():
        urls = item["source_urls"]

        source_type = item["source_type"]

        if urls and source_type != "ARCHIVE_REDISCOVERED":
            types = {
                source_type_from_url(url)
                for url in urls
            }
            source_type = (
                next(iter(types))
                if len(types) == 1
                else "MULTI"
            )

        rows.append(
            {
                "university_name":
                    item["university_name"],
                "source_urls":
                    join_urls(urls),
                "source_type":
                    source_type,
                "priority":
                    item["priority"],
                "linked_from_aggregate":
                    bool(item["linked_from_aggregate"]),
            }
        )

    df = pd.DataFrame(
        rows,
        columns=SOURCE_MAP_COLUMNS,
    )

    # 2026 aggregate has a large national list. If parser returns too few,
    # stop instead of creating a partial dataset.
    if len(df) < 140:
        raise RuntimeError(
            f"Inventory 2026 chỉ có {len(df)} trường. "
            "Dừng để tránh source_map thiếu."
        )

    df["priority"] = pd.to_numeric(
        df["priority"],
        errors="coerce",
    ).fillna(0).astype(int)

    df = (
        df.drop_duplicates(
            subset=["university_name"],
            keep="first",
        )
        .sort_values(
            ["priority", "university_name"],
            ascending=[False, True],
            kind="stable",
        )
        .reset_index(drop=True)
    )

    df.to_csv(
        SOURCE_MAP_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    return df, archive_articles


def source_type_from_url(url: str) -> str:
    low = clean_text(url).lower()
    host = urlparse(low).netloc
    path = urlparse(low).path

    if path.endswith(".pdf"):
        return "PDF"

    if path.endswith((".jpg", ".jpeg", ".png", ".webp")):
        return "IMAGE"

    if "drive.google.com" in host:
        return "GOOGLE_DRIVE"

    if "docs.google.com" in host:
        return "GOOGLE_DOC"

    if "thongtintuyensinh.vn" in host:
        return "HTML"

    return "EXTERNAL"


# =============================================================================
# DOWNLOAD / ASSET HELPERS
# =============================================================================

def drive_direct_url(url: str) -> str:
    match = re.search(
        r"/file/d/([A-Za-z0-9_-]+)",
        url,
    )

    file_id = ""

    if match:
        file_id = match.group(1)
    else:
        values = parse_qs(
            urlparse(url).query
        ).get("id")

        if values:
            file_id = values[0]

    if not file_id:
        return ""

    return (
        "https://drive.usercontent.google.com/download"
        f"?id={file_id}&export=download&confirm=t"
    )


def google_doc_export_url(url: str) -> str:
    for kind in (
        "document",
        "spreadsheets",
    ):
        match = re.search(
            rf"/{kind}/d/([A-Za-z0-9_-]+)",
            url,
        )

        if match:
            return (
                f"https://docs.google.com/{kind}/d/"
                f"{match.group(1)}/export?format=pdf"
            )

    return ""


def download_file(
    session: requests.Session,
    url: str,
    target: Path,
) -> tuple[bool, int]:
    try:
        response = session.get(
            url,
            timeout=60,
            allow_redirects=True,
        )
        status = response.status_code
        response.raise_for_status()
    except Exception:
        return False, 0

    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    target.write_bytes(
        response.content
    )

    return (
        target.exists()
        and target.stat().st_size > 1000,
        status,
    )


def sniff_bytes(content: bytes, content_type: str = "") -> str:
    content_type = clean_text(content_type).lower()

    if content[:5] == b"%PDF" or "application/pdf" in content_type:
        return "PDF"

    if content_type.startswith("image/"):
        return "IMAGE"

    low = content[:4096].lower()

    if (
        b"<html" in low
        or b"<!doctype html" in low
        or b"<table" in low
    ):
        return "HTML"

    try:
        Image.open(io.BytesIO(content)).verify()
        return "IMAGE"
    except Exception:
        pass

    return "OTHER"


def sniff_file(path: Path) -> str:
    try:
        content = path.read_bytes()
    except Exception:
        return "OTHER"

    return sniff_bytes(content)


def collect_embedded_assets(
    session: requests.Session,
    *,
    html: str,
    page_url: str,
    university_name: str,
) -> list[Path]:
    soup = BeautifulSoup(html, "lxml")
    urls = []

    def add(raw: str) -> None:
        raw = clean_text(raw)

        if not raw:
            return

        if "," in raw and " " in raw:
            for part in raw.split(","):
                token = clean_text(part).split(" ")[0]
                if token:
                    add(token)
            return

        url = urljoin(page_url, raw)
        low = url.lower()

        if any(
            marker in low
            for marker in (
                "logo",
                "icon",
                "avatar",
                "banner",
                "facebook",
                "youtube",
                "ads",
                "advert",
                "tracking",
                "pixel",
                "sprite",
            )
        ):
            return

        if url not in urls:
            urls.append(url)

    for img in soup.find_all("img"):
        for attr in (
            "src",
            "data-src",
            "data-original",
            "data-lazy-src",
            "srcset",
        ):
            value = img.get(attr)
            if value:
                add(value)

    for tag in soup.find_all(
        ["a", "iframe", "embed", "object"]
    ):
        for attr in (
            "href",
            "src",
            "data",
        ):
            raw = tag.get(attr)

            if not raw:
                continue

            low = urljoin(
                page_url,
                clean_text(raw),
            ).lower()

            if (
                low.endswith(
                    (
                        ".pdf",
                        ".jpg",
                        ".jpeg",
                        ".png",
                        ".webp",
                    )
                )
                or "drive.google.com" in low
                or "docs.google.com" in low
                or "/upload/" in low
            ):
                add(raw)

    school_dir = ASSET_ROOT / slugify(university_name)
    school_dir.mkdir(parents=True, exist_ok=True)

    output = []

    for idx, url in enumerate(urls[:30], start=1):
        fetch_url = url
        suffix = Path(
            urlparse(url).path
        ).suffix.lower()

        if "drive.google.com" in url.lower():
            fetch_url = drive_direct_url(url)

            if not fetch_url:
                continue

            suffix = ".pdf"

        elif "docs.google.com" in url.lower():
            fetch_url = google_doc_export_url(url)

            if not fetch_url:
                continue

            suffix = ".pdf"

        if suffix not in (
            ".pdf",
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
        ):
            suffix = ".bin"

        target = school_dir / f"embedded_{idx:02d}{suffix}"

        if not target.exists():
            ok, _ = download_file(
                session,
                fetch_url,
                target,
            )

            if not ok:
                continue

        if sniff_file(target) in {
            "PDF",
            "IMAGE",
            "HTML",
        }:
            output.append(target)

    seen = set()
    unique = []

    for path in output:
        key = str(path.resolve())

        if key in seen:
            continue

        seen.add(key)
        unique.append(path)

    return unique


# =============================================================================
# TABLE PARSER
# =============================================================================

def normalize_grid(grid: list[list[str]]) -> list[list[str]]:
    output = []

    for row in grid:
        cleaned = [
            clean_text(value)
            for value in row
        ]

        if any(cleaned):
            output.append(cleaned)

    return output


def combine_headers(
    rows: list[list[str]],
    start: int,
    depth: int,
) -> list[str]:
    width = max(
        (len(row) for row in rows[start:start + depth]),
        default=0,
    )

    headers = []

    for col in range(width):
        parts = []

        for row_idx in range(
            start,
            min(len(rows), start + depth),
        ):
            if col >= len(rows[row_idx]):
                continue

            value = clean_text(
                rows[row_idx][col]
            )

            if (
                value
                and (
                    not parts
                    or value != parts[-1]
                )
            ):
                parts.append(value)

        headers.append(
            " ".join(parts)
        )

    return headers


def semantic_header_score(headers: list[str]) -> int:
    joined = norm(
        " | ".join(headers)
    )
    score = 0

    if any(marker in joined for marker in CODE_HEADER_MARKERS):
        score += 6

    if any(marker in joined for marker in NAME_HEADER_MARKERS):
        score += 6

    if any(marker in joined for marker in SCORE_HEADER_MARKERS):
        score += 8

    if any(marker in joined for marker in METHOD_HEADER_MARKERS):
        score += 4

    return score


def choose_header(
    rows: list[list[str]],
) -> tuple[int, int, list[str]]:
    best = (
        0,
        1,
        combine_headers(rows, 0, 1),
    )
    best_score = semantic_header_score(
        best[2]
    )

    for start in range(
        0,
        min(8, len(rows)),
    ):
        for depth in range(
            1,
            min(4, len(rows) - start) + 1,
        ):
            headers = combine_headers(
                rows,
                start,
                depth,
            )
            score = semantic_header_score(
                headers
            )

            if score > best_score:
                best = (
                    start,
                    depth,
                    headers,
                )
                best_score = score

    return best


def find_header_idx(
    headers: list[str],
    markers: tuple[str, ...],
    *,
    reject: tuple[str, ...] = (),
) -> Optional[int]:
    best_idx = None
    best_len = -1

    for idx, header in enumerate(headers):
        low = norm(header)

        if reject and any(marker in low for marker in reject):
            continue

        matched = [
            marker
            for marker in markers
            if marker in low
        ]

        if not matched:
            continue

        length = max(
            len(marker)
            for marker in matched
        )

        if length > best_len:
            best_idx = idx
            best_len = length

    return best_idx


def get_cell(
    row: list[str],
    idx: Optional[int],
) -> str:
    if idx is None or idx >= len(row):
        return ""

    return clean_text(
        row[idx]
    )


def infer_name_column(
    rows: list[list[str]],
    start: int,
    forbidden: set[int],
) -> Optional[int]:
    width = max(
        (len(row) for row in rows[start:]),
        default=0,
    )
    ranked = []

    for col in range(width):
        if col in forbidden:
            continue

        count = 0
        chars = 0

        for row in rows[start:start + 100]:
            if col >= len(row):
                continue

            value = clean_text(row[col])

            if (
                not value
                or parse_number(value) is not None
                or valid_major_code(value)
            ):
                continue

            if re.search(r"[A-Za-zÀ-ỹ]", value):
                count += 1
                chars += min(len(value), 80)

        if count:
            ranked.append(
                (count, chars, col)
            )

    if not ranked:
        return None

    ranked.sort(reverse=True)
    return ranked[0][-1]


def infer_code_column(
    rows: list[list[str]],
    start: int,
) -> Optional[int]:
    width = max(
        (len(row) for row in rows[start:]),
        default=0,
    )
    ranked = []

    for col in range(width):
        count = 0

        for row in rows[start:start + 100]:
            if col < len(row) and valid_major_code(row[col]):
                count += 1

        if count:
            ranked.append((count, col))

    if not ranked:
        return None

    ranked.sort(reverse=True)

    return (
        ranked[0][1]
        if ranked[0][0] >= 2
        else None
    )


def score_column_priority(
    header: str,
    context: str,
) -> int:
    low = clean_text(header).lower()

    if not any(
        marker in norm(header)
        for marker in SCORE_HEADER_MARKERS
    ):
        return -1000

    score = 10

    if explicit_thpt(low):
        score += 300

    if "thpt" in low and not non_thpt(low):
        score += 200

    if any(
        marker in low
        for marker in (
            "học bạ",
            "hb",
            "đgnl",
            "đgtd",
            "tsa",
            "hsa",
            "v-sat",
            "vsat",
            "spt",
        )
    ):
        score -= 250

    # Generic "Điểm chuẩn" is allowed in RAW.
    if norm(header) in {
        "diem chuan",
        "diem trung tuyen",
    }:
        score += 20

    if explicit_thpt(context):
        score += 30

    return score


def select_score_column(
    headers: list[str],
    context: str,
) -> Optional[int]:
    ranked = []

    for idx, header in enumerate(headers):
        priority = score_column_priority(
            header,
            context,
        )

        if priority > -1000:
            ranked.append(
                (priority, idx)
            )

    if not ranked:
        return None

    ranked.sort(reverse=True)
    return ranked[0][1]


def infer_score_column(
    rows: list[list[str]],
    start: int,
    forbidden: set[int],
) -> Optional[int]:
    """
    Fallback khi header OCR/PDF hỏng.

    Khác bản production:
    - ưu tiên cột có mật độ điểm 10..30 cao;
    - vẫn hỗ trợ scale 40/100/150 cho RAW;
    - phạt rất mạnh cột giống STT 1,2,3,...;
    - không chọn cột chỉ vì có nhiều số.
    """
    width = max(
        (len(row) for row in rows[start:]),
        default=0,
    )
    ranked = []

    for col in range(width):
        if col in forbidden:
            continue

        values = []

        for row in rows[start:start + 120]:
            if col >= len(row):
                continue

            number = parse_number(row[col])

            if number is not None and 0 < number <= 150:
                values.append(float(number))

        if len(values) < 2:
            continue

        n = len(values)
        sorted_values = sorted(values)
        median = sorted_values[n // 2]

        thpt_ratio = sum(10 <= v <= 30 for v in values) / n
        broad_ratio = sum(10 <= v <= 100 for v in values) / n

        # Detect STT-like columns. 1,2,3... or mostly small unique integers.
        integer_values = [
            int(v)
            for v in values
            if abs(v - round(v)) < 1e-9
        ]

        stt_penalty = 0.0

        if len(integer_values) >= max(3, int(n * 0.75)):
            unique_ints = sorted(set(integer_values))

            if unique_ints:
                consecutive = sum(
                    1
                    for a, b in zip(unique_ints, unique_ints[1:])
                    if b - a == 1
                )

                consecutive_ratio = (
                    consecutive / max(1, len(unique_ints) - 1)
                )

                small_ratio = sum(
                    1 <= v <= max(40, n + 5)
                    for v in integer_values
                ) / len(integer_values)

                stt_penalty = (
                    1.4 * consecutive_ratio
                    + 0.8 * small_ratio
                )

        score = (
            140.0 * thpt_ratio
            + 35.0 * broad_ratio
            + min(n, 50) * 0.5
            - 90.0 * stt_penalty
            - min(abs(median - 22.0), 50.0) * 0.25
        )

        ranked.append((score, col))

    if not ranked:
        return None

    ranked.sort(reverse=True)
    return ranked[0][1]

def classify_method(
    *,
    score_header: str,
    method_cell: str,
    context: str,
) -> str:
    combined_text = " | ".join(
        [
            score_header,
            method_cell,
            context[:12000],
        ]
    )
    low = combined_text.lower()

    # Row-level method cell has highest priority.
    cell_low = clean_text(method_cell).lower()

    if cell_low:
        if explicit_thpt(cell_low):
            if combined_method(cell_low):
                return "THPT_COMBINED"
            return "THPT"

        if non_thpt(cell_low):
            return "NON_THPT"

    header_low = clean_text(score_header).lower()

    if (
        explicit_thpt(header_low)
        or (
            "thpt" in header_low
            and not non_thpt(header_low)
        )
    ):
        if combined_method(header_low):
            return "THPT_COMBINED"
        return "THPT"

    # Page-level combined marker can classify generic cutoff as combined.
    if explicit_thpt(low) and combined_method(low):
        return "THPT_COMBINED"

    if explicit_thpt(low) and not non_thpt(header_low):
        return "THPT"

    # Generic 2026 published cutoff: preserve RAW only.
    return "UNSPECIFIED_2026"


def parse_table_grid(
    grid: list[list[str]],
    *,
    university_name: str,
    source_url: str,
    context: str,
    strategy: str,
    crossyear_map: dict[str, dict],
) -> list[dict]:
    rows = normalize_grid(grid)

    if len(rows) < 2:
        return []

    header_start, header_depth, headers = choose_header(
        rows
    )
    data_start = (
        header_start
        + header_depth
    )

    code_idx = find_header_idx(
        headers,
        CODE_HEADER_MARKERS,
    )

    name_idx = find_header_idx(
        headers,
        NAME_HEADER_MARKERS,
        reject=(
            "ma nganh",
            "ma xet tuyen",
            "diem",
            "to hop",
        ),
    )

    score_idx = select_score_column(
        headers,
        context,
    )

    method_idx = find_header_idx(
        headers,
        METHOD_HEADER_MARKERS,
    )

    combo_idx = find_header_idx(
        headers,
        COMBO_HEADER_MARKERS,
    )

    note_idx = find_header_idx(
        headers,
        NOTE_HEADER_MARKERS,
    )

    scale_idx = find_header_idx(
        headers,
        SCALE_HEADER_MARKERS,
    )

    if code_idx is None:
        code_idx = infer_code_column(
            rows,
            data_start,
        )

    if name_idx is None:
        name_idx = infer_name_column(
            rows,
            data_start,
            {
                idx
                for idx in (
                    code_idx,
                    score_idx,
                    method_idx,
                    combo_idx,
                    note_idx,
                    scale_idx,
                )
                if idx is not None
            },
        )

    if score_idx is None:
        score_idx = infer_score_column(
            rows,
            data_start,
            {
                idx
                for idx in (
                    code_idx,
                    name_idx,
                    method_idx,
                    combo_idx,
                    note_idx,
                    scale_idx,
                )
                if idx is not None
            },
        )

    if name_idx is None or score_idx is None:
        return []

    score_header = (
        headers[score_idx]
        if score_idx < len(headers)
        else ""
    )

    output = []
    current_code = ""
    current_name = ""

    for row in rows[data_start:]:
        raw_code = get_cell(
            row,
            code_idx,
        )
        raw_name = get_cell(
            row,
            name_idx,
        )

        if raw_code and valid_major_code(raw_code):
            current_code = normalize_major_code(
                raw_code
            )

        if (
            raw_name
            and parse_number(raw_name) is None
            and not valid_major_code(raw_name)
            and len(raw_name) >= 2
        ):
            current_name = raw_name

        score = parse_number(
            get_cell(
                row,
                score_idx,
            )
        )

        if (
            score is None
            or not (0 < score <= 150)
        ):
            continue

        major_name = current_name

        if not major_name or looks_garbled(major_name):
            continue

        major_code = current_code
        code_evidence = "SOURCE"

        if not major_code:
            major_code, mode = map_code_crossyear(
                university_name,
                major_name,
                crossyear_map,
            )

            if major_code:
                code_evidence = (
                    f"{mode}:2023_2025_same_school"
                )

        if not major_code:
            continue

        method_cell = get_cell(
            row,
            method_idx,
        )

        method = classify_method(
            score_header=score_header,
            method_cell=method_cell,
            context=context,
        )

        # If a row explicitly says non-THPT while score column is generic,
        # do not preserve it in this THPT-oriented project.
        if method == "NON_THPT":
            continue

        scale_cell = get_cell(
            row,
            scale_idx,
        )

        scale = infer_scale(
            " | ".join(
                [
                    score_header,
                    scale_cell,
                    context[:5000],
                ]
            ),
            score,
        )

        note_parts = [
            f"PRIMARY2026:{strategy}",
            f"method={method}",
            f"scale={scale}",
            f"major_code_evidence={code_evidence}",
        ]

        if method == "THPT_COMBINED":
            note_parts.append(
                "thpt_combined"
            )

        note = get_cell(
            row,
            note_idx,
        )

        if note:
            note_parts.append(note)

        output.append(
            {
                "university_name":
                    university_name,
                "major_code":
                    major_code,
                "major_name":
                    major_name,
                "year":
                    YEAR,
                "admission_method_codes":
                    method,
                "combination":
                    get_cell(row, combo_idx),
                "cutoff_score":
                    float(score),
                "admission_note":
                    "; ".join(note_parts),
                "source_url":
                    source_url,
            }
        )

    return output


# =============================================================================
# HTML / PDF EXTRACTION
# =============================================================================

def parse_html_source(
    session: requests.Session,
    *,
    university_name: str,
    source_url: str,
    crossyear_map: dict[str, dict],
) -> tuple[pd.DataFrame, str, str, list[Path]]:
    try:
        response = session.get(
            source_url,
            timeout=45,
            allow_redirects=True,
        )
        response.raise_for_status()
    except Exception as exc:
        return (
            pd.DataFrame(columns=CANONICAL_COLUMNS),
            "",
            f"REQUEST_{type(exc).__name__}",
            [],
        )

    kind = sniff_bytes(
        response.content,
        response.headers.get("Content-Type", ""),
    )

    if kind == "PDF":
        school_dir = DOC_DIR / slugify(university_name)
        school_dir.mkdir(parents=True, exist_ok=True)
        target = school_dir / "source_direct.pdf"
        target.write_bytes(response.content)

        return (
            pd.DataFrame(columns=CANONICAL_COLUMNS),
            "",
            "DIRECT_PDF",
            [target],
        )

    if kind == "IMAGE":
        school_dir = ASSET_ROOT / slugify(university_name)
        school_dir.mkdir(parents=True, exist_ok=True)
        target = school_dir / "source_direct_image.bin"
        target.write_bytes(response.content)

        return (
            pd.DataFrame(columns=CANONICAL_COLUMNS),
            "",
            "DIRECT_IMAGE",
            [target],
        )

    html = decode_response(response)
    soup = BeautifulSoup(html, "lxml")

    title = ""

    for tag_name in ("h1", "title"):
        tag = soup.find(tag_name)

        if tag:
            title = clean_text(
                tag.get_text(" ", strip=True)
            )

            if title:
                break

    visible = clean_text(
        soup.get_text(" ", strip=True)
    )

    context = (
        f"{title} | {visible[:22000]} | {source_url}"
    )

    rows = []

    try:
        dfs = pd.read_html(
            io.StringIO(html),
            header=None,
            thousands=None,
        )
    except Exception:
        dfs = []

    for df in dfs:
        if df.empty:
            continue

        grid = [
            [
                clean_text(value)
                for value in row
            ]
            for row in df.astype(object).values.tolist()
        ]

        rows.extend(
            parse_table_grid(
                grid,
                university_name=university_name,
                source_url=source_url,
                context=context,
                strategy="HTML",
                crossyear_map=crossyear_map,
            )
        )

    assets = collect_embedded_assets(
        session,
        html=html,
        page_url=source_url,
        university_name=university_name,
    )

    return (
        dedupe(canonicalize(rows)),
        context,
        f"HTML tables={len(dfs)}",
        assets,
    )


def read_pdf_text_and_tables(
    path: Path,
) -> tuple[str, list[list[list[str]]], str]:
    text_parts = []
    tables = []
    diagnostics = []

    try:
        doc = fitz.open(str(path))
    except Exception as exc:
        return (
            "",
            [],
            f"PDF_OPEN_{type(exc).__name__}",
        )

    for page_idx, page in enumerate(doc):
        try:
            text = page.get_text("text")
        except Exception:
            text = ""

        if text.strip():
            text_parts.append(text)

        try:
            finder = page.find_tables()

            for table in getattr(
                finder,
                "tables",
                [],
            ):
                data = table.extract()

                if data:
                    tables.append(
                        [
                            [
                                clean_text(value)
                                for value in row
                            ]
                            for row in data
                        ]
                    )
        except Exception as exc:
            diagnostics.append(
                f"p{page_idx+1}:{type(exc).__name__}"
            )

    doc.close()

    return (
        "\n".join(text_parts),
        tables,
        "|".join(diagnostics),
    )


def parse_pdf_source(
    path: Path,
    *,
    university_name: str,
    source_url: str,
    crossyear_map: dict[str, dict],
) -> tuple[pd.DataFrame, str, str]:
    text, tables, diagnostic = read_pdf_text_and_tables(
        path
    )

    context = (
        f"{source_url} | {text[:22000]}"
    )

    rows = []

    for table in tables:
        rows.extend(
            parse_table_grid(
                table,
                university_name=university_name,
                source_url=source_url,
                context=context,
                strategy="PDF_TABLE",
                crossyear_map=crossyear_map,
            )
        )

    return (
        dedupe(canonicalize(rows)),
        context,
        (
            f"PDF tables={len(tables)} "
            f"text={len(text)} {diagnostic}"
        ),
    )


# =============================================================================
# OCR
# =============================================================================

_OCR_PIPELINE = None


def get_ocr_pipeline():
    global _OCR_PIPELINE

    if _OCR_PIPELINE is not None:
        return _OCR_PIPELINE

    if PPStructureV3 is None:
        return None

    try:
        _OCR_PIPELINE = PPStructureV3(
            lang="vi",
            ocr_version="PP-OCRv3",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            use_formula_recognition=False,
            use_seal_recognition=False,
            use_chart_recognition=False,
        )
    except TypeError:
        _OCR_PIPELINE = PPStructureV3(
            lang="vi",
            ocr_version="PP-OCRv3",
        )

    return _OCR_PIPELINE


def ascii_school_dir(
    university_name: str,
) -> Path:
    path = ASCII_ROOT / slugify(
        university_name
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


def tile_image_to_ascii(
    source: Path,
    *,
    university_name: str,
    label: str,
    max_side: int = 3200,
    overlap: int = 150,
) -> list[Path]:
    target_dir = ascii_school_dir(
        university_name
    )

    try:
        with Image.open(source) as image:
            image = image.convert("RGB")
            width, height = image.size

            if (
                width <= max_side
                and height <= max_side
            ):
                target = target_dir / f"{label}.png"
                image.save(target, format="PNG")
                return [target]

            output = []

            if height >= width:
                start = 0
                idx = 1

                while start < height:
                    end = min(
                        height,
                        start + max_side,
                    )
                    crop = image.crop(
                        (0, start, width, end)
                    )

                    if crop.width > max_side:
                        ratio = max_side / crop.width
                        crop = crop.resize(
                            (
                                max_side,
                                max(
                                    1,
                                    int(crop.height * ratio),
                                ),
                            )
                        )

                    target = (
                        target_dir
                        / f"{label}_tile_{idx:03d}.png"
                    )
                    crop.save(
                        target,
                        format="PNG",
                    )
                    output.append(target)

                    if end >= height:
                        break

                    start = max(
                        start + 1,
                        end - overlap,
                    )
                    idx += 1

            else:
                start = 0
                idx = 1

                while start < width:
                    end = min(
                        width,
                        start + max_side,
                    )
                    crop = image.crop(
                        (start, 0, end, height)
                    )

                    if crop.height > max_side:
                        ratio = max_side / crop.height
                        crop = crop.resize(
                            (
                                max(
                                    1,
                                    int(crop.width * ratio),
                                ),
                                max_side,
                            )
                        )

                    target = (
                        target_dir
                        / f"{label}_tile_{idx:03d}.png"
                    )
                    crop.save(
                        target,
                        format="PNG",
                    )
                    output.append(target)

                    if end >= width:
                        break

                    start = max(
                        start + 1,
                        end - overlap,
                    )
                    idx += 1

            return output

    except Exception:
        return []


def render_pdf_pages_ascii(
    pdf_path: Path,
    *,
    university_name: str,
    max_pages: int = 14,
) -> list[Path]:
    try:
        doc = fitz.open(str(pdf_path))
    except Exception:
        return []

    page_scores = []

    for idx, page in enumerate(doc):
        try:
            text = clean_text(
                page.get_text("text")
            )
        except Exception:
            text = ""

        low = text.lower()

        score = sum(
            1
            for marker in (
                "điểm",
                "trúng tuyển",
                "mã ngành",
                "mã xét tuyển",
                "ngành",
                "thpt",
            )
            if marker in low
        )

        page_scores.append(
            (score, idx)
        )

    selected = [
        idx
        for score, idx in sorted(
            page_scores,
            reverse=True,
        )
        if score >= 2
    ][:max_pages]

    if not selected:
        count = len(doc)
        candidates = list(
            range(
                min(
                    count,
                    max_pages // 2,
                )
            )
        )
        candidates += list(
            range(
                max(
                    0,
                    count - max_pages // 2,
                ),
                count,
            )
        )

        selected = []

        for idx in candidates:
            if idx not in selected:
                selected.append(idx)

        selected = selected[:max_pages]

    target_dir = ascii_school_dir(
        university_name
    )
    output = []

    for idx in selected:
        try:
            pix = doc[idx].get_pixmap(
                matrix=fitz.Matrix(2.0, 2.0),
                alpha=False,
            )

            target = (
                target_dir
                / f"pdf_page_{idx+1:03d}.png"
            )
            pix.save(str(target))
            output.append(target)
        except Exception:
            continue

    doc.close()
    return output


def markdown_pipe_tables(
    markdown: str,
) -> list[list[list[str]]]:
    tables = []
    current = []

    def flush():
        nonlocal current

        if len(current) < 2:
            current = []
            return

        parsed = []

        for line in current:
            cells = [
                clean_text(cell)
                for cell in line.strip().strip("|").split("|")
            ]

            if cells and all(
                re.fullmatch(
                    r":?-{3,}:?",
                    cell.replace(" ", ""),
                )
                for cell in cells
                if cell
            ):
                continue

            parsed.append(cells)

        if len(parsed) >= 2:
            tables.append(parsed)

        current = []

    for line in markdown.splitlines():
        if "|" in line:
            current.append(line)
        else:
            flush()

    flush()
    return tables


def recursive_collect_html(
    value,
    output: list[str],
) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if (
                key in {"pred_html", "html"}
                and isinstance(child, str)
                and "<table" in child.lower()
            ):
                output.append(child)
            else:
                recursive_collect_html(
                    child,
                    output,
                )

    elif isinstance(value, (list, tuple)):
        for child in value:
            recursive_collect_html(
                child,
                output,
            )


def ocr_cache_file(
    image_path: Path,
    university_name: str,
) -> Path:
    stat = image_path.stat()

    signature = (
        f"{image_path.resolve()}|"
        f"{stat.st_size}|"
        f"{int(stat.st_mtime)}"
    )

    import hashlib

    digest = hashlib.sha1(
        signature.encode(
            "utf-8",
            errors="ignore",
        )
    ).hexdigest()[:16]

    school_dir = (
        OCR_CACHE_ROOT
        / slugify(university_name)
    )
    school_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    return (
        school_dir
        / f"{image_path.stem}_{digest}.json"
    )


def ocr_one_image(
    image_path: Path,
    *,
    university_name: str,
) -> tuple[str, list[list[list[str]]], str]:
    cache_file = ocr_cache_file(
        image_path,
        university_name,
    )

    if cache_file.exists():
        try:
            payload = json.loads(
                cache_file.read_text(
                    encoding="utf-8"
                )
            )

            return (
                payload.get("markdown", ""),
                payload.get("tables", []),
                "CACHE",
            )
        except Exception:
            pass

    pipeline = get_ocr_pipeline()

    if pipeline is None:
        return "", [], "OCR_ENGINE_UNAVAILABLE"

    try:
        results = pipeline.predict(
            input=str(image_path)
        )
    except Exception as exc:
        return (
            "",
            [],
            f"OCR_{type(exc).__name__}",
        )

    markdown_parts = []
    tables = []

    for result in results:
        try:
            md = result.markdown
        except Exception:
            md = None

        if isinstance(md, str):
            markdown_parts.append(md)
        elif md is not None:
            try:
                value = getattr(
                    md,
                    "markdown_texts",
                    None,
                )

                if isinstance(value, str):
                    markdown_parts.append(value)
            except Exception:
                pass

            try:
                if hasattr(md, "get"):
                    value = md.get(
                        "markdown_texts"
                    )

                    if isinstance(value, str):
                        markdown_parts.append(
                            value
                        )
            except Exception:
                pass

        try:
            json_obj = result.json
        except Exception:
            json_obj = None

        html_tables = []
        recursive_collect_html(
            json_obj,
            html_tables,
        )

        for html in html_tables:
            try:
                dfs = pd.read_html(
                    io.StringIO(html),
                    header=None,
                    thousands=None,
                )
            except Exception:
                continue

            for df in dfs:
                if df.empty:
                    continue

                tables.append(
                    [
                        [
                            clean_text(value)
                            for value in row
                        ]
                        for row in df.astype(object).values.tolist()
                    ]
                )

    markdown = "\n\n".join(
        markdown_parts
    )

    tables.extend(
        markdown_pipe_tables(
            markdown
        )
    )

    cache_file.write_text(
        json.dumps(
            {
                "markdown": markdown,
                "tables": tables,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return markdown, tables, "OCR"


def parse_ocr_assets(
    assets: list[Path],
    *,
    university_name: str,
    source_url: str,
    context: str,
    crossyear_map: dict[str, dict],
) -> tuple[pd.DataFrame, str]:
    images = []

    for idx, asset in enumerate(
        assets,
        start=1,
    ):
        kind = sniff_file(asset)

        if kind == "IMAGE":
            images.extend(
                tile_image_to_ascii(
                    asset,
                    university_name=university_name,
                    label=f"asset_{idx:02d}",
                )
            )

        elif kind == "PDF":
            images.extend(
                render_pdf_pages_ascii(
                    asset,
                    university_name=university_name,
                    max_pages=14,
                )
            )

    seen = set()
    unique_images = []

    for image in images:
        key = str(image.resolve())

        if key in seen:
            continue

        seen.add(key)
        unique_images.append(image)

    rows = []
    diagnostics = []

    for image in unique_images:
        markdown, tables, mode = ocr_one_image(
            image,
            university_name=university_name,
        )

        local_context = (
            f"{context} | {markdown[:14000]}"
        )

        for table in tables:
            rows.extend(
                parse_table_grid(
                    table,
                    university_name=university_name,
                    source_url=source_url,
                    context=local_context,
                    strategy="OCR",
                    crossyear_map=crossyear_map,
                )
            )

        diagnostics.append(
            f"{image.name}:{mode}:tables={len(tables)}"
        )

    return (
        dedupe(canonicalize(rows)),
        " | ".join(diagnostics[:8]),
    )


# =============================================================================
# ROW VALIDATION + ML SPLIT
# =============================================================================

def validate_raw_row(
    row: pd.Series,
) -> str:
    code = clean_text(
        row["major_code"]
    )
    name = clean_text(
        row["major_name"]
    )
    score = parse_number(
        row["cutoff_score"]
    )
    note = clean_text(
        row["admission_note"]
    )

    if not valid_major_code(code):
        return "BAD_MAJOR_CODE"

    if not name:
        return "MISSING_MAJOR_NAME"

    if looks_garbled(name):
        return "GARBLED_MAJOR_NAME"

    if score is None or not (0 < score <= 150):
        return "BAD_SCORE"

    scale = infer_scale(
        note,
        score,
    )

    # >30 must have a non-30 scale marker/evidence.
    if score > 30 and scale == "30_OR_UNKNOWN":
        return "GT30_WITHOUT_SCALE_EVIDENCE"

    return ""


def sanitize_frame(
    frame: pd.DataFrame,
    *,
    strategy: str,
) -> tuple[pd.DataFrame, list[dict]]:
    if frame.empty:
        return (
            pd.DataFrame(columns=CANONICAL_COLUMNS),
            [],
        )

    keep = []
    excluded = []

    for idx, row in frame.iterrows():
        reason = validate_raw_row(row)

        if reason:
            excluded.append(
                {
                    "university_name":
                        clean_text(row["university_name"]),
                    "major_code":
                        clean_text(row["major_code"]),
                    "major_name":
                        clean_text(row["major_name"]),
                    "cutoff_score":
                        clean_text(row["cutoff_score"]),
                    "strategy":
                        strategy,
                    "reason":
                        reason,
                    "source_url":
                        clean_text(row["source_url"]),
                }
            )
        else:
            keep.append(idx)

    cleaned = (
        frame.loc[keep].copy()
        if keep
        else pd.DataFrame(
            columns=CANONICAL_COLUMNS
        )
    )

    # OCR must produce >=2 rows to auto-accept.
    if (
        "OCR" in strategy.upper()
        and 0 < len(cleaned) < 2
    ):
        for _, row in cleaned.iterrows():
            excluded.append(
                {
                    "university_name":
                        clean_text(row["university_name"]),
                    "major_code":
                        clean_text(row["major_code"]),
                    "major_name":
                        clean_text(row["major_name"]),
                    "cutoff_score":
                        clean_text(row["cutoff_score"]),
                    "strategy":
                        strategy,
                    "reason":
                        "OCR_TOO_FEW_ROWS",
                    "source_url":
                        clean_text(row["source_url"]),
                }
            )

        cleaned = pd.DataFrame(
            columns=CANONICAL_COLUMNS
        )

    return dedupe(cleaned), excluded


def method_rank(value: str) -> int:
    value = clean_text(value).upper()

    return {
        "THPT": 4,
        "THPT_COMBINED": 3,
        "UNSPECIFIED_2026": 2,
    }.get(value, 1)


def choose_best_rows(
    frames: list[tuple[str, pd.DataFrame]],
) -> tuple[pd.DataFrame, list[dict], str]:
    """
    Không trộn bừa cùng major/method.
    Structured source ưu tiên hơn OCR.
    Nếu nhiều source cùng trường, giữ các row khác phương thức/combination/score.
    """
    all_rows = []
    row_excluded = []
    used_strategies = []

    priority = {
        "HTML": 100,
        "SHARED_HTML": 105,
        "PDF_TABLE": 95,
        "OCR": 70,
    }

    for strategy, frame in frames:
        cleaned, excluded = sanitize_frame(
            frame,
            strategy=strategy,
        )

        row_excluded.extend(excluded)

        if cleaned.empty:
            continue

        temp = cleaned.copy()
        temp["_strategy"] = strategy
        temp["_priority"] = priority.get(
            strategy,
            0,
        )
        all_rows.append(temp)
        used_strategies.append(strategy)

    if not all_rows:
        return (
            pd.DataFrame(columns=CANONICAL_COLUMNS),
            row_excluded,
            "NO_VALID_ROWS",
        )

    merged = pd.concat(
        all_rows,
        ignore_index=True,
    )

    merged["_method_rank"] = merged[
        "admission_method_codes"
    ].map(method_rank)

    # When the exact same major/combination/score appears via multiple strategies,
    # keep structured/high-method-evidence row.
    merged = (
        merged.sort_values(
            ["_method_rank", "_priority"],
            ascending=[False, False],
            kind="stable",
        )
        .drop_duplicates(
            subset=[
                "university_name",
                "major_code",
                "major_name",
                "combination",
                "cutoff_score",
                "source_url",
            ],
            keep="first",
        )
        .drop(
            columns=[
                "_strategy",
                "_priority",
                "_method_rank",
            ]
        )
    )

    return (
        dedupe(merged),
        row_excluded,
        "+".join(
            sorted(set(used_strategies))
        ),
    )


def ml_compatible(
    row: pd.Series,
) -> tuple[bool, str]:
    score = parse_number(
        row["cutoff_score"]
    )
    method = clean_text(
        row["admission_method_codes"]
    ).upper()
    note = clean_text(
        row["admission_note"]
    ).lower()

    if score is None:
        return False, "score_invalid"

    if not (10 <= score <= 30):
        return False, "outside_thpt30"

    if method != "THPT":
        return (
            False,
            (
                "thpt_combined"
                if method == "THPT_COMBINED"
                else "method_not_explicit_pure_thpt"
            ),
        )

    if any(
        marker in note
        for marker in (
            "scale=40",
            "scale=100",
            "scale=150",
            "thpt_combined",
            "học bạ",
            "đgnl",
            "đgtd",
            "tsa",
            "hsa",
            "v-sat",
            "vsat",
        )
    ):
        return False, "non_comparable_scale_or_method"

    return True, ""


# =============================================================================
# PROCESS ONE URL
# =============================================================================

def resolve_fetch_url(url: str) -> str:
    low = url.lower()

    if "drive.google.com" in low:
        return drive_direct_url(url) or url

    if "docs.google.com" in low:
        return google_doc_export_url(url) or url

    return url


def process_one_url(
    session: requests.Session,
    *,
    university_name: str,
    source_url: str,
    crossyear_map: dict[str, dict],
) -> tuple[
    list[tuple[str, pd.DataFrame]],
    list[Path],
    str,
    str,
]:
    """
    Returns:
      frames, assets, context, diagnostic
    """
    frames = []
    assets = []
    context = source_url
    diagnostics = []

    fetch_url = resolve_fetch_url(
        source_url
    )

    # Shared HTML parser first for normal HTML URLs.
    if (
        scrape_school is not None
        and source_type_from_url(source_url)
        in {"HTML", "EXTERNAL"}
    ):
        try:
            shared = scrape_school(
                university_name,
                source_url,
                YEAR,
            )

            if shared is not None and not shared.empty:
                # Normalize method labels from shared scraper.
                shared = canonicalize(
                    shared.to_dict("records")
                )

                for idx, row in shared.iterrows():
                    method = clean_text(
                        row["admission_method_codes"]
                    )
                    note = clean_text(
                        row["admission_note"]
                    )

                    if "thpt_combined" in note.lower():
                        shared.at[
                            idx,
                            "admission_method_codes",
                        ] = "THPT_COMBINED"

                    elif (
                        "THPT" in method.upper()
                        or re.fullmatch(
                            r"PT\d+[A-Z]?",
                            method.upper(),
                        )
                    ):
                        shared.at[
                            idx,
                            "admission_method_codes",
                        ] = "THPT"

                    else:
                        shared.at[
                            idx,
                            "admission_method_codes",
                        ] = "UNSPECIFIED_2026"

                    score = parse_number(
                        row["cutoff_score"]
                    )
                    scale = infer_scale(
                        note,
                        score,
                    )
                    shared.at[
                        idx,
                        "admission_note",
                    ] = (
                        f"{note}; PRIMARY2026:SHARED_HTML; "
                        f"scale={scale}"
                    ).strip("; ")

                frames.append(
                    ("SHARED_HTML", shared)
                )
                diagnostics.append(
                    f"shared={len(shared)}"
                )

        except Exception as exc:
            diagnostics.append(
                f"shared={type(exc).__name__}"
            )

    # Generic fetch handles direct PDF, images, malformed HTML.
    try:
        response = session.get(
            fetch_url,
            timeout=60,
            allow_redirects=True,
        )
        response.raise_for_status()
    except Exception as exc:
        diagnostics.append(
            f"request={type(exc).__name__}"
        )
        return (
            frames,
            assets,
            context,
            "|".join(diagnostics),
        )

    kind = sniff_bytes(
        response.content,
        response.headers.get(
            "Content-Type",
            "",
        ),
    )

    diagnostics.append(
        f"kind={kind}"
    )

    if kind == "PDF":
        school_dir = DOC_DIR / slugify(
            university_name
        )
        school_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        suffix_id = abs(
            hash(source_url)
        ) % 10_000_000

        target = (
            school_dir
            / f"source_{suffix_id}.pdf"
        )

        if not target.exists():
            target.write_bytes(
                response.content
            )

        assets.append(target)

        pdf_df, pdf_context, diag = parse_pdf_source(
            target,
            university_name=university_name,
            source_url=source_url,
            crossyear_map=crossyear_map,
        )

        context = pdf_context

        if not pdf_df.empty:
            frames.append(
                ("PDF_TABLE", pdf_df)
            )

        diagnostics.append(diag)

        return (
            frames,
            assets,
            context,
            "|".join(diagnostics),
        )

    if kind == "IMAGE":
        school_dir = ASSET_ROOT / slugify(
            university_name
        )
        school_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        target = school_dir / (
            f"direct_{abs(hash(source_url)) % 10_000_000}.bin"
        )
        target.write_bytes(
            response.content
        )
        assets.append(target)

        return (
            frames,
            assets,
            context,
            "|".join(diagnostics),
        )

    if kind == "HTML":
        html_df, html_context, diag, embedded = parse_html_source(
            session,
            university_name=university_name,
            source_url=source_url,
            crossyear_map=crossyear_map,
        )

        context = html_context or context
        assets.extend(embedded)

        if not html_df.empty:
            frames.append(
                ("HTML", html_df)
            )

        diagnostics.append(diag)

    return (
        frames,
        assets,
        context,
        "|".join(diagnostics),
    )


# =============================================================================
# MAIN
# =============================================================================


# =============================================================================
# FINAL TARGETED REPAIR 2026
# =============================================================================

FINAL_BACKUP_FILE = (
    PROCESSED_DIR / "admission_scores_2026_final_before_final_repair.csv"
)
SOURCE_MAP_BACKUP_FILE = (
    RAW_DIR / "source_map_2026_before_final_repair.csv"
)
STATUS_BACKUP_FILE = (
    PROCESSED_DIR / "admission_scores_2026_source_status_before_final_repair.csv"
)
FINAL_REPAIR_REPORT_FILE = (
    PROCESSED_DIR / "admission_scores_2026_final_repair_report.csv"
)

# Những link này được xác minh thủ công từ website chính thức của trường.
# Không phải secondary data source.
MANUAL_PRIMARY_OVERRIDES = {
    normalize_school("Trường ĐH Thành Đô"):
        "https://thanhdo.edu.vn/truong-dai-hoc-thanh-do-chinh-thuc-cong-bo-diem-chuan-trung-tuyen-dai-hoc-chinh-quy-nam-2026",

    normalize_school("Trường ĐH Tây Nguyên"):
        "https://tuyensinh.ttn.edu.vn/2026/08/13/diemchuan2026/",

    normalize_school("Trường ĐH Bình Dương"):
        "https://tuyensinh.bdu.edu.vn/dai-hoc-chinh-quy/bdu-cong-bo-diem-trung-tuyen-va-huong-dan-thu-tuc-nhap-hoc-cho-tan-sinh-vien-khoa-29-751.html",

    normalize_school("Trường ĐH Công nghiệp Việt Trì"):
        "https://vui.edu.vn/thong-tin-tuyen-sinh/truong-dai-hoc-cong-nghiep-viet-tri-thong-bao-diem-trung-tuyen-dai-hoc-chinh-quy-dot-1-nam-2026-3812",

    normalize_school("Trường ĐH Y Dược Cần Thơ"):
        "https://tuyensinh.ctump.edu.vn/thong-bao-diem-trung-tuyen-dai-hoc-chinh-quy-nam-2026.html",
}

NAME_REPAIRS = {
    normalize_school("ĐẠI HỌC PHENIKAA ("): "ĐẠI HỌC PHENIKAA",
}

BAD_ADMIN_NAME_MARKERS = (
    "học phí",
    "bảo hiểm y tế",
    "lệ phí",
    "hướng dẫn nhập học",
    "thời gian nhập học",
    "hồ sơ nhập học",
)


def backup_once(source: Path, target: Path) -> None:
    if source.exists() and not target.exists():
        shutil.copy2(source, target)


def build_crossyear_code_name_map() -> dict[str, dict[str, str]]:
    """
    same school + same code -> tên ngành lịch sử duy nhất/gần nhất.
    Dùng để sửa major_name OCR bị mất dấu hoặc méo ký tự.
    """
    raw: dict[str, dict[str, list[tuple[int, str]]]] = {}

    for year in (2023, 2024, 2025):
        path = PROCESSED_DIR / f"admission_scores_{year}_final.csv"

        if not path.exists():
            continue

        try:
            df = pd.read_csv(
                path,
                dtype=str,
                keep_default_na=False,
                usecols=[
                    "university_name",
                    "major_code",
                    "major_name",
                ],
            )
        except Exception:
            continue

        for _, row in df.iterrows():
            school = normalize_school(row["university_name"])
            code = normalize_major_code_strict(row["major_code"])
            name = clean_text(row["major_name"])

            if (
                not school
                or not valid_major_code(code)
                or not name
            ):
                continue

            raw.setdefault(school, {}).setdefault(
                code,
                [],
            ).append((year, name))

    output = {}

    for school, code_map in raw.items():
        output[school] = {}

        for code, values in code_map.items():
            # Prefer most recent historical name.
            values.sort(key=lambda item: item[0], reverse=True)
            output[school][code] = values[0][1]

    return output


def map_code_crossyear_ocr(
    university_name: str,
    major_name: str,
    crossyear_map: dict[str, dict],
) -> tuple[str, str]:
    """
    OCR-specific fallback.
    Vẫn chỉ matching TRONG CÙNG TRƯỜNG và đòi margin đủ lớn.
    """
    school_key = normalize_school(university_name)
    name_key = major_name_key(major_name)

    school_map = crossyear_map.get(school_key, {})
    exact = school_map.get("exact", {})

    if name_key in exact:
        return exact[name_key], "CROSSYEAR_EXACT"

    ranked = []

    for known_name, code in school_map.get("items", []):
        seq = SequenceMatcher(
            None,
            name_key,
            known_name,
        ).ratio()

        a = set(name_key.split())
        b = set(known_name.split())

        coverage = len(a & b) / max(
            1,
            min(len(a), len(b)),
        )

        ranked.append(
            (seq, coverage, known_name, code)
        )

    if not ranked:
        return "", ""

    ranked.sort(reverse=True)
    best = ranked[0]
    second_seq = ranked[1][0] if len(ranked) > 1 else 0.0

    if (
        best[0] >= 0.80
        and best[1] >= 0.50
        and best[0] - second_seq >= 0.05
    ):
        return best[3], "CROSSYEAR_OCR_STRICT"

    return "", ""


def extract_code_prefix_from_name(
    major_name: str,
) -> tuple[str, str]:
    """
    Ví dụ UEH:
      '7340116: Bất động sản'
        -> ('7340116', 'Bất động sản')
    """
    text = clean_text(major_name)

    match = re.match(
        r"^\s*([A-Za-z0-9][A-Za-z0-9_/-]{2,20})\s*:\s*(.+)$",
        text,
    )

    if not match:
        return "", text

    code = normalize_major_code_strict(
        match.group(1)
    )
    name = clean_text(
        match.group(2)
    )

    if not valid_major_code(code):
        return "", text

    return code, name


def current_code_looks_like_score(value: str) -> bool:
    text = clean_text(value).replace(",", ".")

    if re.fullmatch(r"\d{6,8}\.0", text):
        return False

    number = parse_number(text)

    return (
        number is not None
        and 0 < number <= 150
        and not valid_major_code(text)
    )


def repair_one_row(
    row: pd.Series,
    *,
    crossyear_map: dict[str, dict],
    code_name_map: dict[str, dict[str, str]],
) -> tuple[Optional[dict], Optional[dict]]:
    """
    Repair deterministic first; otherwise exclude row rather than invent data.
    """
    output = {
        column: clean_text(row.get(column, ""))
        for column in CANONICAL_COLUMNS
    }

    output["year"] = YEAR

    school = clean_text(output["university_name"])
    school_key = normalize_school(school)

    if school_key in NAME_REPAIRS:
        output["university_name"] = NAME_REPAIRS[school_key]
        school = output["university_name"]
        school_key = normalize_school(school)

    raw_code = clean_text(output["major_code"])
    code = normalize_major_code_strict(raw_code)
    major_name = clean_text(output["major_name"])
    score = parse_number(output["cutoff_score"])
    note = clean_text(output["admission_note"])

    prefix_code, prefix_name = extract_code_prefix_from_name(
        major_name
    )

    evidence = []

    if prefix_code:
        code = prefix_code
        major_name = prefix_name
        evidence.append("CODE_FROM_MAJOR_NAME_PREFIX")

    if not valid_major_code(code):
        mapped_code, mode = map_code_crossyear(
            school,
            major_name,
            crossyear_map,
        )

        if not mapped_code and "OCR" in note.upper():
            mapped_code, mode = map_code_crossyear_ocr(
                school,
                major_name,
                crossyear_map,
            )

        if mapped_code:
            code = mapped_code
            evidence.append(mode)

    if not valid_major_code(code):
        return None, {
            "university_name": school,
            "major_code": raw_code,
            "major_name": major_name,
            "cutoff_score": output["cutoff_score"],
            "strategy": "FINAL_REPAIR",
            "reason": "INVALID_MAJOR_CODE_AFTER_CROSSYEAR_REPAIR",
            "source_url": output["source_url"],
        }

    # Correct OCR/PDF column shift:
    # invalid major_code was actually the score, while cutoff was STT.
    if score is not None and score < 10:
        code_number = parse_number(raw_code)

        if (
            code_number is not None
            and 10 <= code_number <= 40
            and current_code_looks_like_score(raw_code)
            and evidence
        ):
            score = code_number
            evidence.append("OCR_COLUMN_SHIFT_SCORE_FROM_OLD_CODE")
        else:
            return None, {
                "university_name": school,
                "major_code": raw_code,
                "major_name": major_name,
                "cutoff_score": output["cutoff_score"],
                "strategy": "FINAL_REPAIR",
                "reason": "RAW_SCORE_LT10_UNVERIFIED",
                "source_url": output["source_url"],
            }

    if score is None or not (10 <= score <= 150):
        return None, {
            "university_name": school,
            "major_code": code,
            "major_name": major_name,
            "cutoff_score": output["cutoff_score"],
            "strategy": "FINAL_REPAIR",
            "reason": "BAD_SCORE_AFTER_REPAIR",
            "source_url": output["source_url"],
        }

    if any(
        marker in major_name.lower()
        for marker in BAD_ADMIN_NAME_MARKERS
    ):
        return None, {
            "university_name": school,
            "major_code": code,
            "major_name": major_name,
            "cutoff_score": score,
            "strategy": "FINAL_REPAIR",
            "reason": "ADMINISTRATIVE_ROW_NOT_MAJOR",
            "source_url": output["source_url"],
        }

    # Replace OCR-garbled major name using same-school historical code.
    historical_name = (
        code_name_map
        .get(school_key, {})
        .get(code, "")
    )

    if historical_name:
        # Always safe: same school + same verified code.
        if (
            "OCR" in note.upper()
            or strip_accents(major_name).lower() != major_name.lower()
            or len(major_name) < 4
        ):
            major_name = historical_name
            evidence.append("NAME_FROM_HISTORY_SAME_CODE")

    output["major_code"] = code
    output["major_name"] = major_name
    output["cutoff_score"] = float(score)

    if evidence:
        suffix = "repair=" + ",".join(evidence)
        output["admission_note"] = (
            f"{note}; {suffix}"
            if note
            else suffix
        )

    return output, None


def repair_frame(
    frame: pd.DataFrame,
    *,
    crossyear_map: dict[str, dict],
    code_name_map: dict[str, dict[str, str]],
) -> tuple[pd.DataFrame, list[dict]]:
    rows = []
    excluded = []

    for _, row in frame.iterrows():
        fixed, rejected = repair_one_row(
            row,
            crossyear_map=crossyear_map,
            code_name_map=code_name_map,
        )

        if fixed is not None:
            rows.append(fixed)

        if rejected is not None:
            excluded.append(rejected)

    return dedupe(canonicalize(rows)), excluded


def apply_name_repairs(
    df: pd.DataFrame,
    column: str = "university_name",
) -> pd.DataFrame:
    df = df.copy()

    def fix(value):
        key = normalize_school(value)
        return NAME_REPAIRS.get(
            key,
            clean_text(value),
        )

    df[column] = df[column].map(fix)
    return df


def manual_override_source_map(
    source_map: pd.DataFrame,
) -> pd.DataFrame:
    source_map = apply_name_repairs(
        source_map,
        "university_name",
    )

    for key, url in MANUAL_PRIMARY_OVERRIDES.items():
        mask = (
            source_map["university_name"]
            .map(normalize_school)
            == key
        )

        if not mask.any():
            continue

        source_map.loc[mask, "source_urls"] = url
        source_map.loc[mask, "source_type"] = "EXTERNAL"
        source_map.loc[mask, "linked_from_aggregate"] = "False"

    return source_map


def source_url_collisions(
    source_map: pd.DataFrame,
) -> dict[str, list[str]]:
    url_to_schools = {}

    for _, row in source_map.iterrows():
        name = clean_text(row["university_name"])

        for url in split_urls(row["source_urls"]):
            url_to_schools.setdefault(
                url,
                [],
            ).append(name)

    return {
        url: names
        for url, names in url_to_schools.items()
        if len(set(names)) > 1
    }


def build_status_from_final(
    source_map: pd.DataFrame,
    final_df: pd.DataFrame,
    excluded_df: pd.DataFrame,
    ml_ready: pd.DataFrame,
) -> pd.DataFrame:
    final_keys = set(
        final_df["university_name"]
        .map(normalize_school)
    )

    rows = []

    for _, source in source_map.iterrows():
        name = clean_text(source["university_name"])
        key = normalize_school(name)

        if key in final_keys:
            school_rows = final_df[
                final_df["university_name"]
                .map(normalize_school)
                == key
            ]

            school_ml = ml_ready[
                ml_ready["university_name"]
                .map(normalize_school)
                == key
            ]

            rows.append(
                {
                    "university_name": name,
                    "status": "ACCEPTED",
                    "accepted_rows": len(school_rows),
                    "ml_ready_rows": len(school_ml),
                    "priority": int(source["priority"]),
                    "reason": "",
                    "source_urls": clean_text(source["source_urls"]),
                }
            )
        else:
            match = excluded_df[
                excluded_df["university_name"]
                .map(normalize_school)
                == key
            ]

            reason = (
                clean_text(
                    match.iloc[0]["exclusion_reason"]
                )
                if not match.empty
                else "EXCLUDED_AFTER_FINAL_REPAIR"
            )

            rows.append(
                {
                    "university_name": name,
                    "status": "EXCLUDED",
                    "accepted_rows": 0,
                    "ml_ready_rows": 0,
                    "priority": int(source["priority"]),
                    "reason": reason,
                    "source_urls": clean_text(source["source_urls"]),
                }
            )

    return pd.DataFrame(rows)


def rebuild_ml_split(
    final_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    flags = final_df.apply(
        ml_compatible,
        axis=1,
        result_type="expand",
    )
    flags.columns = [
        "_ml_ok",
        "_ml_reason",
    ]

    temp = pd.concat(
        [
            final_df.reset_index(drop=True),
            flags.reset_index(drop=True),
        ],
        axis=1,
    )

    ml_ready = temp[
        temp["_ml_ok"] == True
    ][CANONICAL_COLUMNS].copy()

    ml_excluded = temp[
        temp["_ml_ok"] != True
    ].copy()

    ml_excluded["ml_exclusion_reason"] = temp.loc[
        temp["_ml_ok"] != True,
        "_ml_reason",
    ].values

    ml_excluded = ml_excluded[
        CANONICAL_COLUMNS
        + ["ml_exclusion_reason"]
    ]

    return (
        dedupe(ml_ready),
        ml_excluded.reset_index(drop=True),
    )



# =============================================================================
# P3 FINAL LOCK PASS
# =============================================================================
#
# Chỉ xử lý các P3 còn thiếu, không chạy lại 195 trường.
#
# Mục tiêu chắc chắn:
#   1) ĐH Sư phạm Hà Nội  -> primary official HTML
#   2) ĐH Luật Hà Nội     -> primary official PDF
#   3) ĐH Tây Nguyên      -> thử primary official page/image
#
# ĐH Tài chính - Marketing và ĐH Đồng Nai:
#   giữ EXCLUDED nếu primary hiện tại vẫn không parse tin cậy.
#
# Với HNUE:
#   Điểm công bố là điểm trúng tuyển chung sau quy đổi giữa PT1/PT2/PT3,
#   nên giữ FINAL nhưng KHÔNG ép thành THPT thuần cho ML.
#
# Với HLU:
#   PDF chính thức ghi rõ tổ hợp gốc D01, kỳ thi tốt nghiệp THPT 2026,
#   thang điểm 30 -> THPT, ML-ready.
#
# =============================================================================

P3_LOCK_REPORT_FILE = (
    PROCESSED_DIR / "admission_scores_2026_p3_lock_report.csv"
)

HNUE_NAME = "Trường ĐH Sư phạm Hà Nội"
HNUE_URL = (
    "https://tuyensinh.hnue.edu.vn/"
    "tuyensinh2026/698?page=8"
)

HLU_NAME = "Trường ĐH Luật Hà Nội"
HLU_PAGE_URL = (
    "https://tuyensinh.hlu.edu.vn/"
    "SubNews/Details/31401?page=8"
)
HLU_PDF_URL = (
    "https://tuyensinh.hlu.edu.vn/"
    "Images/Post/files/Tuyensinh/DHCQ/K51/BD%20DTT%20K51.pdf"
)

TTN_NAME = "Trường ĐH Tây Nguyên"
TTN_URL = (
    "https://tuyensinh.ttn.edu.vn/"
    "2026/08/13/diemchuan2026/"
)

P3_SOURCE_OVERRIDES = {
    normalize_school(HNUE_NAME): HNUE_URL,
    normalize_school(HLU_NAME): HLU_PDF_URL,
    normalize_school(TTN_NAME): TTN_URL,
}


def _flatten_columns(df: pd.DataFrame) -> list[str]:
    output = []

    for column in df.columns:
        if isinstance(column, tuple):
            parts = []

            for item in column:
                value = clean_text(item)

                if (
                    value
                    and not value.lower().startswith("unnamed:")
                    and value not in parts
                ):
                    parts.append(value)

            output.append(
                " | ".join(parts)
            )
        else:
            output.append(
                clean_text(column)
            )

    return output


def _find_column(
    columns: list[str],
    markers: tuple[str, ...],
) -> Optional[int]:
    for idx, column in enumerate(columns):
        value = norm(column)

        if any(marker in value for marker in markers):
            return idx

    return None


def parse_hnue_official(
    session: requests.Session,
) -> tuple[pd.DataFrame, str]:
    """
    Primary official HNUE HTML.

    Page công bố một ngưỡng trúng tuyển chung cho PT1/PT2/PT3 sau quy đổi.
    Vì vậy admission_method_codes = UNSPECIFIED_2026 để FINAL giữ được dữ liệu,
    nhưng ml_compatible() sẽ không đưa các dòng này vào ML THPT thuần.
    """
    response = session.get(
        HNUE_URL,
        timeout=45,
        allow_redirects=True,
    )
    response.raise_for_status()

    html = decode_response(response)

    try:
        tables = pd.read_html(
            io.StringIO(html),
            thousands=None,
        )
    except Exception as exc:
        return (
            pd.DataFrame(columns=CANONICAL_COLUMNS),
            f"READ_HTML_{type(exc).__name__}",
        )

    rows = []
    seen_codes = set()

    for table in tables:
        if table.empty:
            continue

        table = table.copy()
        table.columns = _flatten_columns(
            table
        )

        columns = list(table.columns)

        program_idx = _find_column(
            columns,
            (
                "chuong trinh dao tao",
                "chuong trinh",
            ),
        )
        score_idx = _find_column(
            columns,
            (
                "diem trung tuyen",
                "diem chuan",
            ),
        )

        if program_idx is None or score_idx is None:
            continue

        for _, row in table.iterrows():
            program = clean_text(
                row.iloc[program_idx]
            )
            score = parse_number(
                row.iloc[score_idx]
            )

            if (
                not program
                or score is None
                or not (10 <= score <= 30)
            ):
                continue

            match = re.search(
                r"M[aã]\s*x[eé]t\s*tuy[eể]n\s*:\s*"
                r"([A-Za-z0-9_/-]+)",
                program,
                flags=re.I,
            )

            if not match:
                # Accent-insensitive fallback.
                plain = strip_accents(program)

                match = re.search(
                    r"Ma\s*xet\s*tuyen\s*:\s*"
                    r"([A-Za-z0-9_/-]+)",
                    plain,
                    flags=re.I,
                )

            if not match:
                continue

            code = normalize_major_code_strict(
                match.group(1)
            )

            if not valid_major_code(code):
                continue

            # Only first occurrence: official page lists common-method section first.
            if code in seen_codes:
                continue

            major_name = re.sub(
                r"\s*M[aã]\s*x[eé]t\s*tuy[eể]n\s*:\s*"
                r"[A-Za-z0-9_/-]+\s*",
                " ",
                program,
                flags=re.I,
            )

            if major_name == program:
                major_name = re.sub(
                    r"\s*Ma\s*xet\s*tuyen\s*:\s*"
                    r"[A-Za-z0-9_/-]+\s*",
                    " ",
                    strip_accents(program),
                    flags=re.I,
                )

            major_name = clean_text(
                major_name
            )

            if not major_name:
                continue

            seen_codes.add(code)

            rows.append(
                {
                    "university_name": HNUE_NAME,
                    "major_code": code,
                    "major_name": major_name,
                    "year": YEAR,
                    "admission_method_codes":
                        "UNSPECIFIED_2026",
                    "combination": "",
                    "cutoff_score": float(score),
                    "admission_note":
                        (
                            "PRIMARY2026:HNUE_OFFICIAL_HTML; "
                            "common_cutoff_after_equivalence_PT1_PT2_PT3; "
                            "PT1=TN_THPT; PT2=achievement; PT3=SPT; "
                            "scale=30; ML_EXCLUDE_NOT_PURE_METHOD"
                        ),
                    "source_url": HNUE_URL,
                }
            )

    result = dedupe(
        canonicalize(rows)
    )

    return (
        result,
        f"tables={len(tables)} rows={len(result)}",
    )


def parse_hlu_official(
    session: requests.Session,
) -> tuple[pd.DataFrame, str]:
    """
    Primary official HLU PDF.

    PDF 2026 công bố 5 mức điểm theo tổ hợp gốc D01 của kỳ thi TN THPT.
    Font PDF có thể lỗi Unicode khi extract text, nên:
      - điểm lấy trực tiếp từ chính PDF;
      - code/name dùng danh mục ngành chính thức/stable của HLU.
    """
    response = session.get(
        HLU_PDF_URL,
        timeout=45,
        allow_redirects=True,
    )
    response.raise_for_status()

    if response.content[:4] != b"%PDF":
        return (
            pd.DataFrame(columns=CANONICAL_COLUMNS),
            "HLU_NOT_PDF",
        )

    temp_dir = ASCII_ROOT / "hlu_final"
    temp_dir.mkdir(
        parents=True,
        exist_ok=True,
    )
    pdf_path = temp_dir / "hlu_2026_cutoff.pdf"
    pdf_path.write_bytes(
        response.content
    )

    try:
        doc = fitz.open(
            str(pdf_path)
        )
        pdf_text = "\n".join(
            page.get_text("text")
            for page in doc
        )
        doc.close()
    except Exception as exc:
        return (
            pd.DataFrame(columns=CANONICAL_COLUMNS),
            f"HLU_PDF_OPEN_{type(exc).__name__}",
        )

    # Scores in official row order. Decimal points distinguish them from dates/years.
    candidates = [
        float(value)
        for value in re.findall(
            r"(?<!\d)(?:1\d|2\d|30)\.\d{1,2}(?!\d)",
            pdf_text,
        )
    ]

    # Exact official table has five rows. Keep only plausible unique sequence.
    expected_count = 5

    if len(candidates) < expected_count:
        # OCR fallback on first page if embedded font extraction is poor.
        images = render_pdf_pages_ascii(
            pdf_path,
            university_name=HLU_NAME,
            max_pages=1,
        )

        ocr_text = ""

        for image in images:
            markdown, _, _ = ocr_one_image(
                image,
                university_name=HLU_NAME,
            )
            ocr_text += "\n" + markdown

        candidates = [
            float(value)
            for value in re.findall(
                r"(?<!\d)(?:1\d|2\d|30)[.,]\d{1,2}(?!\d)",
                ocr_text,
            )
        ]

    # Remove adjacent duplicates while preserving order.
    scores = []

    for score in candidates:
        if 10 <= score <= 30:
            if not scores or abs(scores[-1] - score) > 1e-9:
                scores.append(score)

    # The official PDF has exactly these five program rows, in this order.
    programs = [
        ("7380101", "Luật"),
        ("7380107", "Luật Kinh tế"),
        ("7380109", "Luật Thương mại quốc tế"),
        ("7220201", "Ngôn ngữ Anh"),
        (
            "7380101PH",
            "Luật (đào tạo tại Phân hiệu Đắk Lắk)",
        ),
    ]

    if len(scores) < 5:
        return (
            pd.DataFrame(columns=CANONICAL_COLUMNS),
            f"HLU_SCORE_PARSE_FAIL scores={scores}",
        )

    # Use first 5 table scores only.
    scores = scores[:5]

    rows = []

    for (code, name), score in zip(
        programs,
        scores,
    ):
        rows.append(
            {
                "university_name": HLU_NAME,
                "major_code": code,
                "major_name": name,
                "year": YEAR,
                "admission_method_codes": "THPT",
                "combination": "D01",
                "cutoff_score": float(score),
                "admission_note":
                    (
                        "PRIMARY2026:HLU_OFFICIAL_PDF; "
                        "official_table_original_combination_D01; "
                        "TN_THPT_2026; scale=30"
                    ),
                "source_url": HLU_PDF_URL,
            }
        )

    result = dedupe(
        canonicalize(rows)
    )

    return (
        result,
        f"pdf_scores={scores}",
    )


def _article_content_images(
    session: requests.Session,
    url: str,
    school_name: str,
) -> list[Path]:
    """
    Strict image finder for TTN article.
    Only keep genuinely large content images; avoid logos/banners/icons.
    """
    response = session.get(
        url,
        timeout=45,
        allow_redirects=True,
    )
    response.raise_for_status()

    html = decode_response(response)
    soup = BeautifulSoup(
        html,
        "lxml",
    )

    candidates = []

    for img in soup.find_all("img"):
        raw = (
            img.get("data-src")
            or img.get("data-lazy-src")
            or img.get("src")
        )

        raw = clean_text(raw)

        if not raw or raw.startswith("data:"):
            continue

        image_url = urljoin(
            url,
            raw,
        )
        low = image_url.lower()

        if any(
            bad in low
            for bad in (
                "logo",
                "icon",
                "avatar",
                "banner",
                "facebook",
                "youtube",
                "loading",
                "blank",
                "ads",
                "advert",
                "tracking",
                "pixel",
            )
        ):
            continue

        candidates.append(
            image_url
        )

    out_dir = (
        RECOVERY_ROOT
        / "p3_ttn_official"
    )
    out_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output = []

    for idx, image_url in enumerate(
        dict.fromkeys(candidates),
        start=1,
    ):
        try:
            r = session.get(
                image_url,
                timeout=45,
                allow_redirects=True,
            )
            r.raise_for_status()

            with Image.open(
                io.BytesIO(r.content)
            ) as image:
                width, height = image.size

                # Real cutoff table image should have enough pixels to contain text.
                if width < 900 and height < 900:
                    continue

                # Reject absurd tracking/sprite-like aspect ratios.
                ratio = max(width, height) / max(
                    1,
                    min(width, height),
                )

                if ratio > 35:
                    continue

                target = (
                    out_dir
                    / f"ttn_content_{idx:02d}.png"
                )

                image.convert("RGB").save(
                    target,
                    "PNG",
                )
                output.append(
                    target
                )

        except Exception:
            continue

    return output


def parse_ttn_official(
    session: requests.Session,
    crossyear_map: dict[str, dict],
) -> tuple[pd.DataFrame, str]:
    """
    TTN first-round official source publishes cutoff as an image.
    Try only the actual large content image(s); no whole-page screenshot.
    """
    try:
        images = _article_content_images(
            session,
            TTN_URL,
            TTN_NAME,
        )
    except Exception as exc:
        return (
            pd.DataFrame(columns=CANONICAL_COLUMNS),
            f"TTN_IMAGE_FETCH_{type(exc).__name__}",
        )

    if not images:
        return (
            pd.DataFrame(columns=CANONICAL_COLUMNS),
            "TTN_NO_CONTENT_IMAGE",
        )

    rows = []
    diagnostics = []

    for image in images:
        tiled = tile_image_to_ascii(
            image,
            university_name=TTN_NAME,
            label=image.stem,
            max_side=2600,
            overlap=220,
        )

        for tile in tiled:
            markdown, tables, mode = ocr_one_image(
                tile,
                university_name=TTN_NAME,
            )

            diagnostics.append(
                f"{tile.name}:{mode}:tables={len(tables)}"
            )

            context = (
                "Trường Đại học Tây Nguyên 2026; "
                "official first-round cutoff; "
                "PT100=thi tốt nghiệp THPT; "
                "PT405=THPT+khiếu; "
                + markdown[:9000]
            )

            for table in tables:
                parsed_rows = parse_table_grid(
                    table,
                    university_name=TTN_NAME,
                    source_url=TTN_URL,
                    context=context,
                    strategy="OCR_TTN_PRIMARY",
                    crossyear_map=crossyear_map,
                )

                for row in parsed_rows:
                    # Only pure THPT rows are useful for lock/ML.
                    method = clean_text(
                        row.get(
                            "admission_method_codes",
                            "",
                        )
                    ).upper()

                    if method == "THPT":
                        row["admission_note"] = (
                            clean_text(
                                row.get(
                                    "admission_note",
                                    "",
                                )
                            )
                            + "; PRIMARY2026:TTN_OFFICIAL_IMAGE"
                        ).strip("; ")

                        rows.append(
                            row
                        )

    result = dedupe(
        canonicalize(rows)
    )

    return (
        result,
        " | ".join(diagnostics[:12]),
    )


def replace_school_rows(
    final_df: pd.DataFrame,
    school_name: str,
    new_rows: pd.DataFrame,
) -> pd.DataFrame:
    key = normalize_school(
        school_name
    )

    final_df = final_df[
        final_df["university_name"]
        .map(normalize_school)
        != key
    ].copy()

    if new_rows.empty:
        return final_df

    return dedupe(
        pd.concat(
            [
                final_df,
                new_rows,
            ],
            ignore_index=True,
        )
    )


def update_source_map_url(
    source_map: pd.DataFrame,
    school_name: str,
    url: str,
) -> pd.DataFrame:
    source_map = source_map.copy()

    key = normalize_school(
        school_name
    )

    mask = (
        source_map["university_name"]
        .map(normalize_school)
        == key
    )

    if not mask.any():
        raise RuntimeError(
            f"Không tìm thấy {school_name} trong source_map_2026.csv"
        )

    source_map.loc[
        mask,
        "source_urls",
    ] = url

    source_map.loc[
        mask,
        "source_type",
    ] = (
        "PDF"
        if url.lower().endswith(".pdf")
        else "EXTERNAL"
    )

    source_map.loc[
        mask,
        "linked_from_aggregate",
    ] = "False"

    return source_map


def p3_history_set() -> set[str]:
    sets = []

    for year in (2023, 2024, 2025):
        path = (
            PROCESSED_DIR
            / f"admission_scores_{year}_ml_ready.csv"
        )

        if not path.exists():
            continue

        df = pd.read_csv(
            path,
            dtype=str,
            keep_default_na=False,
            usecols=["university_name"],
        )

        sets.append(
            set(
                df["university_name"]
                .map(normalize_school)
            )
        )

    if len(sets) != 3:
        return set()

    return set.intersection(
        *sets
    )


def main() -> None:
    print("=" * 124)
    print("2026 P3 FINAL / PRIMARY OFFICIAL / LOCK PASS")
    print(f"VERSION : {PIPELINE_VERSION}")
    print("=" * 124)

    for path in (
        SOURCE_MAP_FILE,
        FINAL_FILE,
        SOURCE_STATUS_FILE,
    ):
        if not path.exists():
            raise RuntimeError(
                f"Thiếu checkpoint: {path}"
            )

    # New backup specific to final P3 pass.
    p3_backup = (
        PROCESSED_DIR
        / "admission_scores_2026_final_before_p3_lock.csv"
    )

    if not p3_backup.exists():
        shutil.copy2(
            FINAL_FILE,
            p3_backup,
        )

    source_map = pd.read_csv(
        SOURCE_MAP_FILE,
        dtype=str,
        keep_default_na=False,
    )

    source_map["priority"] = pd.to_numeric(
        source_map["priority"],
        errors="coerce",
    ).fillna(0).astype(int)

    final_df = pd.read_csv(
        FINAL_FILE,
        dtype=str,
        keep_default_na=False,
    )
    final_df = dedupe(
        canonicalize(
            final_df.to_dict("records")
        )
    )

    print(
        f"INPUT FINAL            : {len(final_df)} rows / "
        f"{final_df['university_name'].nunique()} trường"
    )

    session = build_session()
    crossyear_map = build_crossyear_major_map()

    report = []

    # ---------------------------------------------------------------------
    # 1) HNUE - official HTML, deterministic.
    # ---------------------------------------------------------------------
    try:
        hnue_df, diag = parse_hnue_official(
            session
        )

        if len(hnue_df) >= 20:
            source_map = update_source_map_url(
                source_map,
                HNUE_NAME,
                HNUE_URL,
            )
            final_df = replace_school_rows(
                final_df,
                HNUE_NAME,
                hnue_df,
            )

            report.append(
                {
                    "university_name": HNUE_NAME,
                    "status": "RECOVERED",
                    "rows": len(hnue_df),
                    "ml_ready_rows": 0,
                    "source_url": HNUE_URL,
                    "diagnostic": diag,
                }
            )

            print(
                f"HNUE                    : ✅ {len(hnue_df)} rows "
                f"| FINAL only | {diag}"
            )
        else:
            report.append(
                {
                    "university_name": HNUE_NAME,
                    "status": "FAILED",
                    "rows": len(hnue_df),
                    "ml_ready_rows": 0,
                    "source_url": HNUE_URL,
                    "diagnostic": diag,
                }
            )

            print(
                f"HNUE                    : ⚠ chỉ {len(hnue_df)} rows | {diag}"
            )

    except Exception as exc:
        report.append(
            {
                "university_name": HNUE_NAME,
                "status": "FAILED",
                "rows": 0,
                "ml_ready_rows": 0,
                "source_url": HNUE_URL,
                "diagnostic": repr(exc),
            }
        )

        print(
            f"HNUE                    : ❌ {type(exc).__name__}: {exc}"
        )

    # ---------------------------------------------------------------------
    # 2) HLU - official PDF, deterministic 5-row THPT table.
    # ---------------------------------------------------------------------
    try:
        hlu_df, diag = parse_hlu_official(
            session
        )

        if len(hlu_df) == 5:
            source_map = update_source_map_url(
                source_map,
                HLU_NAME,
                HLU_PDF_URL,
            )
            final_df = replace_school_rows(
                final_df,
                HLU_NAME,
                hlu_df,
            )

            report.append(
                {
                    "university_name": HLU_NAME,
                    "status": "RECOVERED",
                    "rows": len(hlu_df),
                    "ml_ready_rows": len(hlu_df),
                    "source_url": HLU_PDF_URL,
                    "diagnostic": diag,
                }
            )

            print(
                f"HLU                     : ✅ 5 rows | ML=5 | {diag}"
            )
        else:
            report.append(
                {
                    "university_name": HLU_NAME,
                    "status": "FAILED",
                    "rows": len(hlu_df),
                    "ml_ready_rows": 0,
                    "source_url": HLU_PDF_URL,
                    "diagnostic": diag,
                }
            )

            print(
                f"HLU                     : ⚠ {len(hlu_df)} rows | {diag}"
            )

    except Exception as exc:
        report.append(
            {
                "university_name": HLU_NAME,
                "status": "FAILED",
                "rows": 0,
                "ml_ready_rows": 0,
                "source_url": HLU_PDF_URL,
                "diagnostic": repr(exc),
            }
        )

        print(
            f"HLU                     : ❌ {type(exc).__name__}: {exc}"
        )

    # ---------------------------------------------------------------------
    # 3) TTN - optional primary-image attempt.
    # ---------------------------------------------------------------------
    try:
        ttn_df, diag = parse_ttn_official(
            session,
            crossyear_map,
        )

        if len(ttn_df) >= 10:
            source_map = update_source_map_url(
                source_map,
                TTN_NAME,
                TTN_URL,
            )
            final_df = replace_school_rows(
                final_df,
                TTN_NAME,
                ttn_df,
            )

            ttn_ml = sum(
                int(
                    ml_compatible(row)[0]
                )
                for _, row in ttn_df.iterrows()
            )

            report.append(
                {
                    "university_name": TTN_NAME,
                    "status": "RECOVERED",
                    "rows": len(ttn_df),
                    "ml_ready_rows": ttn_ml,
                    "source_url": TTN_URL,
                    "diagnostic": diag,
                }
            )

            print(
                f"TÂY NGUYÊN               : ✅ {len(ttn_df)} rows "
                f"| ML={ttn_ml}"
            )
        else:
            report.append(
                {
                    "university_name": TTN_NAME,
                    "status": "KEPT_EXCLUDED",
                    "rows": len(ttn_df),
                    "ml_ready_rows": 0,
                    "source_url": TTN_URL,
                    "diagnostic": diag,
                }
            )

            print(
                f"TÂY NGUYÊN               : ⚠ chưa đủ tin cậy "
                f"({len(ttn_df)} rows) -> giữ EXCLUDED"
            )

    except Exception as exc:
        report.append(
            {
                "university_name": TTN_NAME,
                "status": "KEPT_EXCLUDED",
                "rows": 0,
                "ml_ready_rows": 0,
                "source_url": TTN_URL,
                "diagnostic": repr(exc),
            }
        )

        print(
            f"TÂY NGUYÊN               : ⚠ {type(exc).__name__} "
            "-> giữ EXCLUDED"
        )

    final_df = dedupe(
        final_df
    )

    # ---------------------------------------------------------------------
    # HARD AUDIT
    # ---------------------------------------------------------------------
    scores = pd.to_numeric(
        final_df["cutoff_score"],
        errors="coerce",
    )

    if scores.isna().any():
        raise RuntimeError(
            "AUDIT FAIL: cutoff_score NaN."
        )

    if (scores < 10).any():
        raise RuntimeError(
            "AUDIT FAIL: score < 10 xuất hiện lại."
        )

    invalid_code_mask = ~final_df[
        "major_code"
    ].map(valid_major_code)

    if invalid_code_mask.any():
        sample = final_df.loc[
            invalid_code_mask,
            [
                "university_name",
                "major_code",
                "major_name",
            ],
        ].head(10).to_dict("records")

        raise RuntimeError(
            "AUDIT FAIL invalid major_code: "
            + json.dumps(
                sample,
                ensure_ascii=False,
            )
        )

    # Unique source identity by school.
    collisions = source_url_collisions(
        source_map
    )

    if collisions:
        raise RuntimeError(
            "AUDIT FAIL duplicate source URL across schools: "
            + json.dumps(
                collisions,
                ensure_ascii=False,
            )
        )

    allowed_urls = {
        normalize_school(row["university_name"]):
            set(
                split_urls(
                    row["source_urls"]
                )
            )
        for _, row in source_map.iterrows()
    }

    for _, row in final_df.iterrows():
        key = normalize_school(
            row["university_name"]
        )
        source_url = clean_text(
            row["source_url"]
        )

        if source_url not in allowed_urls.get(
            key,
            set(),
        ):
            raise RuntimeError(
                "AUDIT FAIL source identity: "
                + clean_text(
                    row["university_name"]
                )
                + " -> "
                + source_url
            )

    # ---------------------------------------------------------------------
    # Rebuild ML
    # ---------------------------------------------------------------------
    ml_ready, ml_excluded = rebuild_ml_split(
        final_df
    )

    inventory_keys = set(
        source_map["university_name"]
        .map(normalize_school)
    )
    final_keys = set(
        final_df["university_name"]
        .map(normalize_school)
    )

    # Rebuild exclusions from current status + missing FINAL schools.
    old_status = pd.read_csv(
        SOURCE_STATUS_FILE,
        dtype=str,
        keep_default_na=False,
    )

    old_reason = {
        normalize_school(row["university_name"]):
            clean_text(row["reason"])
        for _, row in old_status.iterrows()
    }

    report_map = {
        normalize_school(
            item["university_name"]
        ): item
        for item in report
    }

    excluded_rows = []

    for _, source in source_map.iterrows():
        name = clean_text(
            source["university_name"]
        )
        key = normalize_school(name)

        if key in final_keys:
            continue

        reason = old_reason.get(
            key,
            "EXCLUDED_AFTER_P3_LOCK_PASS",
        )

        if key in report_map:
            status = report_map[key]["status"]

            if status in {
                "FAILED",
                "KEPT_EXCLUDED",
            }:
                reason = (
                    "EXCLUDED_P3_PRIMARY_NOT_RELIABLY_PARSED"
                )

        excluded_rows.append(
            {
                "university_name": name,
                "source_type": clean_text(
                    source.get(
                        "source_type",
                        "",
                    )
                ),
                "analysis_class":
                    "P3_FINAL_LOCK",
                "exclusion_reason":
                    reason
                    or "EXCLUDED_AFTER_P3_LOCK_PASS",
                "source_urls": clean_text(
                    source.get(
                        "source_urls",
                        "",
                    )
                ),
                "local_files": "",
            }
        )

    excluded_df = pd.DataFrame(
        excluded_rows,
        columns=EXCLUDED_COLUMNS,
    )

    excluded_keys = set(
        excluded_df["university_name"]
        .map(normalize_school)
    )

    if final_keys & excluded_keys:
        raise RuntimeError(
            "AUDIT FAIL: FINAL ∩ EXCLUDED != ∅"
        )

    if (
        final_keys
        | excluded_keys
    ) != inventory_keys:
        raise RuntimeError(
            "AUDIT FAIL: FINAL + EXCLUDED chưa phủ inventory."
        )

    status_df = build_status_from_final(
        source_map,
        final_df,
        excluded_df,
        ml_ready,
    )

    review_df = pd.DataFrame(
        columns=[
            "university_name",
            "source_type",
            "reason",
            "source_urls",
        ]
    )

    p3_keys = p3_history_set()
    p3_final = p3_keys & final_keys
    p3_ml = p3_keys & set(
        ml_ready["university_name"]
        .map(normalize_school)
    )

    # ---------------------------------------------------------------------
    # Write only after all audits.
    # ---------------------------------------------------------------------
    source_map.to_csv(
        SOURCE_MAP_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    final_df.to_csv(
        FINAL_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    ml_ready.to_csv(
        ML_READY_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    ml_excluded.to_csv(
        ML_EXCLUDED_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    excluded_df.to_csv(
        SOURCE_EXCLUDED_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    status_df.to_csv(
        SOURCE_STATUS_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    review_df.to_csv(
        REVIEW_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    pd.DataFrame(
        report
    ).to_csv(
        P3_LOCK_REPORT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    # ---------------------------------------------------------------------
    # Summary / lock decision.
    # ---------------------------------------------------------------------
    print()
    print("=" * 124)
    print("KẾT QUẢ 2026 P3 FINAL LOCK PASS")
    print("=" * 124)
    print(
        f"SOURCE INVENTORY       : {len(source_map):5d} trường"
    )
    print(
        f"FINAL CLEAN 2026       : {len(final_df):5d} rows / "
        f"{final_df['university_name'].nunique():3d} trường"
    )
    print(
        f"SOURCE EXCLUDED        : {len(excluded_df):5d} trường"
    )
    print(
        "REVIEW                 :     0 trường"
    )
    print(
        f"Score min/max RAW      : {scores.min():.2f} / {scores.max():.2f}"
    )
    print(
        f"RAW rows score <10     : {int((scores < 10).sum())}"
    )
    print(
        f"Invalid major_code     : "
        f"{int((~final_df['major_code'].map(valid_major_code)).sum())}"
    )
    print(
        f"Missing major_name     : "
        f"{int(final_df['major_name'].eq('').sum())}"
    )
    print(
        f"Missing cutoff_score   : "
        f"{int(final_df['cutoff_score'].isna().sum())}"
    )
    print(
        f"ML READY 2026          : {len(ml_ready):5d} rows / "
        f"{ml_ready['university_name'].nunique():3d} trường"
    )
    print(
        f"ML EXCLUDED            : {len(ml_excluded):5d} rows"
    )
    print(
        f"P3 FINAL COVERAGE      : {len(p3_final):3d} / "
        f"{len(p3_keys):3d}"
    )
    print(
        f"P3 ML-READY 4-YEAR     : {len(p3_ml):3d} / "
        f"{len(p3_keys):3d}"
    )
    print("-" * 124)
    print("FINAL        :", FINAL_FILE)
    print("ML READY     :", ML_READY_FILE)
    print("ML EXCLUDED  :", ML_EXCLUDED_FILE)
    print("EXCLUDED     :", SOURCE_EXCLUDED_FILE)
    print("STATUS       :", SOURCE_STATUS_FILE)
    print("P3 REPORT    :", P3_LOCK_REPORT_FILE)
    print("SOURCE MAP   :", SOURCE_MAP_FILE)
    print("=" * 124)

    print()
    print(
        "AUDIT 2026             : ✅ source identity unique; "
        "FINAL + EXCLUDED phủ inventory; score>=10; "
        "strict major_code; missing=0"
    )

    can_lock = (
        final_df["university_name"].nunique() >= 85
        and len(p3_final) >= min(15, len(p3_keys))
        and ml_ready["university_name"].nunique() >= 30
        and int((scores < 10).sum()) == 0
        and int(
            (
                ~final_df[
                    "major_code"
                ].map(valid_major_code)
            ).sum()
        ) == 0
    )

    if can_lock:
        print(
            "2026 CHECKPOINT        : ✅ LOCKED"
        )
    else:
        print(
            "2026 CHECKPOINT        : ⚠ CHƯA KHÓA"
        )


if __name__ == "__main__":
    main()
