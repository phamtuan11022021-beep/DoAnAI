from __future__ import annotations

import io
import os
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
    from paddleocr import PPStructureV3
except ImportError:
    PPStructureV3 = None


# =============================================================================
# 2024 FINAL TARGETED RECOVERY
# =============================================================================
#
# MỤC TIÊU
# -------
# Dùng checkpoint hiện tại:
#   FINAL 2024 = 818 rows / 36 trường
#   EXCLUDED   = 131 trường
#
# Chỉ cứu các nguồn bị loại vì LỖI KỸ THUẬT / PARSER, không đụng vào dữ liệu
# 36 trường đã pass.
#
# Thứ tự recovery:
#   1. Parse lại bảng HTML primary bằng parser linh hoạt hơn.
#   2. PDF text: dùng PyMuPDF find_tables() + text parser, KHÔNG OCR trước.
#   3. Tận dụng cache PP-StructureV3 đã tạo ở lần trước.
#   4. Ảnh lỗi "Image read Error":
#        chuyển ảnh -> PNG trong thư mục ASCII ở %TEMP%, rồi OCR.
#   5. PDF lỗi native/OpenBLAS:
#        render PDF -> PNG trong thư mục ASCII, OCR từng trang ảnh.
#   6. Nếu vẫn không đủ bằng chứng:
#        EXCLUDED với lý do nghiệp vụ rõ ràng, không để lỗi runtime làm lý do.
#
# NGUYÊN TẮC AN TOÀN
# ------------------
# - Chỉ dùng PRIMARY SOURCE trong source_map_2024.csv.
# - Không dùng VietNamNet/TS247 để tạo row FINAL.
# - Không tự quy đổi 290 -> 29, 668 -> 26.68...
# - Raw FINAL: score 10..40 nếu phương thức THPT được xác minh.
# - Score >30 chỉ nhận khi có evidence thang 40 / nhân hệ số.
# - ML READY: chỉ dữ liệu tương thích THPT thang 30.
# - FINAL + SOURCE_EXCLUDED bắt buộc phủ đúng 167 trường.
#
# =============================================================================

YEAR = 2024
PIPELINE_VERSION = "2024-FINAL-TARGETED-RECOVERY-20260923"

ROOT_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT_DIR / "data" / "raw"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"

SOURCE_MAP_FILE = RAW_DIR / "source_map_2024.csv"
SOURCE_ANALYSIS_FILE = RAW_DIR / "source_analysis_2024.csv"

FINAL_FILE = PROCESSED_DIR / "admission_scores_2024_final.csv"
ML_READY_FILE = PROCESSED_DIR / "admission_scores_2024_ml_ready.csv"
ML_EXCLUDED_FILE = PROCESSED_DIR / "admission_scores_2024_ml_excluded.csv"
REVIEW_FILE = PROCESSED_DIR / "admission_scores_2024_review.csv"
SOURCE_EXCLUDED_FILE = PROCESSED_DIR / "admission_scores_2024_source_excluded.csv"
SOURCE_STATUS_FILE = PROCESSED_DIR / "admission_scores_2024_source_status.csv"
RECOVERY_REPORT_FILE = PROCESSED_DIR / "admission_scores_2024_final_recovery_report.csv"

BACKUP_FINAL = PROCESSED_DIR / "admission_scores_2024_final_before_targeted_recovery.csv"
BACKUP_EXCLUDED = PROCESSED_DIR / "admission_scores_2024_source_excluded_before_targeted_recovery.csv"
BACKUP_STATUS = PROCESSED_DIR / "admission_scores_2024_source_status_before_targeted_recovery.csv"

RECOVERY_ROOT = RAW_DIR / "primary_recovery_2024"
ASSET_ROOT = RECOVERY_ROOT / "assets"
OLD_OCR_ROOT = RECOVERY_ROOT / "ocr_final_structure"

ASCII_ROOT = Path(tempfile.gettempdir()) / "uniconnect_2024_recovery"
ASCII_ROOT.mkdir(parents=True, exist_ok=True)

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

EXCLUDED_COLUMNS = [
    "university_name",
    "source_type",
    "analysis_class",
    "exclusion_reason",
    "source_url",
    "local_file",
]

REPORT_COLUMNS = [
    "university_name",
    "source_type",
    "analysis_class",
    "old_reason",
    "strategies",
    "candidate_rows",
    "accepted_rows",
    "status",
    "final_reason",
    "source_url",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/153.0.0.0 Safari/537.36"
    )
}

POSITIVE_THPT = (
    "thi tốt nghiệp thpt",
    "điểm thi tốt nghiệp thpt",
    "kết quả thi tốt nghiệp thpt",
    "xét điểm thi tốt nghiệp thpt",
    "xét tuyển theo kết quả thi tốt nghiệp thpt",
    "xét tuyển kết quả thi tốt nghiệp thpt",
    "thi tn thpt",
    "điểm thi tn thpt",
    "xét điểm thi tn thpt",
    "xét kết quả thi thpt",
    "xét điểm thi thpt",
    "theo điểm thi thpt",
)

NEGATIVE_METHODS = (
    "học bạ",
    "đánh giá năng lực",
    "đgnl",
    "đánh giá tư duy",
    "đgtd",
    "v-sat",
    "vsat",
    "tuyển thẳng",
    "xét tuyển sớm",
    "kỳ thi riêng",
    "đánh giá đầu vào đại học trên máy tính",
)

SCALE40_MARKERS = (
    "thang 40",
    "thang điểm 40",
    "thang điểm: 40",
    "nhân hệ số 2",
    "nhân đôi",
    "ngoại ngữ nhân hệ số",
    "môn ngoại ngữ nhân hệ số",
)

ML_EXCLUDE_MARKERS = (
    "outside_thpt30",
    "scale=40",
    "thang 40",
    "nhân hệ số",
    "quy đổi",
    "xét tuyển tổng hợp",
    "kết hợp",
    "chứng chỉ",
    "ielts",
    "sat",
    "đgnl",
    "đánh giá năng lực",
    "đánh giá tư duy",
    "v-sat",
    "vsat",
)

FORCE_EXCLUDE_NAMES = {
    "đại học huế",
    "đại học đà nẵng",
    "trường đh ngoại thương",
    "trường đh tôn đức thắng",
    "trường đh tài nguyên và môi trường",
}

CODE_HEADER_MARKERS = (
    "ma nganh",
    "ma tuyen sinh",
    "ma xet tuyen",
    "ma chuong trinh",
    "ma ct",
    "ma ctdt",
)

NAME_HEADER_MARKERS = (
    "ten nganh",
    "nganh dao tao",
    "nganh tuyen sinh",
    "ten chuong trinh",
    "chuong trinh dao tao",
    "nganh hoc",
    "nganh",
)

SCORE_HEADER_MARKERS = (
    "diem chuan",
    "diem trung tuyen",
    "muc diem trung tuyen",
    "diem thi thpt",
    "diem thi tn thpt",
    "diem thi tot nghiep thpt",
    "diem xet tuyen",
    "diem tt",
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
    text = str(value)
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
        (r"\bsp\b", "su pham"),
        (r"\bkh\b", "khoa hoc"),
        (r"\bcn\b", "cong nghe"),
        (r"\bdhqghcm\b", "dai hoc quoc gia tp hcm"),
        (r"\bdhqg hcm\b", "dai hoc quoc gia tp hcm"),
        (r"\bdhqg tp hcm\b", "dai hoc quoc gia tp hcm"),
        (r"\bdhqghn\b", "dai hoc quoc gia ha noi"),
        (r"\bdhqg ha noi\b", "dai hoc quoc gia ha noi"),
        (r"\bdhtn\b", "dai hoc thai nguyen"),
        (r"\bqg\b", "quoc gia"),
        (r"\bvn\b", "viet nam"),
        (r"\btphcm\b", "tp hcm"),
    ]

    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text)

    return re.sub(r"\s+", " ", text).strip()


def slugify(value: str) -> str:
    out = norm(value).replace(" ", "_")
    return re.sub(r"[^a-z0-9_]+", "", out)[:90] or "school"


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


def valid_major_code(value) -> bool:
    text = normalize_major_code(value)

    if not text:
        return False

    if text.isdigit():
        # numeric major codes are normally >= 6 digits.
        return 6 <= len(text) <= 8

    if re.fullmatch(r"[A-Z]{1,8}\d{1,10}[A-Z0-9]{0,10}", text):
        return True

    if re.fullmatch(r"\d{3,8}[A-Z][A-Z0-9]{0,10}", text):
        return True

    if re.fullmatch(r"[A-Z0-9]{2,14}[_./|-][A-Z0-9_.|/-]{1,20}", text):
        return True

    return False


def looks_garbled(value: str) -> bool:
    text = clean_text(value)
    low = text.lower()

    if "�" in text:
        return True

    suspicious = (
        "trüng",
        "tuyén",
        "dgi hoc",
        "h9c",
        "ngµnh",
        "®iÓm",
    )

    return any(marker in low for marker in suspicious)


def explicit_thpt_context(*values: str) -> bool:
    text = " | ".join(
        clean_text(value).lower()
        for value in values
        if clean_text(value)
    )

    return any(marker in text for marker in POSITIVE_THPT)


def negative_method_context(value: str) -> bool:
    low = clean_text(value).lower()
    return any(marker in low for marker in NEGATIVE_METHODS)


def scale40_context(value: str) -> bool:
    low = clean_text(value).lower()
    return any(marker in low for marker in SCALE40_MARKERS)


def force_exclude(name: str) -> bool:
    target = normalize_school(name)
    return any(
        normalize_school(item) == target
        for item in FORCE_EXCLUDE_NAMES
    )


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
    ]

    return (
        df.drop_duplicates(
            subset=keys,
            keep="first",
        )
        .sort_values(
            ["university_name", "major_code", "combination", "cutoff_score"],
            kind="stable",
        )
        .reset_index(drop=True)
    )


def replace_school(
    base_df: pd.DataFrame,
    school_df: pd.DataFrame,
) -> pd.DataFrame:
    target = normalize_school(
        school_df.iloc[0]["university_name"]
    )

    keep = (
        base_df["university_name"].map(normalize_school)
        != target
    )

    return dedupe(
        pd.concat(
            [base_df.loc[keep], school_df],
            ignore_index=True,
        )
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


def backup_once(source: Path, destination: Path) -> None:
    if source.exists() and not destination.exists():
        shutil.copy2(source, destination)


# =============================================================================
# SOURCE METADATA
# =============================================================================

def load_analysis_map() -> dict[str, dict]:
    if not SOURCE_ANALYSIS_FILE.exists():
        return {}

    try:
        df = pd.read_csv(
            SOURCE_ANALYSIS_FILE,
            dtype=str,
            keep_default_na=False,
        )
    except Exception:
        return {}

    return {
        normalize_school(row["university_name"]): row.to_dict()
        for _, row in df.iterrows()
    }


def method_context_from_metadata(
    school_name: str,
    source_url: str,
    analysis_row: dict,
    extra_text: str = "",
) -> bool:
    analysis_class = clean_text(
        analysis_row.get("analysis_class", "")
    ).upper()

    title = clean_text(
        analysis_row.get("page_title", "")
    )

    if explicit_thpt_context(
        source_url,
        title,
        extra_text,
    ):
        return True

    if "THPT_CANDIDATE" in analysis_class:
        return True

    return False


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
        (len(row) for row in rows[start : start + depth]),
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

            value = clean_text(rows[row_idx][col])

            if not value:
                continue

            if parts and value == parts[-1]:
                continue

            parts.append(value)

        headers.append(" ".join(parts))

    return headers


def semantic_header_score(headers: list[str]) -> int:
    joined = norm(" | ".join(headers))
    score = 0

    if any(marker in joined for marker in CODE_HEADER_MARKERS):
        score += 6

    if any(marker in joined for marker in NAME_HEADER_MARKERS):
        score += 6

    if any(marker in joined for marker in SCORE_HEADER_MARKERS):
        score += 8

    if any(marker in joined for marker in COMBO_HEADER_MARKERS):
        score += 2

    if any(marker in joined for marker in METHOD_HEADER_MARKERS):
        score += 3

    return score


def choose_header(
    rows: list[list[str]],
) -> tuple[int, int, list[str]]:
    best = (0, 1, combine_headers(rows, 0, 1))
    best_score = semantic_header_score(best[2])

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

        longest = max(len(marker) for marker in matched)

        if longest > best_len:
            best_idx = idx
            best_len = longest

    return best_idx


def get_cell(row: list[str], idx: Optional[int]) -> str:
    if idx is None or idx >= len(row):
        return ""
    return clean_text(row[idx])


def infer_code_column(
    rows: list[list[str]],
    start: int,
) -> Optional[int]:
    width = max(
        (len(row) for row in rows[start:]),
        default=0,
    )

    best_col = None
    best_count = 0

    for col in range(width):
        count = 0

        for row in rows[start : start + 100]:
            if col < len(row) and valid_major_code(row[col]):
                count += 1

        if count > best_count:
            best_count = count
            best_col = col

    return best_col if best_count >= 2 else None


def infer_score_column(
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

        values = []

        for row in rows[start : start + 100]:
            if col >= len(row):
                continue

            number = parse_number(row[col])

            if number is not None and 10 <= number <= 40:
                values.append(number)

        if len(values) < 2:
            continue

        # Điểm chuẩn thường nằm 15..30, không phải cột STT.
        median = sorted(values)[len(values) // 2]
        plausibility = sum(
            1
            for value in values
            if 14 <= value <= 30
        )

        ranked.append(
            (
                len(values),
                plausibility,
                -abs(median - 22),
                col,
            )
        )

    if not ranked:
        return None

    ranked.sort(reverse=True)
    return ranked[0][-1]


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

        score = 0
        count = 0

        for row in rows[start : start + 80]:
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
                score += min(len(value), 60)
                count += 1

        if count:
            ranked.append(
                (
                    count,
                    score,
                    col,
                )
            )

    if not ranked:
        return None

    ranked.sort(reverse=True)
    return ranked[0][-1]


def code_from_name(value: str) -> tuple[str, str]:
    text = clean_text(value)

    matches = re.findall(
        r"\(([A-Za-z0-9_.-]{3,20})\)",
        text,
    )

    for raw in reversed(matches):
        if valid_major_code(raw):
            cleaned = re.sub(
                r"\s*\(" + re.escape(raw) + r"\)\s*$",
                "",
                text,
            ).strip()

            return normalize_major_code(raw), cleaned

    return "", text


def method_map_from_context(text: str) -> dict[str, str]:
    low = clean_text(text).lower()
    mapping: dict[str, str] = {}

    for match in re.finditer(
        r"(?:phương\s*thức|mã\s*phương\s*thức|pt)\s*[:\-]?\s*(\d{1,3})",
        low,
        flags=re.I,
    ):
        code = match.group(1)
        start = max(0, match.start() - 100)
        end = min(len(low), match.end() + 260)
        context = low[start:end]

        if explicit_thpt_context(context):
            mapping[code] = "THPT"
            mapping[f"PT{code}"] = "THPT"
        elif negative_method_context(context):
            mapping[code] = "OTHER"
            mapping[f"PT{code}"] = "OTHER"

    return mapping


def row_method_ok(
    row: list[str],
    method_idx: Optional[int],
    method_map: dict[str, str],
    global_thpt: bool,
) -> tuple[bool, str]:
    if method_idx is None:
        return global_thpt, "GLOBAL_THPT" if global_thpt else "UNKNOWN"

    value = get_cell(row, method_idx)
    low = value.lower()

    if negative_method_context(low):
        return False, "NEGATIVE"

    if explicit_thpt_context(low):
        return True, "EXPLICIT"

    compact = re.sub(r"\s+", "", value).upper()
    digits = re.sub(r"\D", "", compact)

    for key in (
        compact,
        digits,
        f"PT{digits}" if digits else "",
    ):
        if key in method_map:
            return (
                method_map[key] == "THPT",
                f"MAP_{key}",
            )

    return global_thpt, "GLOBAL_THPT" if global_thpt else "UNKNOWN"


def parse_table_grid(
    grid: list[list[str]],
    *,
    university_name: str,
    source_url: str,
    context: str,
    strategy: str,
) -> list[dict]:
    rows = normalize_grid(grid)

    if len(rows) < 2:
        return []

    header_start, header_depth, headers = choose_header(rows)
    data_start = header_start + header_depth

    code_idx = find_header_idx(
        headers,
        CODE_HEADER_MARKERS,
    )

    name_idx = find_header_idx(
        headers,
        NAME_HEADER_MARKERS,
        reject=(
            "ma nganh",
            "ma tuyen sinh",
            "diem",
            "to hop",
        ),
    )

    score_idx = find_header_idx(
        headers,
        SCORE_HEADER_MARKERS,
        reject=(
            "hoc ba",
            "dgnl",
            "danh gia nang luc",
            "danh gia tu duy",
            "vsat",
        ),
    )

    combo_idx = find_header_idx(
        headers,
        COMBO_HEADER_MARKERS,
    )

    method_idx = find_header_idx(
        headers,
        METHOD_HEADER_MARKERS,
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

    if score_idx is None:
        forbidden = {
            idx
            for idx in (
                code_idx,
                combo_idx,
                method_idx,
                note_idx,
                scale_idx,
            )
            if idx is not None
        }

        score_idx = infer_score_column(
            rows,
            data_start,
            forbidden,
        )

    if score_idx is None:
        return []

    if name_idx is None:
        forbidden = {
            idx
            for idx in (
                code_idx,
                score_idx,
                combo_idx,
                method_idx,
                note_idx,
                scale_idx,
            )
            if idx is not None
        }

        name_idx = infer_name_column(
            rows,
            data_start,
            forbidden,
        )

    if name_idx is None:
        return []

    global_thpt = explicit_thpt_context(
        context
    )
    method_map = method_map_from_context(
        context
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
            current_code = normalize_major_code(raw_code)

        embedded_code, embedded_name = code_from_name(raw_name)

        if embedded_code:
            current_code = embedded_code
            raw_name = embedded_name

        if (
            raw_name
            and parse_number(raw_name) is None
            and not valid_major_code(raw_name)
            and len(raw_name) >= 2
        ):
            current_name = raw_name

        score = parse_number(
            get_cell(row, score_idx)
        )

        if score is None or not (10 <= score <= 40):
            continue

        method_ok, method_evidence = row_method_ok(
            row,
            method_idx,
            method_map,
            global_thpt,
        )

        if not method_ok:
            continue

        if not current_code or not current_name:
            continue

        combination = get_cell(
            row,
            combo_idx,
        )

        note = get_cell(
            row,
            note_idx,
        )

        scale = get_cell(
            row,
            scale_idx,
        )

        note_parts = [
            f"PRIMARY_RECOVERY_2024:{strategy}",
            f"method_evidence={method_evidence}",
        ]

        if scale:
            note_parts.append(
                f"scale={scale}"
            )

        if note:
            note_parts.append(note)

        if score > 30:
            note_parts.append("outside_THPT30")

        output.append(
            {
                "university_name": university_name,
                "major_code": current_code,
                "major_name": current_name,
                "year": YEAR,
                "admission_method_codes": "THPT",
                "combination": combination,
                "cutoff_score": float(score),
                "admission_note": "; ".join(note_parts),
                "source_url": source_url,
            }
        )

    return output


# =============================================================================
# PLAIN TEXT FALLBACK FOR TEXT PDF
# =============================================================================

def parse_plain_text_rows(
    text: str,
    *,
    university_name: str,
    source_url: str,
    context: str,
    strategy: str,
) -> pd.DataFrame:
    if not explicit_thpt_context(
        context,
        text[:12000],
    ):
        return pd.DataFrame(
            columns=CANONICAL_COLUMNS
        )

    rows = []

    for raw_line in text.splitlines():
        line = clean_text(raw_line)

        if len(line) < 10:
            continue

        # Major code at/near start.
        match = re.match(
            r"^\s*(\d{6,8}|[A-Z]{1,6}\d{1,8}[A-Z0-9]{0,5})\s+(.+)$",
            line,
            flags=re.I,
        )

        if not match:
            continue

        code = normalize_major_code(
            match.group(1)
        )

        if not valid_major_code(code):
            continue

        rest = match.group(2)

        score_matches = list(
            re.finditer(
                r"(?<!\d)(\d{2}(?:[.,]\d{1,2})?)(?!\d)",
                rest,
            )
        )

        candidates = []

        for item in score_matches:
            value = parse_number(
                item.group(1)
            )

            if value is not None and 10 <= value <= 40:
                candidates.append(
                    (
                        item.start(),
                        item.end(),
                        value,
                    )
                )

        if not candidates:
            continue

        # Ưu tiên score cuối dòng; mã tổ hợp A00/D01 không match numeric regex.
        start, end, score = candidates[-1]

        major_name = clean_text(
            rest[:start]
        )

        if len(major_name) < 3:
            continue

        # Remove ordinal / separators.
        major_name = re.sub(
            r"^[\-\.:]+\s*",
            "",
            major_name,
        )

        if looks_garbled(major_name):
            continue

        note_parts = [
            f"PRIMARY_RECOVERY_2024:{strategy}",
            "method_evidence=TEXT_CONTEXT_THPT",
        ]

        if score > 30:
            note_parts.append(
                "outside_THPT30"
            )

        rows.append(
            {
                "university_name": university_name,
                "major_code": code,
                "major_name": major_name,
                "year": YEAR,
                "admission_method_codes": "THPT",
                "combination": "",
                "cutoff_score": float(score),
                "admission_note": "; ".join(note_parts),
                "source_url": source_url,
            }
        )

    out = dedupe(
        canonicalize(rows)
    )

    # Plain-text fallback must have >=2 coherent rows.
    if len(out) < 2:
        return pd.DataFrame(
            columns=CANONICAL_COLUMNS
        )

    return out


# =============================================================================
# HTML PRIMARY
# =============================================================================

def parse_html_primary(
    session: requests.Session,
    *,
    university_name: str,
    source_url: str,
    analysis_row: dict,
) -> tuple[pd.DataFrame, str, str]:
    try:
        response = session.get(
            source_url,
            timeout=35,
            allow_redirects=True,
        )
        response.raise_for_status()
    except Exception as exc:
        return (
            pd.DataFrame(columns=CANONICAL_COLUMNS),
            "",
            f"HTML_REQUEST_{type(exc).__name__}",
        )

    content_type = clean_text(
        response.headers.get(
            "Content-Type",
            "",
        )
    ).lower()

    if (
        "pdf" in content_type
        or response.content[:5] == b"%PDF-"
    ):
        return (
            pd.DataFrame(columns=CANONICAL_COLUMNS),
            "",
            "HTML_IS_PDF",
        )

    html = decode_response(
        response
    )
    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    title = ""
    for tag_name in (
        "h1",
        "title",
    ):
        tag = soup.find(
            tag_name
        )
        if tag:
            title = clean_text(
                tag.get_text(
                    " ",
                    strip=True,
                )
            )
            if title:
                break

    visible = clean_text(
        soup.get_text(
            " ",
            strip=True,
        )
    )

    context = (
        f"{title} | {visible[:15000]} | {source_url}"
    )

    # Analysis class THPT candidate is usable method evidence.
    if method_context_from_metadata(
        university_name,
        source_url,
        analysis_row,
        context,
    ):
        context += " | PRIMARY_ANALYSIS_THPT_CANDIDATE"

    try:
        dfs = pd.read_html(
            io.StringIO(html),
            header=None,
            thousands=None,
        )
    except Exception:
        dfs = []

    rows = []

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
                strategy="HTML_FLEX",
            )
        )

    return (
        dedupe(canonicalize(rows)),
        context,
        f"html_tables={len(dfs)}",
    )


# =============================================================================
# PDF TEXT / TABLE PARSER
# =============================================================================

def read_pdf_text_and_tables(
    path: Path,
) -> tuple[str, list[list[list[str]]], str]:
    text_parts = []
    tables = []
    diagnostics = []

    try:
        doc = fitz.open(
            str(path)
        )
    except Exception as exc:
        return "", [], f"PDF_OPEN_{type(exc).__name__}"

    for page_idx, page in enumerate(doc):
        try:
            text = page.get_text(
                "text"
            )
        except Exception:
            text = ""

        if text.strip():
            text_parts.append(text)

        try:
            finder = page.find_tables()
            found = getattr(
                finder,
                "tables",
                [],
            )

            for table in found:
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
                f"p{page_idx+1}:find_tables={type(exc).__name__}"
            )

    doc.close()

    return (
        "\n".join(text_parts),
        tables,
        "|".join(diagnostics),
    )


# =============================================================================
# EXISTING OCR CACHE READER
# =============================================================================

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

            # Skip markdown separator row.
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


def read_cached_ocr(
    university_name: str,
) -> tuple[str, list[list[list[str]]], str]:
    school_dir = OLD_OCR_ROOT / slugify(
        university_name
    )

    if not school_dir.exists():
        return "", [], "NO_CACHE"

    markdown_parts = []
    tables = []

    for path in sorted(
        school_dir.rglob(
            "combined.md"
        )
    ):
        try:
            text = path.read_text(
                encoding="utf-8",
                errors="replace",
            )
        except Exception:
            continue

        if text.strip():
            markdown_parts.append(
                text
            )
            tables.extend(
                markdown_pipe_tables(
                    text
                )
            )

    for path in sorted(
        school_dir.rglob(
            "*.html"
        )
    ):
        try:
            html = path.read_text(
                encoding="utf-8",
                errors="replace",
            )
        except Exception:
            continue

        if "<table" not in html.lower():
            continue

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

    return (
        "\n\n".join(markdown_parts),
        tables,
        f"cache_md={len(markdown_parts)},cache_tables={len(tables)}",
    )


# =============================================================================
# PRIMARY ASSETS
# =============================================================================

def drive_direct_url(url: str) -> str:
    text = clean_text(url)

    match = re.search(
        r"/file/d/([A-Za-z0-9_-]+)",
        text,
    )

    if not match:
        parsed = urlparse(
            text
        )
        values = parse_qs(
            parsed.query
        ).get("id")

        if values:
            file_id = values[0]
        else:
            return ""
    else:
        file_id = match.group(1)

    return (
        "https://drive.usercontent.google.com/download"
        f"?id={file_id}&export=download&confirm=t"
    )


def download_asset(
    session: requests.Session,
    url: str,
    target: Path,
) -> bool:
    try:
        response = session.get(
            url,
            timeout=45,
            allow_redirects=True,
        )
        response.raise_for_status()
    except Exception:
        return False

    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    target.write_bytes(
        response.content
    )

    return (
        target.exists()
        and target.stat().st_size > 1000
    )


def find_assets(
    session: requests.Session,
    *,
    university_name: str,
    source_url: str,
    source_type: str,
    analysis_row: dict,
) -> list[Path]:
    assets = []

    local_file = clean_text(
        analysis_row.get(
            "local_file",
            "",
        )
    )

    if local_file:
        path = Path(
            local_file
        )

        if path.exists():
            assets.append(
                path
            )

    school_dir = ASSET_ROOT / slugify(
        university_name
    )

    if school_dir.exists():
        for path in sorted(
            school_dir.iterdir()
        ):
            if (
                path.is_file()
                and path.suffix.lower()
                in {
                    ".pdf",
                    ".png",
                    ".jpg",
                    ".jpeg",
                    ".webp",
                }
            ):
                assets.append(
                    path
                )

    # Direct PDF if nothing local.
    if not assets and (
        source_type.upper() == "PDF"
        or source_url.lower().endswith(
            ".pdf"
        )
    ):
        target = school_dir / "source_retry.pdf"

        if download_asset(
            session,
            source_url,
            target,
        ):
            assets.append(
                target
            )

    # Public Google Drive direct download.
    if (
        not assets
        and (
            "DRIVE" in source_type.upper()
            or "drive.google.com" in source_url.lower()
        )
    ):
        direct = drive_direct_url(
            source_url
        )

        if direct:
            target = school_dir / "drive_retry.pdf"

            if download_asset(
                session,
                direct,
                target,
            ):
                if target.read_bytes()[:5] == b"%PDF":
                    assets.append(
                        target
                    )

    # Stable unique paths.
    seen = set()
    output = []

    for path in assets:
        try:
            key = str(
                path.resolve()
            )
        except Exception:
            key = str(path)

        if key in seen:
            continue

        seen.add(key)
        output.append(path)

    return output


# =============================================================================
# ASCII SHADOW OCR
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
    path.mkdir(
        parents=True,
        exist_ok=True,
    )
    return path


def normalize_image_to_ascii_png(
    source: Path,
    university_name: str,
    label: str,
) -> Optional[Path]:
    target = (
        ascii_school_dir(
            university_name
        )
        / f"{label}.png"
    )

    try:
        with Image.open(
            source
        ) as image:
            image = image.convert(
                "RGB"
            )
            image.save(
                target,
                format="PNG",
            )
    except Exception:
        return None

    return target if target.exists() else None


def render_pdf_to_ascii_images(
    pdf_path: Path,
    university_name: str,
    *,
    max_pages: int = 12,
) -> list[Path]:
    output = []

    try:
        doc = fitz.open(
            str(pdf_path)
        )
    except Exception:
        return []

    page_scores = []

    for idx, page in enumerate(
        doc
    ):
        try:
            text = clean_text(
                page.get_text(
                    "text"
                )
            )
        except Exception:
            text = ""

        low = text.lower()

        keyword_score = sum(
            1
            for marker in (
                "điểm",
                "trúng tuyển",
                "mã ngành",
                "thpt",
                "tốt nghiệp",
                "ngành",
            )
            if marker in low
        )

        page_scores.append(
            (
                keyword_score,
                idx,
                bool(text),
            )
        )

    # Text PDF: ưu tiên page có keyword.
    selected = [
        idx
        for score, idx, has_text in sorted(
            page_scores,
            reverse=True,
        )
        if score >= 2
    ][:max_pages]

    # Scan PDF: text có thể rỗng; lấy đầu + cuối vì phụ lục điểm thường ở cuối.
    if not selected:
        count = len(doc)

        candidate_indices = list(
            range(
                min(count, max_pages // 2)
            )
        )

        tail_start = max(
            0,
            count - max_pages // 2,
        )

        candidate_indices.extend(
            range(
                tail_start,
                count,
            )
        )

        selected = []

        for idx in candidate_indices:
            if idx not in selected:
                selected.append(
                    idx
                )

        selected = selected[
            :max_pages
        ]

    target_dir = ascii_school_dir(
        university_name
    )

    for idx in selected:
        page = doc[idx]

        try:
            pix = page.get_pixmap(
                matrix=fitz.Matrix(
                    2.0,
                    2.0,
                ),
                alpha=False,
            )

            target = (
                target_dir
                / f"pdf_page_{idx+1:03d}.png"
            )

            pix.save(
                str(target)
            )

            output.append(
                target
            )
        except Exception:
            continue

    doc.close()
    return output


def extract_tables_from_paddle_result(
    result,
) -> tuple[str, list[list[list[str]]]]:
    markdown_parts = []
    tables = []

    # markdown field
    try:
        markdown_obj = result.markdown
    except Exception:
        markdown_obj = None

    if isinstance(markdown_obj, str):
        markdown_parts.append(
            markdown_obj
        )
    elif markdown_obj is not None:
        for attr in (
            "markdown_texts",
            "text",
        ):
            try:
                value = getattr(
                    markdown_obj,
                    attr,
                    None,
                )

                if isinstance(value, str):
                    markdown_parts.append(
                        value
                    )
            except Exception:
                pass

        try:
            if hasattr(
                markdown_obj,
                "get",
            ):
                for key in (
                    "markdown_texts",
                    "text",
                ):
                    value = markdown_obj.get(
                        key
                    )

                    if isinstance(value, str):
                        markdown_parts.append(
                            value
                        )
        except Exception:
            pass

    # result.json recursive pred_html
    try:
        json_obj = result.json
    except Exception:
        json_obj = None

    def collect_html(value):
        if isinstance(
            value,
            dict,
        ):
            for key, child in value.items():
                if (
                    key in {
                        "pred_html",
                        "html",
                    }
                    and isinstance(
                        child,
                        str,
                    )
                    and "<table" in child.lower()
                ):
                    try:
                        dfs = pd.read_html(
                            io.StringIO(
                                child
                            ),
                            header=None,
                            thousands=None,
                        )

                        for df in dfs:
                            if not df.empty:
                                tables.append(
                                    [
                                        [
                                            clean_text(cell)
                                            for cell in row
                                        ]
                                        for row in df.astype(object).values.tolist()
                                    ]
                                )
                    except Exception:
                        pass
                else:
                    collect_html(
                        child
                    )

        elif isinstance(
            value,
            (list, tuple),
        ):
            for child in value:
                collect_html(
                    child
                )

    collect_html(
        json_obj
    )

    markdown = "\n\n".join(
        part
        for part in markdown_parts
        if clean_text(part)
    )

    tables.extend(
        markdown_pipe_tables(
            markdown
        )
    )

    return markdown, tables


def ocr_ascii_images(
    images: list[Path],
    *,
    university_name: str,
    source_url: str,
    context: str,
) -> tuple[pd.DataFrame, str]:
    pipeline = get_ocr_pipeline()

    if pipeline is None:
        return (
            pd.DataFrame(
                columns=CANONICAL_COLUMNS
            ),
            "OCR_ENGINE_UNAVAILABLE",
        )

    rows = []
    diagnostics = []

    for image_path in images:
        try:
            output = pipeline.predict(
                input=str(
                    image_path
                )
            )
        except Exception as exc:
            diagnostics.append(
                f"{image_path.name}:predict={type(exc).__name__}"
            )
            continue

        result_count = 0
        table_count = 0

        for result in output:
            result_count += 1

            markdown, tables = extract_tables_from_paddle_result(
                result
            )

            table_count += len(
                tables
            )

            local_context = (
                f"{context} | {markdown[:10000]}"
            )

            for table in tables:
                rows.extend(
                    parse_table_grid(
                        table,
                        university_name=university_name,
                        source_url=source_url,
                        context=local_context,
                        strategy="ASCII_OCR",
                    )
                )

        diagnostics.append(
            f"{image_path.name}:results={result_count},tables={table_count}"
        )

    return (
        dedupe(
            canonicalize(
                rows
            )
        ),
        " | ".join(
            diagnostics[:8]
        ),
    )


# =============================================================================
# VALIDATION / RECONCILIATION
# =============================================================================

def names_compatible(a: str, b: str) -> bool:
    na = norm(a)
    nb = norm(b)

    if not na or not nb:
        return False

    if na == nb or na in nb or nb in na:
        return True

    return (
        SequenceMatcher(
            None,
            na,
            nb,
        ).ratio()
        >= 0.72
    )


def validate_candidate(
    df: pd.DataFrame,
    *,
    university_name: str,
    context: str,
) -> tuple[bool, str]:
    if df.empty:
        return False, "NO_ROWS"

    if (
        df["university_name"].map(clean_text)
        != clean_text(university_name)
    ).any():
        return False, "WRONG_SCHOOL_NAME"

    if df["major_code"].eq("").any():
        return False, "MISSING_MAJOR_CODE"

    if df["major_name"].eq("").any():
        return False, "MISSING_MAJOR_NAME"

    if df["cutoff_score"].isna().any():
        return False, "MISSING_SCORE"

    for code in df["major_code"]:
        if not valid_major_code(code):
            return False, f"BAD_MAJOR_CODE:{code}"

    if df["major_name"].map(
        looks_garbled
    ).any():
        return False, "GARBLED_MAJOR_NAME"

    scores = pd.to_numeric(
        df["cutoff_score"],
        errors="coerce",
    )

    if scores.isna().any():
        return False, "NON_NUMERIC_SCORE"

    if (
        (scores < 10)
        | (scores > 40)
    ).any():
        return False, "SCORE_OUTSIDE_10_40"

    joined = (
        context
        + " | "
        + " | ".join(
            df["admission_note"].astype(str)
        )
    )

    if not explicit_thpt_context(
        joined
    ) and "method_evidence=GLOBAL_THPT" not in joined:
        return False, "METHOD_THPT_UNVERIFIED"

    if (scores > 30).any():
        if not scale40_context(
            joined
        ):
            return False, "SCORE_GT30_WITHOUT_SCALE40_EVIDENCE"

    # Same code should not map to incompatible names.
    for code, group in df.groupby(
        "major_code",
        sort=False,
    ):
        names = [
            clean_text(value)
            for value in group[
                "major_name"
            ].unique()
            if clean_text(value)
        ]

        if len(names) <= 1:
            continue

        anchor = names[0]

        if any(
            not names_compatible(
                anchor,
                other,
            )
            for other in names[1:]
        ):
            return False, f"CODE_NAME_CONFLICT:{code}"

    # Need at least one sensible row; for plain-text-only recovery, parser itself requires >=2.
    return True, ""


def reconcile_candidates(
    frames: list[tuple[str, pd.DataFrame]],
    *,
    university_name: str,
    context: str,
) -> tuple[pd.DataFrame, str]:
    valid = []

    for strategy, frame in frames:
        if frame.empty:
            continue

        frame = dedupe(
            frame
        )

        ok, reason = validate_candidate(
            frame,
            university_name=university_name,
            context=context,
        )

        if ok:
            valid.append(
                (
                    strategy,
                    frame,
                )
            )

    if not valid:
        return (
            pd.DataFrame(
                columns=CANONICAL_COLUMNS
            ),
            "NO_VALID_STRATEGY",
        )

    # Priority:
    # HTML/PyMuPDF table > cached structured OCR > text line > fresh OCR.
    priority = {
        "HTML_FLEX": 100,
        "PDF_TABLE": 95,
        "OCR_CACHE_TABLE": 90,
        "PDF_TEXT_LINE": 80,
        "ASCII_OCR": 70,
    }

    valid.sort(
        key=lambda item: (
            priority.get(
                item[0],
                0,
            ),
            len(item[1]),
        ),
        reverse=True,
    )

    best_strategy, best = valid[0]

    # Cross-check additional valid strategies on common major codes.
    best_map = {}

    for _, row in best.iterrows():
        best_map.setdefault(
            normalize_major_code(
                row["major_code"]
            ),
            [],
        ).append(
            float(
                row["cutoff_score"]
            )
        )

    for strategy, other in valid[1:]:
        other_map = {}

        for _, row in other.iterrows():
            other_map.setdefault(
                normalize_major_code(
                    row["major_code"]
                ),
                [],
            ).append(
                float(
                    row["cutoff_score"]
                )
            )

        common = set(
            best_map
        ) & set(
            other_map
        )

        if len(common) < 3:
            continue

        mismatches = 0

        for code in common:
            agree = any(
                abs(a - b) <= 0.12
                for a in best_map[code]
                for b in other_map[code]
            )

            if not agree:
                mismatches += 1

        if (
            len(common) >= 3
            and mismatches / len(common) > 0.60
        ):
            return (
                pd.DataFrame(
                    columns=CANONICAL_COLUMNS
                ),
                (
                    f"STRATEGY_CONFLICT:"
                    f"{best_strategy}_VS_{strategy}:"
                    f"{mismatches}/{len(common)}"
                ),
            )

    return best, best_strategy


# =============================================================================
# ML SPLIT
# =============================================================================

def ml_compatible(
    row: pd.Series,
) -> tuple[bool, str]:
    score = parse_number(
        row["cutoff_score"]
    )

    if score is None:
        return False, "score_invalid"

    if not (
        10 <= score <= 30
    ):
        return False, "outside_10_30"

    note = clean_text(
        row["admission_note"]
    ).lower()

    if any(
        marker in note
        for marker in ML_EXCLUDE_MARKERS
    ):
        return False, "note_non_comparable"

    method = clean_text(
        row["admission_method_codes"]
    ).lower()

    if (
        "thpt" not in method
        and not re.search(
            r"\bpt\d{1,3}\b",
            method,
        )
    ):
        return False, "method_not_thpt"

    return True, ""


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    print("=" * 122)
    print("2024 FINAL / TARGETED TECHNICAL RECOVERY")
    print(f"VERSION : {PIPELINE_VERSION}")
    print("=" * 122)

    required = (
        SOURCE_MAP_FILE,
        FINAL_FILE,
        SOURCE_EXCLUDED_FILE,
    )

    for path in required:
        if not path.exists():
            raise RuntimeError(
                f"Thiếu file bắt buộc: {path}"
            )

    source_map = pd.read_csv(
        SOURCE_MAP_FILE,
        dtype=str,
        keep_default_na=False,
    )

    if (
        len(source_map) != 167
        or source_map[
            "university_name"
        ].nunique() != 167
    ):
        raise RuntimeError(
            "source_map_2024.csv không còn checkpoint 167/167."
        )

    final_df = pd.read_csv(
        FINAL_FILE,
        dtype=str,
        keep_default_na=False,
    )
    final_df = dedupe(
        canonicalize(
            final_df.to_dict(
                "records"
            )
        )
    )

    excluded_df = pd.read_csv(
        SOURCE_EXCLUDED_FILE,
        dtype=str,
        keep_default_na=False,
    )

    analysis_map = load_analysis_map()

    backup_once(
        FINAL_FILE,
        BACKUP_FINAL,
    )
    backup_once(
        SOURCE_EXCLUDED_FILE,
        BACKUP_EXCLUDED,
    )
    backup_once(
        SOURCE_STATUS_FILE,
        BACKUP_STATUS,
    )

    print(
        f"SOURCE INVENTORY : {len(source_map)} trường"
    )
    print(
        f"INPUT FINAL      : {len(final_df)} rows / "
        f"{final_df['university_name'].nunique()} trường"
    )
    print(
        f"INPUT EXCLUDED   : {excluded_df['university_name'].nunique()} trường"
    )

    session = build_session()

    source_lookup = {
        normalize_school(
            row["university_name"]
        ): row
        for _, row in source_map.iterrows()
    }

    recovered = []
    report_rows = []
    new_excluded_rows = []

    total = len(
        excluded_df
    )

    for idx, (_, excluded_row) in enumerate(
        excluded_df.iterrows(),
        start=1,
    ):
        name = clean_text(
            excluded_row["university_name"]
        )
        school_key = normalize_school(
            name
        )

        source = source_lookup.get(
            school_key
        )

        if source is None:
            new_excluded_rows.append(
                {
                    "university_name": name,
                    "source_type": clean_text(
                        excluded_row.get(
                            "source_type",
                            "",
                        )
                    ),
                    "analysis_class": clean_text(
                        excluded_row.get(
                            "analysis_class",
                            "",
                        )
                    ),
                    "exclusion_reason": "SOURCE_MAP_MISSING",
                    "source_url": clean_text(
                        excluded_row.get(
                            "source_url",
                            "",
                        )
                    ),
                    "local_file": clean_text(
                        excluded_row.get(
                            "local_file",
                            "",
                        )
                    ),
                }
            )
            continue

        source_type = clean_text(
            source["source_type"]
        )
        source_url = clean_text(
            source["source_url"]
        )

        analysis_row = analysis_map.get(
            school_key,
            {},
        )

        analysis_class = clean_text(
            analysis_row.get(
                "analysis_class",
                excluded_row.get(
                    "analysis_class",
                    "",
                ),
            )
        )

        old_reason = clean_text(
            excluded_row.get(
                "exclusion_reason",
                "",
            )
        )

        print(
            f"[{idx:03d}/{total:03d}] {name} | "
            f"{analysis_class or source_type} ... ",
            end="",
            flush=True,
        )

        if force_exclude(
            name
        ):
            final_reason = (
                "EXCLUDED_COMPLEX_UMBRELLA_OR_SCALE"
            )

            new_excluded_rows.append(
                {
                    "university_name": name,
                    "source_type": source_type,
                    "analysis_class": analysis_class,
                    "exclusion_reason": final_reason,
                    "source_url": source_url,
                    "local_file": clean_text(
                        analysis_row.get(
                            "local_file",
                            "",
                        )
                    ),
                }
            )

            report_rows.append(
                {
                    "university_name": name,
                    "source_type": source_type,
                    "analysis_class": analysis_class,
                    "old_reason": old_reason,
                    "strategies": "",
                    "candidate_rows": 0,
                    "accepted_rows": 0,
                    "status": "EXCLUDED",
                    "final_reason": final_reason,
                    "source_url": source_url,
                }
            )

            print(
                f"EXCLUDED ⚠ {final_reason}"
            )
            continue

        strategies = []
        candidate_frames: list[
            tuple[str, pd.DataFrame]
        ] = []

        # ------------------------------------------------------------------
        # Strategy 1: flexible HTML parser.
        # ------------------------------------------------------------------
        html_df, html_context, html_diag = parse_html_primary(
            session,
            university_name=name,
            source_url=source_url,
            analysis_row=analysis_row,
        )

        strategies.append(
            f"HTML:{html_diag}:rows={len(html_df)}"
        )

        if not html_df.empty:
            candidate_frames.append(
                (
                    "HTML_FLEX",
                    html_df,
                )
            )

        base_context = (
            html_context
            or (
                f"{source_url} | "
                f"{clean_text(analysis_row.get('page_title', ''))}"
            )
        )

        if method_context_from_metadata(
            name,
            source_url,
            analysis_row,
            base_context,
        ):
            base_context += (
                " | điểm thi tốt nghiệp THPT"
            )

        # ------------------------------------------------------------------
        # Strategy 2: primary assets.
        # ------------------------------------------------------------------
        assets = find_assets(
            session,
            university_name=name,
            source_url=source_url,
            source_type=source_type,
            analysis_row=analysis_row,
        )

        pdf_text_parts = []

        for asset in assets:
            suffix = asset.suffix.lower()

            if suffix == ".pdf":
                text, tables, pdf_diag = read_pdf_text_and_tables(
                    asset
                )

                pdf_text_parts.append(
                    text
                )

                strategies.append(
                    f"PDF:{asset.name}:tables={len(tables)}:{pdf_diag}"
                )

                pdf_context = (
                    f"{base_context} | "
                    f"{text[:16000]}"
                )

                if method_context_from_metadata(
                    name,
                    source_url,
                    analysis_row,
                    pdf_context,
                ):
                    pdf_context += (
                        " | điểm thi tốt nghiệp THPT"
                    )

                pdf_rows = []

                for table in tables:
                    pdf_rows.extend(
                        parse_table_grid(
                            table,
                            university_name=name,
                            source_url=source_url,
                            context=pdf_context,
                            strategy="PDF_TABLE",
                        )
                    )

                pdf_table_df = dedupe(
                    canonicalize(
                        pdf_rows
                    )
                )

                if not pdf_table_df.empty:
                    candidate_frames.append(
                        (
                            "PDF_TABLE",
                            pdf_table_df,
                        )
                    )

                text_df = parse_plain_text_rows(
                    text,
                    university_name=name,
                    source_url=source_url,
                    context=pdf_context,
                    strategy="PDF_TEXT_LINE",
                )

                if not text_df.empty:
                    candidate_frames.append(
                        (
                            "PDF_TEXT_LINE",
                            text_df,
                        )
                    )

        # ------------------------------------------------------------------
        # Strategy 3: reparse structured OCR cache.
        # ------------------------------------------------------------------
        cache_md, cache_tables, cache_diag = read_cached_ocr(
            name
        )

        strategies.append(
            f"OCR_CACHE:{cache_diag}"
        )

        cache_context = (
            f"{base_context} | "
            f"{' '.join(pdf_text_parts)[:10000]} | "
            f"{cache_md[:12000]}"
        )

        if method_context_from_metadata(
            name,
            source_url,
            analysis_row,
            cache_context,
        ):
            cache_context += (
                " | điểm thi tốt nghiệp THPT"
            )

        cache_rows = []

        for table in cache_tables:
            cache_rows.extend(
                parse_table_grid(
                    table,
                    university_name=name,
                    source_url=source_url,
                    context=cache_context,
                    strategy="OCR_CACHE_TABLE",
                )
            )

        cache_df = dedupe(
            canonicalize(
                cache_rows
            )
        )

        if not cache_df.empty:
            candidate_frames.append(
                (
                    "OCR_CACHE_TABLE",
                    cache_df,
                )
            )

        # ------------------------------------------------------------------
        # Strategy 4: ASCII retry only if still no valid structured candidate.
        # ------------------------------------------------------------------
        preliminary, preliminary_reason = reconcile_candidates(
            candidate_frames,
            university_name=name,
            context=cache_context,
        )

        if preliminary.empty:
            ascii_images = []

            for asset_idx, asset in enumerate(
                assets,
                start=1,
            ):
                suffix = asset.suffix.lower()

                if suffix in {
                    ".jpg",
                    ".jpeg",
                    ".png",
                    ".webp",
                }:
                    normalized = normalize_image_to_ascii_png(
                        asset,
                        name,
                        f"img_{asset_idx:02d}",
                    )

                    if normalized:
                        ascii_images.append(
                            normalized
                        )

                elif suffix == ".pdf":
                    ascii_images.extend(
                        render_pdf_to_ascii_images(
                            asset,
                            name,
                            max_pages=12,
                        )
                    )

            # Stable unique.
            unique_images = []
            seen_images = set()

            for image_path in ascii_images:
                key = str(
                    image_path.resolve()
                )

                if key in seen_images:
                    continue

                seen_images.add(
                    key
                )
                unique_images.append(
                    image_path
                )

            if unique_images:
                ascii_df, ascii_diag = ocr_ascii_images(
                    unique_images,
                    university_name=name,
                    source_url=source_url,
                    context=cache_context,
                )

                strategies.append(
                    f"ASCII_OCR:{ascii_diag}:rows={len(ascii_df)}"
                )

                if not ascii_df.empty:
                    candidate_frames.append(
                        (
                            "ASCII_OCR",
                            ascii_df,
                        )
                    )

        # ------------------------------------------------------------------
        # Final reconciliation for this school.
        # ------------------------------------------------------------------
        candidate, strategy_or_reason = reconcile_candidates(
            candidate_frames,
            university_name=name,
            context=cache_context,
        )

        candidate_count = max(
            (
                len(frame)
                for _, frame in candidate_frames
            ),
            default=0,
        )

        if not candidate.empty:
            final_df = replace_school(
                final_df,
                candidate,
            )

            recovered.append(
                name
            )

            report_rows.append(
                {
                    "university_name": name,
                    "source_type": source_type,
                    "analysis_class": analysis_class,
                    "old_reason": old_reason,
                    "strategies": " || ".join(
                        strategies
                    ),
                    "candidate_rows": candidate_count,
                    "accepted_rows": len(
                        candidate
                    ),
                    "status": "ACCEPTED",
                    "final_reason": (
                        f"RECOVERED_BY_{strategy_or_reason}"
                    ),
                    "source_url": source_url,
                }
            )

            print(
                f"RECOVERED ✅ {len(candidate)} rows | "
                f"{strategy_or_reason}"
            )

        else:
            # Classify remaining exclusion by evidence, never by raw runtime error.
            joined_strategy = " | ".join(
                strategies
            )

            if (
                "DRIVE" in source_type.upper()
                and not assets
            ):
                final_reason = (
                    "EXCLUDED_PRIMARY_SOURCE_UNAVAILABLE"
                )

            elif not assets and html_diag.startswith(
                "HTML_REQUEST"
            ):
                final_reason = (
                    "EXCLUDED_PRIMARY_SOURCE_UNAVAILABLE"
                )

            elif "METHOD_THPT_UNVERIFIED" in strategy_or_reason:
                final_reason = (
                    "EXCLUDED_METHOD_NOT_VERIFIABLE_AS_THPT"
                )

            elif "SCORE_GT30_WITHOUT_SCALE40_EVIDENCE" in strategy_or_reason:
                final_reason = (
                    "EXCLUDED_SCALE_NOT_COMPARABLE"
                )

            elif (
                cache_tables
                or any(
                    asset.suffix.lower() == ".pdf"
                    for asset in assets
                )
            ):
                final_reason = (
                    "EXCLUDED_STRUCTURE_NOT_RELIABLY_PARSED"
                )

            elif assets:
                final_reason = (
                    "EXCLUDED_OCR_NOT_RELIABLE"
                )

            else:
                final_reason = (
                    "EXCLUDED_NO_RELIABLE_PRIMARY_DATA"
                )

            new_excluded_rows.append(
                {
                    "university_name": name,
                    "source_type": source_type,
                    "analysis_class": analysis_class,
                    "exclusion_reason": final_reason,
                    "source_url": source_url,
                    "local_file": clean_text(
                        analysis_row.get(
                            "local_file",
                            "",
                        )
                    ),
                }
            )

            report_rows.append(
                {
                    "university_name": name,
                    "source_type": source_type,
                    "analysis_class": analysis_class,
                    "old_reason": old_reason,
                    "strategies": " || ".join(
                        strategies
                    ),
                    "candidate_rows": candidate_count,
                    "accepted_rows": 0,
                    "status": "EXCLUDED",
                    "final_reason": final_reason,
                    "source_url": source_url,
                }
            )

            print(
                f"EXCLUDED ⚠ {final_reason}"
            )

        # Incremental recovery report.
        pd.DataFrame(
            report_rows,
            columns=REPORT_COLUMNS,
        ).to_csv(
            RECOVERY_REPORT_FILE,
            index=False,
            encoding="utf-8-sig",
        )

        time.sleep(
            0.01
        )

    final_df = dedupe(
        final_df
    )

    new_excluded_df = pd.DataFrame(
        new_excluded_rows,
        columns=EXCLUDED_COLUMNS,
    )

    if not new_excluded_df.empty:
        new_excluded_df = (
            new_excluded_df
            .drop_duplicates(
                subset=[
                    "university_name"
                ],
                keep="last",
            )
            .sort_values(
                "university_name",
                kind="stable",
            )
            .reset_index(
                drop=True
            )
        )

    # =========================================================================
    # HARD AUDIT: 167 source accounting
    # =========================================================================

    final_norms = set(
        final_df[
            "university_name"
        ].map(
            normalize_school
        )
    )

    excluded_norms = set(
        new_excluded_df[
            "university_name"
        ].map(
            normalize_school
        )
    )

    overlap = (
        final_norms
        & excluded_norms
    )

    if overlap:
        raise RuntimeError(
            f"AUDIT FAIL: {len(overlap)} trường vừa FINAL vừa EXCLUDED."
        )

    union = (
        final_norms
        | excluded_norms
    )

    if len(union) != 167:
        missing = []

        for _, source in source_map.iterrows():
            key = normalize_school(
                source["university_name"]
            )

            if key not in union:
                missing.append(
                    source["university_name"]
                )

        raise RuntimeError(
            f"AUDIT FAIL: FINAL + EXCLUDED phủ {len(union)}/167. "
            f"Missing: {missing[:8]}"
        )

    if final_df["major_code"].eq("").any():
        raise RuntimeError(
            "AUDIT FAIL: FINAL còn missing major_code."
        )

    if final_df["major_name"].eq("").any():
        raise RuntimeError(
            "AUDIT FAIL: FINAL còn missing major_name."
        )

    if final_df["cutoff_score"].isna().any():
        raise RuntimeError(
            "AUDIT FAIL: FINAL còn missing cutoff_score."
        )

    # Source URL phải chính là URL source-map của trường.
    source_url_map = {
        normalize_school(
            row["university_name"]
        ): clean_text(
            row["source_url"]
        )
        for _, row in source_map.iterrows()
    }

    for _, row in final_df.iterrows():
        school_key = normalize_school(
            row["university_name"]
        )

        expected_url = source_url_map.get(
            school_key,
            "",
        )

        actual_url = clean_text(
            row["source_url"]
        )

        if (
            expected_url
            and actual_url
            and actual_url != expected_url
        ):
            raise RuntimeError(
                "AUDIT FAIL: source_url không phải primary source "
                f"của {row['university_name']}"
            )

    # =========================================================================
    # ML SPLIT
    # =========================================================================

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
            final_df.reset_index(
                drop=True
            ),
            flags.reset_index(
                drop=True
            ),
        ],
        axis=1,
    )

    ml_ready = temp[
        temp["_ml_ok"] == True
    ][CANONICAL_COLUMNS].copy()

    ml_excluded = temp[
        temp["_ml_ok"] != True
    ].copy()

    ml_excluded[
        "ml_exclusion_reason"
    ] = temp.loc[
        temp["_ml_ok"] != True,
        "_ml_reason",
    ].values

    ml_excluded = ml_excluded[
        CANONICAL_COLUMNS
        + [
            "ml_exclusion_reason"
        ]
    ]

    # Review is intentionally empty after final accounting.
    review_df = pd.DataFrame(
        columns=[
            "university_name",
            "source_type",
            "reason",
            "primary_url",
            "analysis_class",
            "local_file",
        ]
    )

    # =========================================================================
    # WRITE AFTER ALL AUDITS PASS
    # =========================================================================

    final_df.to_csv(
        FINAL_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    new_excluded_df.to_csv(
        SOURCE_EXCLUDED_FILE,
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

    review_df.to_csv(
        REVIEW_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    report_df = pd.DataFrame(
        report_rows,
        columns=REPORT_COLUMNS,
    )

    report_df.to_csv(
        RECOVERY_REPORT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    # One-row-per-source status.
    status_rows = []

    for _, source in source_map.iterrows():
        name = clean_text(
            source["university_name"]
        )
        key = normalize_school(
            name
        )

        if key in final_norms:
            school_rows = final_df[
                final_df["university_name"]
                .map(normalize_school)
                == key
            ]

            status_rows.append(
                {
                    "university_name": name,
                    "status": "ACCEPTED",
                    "accepted_rows": len(
                        school_rows
                    ),
                    "reason": "",
                    "source_url": clean_text(
                        source["source_url"]
                    ),
                }
            )
        else:
            match = new_excluded_df[
                new_excluded_df["university_name"]
                .map(normalize_school)
                == key
            ]

            reason = (
                clean_text(
                    match.iloc[0][
                        "exclusion_reason"
                    ]
                )
                if not match.empty
                else "EXCLUDED"
            )

            status_rows.append(
                {
                    "university_name": name,
                    "status": "EXCLUDED",
                    "accepted_rows": 0,
                    "reason": reason,
                    "source_url": clean_text(
                        source["source_url"]
                    ),
                }
            )

    pd.DataFrame(
        status_rows
    ).to_csv(
        SOURCE_STATUS_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    scores = pd.to_numeric(
        final_df[
            "cutoff_score"
        ],
        errors="coerce",
    )

    print()
    print("=" * 122)
    print("KẾT QUẢ 2024 FINAL TARGETED RECOVERY")
    print("=" * 122)
    print(
        f"SOURCE INVENTORY      : {len(source_map):5d} trường"
    )
    print(
        f"RECOVERED THIS PASS   : {len(recovered):5d} trường"
    )
    print(
        f"FINAL CLEAN 2024      : {len(final_df):5d} rows / "
        f"{final_df['university_name'].nunique():3d} trường"
    )
    print(
        f"SOURCE EXCLUDED       : {len(new_excluded_df):5d} trường"
    )
    print(
        f"REVIEW                : {len(review_df):5d} trường"
    )
    if not scores.empty:
        print(
            f"Score min/max         : "
            f"{scores.min():.2f} / {scores.max():.2f}"
        )
    print(
        f"Missing major_code    : "
        f"{int(final_df['major_code'].eq('').sum())}"
    )
    print(
        f"Missing major_name    : "
        f"{int(final_df['major_name'].eq('').sum())}"
    )
    print(
        f"Missing cutoff_score  : "
        f"{int(final_df['cutoff_score'].isna().sum())}"
    )
    print(
        f"ML READY 2024         : {len(ml_ready):5d} rows / "
        f"{ml_ready['university_name'].nunique():3d} trường"
    )
    print(
        f"ML EXCLUDED           : {len(ml_excluded):5d} rows"
    )
    print("-" * 122)
    print("FINAL       :", FINAL_FILE)
    print("ML READY    :", ML_READY_FILE)
    print("ML EXCLUDED :", ML_EXCLUDED_FILE)
    print("EXCLUDED    :", SOURCE_EXCLUDED_FILE)
    print("STATUS      :", SOURCE_STATUS_FILE)
    print("REPORT      :", RECOVERY_REPORT_FILE)
    print("BACKUP      :", BACKUP_FINAL)
    print("=" * 122)

    if recovered:
        print()
        print("CÁC TRƯỜNG CỨU THÊM:")
        for name in recovered:
            print(
                f"  ✅ {name}"
            )

    if not new_excluded_df.empty:
        print()
        print("15 EXCLUDED ĐẦU:")
        for _, row in new_excluded_df.head(
            15
        ).iterrows():
            print(
                f"  ⚠ {row['university_name']} | "
                f"{row['exclusion_reason']}"
            )

    print()
    print(
        "AUDIT 2024            : ✅ FINAL + EXCLUDED phủ đúng 167 trường; "
        "FINAL chỉ dùng primary source"
    )
    print(
        "2024 CHECKPOINT       : ✅ KHÓA NĂM 2024 SAU TARGETED RECOVERY"
    )


if __name__ == "__main__":
    main()
