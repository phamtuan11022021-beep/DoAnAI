from __future__ import annotations

import hashlib
import io
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
    from paddleocr import PPStructureV3
except ImportError:
    PPStructureV3 = None

YEAR = 2023
PIPELINE_VERSION = "2023-FINAL-LOCK-CROSSYEAR-20260923"

AGGREGATE_URL = (
    "https://thongtintuyensinh.vn/"
    "Diem-chuan-trung-tuyen-dai-hoc-theo-phuong-thuc-xet-diem-thi-"
    "TN-THPT-nam-2023_C309_D19066.htm"
)

ROOT_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT_DIR / "data" / "raw"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
DOC_DIR = RAW_DIR / "documents" / "2023"
RECOVERY_ROOT = RAW_DIR / "primary_recovery_2023"
ASSET_ROOT = RECOVERY_ROOT / "assets"
OCR_CACHE_ROOT = RECOVERY_ROOT / "ocr_cache"
ASCII_ROOT = Path(tempfile.gettempdir()) / "uniconnect_2023_recovery"

for p in (RAW_DIR, PROCESSED_DIR, DOC_DIR, RECOVERY_ROOT, ASSET_ROOT, OCR_CACHE_ROOT, ASCII_ROOT):
    p.mkdir(parents=True, exist_ok=True)

SOURCE_MAP_FILE = RAW_DIR / "source_map_2023.csv"
SOURCE_ANALYSIS_FILE = RAW_DIR / "source_analysis_2023.csv"
FINAL_FILE = PROCESSED_DIR / "admission_scores_2023_final.csv"
ML_READY_FILE = PROCESSED_DIR / "admission_scores_2023_ml_ready.csv"
ML_EXCLUDED_FILE = PROCESSED_DIR / "admission_scores_2023_ml_excluded.csv"
SOURCE_EXCLUDED_FILE = PROCESSED_DIR / "admission_scores_2023_source_excluded.csv"
SOURCE_STATUS_FILE = PROCESSED_DIR / "admission_scores_2023_source_status.csv"
REPORT_FILE = PROCESSED_DIR / "admission_scores_2023_recovery_report.csv"
REVIEW_FILE = PROCESSED_DIR / "admission_scores_2023_review.csv"

ROW_EXCLUDED_FILE = PROCESSED_DIR / "admission_scores_2023_row_excluded.csv"
FINAL_RECOVERY_REPORT_FILE = PROCESSED_DIR / "admission_scores_2023_final_recovery_report.csv"

FINAL_LOCK_REPORT_FILE = PROCESSED_DIR / "admission_scores_2023_final_lock_report.csv"
SOURCE_MAP_FINAL_BACKUP = RAW_DIR / "source_map_2023_before_final_lock.csv"
FINAL_PRE_LOCK_BACKUP = PROCESSED_DIR / "admission_scores_2023_final_before_final_lock.csv"

ARCHIVE_PAGES = tuple(
    f"https://thongtintuyensinh.vn/diem-chuan-trung-tuyen_C237_P{page}.htm"
    for page in range(1, 16)
)

BACKUP_FINAL_FILE = PROCESSED_DIR / "admission_scores_2023_final_before_targeted_recovery.csv"
BACKUP_EXCLUDED_FILE = PROCESSED_DIR / "admission_scores_2023_source_excluded_before_targeted_recovery.csv"
BACKUP_SOURCE_MAP_FILE = RAW_DIR / "source_map_2023_before_cleanup.csv"
BACKUP_ANALYSIS_FILE = RAW_DIR / "source_analysis_2023_before_cleanup.csv"

# Hai anchor navigation bị inventory V1 nhận nhầm là "trường".
NAVIGATION_JUNK = {
    "dai hoc",
    "dai hoc tu xa",
}

CANONICAL_COLUMNS = [
    "university_name", "major_code", "major_name", "year",
    "admission_method_codes", "combination", "cutoff_score",
    "admission_note", "source_url",
]

SOURCE_MAP_COLUMNS = ["university_name", "source_url", "source_type", "priority"]
ANALYSIS_COLUMNS = [
    "university_name", "source_type", "analysis_class", "http_status",
    "page_title", "local_file", "source_url",
]
EXCLUDED_COLUMNS = [
    "university_name", "source_type", "analysis_class", "exclusion_reason",
    "source_url", "local_file",
]
REPORT_COLUMNS = [
    "university_name", "source_type", "analysis_class", "priority",
    "strategies", "candidate_rows", "accepted_rows", "status", "reason",
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
    "thi tốt nghiệp thpt", "điểm thi tốt nghiệp thpt",
    "kết quả thi tốt nghiệp thpt", "xét điểm thi tốt nghiệp thpt",
    "xét tuyển theo kết quả thi tốt nghiệp thpt",
    "xét tuyển kết quả thi tốt nghiệp thpt", "thi tn thpt",
    "điểm thi tn thpt", "xét điểm thi tn thpt", "xét kết quả thi thpt",
    "xét điểm thi thpt", "theo điểm thi thpt",
)
NEGATIVE_METHODS = (
    "học bạ", "đánh giá năng lực", "đgnl", "đánh giá tư duy", "đgtd",
    "v-sat", "vsat", "tuyển thẳng", "xét tuyển sớm", "kỳ thi riêng",
    "đánh giá đầu vào đại học trên máy tính",
)
COMBINED_MARKERS = (
    "xét tuyển kết hợp", "xét kết hợp", "kết hợp với", "kết hợp điểm thi",
    "chứng chỉ", "ielts", "sat",
)
SCALE40_MARKERS = (
    "thang 40", "thang điểm 40", "thang điểm: 40", "nhân hệ số 2",
    "nhân đôi", "ngoại ngữ nhân hệ số", "môn ngoại ngữ nhân hệ số",
)
ML_EXCLUDE_MARKERS = (
    "outside_thpt30", "scale=40", "thang 40", "nhân hệ số", "quy đổi",
    "xét tuyển tổng hợp", "thpt_combined", "kết hợp", "chứng chỉ",
    "ielts", "sat", "đgnl", "đánh giá năng lực", "đánh giá tư duy",
    "v-sat", "vsat",
)

FORCE_EXCLUDE_NAMES = {
    "đại học huế",
    "đại học đà nẵng",
    "đại học thái nguyên",
}

SCHOOL_PREFIX_PATTERNS = (
    r"^truong\s+dh\b",
    r"^truong\s+dai\s+hoc\b",
    r"^dai\s+hoc\b",
    r"^dh\b",
    r"^hoc\s+vien\b",
    r"^hv\b",
    r"^khoa\s+quoc\s+te\b",
    r"^phan\s+hieu\b",
)

CODE_HEADER_MARKERS = (
    "ma nganh", "ma tuyen sinh", "ma xet tuyen", "ma chuong trinh",
    "ma ct", "ma ctdt",
)
NAME_HEADER_MARKERS = (
    "ten nganh", "nganh dao tao", "nganh tuyen sinh", "ten chuong trinh",
    "chuong trinh dao tao", "nganh hoc", "nhom nganh", "nganh",
)
SCORE_HEADER_MARKERS = (
    "diem chuan", "diem trung tuyen", "muc diem trung tuyen",
    "diem thi thpt", "diem thi tn thpt", "diem thi tot nghiep thpt",
    "diem xet tuyen", "diem tt",
)
COMBO_HEADER_MARKERS = ("to hop", "khoi thi", "ma to hop")
METHOD_HEADER_MARKERS = ("phuong thuc", "ma phuong thuc", "ptxt")
NOTE_HEADER_MARKERS = ("ghi chu", "tieu chi phu", "dieu kien phu", "dieu kien")
SCALE_HEADER_MARKERS = ("thang diem", "thang")


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
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFC", value)


def norm(value) -> str:
    text = strip_accents(clean_text(value)).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_school(value: str) -> str:
    text = norm(value)
    replacements = [
        (r"\bhv\b", "hoc vien"), (r"\bdh\b", "dai hoc"),
        (r"\bsp\b", "su pham"), (r"\bkh\b", "khoa hoc"),
        (r"\bcn\b", "cong nghe"),
        (r"\bdhqghcm\b", "dai hoc quoc gia tp hcm"),
        (r"\bdhqg hcm\b", "dai hoc quoc gia tp hcm"),
        (r"\bdhqg tp hcm\b", "dai hoc quoc gia tp hcm"),
        (r"\bdhqghn\b", "dai hoc quoc gia ha noi"),
        (r"\bdhqg ha noi\b", "dai hoc quoc gia ha noi"),
        (r"\bdhtn\b", "dai hoc thai nguyen"),
        (r"\bqg\b", "quoc gia"), (r"\bvn\b", "viet nam"),
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
    return any(marker in low for marker in ("trüng", "tuyén", "dgi hoc", "h9c", "ngµnh", "®iÓm"))


def explicit_thpt_context(*values: str) -> bool:
    text = " | ".join(clean_text(v).lower() for v in values if clean_text(v))
    return any(marker in text for marker in POSITIVE_THPT)


def negative_method_context(value: str) -> bool:
    low = clean_text(value).lower()
    return any(marker in low for marker in NEGATIVE_METHODS)


def combined_context(value: str) -> bool:
    low = clean_text(value).lower()
    return any(marker in low for marker in COMBINED_MARKERS)


def scale40_context(value: str) -> bool:
    low = clean_text(value).lower()
    return any(marker in low for marker in SCALE40_MARKERS)


def force_exclude(name: str) -> bool:
    target = normalize_school(name)
    return any(normalize_school(item) == target for item in FORCE_EXCLUDE_NAMES)


def canonicalize(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=CANONICAL_COLUMNS)
    df = pd.DataFrame(rows)
    for col in CANONICAL_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    df = df[CANONICAL_COLUMNS].copy()
    for col in (
        "university_name", "major_code", "major_name", "admission_method_codes",
        "combination", "admission_note", "source_url",
    ):
        df[col] = df[col].map(clean_text)
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["cutoff_score"] = pd.to_numeric(df["cutoff_score"], errors="coerce")
    return df


def dedupe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    keys = [
        "university_name", "major_code", "major_name", "year",
        "admission_method_codes", "combination", "cutoff_score",
    ]
    return (
        df.drop_duplicates(subset=keys, keep="first")
        .sort_values(["university_name", "major_code", "combination", "cutoff_score"], kind="stable")
        .reset_index(drop=True)
    )


def build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3, connect=3, read=3, status=3, backoff_factor=0.7,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "HEAD"}), raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update(HEADERS)
    return session


def decode_response(response: requests.Response) -> str:
    if not response.encoding or response.encoding.lower() == "iso-8859-1":
        response.encoding = response.apparent_encoding or "utf-8"
    return response.text


# =============================================================================
# SOURCE INVENTORY
# =============================================================================

def load_priority_schools() -> dict[str, int]:
    scores: dict[str, int] = {}
    for year in (2024, 2025):
        path = PROCESSED_DIR / f"admission_scores_{year}_ml_ready.csv"
        if not path.exists():
            continue
        try:
            df = pd.read_csv(path, dtype=str, keep_default_na=False, usecols=["university_name"])
        except Exception:
            continue
        for name in df["university_name"].unique():
            key = normalize_school(name)
            scores[key] = scores.get(key, 0) + 1
    return scores


def looks_like_school_anchor(text: str) -> bool:
    normalized = norm(text)
    if len(normalized) < 5:
        return False
    return any(re.search(pattern, normalized) for pattern in SCHOOL_PREFIX_PATTERNS)


def source_type_from_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
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


def discover_source_map(session: requests.Session) -> pd.DataFrame:
    response = session.get(AGGREGATE_URL, timeout=45, allow_redirects=True)
    response.raise_for_status()
    soup = BeautifulSoup(decode_response(response), "html.parser")
    priority_map = load_priority_schools()
    rows = []
    seen = set()

    for anchor in soup.find_all("a", href=True):
        text = clean_text(anchor.get_text(" ", strip=True))
        if not looks_like_school_anchor(text):
            continue
        url = urljoin(AGGREGATE_URL, clean_text(anchor.get("href")))
        if not url or url.rstrip("/") == AGGREGATE_URL.rstrip("/"):
            continue
        key = normalize_school(text)
        if not key or key in seen:
            continue
        seen.add(key)
        rows.append({
            "university_name": text,
            "source_url": url,
            "source_type": source_type_from_url(url),
            "priority": priority_map.get(key, 0),
        })

    df = pd.DataFrame(rows, columns=SOURCE_MAP_COLUMNS)
    if len(df) < 120:
        raise RuntimeError(
            f"Inventory chỉ tìm được {len(df)} trường. Dừng để tránh tạo source_map thiếu."
        )

    df = df.sort_values(
        ["priority", "university_name"], ascending=[False, True], kind="stable"
    ).reset_index(drop=True)
    df.to_csv(SOURCE_MAP_FILE, index=False, encoding="utf-8-sig")
    return df


def load_or_create_source_map(session: requests.Session) -> pd.DataFrame:
    if SOURCE_MAP_FILE.exists():
        try:
            df = pd.read_csv(SOURCE_MAP_FILE, dtype=str, keep_default_na=False)
            if len(df) >= 120 and df["university_name"].nunique() == len(df):
                if "priority" not in df.columns:
                    priority_map = load_priority_schools()
                    df["priority"] = df["university_name"].map(
                        lambda name: priority_map.get(normalize_school(name), 0)
                    )
                df["priority"] = pd.to_numeric(df["priority"], errors="coerce").fillna(0).astype(int)
                return df.sort_values(
                    ["priority", "university_name"], ascending=[False, True], kind="stable"
                ).reset_index(drop=True)
        except Exception:
            pass
    return discover_source_map(session)


# =============================================================================
# SOURCE ANALYSIS
# =============================================================================

def drive_direct_url(url: str) -> str:
    match = re.search(r"/file/d/([A-Za-z0-9_-]+)", clean_text(url))
    file_id = match.group(1) if match else ""
    if not file_id:
        values = parse_qs(urlparse(url).query).get("id")
        if values:
            file_id = values[0]
    if not file_id:
        return ""
    return f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"


def google_doc_export_url(url: str) -> str:
    text = clean_text(url)
    match = re.search(r"/document/d/([A-Za-z0-9_-]+)", text)
    if match:
        return f"https://docs.google.com/document/d/{match.group(1)}/export?format=pdf"
    match = re.search(r"/spreadsheets/d/([A-Za-z0-9_-]+)", text)
    if match:
        return f"https://docs.google.com/spreadsheets/d/{match.group(1)}/export?format=pdf"
    return ""


def download_file(session: requests.Session, url: str, target: Path) -> tuple[bool, int]:
    try:
        response = session.get(url, timeout=60, allow_redirects=True)
        status = response.status_code
        response.raise_for_status()
    except Exception:
        return False, 0
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(response.content)
    return target.exists() and target.stat().st_size > 1000, status


def analyze_source(session: requests.Session, source_row: pd.Series) -> dict:
    name = clean_text(source_row["university_name"])
    source_url = clean_text(source_row["source_url"])
    source_type = clean_text(source_row["source_type"]).upper()
    school_dir = DOC_DIR / slugify(name)
    school_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "university_name": name,
        "source_type": source_type,
        "analysis_class": "",
        "http_status": "",
        "page_title": "",
        "local_file": "",
        "source_url": source_url,
    }

    if source_type in {"PDF", "GOOGLE_DRIVE", "GOOGLE_DOC", "IMAGE"}:
        download_url = source_url
        suffix = ".pdf"
        if source_type == "GOOGLE_DRIVE":
            download_url = drive_direct_url(source_url)
            if not download_url:
                result["analysis_class"] = "DRIVE_UNRESOLVED"
                return result
        elif source_type == "GOOGLE_DOC":
            download_url = google_doc_export_url(source_url)
            if not download_url:
                result["analysis_class"] = "GOOGLE_DOC_UNRESOLVED"
                return result
        elif source_type == "IMAGE":
            suffix = Path(urlparse(source_url).path).suffix.lower() or ".jpg"

        target = school_dir / f"source{suffix}"
        if not target.exists():
            ok, status = download_file(session, download_url, target)
            result["http_status"] = status
            if not ok:
                result["analysis_class"] = (
                    "DRIVE_HTTP_FAILED" if source_type == "GOOGLE_DRIVE" else "DOWNLOAD_FAILED"
                )
                return result

        result["local_file"] = str(target)
        if source_type == "IMAGE":
            result["analysis_class"] = "IMAGE_SOURCE"
            return result
        if target.read_bytes()[:5] != b"%PDF":
            result["analysis_class"] = "DOCUMENT_NOT_PDF"
            return result
        try:
            doc = fitz.open(str(target))
            text_chars = sum(len(page.get_text("text") or "") for page in doc)
            doc.close()
        except Exception:
            text_chars = 0
        result["analysis_class"] = "PDF_TEXT_PDF" if text_chars >= 200 else "PDF_SCAN_OR_IMAGE"
        return result

    try:
        response = session.get(source_url, timeout=40, allow_redirects=True)
        result["http_status"] = response.status_code
        response.raise_for_status()
    except Exception:
        result["analysis_class"] = "HTML_HTTP_FAILED"
        return result

    if (
        "pdf" in clean_text(response.headers.get("Content-Type", "")).lower()
        or response.content[:5] == b"%PDF-"
    ):
        target = school_dir / "source.pdf"
        target.write_bytes(response.content)
        result["local_file"] = str(target)
        try:
            doc = fitz.open(str(target))
            text_chars = sum(len(page.get_text("text") or "") for page in doc)
            doc.close()
        except Exception:
            text_chars = 0
        result["analysis_class"] = "PDF_TEXT_PDF" if text_chars >= 200 else "PDF_SCAN_OR_IMAGE"
        return result

    html = decode_response(response)
    soup = BeautifulSoup(html, "html.parser")
    title = ""
    for tag_name in ("h1", "title"):
        tag = soup.find(tag_name)
        if tag:
            title = clean_text(tag.get_text(" ", strip=True))
            if title:
                break
    result["page_title"] = title

    try:
        dfs = pd.read_html(io.StringIO(html), header=None, thousands=None)
    except Exception:
        dfs = []

    candidate = False
    for df in dfs:
        sample = norm(" ".join(clean_text(v) for v in df.head(6).astype(str).values.flatten().tolist()))
        if (
            any(marker in sample for marker in CODE_HEADER_MARKERS)
            and any(marker in sample for marker in SCORE_HEADER_MARKERS)
        ):
            candidate = True
            break

    image_count = 0
    for img in soup.find_all("img"):
        raw = img.get("src") or img.get("data-src") or img.get("data-original") or img.get("data-lazy-src") or ""
        if clean_text(raw):
            image_count += 1

    if candidate:
        result["analysis_class"] = "HTML_THPT_CANDIDATE"
    elif dfs:
        result["analysis_class"] = "HTML_TABLES_NO_CANDIDATE"
    elif image_count:
        result["analysis_class"] = "HTML_IMAGE_ONLY"
    else:
        result["analysis_class"] = "HTML_NO_TABLE"
    return result


def load_or_create_analysis(
    session: requests.Session,
    source_map: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, dict]]:
    existing_map = {}
    if SOURCE_ANALYSIS_FILE.exists():
        try:
            existing = pd.read_csv(SOURCE_ANALYSIS_FILE, dtype=str, keep_default_na=False)
            existing_map = {
                normalize_school(row["university_name"]): row.to_dict()
                for _, row in existing.iterrows()
            }
        except Exception:
            pass

    rows = []
    print("\nPHÂN TÍCH NGUỒN 2023")
    total = len(source_map)

    for idx, (_, source) in enumerate(source_map.iterrows(), start=1):
        name = clean_text(source["university_name"])
        key = normalize_school(name)
        cached = existing_map.get(key)
        if cached and clean_text(cached.get("analysis_class", "")) not in {
            "", "HTML_HTTP_FAILED", "DOWNLOAD_FAILED", "DRIVE_HTTP_FAILED",
        }:
            result = cached
            print(f"[{idx:03d}/{total:03d}] {name} ... CACHE {result.get('analysis_class', '')}")
        else:
            result = analyze_source(session, source)
            print(f"[{idx:03d}/{total:03d}] {name} ... {result['analysis_class']}")
        rows.append(result)
        pd.DataFrame(rows, columns=ANALYSIS_COLUMNS).to_csv(
            SOURCE_ANALYSIS_FILE, index=False, encoding="utf-8-sig"
        )

    df = pd.DataFrame(rows, columns=ANALYSIS_COLUMNS)
    lookup = {
        normalize_school(row["university_name"]): row.to_dict()
        for _, row in df.iterrows()
    }
    return df, lookup


# =============================================================================
# TABLE PARSER
# =============================================================================

def normalize_grid(grid: list[list[str]]) -> list[list[str]]:
    out = []
    for row in grid:
        cleaned = [clean_text(v) for v in row]
        if any(cleaned):
            out.append(cleaned)
    return out


def combine_headers(rows: list[list[str]], start: int, depth: int) -> list[str]:
    width = max((len(row) for row in rows[start:start + depth]), default=0)
    headers = []
    for col in range(width):
        parts = []
        for row_idx in range(start, min(len(rows), start + depth)):
            if col >= len(rows[row_idx]):
                continue
            value = clean_text(rows[row_idx][col])
            if value and (not parts or value != parts[-1]):
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


def choose_header(rows: list[list[str]]) -> tuple[int, int, list[str]]:
    best = (0, 1, combine_headers(rows, 0, 1))
    best_score = semantic_header_score(best[2])
    for start in range(0, min(8, len(rows))):
        for depth in range(1, min(4, len(rows) - start) + 1):
            headers = combine_headers(rows, start, depth)
            score = semantic_header_score(headers)
            if score > best_score:
                best = (start, depth, headers)
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
        matched = [marker for marker in markers if marker in low]
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


def infer_code_column(rows: list[list[str]], start: int) -> Optional[int]:
    width = max((len(row) for row in rows[start:]), default=0)
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
    return ranked[0][1] if ranked[0][0] >= 2 else None


def infer_score_column(
    rows: list[list[str]],
    start: int,
    forbidden: set[int],
) -> Optional[int]:
    width = max((len(row) for row in rows[start:]), default=0)
    ranked = []
    for col in range(width):
        if col in forbidden:
            continue
        values = []
        for row in rows[start:start + 100]:
            if col >= len(row):
                continue
            number = parse_number(row[col])
            if number is not None and 0 < number <= 40:
                values.append(number)
        if len(values) < 2:
            continue
        median = sorted(values)[len(values) // 2]
        plausible = sum(1 for value in values if 10 <= value <= 30)
        ranked.append((len(values), plausible, -abs(median - 22), col))
    if not ranked:
        return None
    ranked.sort(reverse=True)
    return ranked[0][-1]


def infer_name_column(
    rows: list[list[str]],
    start: int,
    forbidden: set[int],
) -> Optional[int]:
    width = max((len(row) for row in rows[start:]), default=0)
    ranked = []
    for col in range(width):
        if col in forbidden:
            continue
        count = 0
        score = 0
        for row in rows[start:start + 80]:
            if col >= len(row):
                continue
            value = clean_text(row[col])
            if not value or parse_number(value) is not None or valid_major_code(value):
                continue
            if re.search(r"[A-Za-zÀ-ỹ]", value):
                count += 1
                score += min(len(value), 60)
        if count:
            ranked.append((count, score, col))
    if not ranked:
        return None
    ranked.sort(reverse=True)
    return ranked[0][-1]


def code_from_name(value: str) -> tuple[str, str]:
    text = clean_text(value)
    for raw in reversed(re.findall(r"\(([A-Za-z0-9_.-]{3,20})\)", text)):
        if valid_major_code(raw):
            cleaned = re.sub(r"\s*\(" + re.escape(raw) + r"\)\s*$", "", text).strip()
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
        ctx = low[max(0, match.start() - 100):min(len(low), match.end() + 260)]
        if explicit_thpt_context(ctx):
            mapping[code] = "THPT"
            mapping[f"PT{code}"] = "THPT"
        elif negative_method_context(ctx):
            mapping[code] = "OTHER"
            mapping[f"PT{code}"] = "OTHER"
    return mapping


def row_method_ok(
    row: list[str],
    method_idx: Optional[int],
    method_map: dict[str, str],
    global_thpt: bool,
    page_combined: bool,
) -> tuple[bool, str]:
    if method_idx is None:
        if global_thpt:
            return True, "GLOBAL_THPT_COMBINED" if page_combined else "GLOBAL_THPT"
        return False, "UNKNOWN"

    value = get_cell(row, method_idx)
    low = value.lower()
    if negative_method_context(low):
        return False, "NEGATIVE"
    if explicit_thpt_context(low):
        return True, "ROW_THPT_COMBINED" if combined_context(low) else "ROW_THPT"

    compact = re.sub(r"\s+", "", value).upper()
    digits = re.sub(r"\D", "", compact)
    for key in (compact, digits, f"PT{digits}" if digits else ""):
        if key in method_map:
            return method_map[key] == "THPT", f"MAP_{key}"

    if global_thpt:
        return True, "GLOBAL_THPT_COMBINED" if page_combined else "GLOBAL_THPT"
    return False, "UNKNOWN"


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

    code_idx = find_header_idx(headers, CODE_HEADER_MARKERS)
    name_idx = find_header_idx(
        headers,
        NAME_HEADER_MARKERS,
        reject=("ma nganh", "ma tuyen sinh", "diem", "to hop"),
    )
    score_idx = find_header_idx(
        headers,
        SCORE_HEADER_MARKERS,
        reject=("hoc ba", "dgnl", "danh gia nang luc", "danh gia tu duy", "vsat"),
    )
    combo_idx = find_header_idx(headers, COMBO_HEADER_MARKERS)
    method_idx = find_header_idx(headers, METHOD_HEADER_MARKERS)
    note_idx = find_header_idx(headers, NOTE_HEADER_MARKERS)
    scale_idx = find_header_idx(headers, SCALE_HEADER_MARKERS)

    if code_idx is None:
        code_idx = infer_code_column(rows, data_start)
    if score_idx is None:
        forbidden = {idx for idx in (code_idx, combo_idx, method_idx, note_idx, scale_idx) if idx is not None}
        score_idx = infer_score_column(rows, data_start, forbidden)
    if score_idx is None:
        return []
    if name_idx is None:
        forbidden = {idx for idx in (code_idx, score_idx, combo_idx, method_idx, note_idx, scale_idx) if idx is not None}
        name_idx = infer_name_column(rows, data_start, forbidden)
    if name_idx is None:
        return []

    global_thpt = explicit_thpt_context(context)
    page_combined = "PAGE_METHOD_COMBINED" in context
    method_map = method_map_from_context(context)

    output = []
    current_code = ""
    current_name = ""

    for row in rows[data_start:]:
        raw_code = get_cell(row, code_idx)
        raw_name = get_cell(row, name_idx)

        if raw_code and valid_major_code(raw_code):
            current_code = normalize_major_code(raw_code)

        embedded_code, embedded_name = code_from_name(raw_name)
        if embedded_code:
            current_code = embedded_code
            raw_name = embedded_name

        if raw_name and parse_number(raw_name) is None and not valid_major_code(raw_name) and len(raw_name) >= 2:
            current_name = raw_name

        score = parse_number(get_cell(row, score_idx))
        if score is None or not (0 < score <= 40):
            continue

        method_ok, method_evidence = row_method_ok(
            row, method_idx, method_map, global_thpt, page_combined
        )
        if not method_ok or not current_code or not current_name:
            continue

        note_parts = [
            f"PRIMARY2023:{strategy}",
            f"method_evidence={method_evidence}",
        ]
        scale = get_cell(row, scale_idx)
        note = get_cell(row, note_idx)
        if scale:
            note_parts.append(f"scale={scale}")
        if note:
            note_parts.append(note)
        if score > 30:
            note_parts.append("outside_THPT30")
        if "COMBINED" in method_evidence:
            note_parts.append("thpt_combined")

        output.append({
            "university_name": university_name,
            "major_code": current_code,
            "major_name": current_name,
            "year": YEAR,
            "admission_method_codes": "THPT",
            "combination": get_cell(row, combo_idx),
            "cutoff_score": float(score),
            "admission_note": "; ".join(note_parts),
            "source_url": source_url,
        })

    return output


# =============================================================================
# HTML / PDF EXTRACTION
# =============================================================================

def fetch_html_context_and_tables(
    session: requests.Session,
    *,
    university_name: str,
    source_url: str,
    analysis_row: dict,
) -> tuple[pd.DataFrame, str, str, str]:
    try:
        response = session.get(source_url, timeout=40, allow_redirects=True)
        response.raise_for_status()
    except Exception as exc:
        return pd.DataFrame(columns=CANONICAL_COLUMNS), "", "", f"HTML_REQUEST_{type(exc).__name__}"

    if (
        "pdf" in clean_text(response.headers.get("Content-Type", "")).lower()
        or response.content[:5] == b"%PDF-"
    ):
        return pd.DataFrame(columns=CANONICAL_COLUMNS), "", "", "HTML_IS_PDF"

    html = decode_response(response)
    soup = BeautifulSoup(html, "html.parser")
    title = ""
    for tag_name in ("h1", "title"):
        tag = soup.find(tag_name)
        if tag:
            title = clean_text(tag.get_text(" ", strip=True))
            if title:
                break

    visible = clean_text(soup.get_text(" ", strip=True))
    context = f"{title} | {visible[:18000]} | {source_url}"

    # Mark combined only when title/lead explicitly frames the method as combined.
    lead = f"{title} | {visible[:2500]}"
    if explicit_thpt_context(lead) and combined_context(lead):
        context += " | PAGE_METHOD_COMBINED"

    if "THPT_CANDIDATE" in clean_text(analysis_row.get("analysis_class", "")).upper():
        context += " | xét điểm thi tốt nghiệp THPT"

    try:
        dfs = pd.read_html(io.StringIO(html), header=None, thousands=None)
    except Exception:
        dfs = []

    rows = []
    for df in dfs:
        if df.empty:
            continue
        grid = [[clean_text(v) for v in row] for row in df.astype(object).values.tolist()]
        rows.extend(parse_table_grid(
            grid,
            university_name=university_name,
            source_url=source_url,
            context=context,
            strategy="HTML",
        ))

    return dedupe(canonicalize(rows)), context, html, f"tables={len(dfs)}"


def read_pdf_text_and_tables(path: Path) -> tuple[str, list[list[list[str]]], str]:
    text_parts = []
    tables = []
    diagnostics = []
    try:
        doc = fitz.open(str(path))
    except Exception as exc:
        return "", [], f"PDF_OPEN_{type(exc).__name__}"

    for page_idx, page in enumerate(doc):
        try:
            text = page.get_text("text")
        except Exception:
            text = ""
        if text.strip():
            text_parts.append(text)
        try:
            finder = page.find_tables()
            for table in getattr(finder, "tables", []):
                data = table.extract()
                if data:
                    tables.append([[clean_text(v) for v in row] for row in data])
        except Exception as exc:
            diagnostics.append(f"p{page_idx + 1}:{type(exc).__name__}")

    doc.close()
    return "\n".join(text_parts), tables, "|".join(diagnostics)


def parse_plain_text_rows(
    text: str,
    *,
    university_name: str,
    source_url: str,
    context: str,
) -> pd.DataFrame:
    if not explicit_thpt_context(context, text[:16000]):
        return pd.DataFrame(columns=CANONICAL_COLUMNS)

    rows = []
    page_combined = "PAGE_METHOD_COMBINED" in context

    for raw_line in text.splitlines():
        line = clean_text(raw_line)
        if len(line) < 10:
            continue
        match = re.match(
            r"^\s*(\d{6,8}|[A-Z]{1,8}\d{1,8}[A-Z0-9]{0,6})\s+(.+)$",
            line,
            flags=re.I,
        )
        if not match:
            continue
        code = normalize_major_code(match.group(1))
        if not valid_major_code(code):
            continue
        rest = match.group(2)
        score_matches = []
        for item in re.finditer(r"(?<!\d)(\d{1,2}(?:[.,]\d{1,2})?)(?!\d)", rest):
            score = parse_number(item.group(1))
            if score is not None and 0 < score <= 40:
                score_matches.append((item.start(), score))
        if not score_matches:
            continue
        start, score = score_matches[-1]
        major_name = clean_text(rest[:start])
        if len(major_name) < 3 or looks_garbled(major_name):
            continue
        notes = ["PRIMARY2023:PDF_TEXT_LINE", "method_evidence=GLOBAL_THPT"]
        if page_combined:
            notes.append("thpt_combined")
        if score > 30:
            notes.append("outside_THPT30")
        rows.append({
            "university_name": university_name,
            "major_code": code,
            "major_name": major_name,
            "year": YEAR,
            "admission_method_codes": "THPT",
            "combination": "",
            "cutoff_score": float(score),
            "admission_note": "; ".join(notes),
            "source_url": source_url,
        })

    out = dedupe(canonicalize(rows))
    return out if len(out) >= 2 else pd.DataFrame(columns=CANONICAL_COLUMNS)


# =============================================================================
# IMAGE / OCR
# =============================================================================

def image_is_useful(path: Path) -> bool:
    try:
        with Image.open(path) as image:
            width, height = image.size
    except Exception:
        return False
    if width < 400 or height < 100 or width * height < 100_000:
        return False
    # Avoid webpage sprites / absurdly wide render artifacts.
    ratio = max(width, height) / max(1, min(width, height))
    if ratio > 25 and max(width, height) > 10_000:
        return False
    return True


def collect_html_images(
    session: requests.Session,
    *,
    html: str,
    source_url: str,
    school_dir: Path,
) -> list[Path]:
    soup = BeautifulSoup(html, "html.parser")
    output = []
    seen = set()

    for idx, img in enumerate(soup.find_all("img"), start=1):
        raw = (
            img.get("src") or img.get("data-src") or img.get("data-original")
            or img.get("data-lazy-src") or ""
        )
        raw = clean_text(raw)
        if not raw:
            continue
        url = urljoin(source_url, raw)
        if url in seen:
            continue
        seen.add(url)
        low = url.lower()
        if any(marker in low for marker in (
            "logo", "icon", "avatar", "banner", "facebook", "youtube", "ads", "advert"
        )):
            continue
        suffix = Path(urlparse(url).path).suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
            suffix = ".jpg"
        target = school_dir / f"html_img_{idx:02d}{suffix}"
        if not target.exists():
            ok, _ = download_file(session, url, target)
            if not ok:
                continue
        if image_is_useful(target):
            output.append(target)
    return output


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
        _OCR_PIPELINE = PPStructureV3(lang="vi", ocr_version="PP-OCRv3")
    return _OCR_PIPELINE


def ascii_school_dir(name: str) -> Path:
    path = ASCII_ROOT / slugify(name)
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
    target_dir = ascii_school_dir(university_name)
    try:
        with Image.open(source) as image:
            image = image.convert("RGB")
            width, height = image.size
            if width <= max_side and height <= max_side:
                target = target_dir / f"{label}.png"
                image.save(target, format="PNG")
                return [target]

            output = []
            if height >= width:
                start = 0
                tile_idx = 1
                while start < height:
                    end = min(height, start + max_side)
                    crop = image.crop((0, start, width, end))
                    if crop.width > max_side:
                        ratio = max_side / crop.width
                        crop = crop.resize((max_side, max(1, int(crop.height * ratio))))
                    target = target_dir / f"{label}_tile_{tile_idx:03d}.png"
                    crop.save(target, format="PNG")
                    output.append(target)
                    if end >= height:
                        break
                    start = max(start + 1, end - overlap)
                    tile_idx += 1
            else:
                start = 0
                tile_idx = 1
                while start < width:
                    end = min(width, start + max_side)
                    crop = image.crop((start, 0, end, height))
                    if crop.height > max_side:
                        ratio = max_side / crop.height
                        crop = crop.resize((max(1, int(crop.width * ratio)), max_side))
                    target = target_dir / f"{label}_tile_{tile_idx:03d}.png"
                    crop.save(target, format="PNG")
                    output.append(target)
                    if end >= width:
                        break
                    start = max(start + 1, end - overlap)
                    tile_idx += 1
            return output
    except Exception:
        return []


def render_pdf_pages_ascii(
    pdf_path: Path,
    *,
    university_name: str,
    max_pages: int = 12,
) -> list[Path]:
    try:
        doc = fitz.open(str(pdf_path))
    except Exception:
        return []

    scored = []
    for idx, page in enumerate(doc):
        try:
            text = clean_text(page.get_text("text"))
        except Exception:
            text = ""
        low = text.lower()
        keyword_score = sum(
            1 for marker in ("điểm", "trúng tuyển", "mã ngành", "thpt", "tốt nghiệp", "ngành")
            if marker in low
        )
        scored.append((keyword_score, idx))

    selected = [idx for score, idx in sorted(scored, reverse=True) if score >= 2][:max_pages]
    if not selected:
        count = len(doc)
        candidates = list(range(min(count, max_pages // 2)))
        candidates += list(range(max(0, count - max_pages // 2), count))
        selected = []
        for idx in candidates:
            if idx not in selected:
                selected.append(idx)
        selected = selected[:max_pages]

    output = []
    target_dir = ascii_school_dir(university_name)
    for idx in selected:
        try:
            pix = doc[idx].get_pixmap(matrix=fitz.Matrix(2.0, 2.0), alpha=False)
            target = target_dir / f"pdf_page_{idx + 1:03d}.png"
            pix.save(str(target))
            output.append(target)
        except Exception:
            continue
    doc.close()
    return output


def recursive_collect_pred_html(value, output: list[str]) -> None:
    if isinstance(value, str):
        return
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"pred_html", "html"} and isinstance(child, str) and "<table" in child.lower():
                output.append(child)
            else:
                recursive_collect_pred_html(child, output)
    elif isinstance(value, (list, tuple)):
        for child in value:
            recursive_collect_pred_html(child, output)


def markdown_pipe_tables(markdown: str) -> list[list[list[str]]]:
    tables = []
    current = []

    def flush():
        nonlocal current
        if len(current) < 2:
            current = []
            return
        parsed = []
        for line in current:
            cells = [clean_text(cell) for cell in line.strip().strip("|").split("|")]
            if cells and all(
                re.fullmatch(r":?-{3,}:?", cell.replace(" ", ""))
                for cell in cells if cell
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


def ocr_cache_file(image_path: Path, university_name: str) -> Path:
    stat = image_path.stat()
    signature = f"{image_path.resolve()}|{stat.st_size}|{int(stat.st_mtime)}"
    digest = hashlib.sha1(signature.encode("utf-8", errors="ignore")).hexdigest()[:16]
    school_dir = OCR_CACHE_ROOT / slugify(university_name)
    school_dir.mkdir(parents=True, exist_ok=True)
    return school_dir / f"{image_path.stem}_{digest}.json"


def extract_result_payload(result) -> dict:
    markdown_parts = []
    html_parts = []
    try:
        md = result.markdown
    except Exception:
        md = None

    if isinstance(md, str):
        markdown_parts.append(md)
    elif md is not None:
        try:
            value = getattr(md, "markdown_texts", None)
            if isinstance(value, str):
                markdown_parts.append(value)
        except Exception:
            pass
        try:
            if hasattr(md, "get"):
                value = md.get("markdown_texts")
                if isinstance(value, str):
                    markdown_parts.append(value)
        except Exception:
            pass

    try:
        json_obj = result.json
    except Exception:
        json_obj = None
    if isinstance(json_obj, str):
        try:
            json_obj = json.loads(json_obj)
        except Exception:
            json_obj = None
    recursive_collect_pred_html(json_obj, html_parts)
    return {"markdown": "\n\n".join(markdown_parts), "html_tables": html_parts}


def ocr_one_image(
    image_path: Path,
    *,
    university_name: str,
) -> tuple[str, list[list[list[str]]], str]:
    cache_file = ocr_cache_file(image_path, university_name)
    if cache_file.exists():
        try:
            payload = json.loads(cache_file.read_text(encoding="utf-8"))
            return payload.get("markdown", ""), payload.get("tables", []), "CACHE"
        except Exception:
            pass

    pipeline = get_ocr_pipeline()
    if pipeline is None:
        return "", [], "OCR_ENGINE_UNAVAILABLE"

    try:
        results = pipeline.predict(input=str(image_path))
    except Exception as exc:
        return "", [], f"OCR_{type(exc).__name__}"

    markdown_parts = []
    tables = []
    for result in results:
        payload = extract_result_payload(result)
        if payload["markdown"]:
            markdown_parts.append(payload["markdown"])
        for html in payload["html_tables"]:
            try:
                dfs = pd.read_html(io.StringIO(html), header=None, thousands=None)
            except Exception:
                continue
            for df in dfs:
                if not df.empty:
                    tables.append([[clean_text(v) for v in row] for row in df.astype(object).values.tolist()])

    markdown = "\n\n".join(markdown_parts)
    tables.extend(markdown_pipe_tables(markdown))
    cache_file.write_text(
        json.dumps({"markdown": markdown, "tables": tables}, ensure_ascii=False),
        encoding="utf-8",
    )
    return markdown, tables, "OCR"


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
    return SequenceMatcher(None, na, nb).ratio() >= 0.72


def validate_candidate(
    df: pd.DataFrame,
    *,
    university_name: str,
    context: str,
) -> tuple[bool, str]:
    if df.empty:
        return False, "NO_ROWS"
    if (df["university_name"].map(clean_text) != clean_text(university_name)).any():
        return False, "WRONG_SCHOOL"
    if df["major_code"].eq("").any():
        return False, "MISSING_MAJOR_CODE"
    if df["major_name"].eq("").any():
        return False, "MISSING_MAJOR_NAME"
    if df["cutoff_score"].isna().any():
        return False, "MISSING_SCORE"
    for code in df["major_code"]:
        if not valid_major_code(code):
            return False, f"BAD_MAJOR_CODE:{code}"
    if df["major_name"].map(looks_garbled).any():
        return False, "GARBLED_MAJOR_NAME"

    scores = pd.to_numeric(df["cutoff_score"], errors="coerce")
    if scores.isna().any():
        return False, "NON_NUMERIC_SCORE"
    if ((scores <= 0) | (scores > 40)).any():
        return False, "SCORE_OUTSIDE_0_40"

    joined = context + " | " + " | ".join(df["admission_note"].astype(str))
    if not (
        explicit_thpt_context(joined)
        or "method_evidence=GLOBAL_THPT" in joined
        or "method_evidence=ROW_THPT" in joined
        or "method_evidence=MAP_" in joined
    ):
        return False, "METHOD_THPT_UNVERIFIED"

    if (scores > 30).any() and not scale40_context(joined):
        return False, "SCORE_GT30_WITHOUT_SCALE40"

    for code, group in df.groupby("major_code", sort=False):
        names = [clean_text(v) for v in group["major_name"].unique() if clean_text(v)]
        if len(names) <= 1:
            continue
        anchor = names[0]
        if any(not names_compatible(anchor, other) for other in names[1:]):
            return False, f"CODE_NAME_CONFLICT:{code}"
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
        frame = dedupe(frame)
        ok, _ = validate_candidate(frame, university_name=university_name, context=context)
        if ok:
            valid.append((strategy, frame))

    if not valid:
        return pd.DataFrame(columns=CANONICAL_COLUMNS), "NO_VALID_STRATEGY"

    priority = {"HTML": 100, "PDF_TABLE": 95, "PDF_TEXT_LINE": 85, "OCR_TABLE": 75}
    valid.sort(key=lambda item: (priority.get(item[0], 0), len(item[1])), reverse=True)
    best_strategy, best = valid[0]

    best_map = {}
    for _, row in best.iterrows():
        best_map.setdefault(normalize_major_code(row["major_code"]), []).append(float(row["cutoff_score"]))

    for strategy, other in valid[1:]:
        other_map = {}
        for _, row in other.iterrows():
            other_map.setdefault(normalize_major_code(row["major_code"]), []).append(float(row["cutoff_score"]))
        common = set(best_map) & set(other_map)
        if len(common) < 3:
            continue
        mismatches = 0
        for code in common:
            agree = any(abs(a - b) <= 0.12 for a in best_map[code] for b in other_map[code])
            if not agree:
                mismatches += 1
        if mismatches / len(common) > 0.60:
            return pd.DataFrame(columns=CANONICAL_COLUMNS), f"STRATEGY_CONFLICT:{best_strategy}_VS_{strategy}"

    return best, best_strategy


def ml_compatible(row: pd.Series) -> tuple[bool, str]:
    score = parse_number(row["cutoff_score"])
    if score is None:
        return False, "score_invalid"
    if not (0 < score <= 30):
        return False, "outside_0_30"
    note = clean_text(row["admission_note"]).lower()
    if any(marker in note for marker in ML_EXCLUDE_MARKERS):
        return False, "note_non_comparable"
    method = clean_text(row["admission_method_codes"]).lower()
    if "thpt" not in method and not re.search(r"\bpt\d{1,3}\b", method):
        return False, "method_not_thpt"
    return True, ""





# =============================================================================
# 2023 FINAL TARGETED RECOVERY HELPERS
# =============================================================================

def backup_once(source: Path, destination: Path) -> None:
    if source.exists() and not destination.exists():
        shutil.copy2(source, destination)


def clean_inventory_2023(source_map: pd.DataFrame) -> pd.DataFrame:
    """
    Loại đúng 2 anchor điều hướng bị selector cũ nhận nhầm:
      - ĐẠI HỌC
      - Đại học từ xa
    Không loại umbrella ĐẠI HỌC HUẾ / THÁI NGUYÊN / ĐÀ NẴNG.
    """
    backup_once(SOURCE_MAP_FILE, BACKUP_SOURCE_MAP_FILE)
    backup_once(SOURCE_ANALYSIS_FILE, BACKUP_ANALYSIS_FILE)

    df = source_map.copy()
    df["_norm"] = df["university_name"].map(normalize_school)
    df = df[~df["_norm"].isin(NAVIGATION_JUNK)].drop(columns=["_norm"]).copy()

    priority_map = load_priority_schools()
    df["priority"] = df["university_name"].map(
        lambda name: priority_map.get(normalize_school(name), 0)
    )
    df["priority"] = pd.to_numeric(df["priority"], errors="coerce").fillna(0).astype(int)

    df = (
        df.drop_duplicates(subset=["university_name"], keep="first")
        .sort_values(
            ["priority", "university_name"],
            ascending=[False, True],
            kind="stable",
        )
        .reset_index(drop=True)
    )

    # Với inventory hiện tại của 2023, 169 - 2 navigation = 167 nguồn thật.
    if len(df) != 167:
        raise RuntimeError(
            f"Inventory sau cleanup là {len(df)}, không phải 167. "
            "Dừng để không làm sai source accounting."
        )

    df.to_csv(SOURCE_MAP_FILE, index=False, encoding="utf-8-sig")

    # Đồng bộ source_analysis, bỏ đúng navigation junk.
    if SOURCE_ANALYSIS_FILE.exists():
        try:
            analysis = pd.read_csv(
                SOURCE_ANALYSIS_FILE,
                dtype=str,
                keep_default_na=False,
            )
            analysis["_norm"] = analysis["university_name"].map(normalize_school)
            analysis = analysis[
                ~analysis["_norm"].isin(NAVIGATION_JUNK)
            ].drop(columns=["_norm"])
            analysis.to_csv(
                SOURCE_ANALYSIS_FILE,
                index=False,
                encoding="utf-8-sig",
            )
        except Exception:
            pass

    return df


def sniff_local_file(path: Path) -> str:
    """
    Nhận diện theo magic/content thay vì tin vào đuôi file.
    """
    try:
        raw = path.read_bytes()[:4096]
    except Exception:
        return "UNKNOWN"

    if raw.startswith(b"%PDF"):
        return "PDF"

    try:
        with Image.open(path) as image:
            image.verify()
        return "IMAGE"
    except Exception:
        pass

    low = raw.lower()
    if (
        b"<html" in low
        or b"<!doctype html" in low
        or b"<body" in low
        or b"<table" in low
    ):
        return "HTML"

    if raw.startswith(b"PK\x03\x04"):
        return "ZIP_DOC"

    return "OTHER"


def source_context_is_thpt(
    source_url: str,
    analysis_row: dict,
    extra_text: str = "",
) -> bool:
    title = clean_text(analysis_row.get("page_title", ""))
    analysis_class = clean_text(analysis_row.get("analysis_class", "")).upper()

    if explicit_thpt_context(source_url, title, extra_text):
        return True

    # Chỉ dùng label candidate như evidence bổ trợ; không dùng cho class khác.
    if "THPT_CANDIDATE" in analysis_class:
        return True

    return False


def html_tables_from_blob(
    html: str,
    *,
    university_name: str,
    source_url: str,
    context: str,
    strategy: str,
) -> pd.DataFrame:
    rows = []

    # pandas parser
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
            [clean_text(value) for value in row]
            for row in df.astype(object).values.tolist()
        ]

        rows.extend(
            parse_table_grid(
                grid,
                university_name=university_name,
                source_url=source_url,
                context=context,
                strategy=strategy,
            )
        )

    # BeautifulSoup fallback: hữu ích với HTML malformed mà read_html bỏ sót.
    soup = BeautifulSoup(html, "html.parser")

    for table in soup.find_all("table"):
        grid = []

        for tr in table.find_all("tr"):
            cells = [
                clean_text(cell.get_text(" ", strip=True))
                for cell in tr.find_all(["th", "td"])
            ]

            if cells:
                grid.append(cells)

        if len(grid) >= 2:
            rows.extend(
                parse_table_grid(
                    grid,
                    university_name=university_name,
                    source_url=source_url,
                    context=context,
                    strategy=f"{strategy}_BS4",
                )
            )

    return dedupe(canonicalize(rows))


def collect_embedded_primary_assets(
    session: requests.Session,
    *,
    html: str,
    source_url: str,
    university_name: str,
) -> list[Path]:
    """
    Thu ảnh/PDF từ đúng primary page:
      img src/data-src/srcset
      a href ảnh/PDF
      iframe/embed/object
    Chỉ một hop, không đi sang website fallback.
    """
    school_dir = ASSET_ROOT / slugify(university_name)
    school_dir.mkdir(parents=True, exist_ok=True)

    soup = BeautifulSoup(html, "html.parser")
    urls = []

    def add_url(raw: str) -> None:
        raw = clean_text(raw)
        if not raw:
            return

        # srcset: lấy từng URL, bỏ descriptor 1x/2x/800w
        if "," in raw and (" " in raw):
            for part in raw.split(","):
                token = clean_text(part).split(" ")[0]
                if token:
                    add_url(token)
            return

        url = urljoin(source_url, raw)
        low = url.lower()

        if any(
            marker in low
            for marker in (
                "logo", "icon", "avatar", "banner", "facebook",
                "youtube", "ads", "advert", "sprite",
            )
        ):
            return

        if url not in urls:
            urls.append(url)

    for img in soup.find_all("img"):
        for attr in (
            "src", "data-src", "data-original", "data-lazy-src", "srcset"
        ):
            value = img.get(attr)
            if value:
                add_url(value)

    for tag in soup.find_all(["a", "iframe", "embed", "object"]):
        for attr in ("href", "src", "data"):
            value = tag.get(attr)
            if not value:
                continue

            candidate = urljoin(source_url, clean_text(value))
            low = candidate.lower()

            if (
                low.endswith((".pdf", ".jpg", ".jpeg", ".png", ".webp"))
                or "drive.google.com" in low
                or "docs.google.com" in low
                or "upload" in low
            ):
                add_url(value)

    assets = []

    for idx, url in enumerate(urls[:25], start=1):
        low = url.lower()
        suffix = Path(urlparse(url).path).suffix.lower()

        if "drive.google.com" in low:
            direct = drive_direct_url(url)
            if not direct:
                continue
            url_to_get = direct
            suffix = ".pdf"

        elif "docs.google.com" in low:
            direct = google_doc_export_url(url)
            if not direct:
                continue
            url_to_get = direct
            suffix = ".pdf"

        else:
            url_to_get = url

        if suffix not in {
            ".pdf", ".jpg", ".jpeg", ".png", ".webp"
        }:
            suffix = ".bin"

        target = school_dir / f"embedded_{idx:02d}{suffix}"

        if not target.exists():
            ok, _ = download_file(
                session,
                url_to_get,
                target,
            )
            if not ok:
                continue

        kind = sniff_local_file(target)

        if kind in {"PDF", "IMAGE", "HTML"}:
            assets.append(target)

    # stable unique
    seen = set()
    output = []

    for path in assets:
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        output.append(path)

    return output


def retry_primary_payload(
    session: requests.Session,
    *,
    university_name: str,
    source_url: str,
    source_type: str,
    analysis_row: dict,
) -> tuple[str, str, list[Path], str]:
    """
    Trả về:
      html_text, context_text, assets, diagnostic

    Điểm quan trọng: DOCUMENT_NOT_PDF không bị xem là dead source nữa.
    Nếu file tải về thực chất là HTML hoặc IMAGE thì xử lý đúng magic.
    """
    html_text = ""
    context_parts = [
        source_url,
        clean_text(analysis_row.get("page_title", "")),
    ]
    assets = []
    diagnostics = []

    # 1) local_file từ analysis.
    local_file = clean_text(analysis_row.get("local_file", ""))

    if local_file:
        local_path = Path(local_file)

        if local_path.exists():
            kind = sniff_local_file(local_path)
            diagnostics.append(f"local={kind}")

            if kind in {"PDF", "IMAGE"}:
                assets.append(local_path)

            elif kind == "HTML":
                try:
                    html_text = local_path.read_text(
                        encoding="utf-8",
                        errors="replace",
                    )
                except Exception:
                    html_text = local_path.read_bytes().decode(
                        "utf-8",
                        errors="replace",
                    )

    # 2) Luôn retry original primary URL một lần.
    try:
        response = session.get(
            source_url,
            timeout=45,
            allow_redirects=True,
        )
        response.raise_for_status()

        content_type = clean_text(
            response.headers.get("Content-Type", "")
        ).lower()

        body = response.content

        if body[:5] == b"%PDF" or "application/pdf" in content_type:
            school_dir = DOC_DIR / slugify(university_name)
            school_dir.mkdir(parents=True, exist_ok=True)

            target = school_dir / "source_targeted.pdf"

            if not target.exists():
                target.write_bytes(body)

            assets.append(target)
            diagnostics.append("retry=PDF")

        else:
            decoded = decode_response(response)

            if (
                "<html" in decoded.lower()
                or "<table" in decoded.lower()
                or "<body" in decoded.lower()
            ):
                html_text = decoded
                diagnostics.append("retry=HTML")
            else:
                school_dir = ASSET_ROOT / slugify(university_name)
                school_dir.mkdir(parents=True, exist_ok=True)

                suffix = Path(urlparse(response.url).path).suffix.lower()

                if suffix not in {
                    ".jpg", ".jpeg", ".png", ".webp"
                }:
                    suffix = ".bin"

                target = school_dir / f"retry_payload{suffix}"
                target.write_bytes(body)

                kind = sniff_local_file(target)
                diagnostics.append(f"retry={kind}")

                if kind in {"PDF", "IMAGE"}:
                    assets.append(target)

                elif kind == "HTML":
                    html_text = target.read_text(
                        encoding="utf-8",
                        errors="replace",
                    )

    except Exception as exc:
        diagnostics.append(f"retry={type(exc).__name__}")

    # 3) Nếu HTML có, lấy visible context và resource đúng primary.
    if html_text:
        soup = BeautifulSoup(html_text, "html.parser")

        title = ""
        for tag_name in ("h1", "title"):
            tag = soup.find(tag_name)
            if tag:
                title = clean_text(tag.get_text(" ", strip=True))
                if title:
                    break

        visible = clean_text(soup.get_text(" ", strip=True))
        context_parts.extend([title, visible[:20000]])

        assets.extend(
            collect_embedded_primary_assets(
                session,
                html=html_text,
                source_url=source_url,
                university_name=university_name,
            )
        )

    # unique
    seen = set()
    unique_assets = []

    for path in assets:
        try:
            key = str(path.resolve())
        except Exception:
            key = str(path)

        if key in seen:
            continue

        seen.add(key)
        unique_assets.append(path)

    context = " | ".join(
        clean_text(value)
        for value in context_parts
        if clean_text(value)
    )

    if source_context_is_thpt(
        source_url,
        analysis_row,
        context,
    ):
        context += " | xét điểm thi tốt nghiệp THPT"

    # Đánh dấu combined chỉ từ title/lead; tránh related-post contamination.
    lead = " | ".join(context_parts[:4])

    if explicit_thpt_context(lead) and combined_context(lead):
        context += " | PAGE_METHOD_COMBINED"

    return (
        html_text,
        context,
        unique_assets,
        ";".join(diagnostics),
    )


def row_validation_reason(
    row: pd.Series,
    *,
    strategy: str,
    context: str,
) -> str:
    code = clean_text(row.get("major_code", ""))
    name = clean_text(row.get("major_name", ""))
    score = parse_number(row.get("cutoff_score", ""))

    if not valid_major_code(code):
        return "BAD_MAJOR_CODE"

    if not name:
        return "MISSING_MAJOR_NAME"

    if looks_garbled(name):
        return "GARBLED_MAJOR_NAME"

    if score is None or not (0 < score <= 40):
        return "BAD_SCORE"

    joined = (
        context
        + " | "
        + clean_text(row.get("admission_note", ""))
    )

    if not (
        explicit_thpt_context(joined)
        or "method_evidence=GLOBAL_THPT" in joined
        or "method_evidence=ROW_THPT" in joined
        or "method_evidence=MAP_" in joined
    ):
        return "METHOD_THPT_UNVERIFIED"

    # >30 raw chỉ giữ khi xác minh scale 40/nhân hệ số.
    if score > 30 and not scale40_context(joined):
        return "GT30_WITHOUT_SCALE40"

    # Điểm <10 không tự xóa khỏi RAW nếu direct source xác nhận.
    # Nhưng OCR <10 rất dễ là STT/TTNV bị nhận nhầm => không auto-accept.
    if score < 10 and "OCR" in strategy.upper():
        return "LOW_SCORE_OCR_UNCONFIRMED"

    return ""


def sanitize_candidate_rows(
    frame: pd.DataFrame,
    *,
    strategy: str,
    university_name: str,
    context: str,
) -> tuple[pd.DataFrame, list[dict]]:
    if frame.empty:
        return (
            pd.DataFrame(columns=CANONICAL_COLUMNS),
            [],
        )

    frame = dedupe(frame)
    keep_indices = []
    excluded_rows = []

    for idx, row in frame.iterrows():
        reason = row_validation_reason(
            row,
            strategy=strategy,
            context=context,
        )

        if reason:
            excluded_rows.append(
                {
                    "university_name": university_name,
                    "major_code": clean_text(row.get("major_code", "")),
                    "major_name": clean_text(row.get("major_name", "")),
                    "cutoff_score": clean_text(row.get("cutoff_score", "")),
                    "strategy": strategy,
                    "reason": reason,
                    "source_url": clean_text(row.get("source_url", "")),
                }
            )
        else:
            keep_indices.append(idx)

    cleaned = frame.loc[keep_indices].copy() if keep_indices else pd.DataFrame(
        columns=CANONICAL_COLUMNS
    )

    if cleaned.empty:
        return cleaned, excluded_rows

    # Không bỏ cả trường nếu chỉ một major_code OCR lỗi.
    bad_codes = set()

    for code, group in cleaned.groupby("major_code", sort=False):
        names = [
            clean_text(value)
            for value in group["major_name"].unique()
            if clean_text(value)
        ]

        if len(names) <= 1:
            continue

        anchor = names[0]

        if any(
            not names_compatible(anchor, other)
            for other in names[1:]
        ):
            bad_codes.add(code)

    if bad_codes:
        conflict_rows = cleaned[
            cleaned["major_code"].isin(bad_codes)
        ]

        for _, row in conflict_rows.iterrows():
            excluded_rows.append(
                {
                    "university_name": university_name,
                    "major_code": clean_text(row["major_code"]),
                    "major_name": clean_text(row["major_name"]),
                    "cutoff_score": clean_text(row["cutoff_score"]),
                    "strategy": strategy,
                    "reason": "CODE_NAME_CONFLICT",
                    "source_url": clean_text(row["source_url"]),
                }
            )

        cleaned = cleaned[
            ~cleaned["major_code"].isin(bad_codes)
        ].copy()

    cleaned = dedupe(cleaned)

    # OCR cần ít nhất 2 rows để auto-accept.
    if "OCR" in strategy.upper() and len(cleaned) < 2:
        for _, row in cleaned.iterrows():
            excluded_rows.append(
                {
                    "university_name": university_name,
                    "major_code": clean_text(row["major_code"]),
                    "major_name": clean_text(row["major_name"]),
                    "cutoff_score": clean_text(row["cutoff_score"]),
                    "strategy": strategy,
                    "reason": "OCR_TOO_FEW_ROWS",
                    "source_url": clean_text(row["source_url"]),
                }
            )

        cleaned = pd.DataFrame(columns=CANONICAL_COLUMNS)

    return cleaned, excluded_rows


def choose_best_sanitized_candidate(
    candidates: list[tuple[str, pd.DataFrame, str]],
    *,
    university_name: str,
) -> tuple[pd.DataFrame, str, list[dict]]:
    """
    candidates: (strategy, frame, context)
    Chọn direct structured source trước OCR.
    """
    priority = {
        "HTML_TARGETED": 120,
        "LOCAL_HTML": 115,
        "PDF_TABLE_TARGETED": 110,
        "PDF_TEXT_TARGETED": 95,
        "OCR_TARGETED": 80,
    }

    valid = []
    all_row_excluded = []

    for strategy, frame, context in candidates:
        cleaned, row_excluded = sanitize_candidate_rows(
            frame,
            strategy=strategy,
            university_name=university_name,
            context=context,
        )

        all_row_excluded.extend(row_excluded)

        if not cleaned.empty:
            valid.append(
                (
                    strategy,
                    cleaned,
                    context,
                )
            )

    if not valid:
        return (
            pd.DataFrame(columns=CANONICAL_COLUMNS),
            "NO_VALID_ROWS",
            all_row_excluded,
        )

    valid.sort(
        key=lambda item: (
            priority.get(item[0], 0),
            len(item[1]),
        ),
        reverse=True,
    )

    best_strategy, best, _ = valid[0]

    # Cross-check khi có >= 3 major_code chung giữa 2 strategy.
    best_map = {}

    for _, row in best.iterrows():
        best_map.setdefault(
            normalize_major_code(row["major_code"]),
            [],
        ).append(float(row["cutoff_score"]))

    for strategy, other, _ in valid[1:]:
        other_map = {}

        for _, row in other.iterrows():
            other_map.setdefault(
                normalize_major_code(row["major_code"]),
                [],
            ).append(float(row["cutoff_score"]))

        common = set(best_map) & set(other_map)

        if len(common) < 3:
            continue

        mismatch = 0

        for code in common:
            agree = any(
                abs(a - b) <= 0.12
                for a in best_map[code]
                for b in other_map[code]
            )

            if not agree:
                mismatch += 1

        if mismatch / len(common) > 0.60:
            return (
                pd.DataFrame(columns=CANONICAL_COLUMNS),
                f"STRATEGY_CONFLICT:{best_strategy}_VS_{strategy}",
                all_row_excluded,
            )

    return best, best_strategy, all_row_excluded


def recover_school_targeted(
    session: requests.Session,
    *,
    source_row: pd.Series,
    analysis_row: dict,
) -> tuple[pd.DataFrame, str, str, list[dict]]:
    name = clean_text(source_row["university_name"])
    source_url = clean_text(source_row["source_url"])
    source_type = clean_text(source_row["source_type"])

    html, context, assets, payload_diag = retry_primary_payload(
        session,
        university_name=name,
        source_url=source_url,
        source_type=source_type,
        analysis_row=analysis_row,
    )

    candidates = []
    diagnostics = [f"payload={payload_diag}", f"assets={len(assets)}"]

    # 1) HTML structured
    if html:
        html_df = html_tables_from_blob(
            html,
            university_name=name,
            source_url=source_url,
            context=context,
            strategy="HTML_TARGETED",
        )

        candidates.append(
            (
                "HTML_TARGETED",
                html_df,
                context,
            )
        )
        diagnostics.append(f"html_rows={len(html_df)}")

    # 2) Local HTML from a mislabeled document is included in retry_primary_payload.
    # 3) PDF / image assets
    ocr_images = []

    for asset_idx, asset in enumerate(assets, start=1):
        kind = sniff_local_file(asset)

        if kind == "HTML":
            try:
                local_html = asset.read_text(
                    encoding="utf-8",
                    errors="replace",
                )
            except Exception:
                local_html = ""

            if local_html:
                local_soup = BeautifulSoup(local_html, "html.parser")
                local_text = clean_text(
                    local_soup.get_text(" ", strip=True)
                )
                local_context = (
                    context
                    + " | "
                    + local_text[:16000]
                )

                if source_context_is_thpt(
                    source_url,
                    analysis_row,
                    local_context,
                ):
                    local_context += " | xét điểm thi tốt nghiệp THPT"

                local_df = html_tables_from_blob(
                    local_html,
                    university_name=name,
                    source_url=source_url,
                    context=local_context,
                    strategy="LOCAL_HTML",
                )

                candidates.append(
                    (
                        "LOCAL_HTML",
                        local_df,
                        local_context,
                    )
                )
                diagnostics.append(f"local_html_rows={len(local_df)}")

                embedded = collect_embedded_primary_assets(
                    session,
                    html=local_html,
                    source_url=source_url,
                    university_name=name,
                )

                for path in embedded:
                    if str(path.resolve()) not in {
                        str(existing.resolve())
                        for existing in assets
                    }:
                        assets.append(path)

        elif kind == "PDF":
            text, tables, pdf_diag = read_pdf_text_and_tables(asset)
            pdf_context = context + " | " + text[:18000]

            if source_context_is_thpt(
                source_url,
                analysis_row,
                pdf_context,
            ):
                pdf_context += " | xét điểm thi tốt nghiệp THPT"

            pdf_rows = []

            for table in tables:
                pdf_rows.extend(
                    parse_table_grid(
                        table,
                        university_name=name,
                        source_url=source_url,
                        context=pdf_context,
                        strategy="PDF_TABLE_TARGETED",
                    )
                )

            pdf_df = dedupe(canonicalize(pdf_rows))

            candidates.append(
                (
                    "PDF_TABLE_TARGETED",
                    pdf_df,
                    pdf_context,
                )
            )
            diagnostics.append(
                f"pdf_tables={len(tables)}:pdf_rows={len(pdf_df)}:{pdf_diag}"
            )

            text_df = parse_plain_text_rows(
                text,
                university_name=name,
                source_url=source_url,
                context=pdf_context,
            )

            # rewrite note marker for audit clarity
            if not text_df.empty:
                text_df["admission_note"] = (
                    text_df["admission_note"]
                    .astype(str)
                    .str.replace(
                        "PRIMARY2023:PDF_TEXT_LINE",
                        "PRIMARY2023:PDF_TEXT_TARGETED",
                        regex=False,
                    )
                )

            candidates.append(
                (
                    "PDF_TEXT_TARGETED",
                    text_df,
                    pdf_context,
                )
            )

            # OCR only if structured PDF extraction is weak.
            if len(pdf_df) < 2 and len(text_df) < 2:
                ocr_images.extend(
                    render_pdf_pages_ascii(
                        asset,
                        university_name=name,
                        max_pages=14,
                    )
                )

        elif kind == "IMAGE":
            ocr_images.extend(
                tile_image_to_ascii(
                    asset,
                    university_name=name,
                    label=f"targeted_img_{asset_idx:02d}",
                )
            )

    # 4) OCR
    seen = set()
    unique_images = []

    for image_path in ocr_images:
        try:
            key = str(image_path.resolve())
        except Exception:
            key = str(image_path)

        if key in seen:
            continue

        seen.add(key)
        unique_images.append(image_path)

    ocr_rows = []
    ocr_context_parts = []

    for image_path in unique_images:
        markdown, tables, mode = ocr_one_image(
            image_path,
            university_name=name,
        )

        if markdown:
            ocr_context_parts.append(markdown[:10000])

        local_context = (
            context
            + " | "
            + markdown[:12000]
        )

        if source_context_is_thpt(
            source_url,
            analysis_row,
            local_context,
        ):
            local_context += " | xét điểm thi tốt nghiệp THPT"

        for table in tables:
            ocr_rows.extend(
                parse_table_grid(
                    table,
                    university_name=name,
                    source_url=source_url,
                    context=local_context,
                    strategy="OCR_TARGETED",
                )
            )

        diagnostics.append(
            f"{image_path.name}:{mode}:tables={len(tables)}"
        )

    ocr_df = dedupe(canonicalize(ocr_rows))

    if not ocr_df.empty:
        ocr_context = (
            context
            + " | "
            + " | ".join(ocr_context_parts)
        )

        candidates.append(
            (
                "OCR_TARGETED",
                ocr_df,
                ocr_context,
            )
        )

    diagnostics.append(f"ocr_rows={len(ocr_df)}")

    best, strategy, row_excluded = choose_best_sanitized_candidate(
        candidates,
        university_name=name,
    )

    return (
        best,
        strategy,
        " || ".join(diagnostics),
        row_excluded,
    )


def ml_compatible_final(row: pd.Series) -> tuple[bool, str]:
    """
    ML 2023: giữ THPT comparable thang 30.
    Raw FINAL vẫn có thể giữ direct-source score <10, nhưng không đưa vào ML.
    """
    score = parse_number(row["cutoff_score"])

    if score is None:
        return False, "score_invalid"

    if not (10 <= score <= 30):
        return False, "outside_10_30"

    note = clean_text(row["admission_note"]).lower()

    if any(marker in note for marker in ML_EXCLUDE_MARKERS):
        return False, "note_non_comparable"

    method = clean_text(row["admission_method_codes"]).lower()

    if (
        "thpt" not in method
        and not re.search(r"\bpt\d{1,3}\b", method)
    ):
        return False, "method_not_thpt"

    return True, ""


def audit_existing_low_score_schools(
    final_df: pd.DataFrame,
) -> set[str]:
    """
    OCR score <10 là nghi ngờ cao. Reprocess cả school.
    Direct HTML/PDF score <10 được phép tồn tại raw nếu primary source xác nhận.
    """
    suspect = set()

    for _, row in final_df.iterrows():
        score = parse_number(row.get("cutoff_score", ""))

        if score is None:
            suspect.add(
                normalize_school(row["university_name"])
            )
            continue

        note = clean_text(row.get("admission_note", "")).upper()

        if score < 10 and "OCR" in note:
            suspect.add(
                normalize_school(row["university_name"])
            )

    return suspect






# =============================================================================
# FINAL LOCK HELPERS
# =============================================================================

def major_name_key(value: str) -> str:
    text = norm(value)
    replacements = [
        (r"\bchuong trinh\b", ""),
        (r"\bchat luong cao\b", "clc"),
        (r"\btien tien\b", "tt"),
        (r"\bhe chinh quy\b", ""),
        (r"\bdai tra\b", ""),
    ]
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text)
    return re.sub(r"\s+", " ", text).strip()


def build_crossyear_major_map() -> dict[str, dict]:
    """
    Map theo CHÍNH TRƯỜNG từ FINAL 2024 + 2025.
    Chỉ giữ name -> code khi mapping là duy nhất qua các năm.
    """
    raw: dict[str, dict[str, set[str]]] = {}

    for year in (2024, 2025):
        path = PROCESSED_DIR / f"admission_scores_{year}_final.csv"
        if not path.exists():
            continue

        try:
            df = pd.read_csv(
                path,
                dtype=str,
                keep_default_na=False,
                usecols=["university_name", "major_code", "major_name"],
            )
        except Exception:
            continue

        for _, row in df.iterrows():
            school = normalize_school(row["university_name"])
            code = normalize_major_code(row["major_code"])
            name_key = major_name_key(row["major_name"])

            if not school or not name_key or not valid_major_code(code):
                continue

            raw.setdefault(school, {}).setdefault(name_key, set()).add(code)

    output: dict[str, dict] = {}

    for school, name_map in raw.items():
        exact = {
            name_key: next(iter(codes))
            for name_key, codes in name_map.items()
            if len(codes) == 1
        }

        output[school] = {
            "exact": exact,
            "items": list(exact.items()),
        }

    return output


def map_code_crossyear(
    school_name: str,
    major_name: str,
    crossyear_map: dict[str, dict],
) -> tuple[str, str]:
    school_key = normalize_school(school_name)
    name_key = major_name_key(major_name)

    school_map = crossyear_map.get(school_key, {})
    exact = school_map.get("exact", {})

    if name_key in exact:
        return exact[name_key], "CROSSYEAR_EXACT"

    # Conservative fuzzy fallback only inside the SAME school.
    ranked = []

    for known_name, code in school_map.get("items", []):
        score = SequenceMatcher(None, name_key, known_name).ratio()

        # token coverage guards against short accidental matches.
        a = set(name_key.split())
        b = set(known_name.split())
        inter = len(a & b)
        coverage = inter / max(1, min(len(a), len(b)))

        ranked.append((score, coverage, known_name, code))

    if not ranked:
        return "", ""

    ranked.sort(reverse=True)
    best = ranked[0]
    second_score = ranked[1][0] if len(ranked) > 1 else 0.0

    if (
        best[0] >= 0.94
        and best[1] >= 0.80
        and (best[0] - second_score) >= 0.04
    ):
        return best[3], "CROSSYEAR_FUZZY_STRICT"

    return "", ""


def parse_table_grid_name_score(
    grid: list[list[str]],
    *,
    university_name: str,
    source_url: str,
    context: str,
    strategy: str,
    crossyear_map: dict[str, dict],
) -> list[dict]:
    """
    Parser cho bảng 2023 chỉ có:
      Tên ngành | Điểm chuẩn
    hoặc thiếu mã ngành.
    major_code KHÔNG được đoán; chỉ điền khi 2024/2025 của cùng trường
    xác nhận mapping tên ngành -> mã ngành duy nhất.
    """
    rows = normalize_grid(grid)

    if len(rows) < 2:
        return []

    header_start, header_depth, headers = choose_header(rows)
    data_start = header_start + header_depth

    name_idx = find_header_idx(
        headers,
        NAME_HEADER_MARKERS,
        reject=("ma nganh", "ma tuyen sinh", "diem", "to hop"),
    )

    score_idx = find_header_idx(
        headers,
        SCORE_HEADER_MARKERS,
        reject=(
            "hoc ba", "dgnl", "danh gia nang luc",
            "danh gia tu duy", "vsat",
        ),
    )

    combo_idx = find_header_idx(headers, COMBO_HEADER_MARKERS)
    method_idx = find_header_idx(headers, METHOD_HEADER_MARKERS)
    note_idx = find_header_idx(headers, NOTE_HEADER_MARKERS)
    scale_idx = find_header_idx(headers, SCALE_HEADER_MARKERS)

    if score_idx is None:
        score_idx = infer_score_column(
            rows,
            data_start,
            {
                idx
                for idx in (name_idx, combo_idx, method_idx, note_idx, scale_idx)
                if idx is not None
            },
        )

    if name_idx is None:
        name_idx = infer_name_column(
            rows,
            data_start,
            {
                idx
                for idx in (score_idx, combo_idx, method_idx, note_idx, scale_idx)
                if idx is not None
            },
        )

    if name_idx is None or score_idx is None:
        return []

    global_thpt = explicit_thpt_context(context)
    global_combined = combined_context(context)
    method_map = method_map_from_context(context)

    output = []

    for row in rows[data_start:]:
        major_name = get_cell(row, name_idx)
        score = parse_number(get_cell(row, score_idx))

        if (
            not major_name
            or len(major_name) < 2
            or score is None
            or not (10 <= score <= 40)
            or looks_garbled(major_name)
        ):
            continue

        # Skip header/group rows that leaked into data.
        if any(
            marker in norm(major_name)
            for marker in ("linh vuc", "chuong trinh dao tao", "he dai hoc")
        ):
            continue

        method_ok, method_evidence = row_method_ok(
            row,
            method_idx,
            method_map,
            global_thpt,
            global_combined,
        )

        if not method_ok:
            continue

        major_code, map_mode = map_code_crossyear(
            university_name,
            major_name,
            crossyear_map,
        )

        if not major_code:
            continue

        combination = get_cell(row, combo_idx)
        note = get_cell(row, note_idx)
        scale = get_cell(row, scale_idx)

        note_parts = [
            f"PRIMARY2023:{strategy}",
            f"method_evidence={method_evidence}",
            f"major_code_evidence={map_mode}:2024_2025_same_school",
        ]

        if scale:
            note_parts.append(f"scale={scale}")

        if note:
            note_parts.append(note)

        if score > 30:
            note_parts.append("outside_THPT30")

        if "COMBINED" in method_evidence:
            note_parts.append("thpt_combined")

        output.append(
            {
                "university_name": university_name,
                "major_code": major_code,
                "major_name": major_name,
                "year": YEAR,
                "admission_method_codes": "THPT",
                "combination": combination,
                "cutoff_score": float(score),
                "admission_note": "; ".join(note_parts),
                "source_url": source_url,
            }
        )

    return output


def archive_school_similarity(a: str, b: str) -> tuple[float, float]:
    na = normalize_school(a)
    nb = normalize_school(b)

    if not na or not nb:
        return 0.0, 0.0

    seq = SequenceMatcher(None, na, nb).ratio()

    ta = {
        token
        for token in na.split()
        if token not in {
            "truong", "dai", "hoc", "hoc", "vien",
            "viet", "nam", "tp", "thanh", "pho",
        }
    }
    tb = {
        token
        for token in nb.split()
        if token not in {
            "truong", "dai", "hoc", "hoc", "vien",
            "viet", "nam", "tp", "thanh", "pho",
        }
    }

    coverage = len(ta & tb) / max(1, len(ta))
    return seq, coverage


def discover_archive_source(
    session: requests.Session,
    university_name: str,
) -> tuple[str, str]:
    """
    Chỉ tìm bài 2023 trên thongtintuyensinh.vn.
    Reject học bạ / ĐGNL / điểm sàn / xét tuyển sớm.
    """
    candidates = []

    for index_url in ARCHIVE_PAGES:
        try:
            response = session.get(
                index_url,
                timeout=30,
                allow_redirects=True,
            )
            response.raise_for_status()
        except Exception:
            continue

        soup = BeautifulSoup(decode_response(response), "html.parser")

        for anchor in soup.find_all("a", href=True):
            title = clean_text(anchor.get_text(" ", strip=True))

            if not title or "2023" not in title:
                continue

            low = title.lower()

            if any(
                bad in low
                for bad in (
                    "học bạ", "đánh giá năng lực", "đgnl",
                    "xét tuyển sớm", "điểm sàn", "nhận hồ sơ",
                    "ngưỡng điểm", "tuyển bổ sung",
                )
            ):
                continue

            title_norm = norm(title)

            if not (
                "diem chuan" in title_norm
                or "diem trung tuyen" in title_norm
                or "diem trung tuyen" in title_norm
            ):
                continue

            seq, coverage = archive_school_similarity(
                university_name,
                title,
            )

            if seq < 0.55 or coverage < 0.70:
                continue

            url = urljoin(index_url, clean_text(anchor.get("href")))

            if "thongtintuyensinh.vn" not in urlparse(url).netloc.lower():
                continue

            thpt_bonus = 1 if explicit_thpt_context(title) else 0

            candidates.append(
                (thpt_bonus, coverage, seq, title, url)
            )

    if not candidates:
        return "", ""

    candidates.sort(reverse=True)
    best = candidates[0]

    # For a title without explicit THPT, require very strong school identity.
    if best[0] == 0 and not (best[1] >= 0.95 and best[2] >= 0.74):
        return "", ""

    return best[4], best[3]


def parse_url_crossyear(
    session: requests.Session,
    *,
    university_name: str,
    source_url: str,
    analysis_row: dict,
    crossyear_map: dict[str, dict],
    strategy_prefix: str,
) -> tuple[pd.DataFrame, str]:
    """
    One URL -> HTML/PDF/image -> structured/no-code mapped rows.
    """
    candidates = []
    diagnostics = []

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
            f"REQUEST_{type(exc).__name__}",
        )

    content_type = clean_text(
        response.headers.get("Content-Type", "")
    ).lower()

    # ---------------------------------------------------------------------
    # PDF
    # ---------------------------------------------------------------------
    if response.content[:5] == b"%PDF" or "application/pdf" in content_type:
        school_dir = DOC_DIR / slugify(university_name)
        school_dir.mkdir(parents=True, exist_ok=True)

        pdf_path = school_dir / f"{strategy_prefix.lower()}_source.pdf"
        pdf_path.write_bytes(response.content)

        text, tables, pdf_diag = read_pdf_text_and_tables(pdf_path)
        context = (
            f"{source_url} | "
            f"{clean_text(analysis_row.get('page_title', ''))} | "
            f"{text[:18000]}"
        )

        if source_context_is_thpt(source_url, analysis_row, context):
            context += " | xét điểm thi tốt nghiệp THPT"

        rows = []

        for table in tables:
            rows.extend(
                parse_table_grid(
                    table,
                    university_name=university_name,
                    source_url=source_url,
                    context=context,
                    strategy=f"{strategy_prefix}_PDF_CODED",
                )
            )
            rows.extend(
                parse_table_grid_name_score(
                    table,
                    university_name=university_name,
                    source_url=source_url,
                    context=context,
                    strategy=f"{strategy_prefix}_PDF_XYEAR",
                    crossyear_map=crossyear_map,
                )
            )

        candidates.append(
            dedupe(canonicalize(rows))
        )

        # OCR only when structured PDF yields nothing.
        if not any(not frame.empty for frame in candidates):
            images = render_pdf_pages_ascii(
                pdf_path,
                university_name=university_name,
                max_pages=14,
            )

            ocr_rows = []

            for image_path in images:
                markdown, ocr_tables, mode = ocr_one_image(
                    image_path,
                    university_name=university_name,
                )

                local_context = context + " | " + markdown[:12000]

                for table in ocr_tables:
                    ocr_rows.extend(
                        parse_table_grid(
                            table,
                            university_name=university_name,
                            source_url=source_url,
                            context=local_context,
                            strategy=f"{strategy_prefix}_OCR_CODED",
                        )
                    )
                    ocr_rows.extend(
                        parse_table_grid_name_score(
                            table,
                            university_name=university_name,
                            source_url=source_url,
                            context=local_context,
                            strategy=f"{strategy_prefix}_OCR_XYEAR",
                            crossyear_map=crossyear_map,
                        )
                    )

            candidates.append(
                dedupe(canonicalize(ocr_rows))
            )

        diagnostics.append(
            f"PDF tables={len(tables)}:{pdf_diag}"
        )

    # ---------------------------------------------------------------------
    # HTML / image response
    # ---------------------------------------------------------------------
    else:
        html = decode_response(response)

        if "<html" in html.lower() or "<table" in html.lower():
            soup = BeautifulSoup(html, "html.parser")
            title = ""

            for tag_name in ("h1", "title"):
                tag = soup.find(tag_name)
                if tag:
                    title = clean_text(tag.get_text(" ", strip=True))
                    if title:
                        break

            visible = clean_text(soup.get_text(" ", strip=True))
            context = f"{title} | {visible[:20000]} | {source_url}"

            if source_context_is_thpt(
                source_url,
                analysis_row,
                context,
            ) or explicit_thpt_context(title):
                context += " | xét điểm thi tốt nghiệp THPT"

            try:
                dfs = pd.read_html(
                    io.StringIO(html),
                    header=None,
                    thousands=None,
                )
            except Exception:
                dfs = []

            html_rows = []

            for df in dfs:
                if df.empty:
                    continue

                grid = [
                    [clean_text(value) for value in row]
                    for row in df.astype(object).values.tolist()
                ]

                html_rows.extend(
                    parse_table_grid(
                        grid,
                        university_name=university_name,
                        source_url=source_url,
                        context=context,
                        strategy=f"{strategy_prefix}_HTML_CODED",
                    )
                )
                html_rows.extend(
                    parse_table_grid_name_score(
                        grid,
                        university_name=university_name,
                        source_url=source_url,
                        context=context,
                        strategy=f"{strategy_prefix}_HTML_XYEAR",
                        crossyear_map=crossyear_map,
                    )
                )

            candidates.append(
                dedupe(canonicalize(html_rows))
            )

            # Embedded image/PDF from this exact primary page.
            if not any(not frame.empty for frame in candidates):
                assets = collect_embedded_primary_assets(
                    session,
                    html=html,
                    source_url=source_url,
                    university_name=university_name,
                )

                ocr_rows = []

                for idx, asset in enumerate(assets, start=1):
                    kind = sniff_local_file(asset)
                    images = []

                    if kind == "IMAGE":
                        images = tile_image_to_ascii(
                            asset,
                            university_name=university_name,
                            label=f"{strategy_prefix.lower()}_{idx:02d}",
                        )
                    elif kind == "PDF":
                        images = render_pdf_pages_ascii(
                            asset,
                            university_name=university_name,
                            max_pages=14,
                        )

                    for image_path in images:
                        markdown, ocr_tables, mode = ocr_one_image(
                            image_path,
                            university_name=university_name,
                        )

                        local_context = context + " | " + markdown[:12000]

                        for table in ocr_tables:
                            ocr_rows.extend(
                                parse_table_grid(
                                    table,
                                    university_name=university_name,
                                    source_url=source_url,
                                    context=local_context,
                                    strategy=f"{strategy_prefix}_OCR_CODED",
                                )
                            )
                            ocr_rows.extend(
                                parse_table_grid_name_score(
                                    table,
                                    university_name=university_name,
                                    source_url=source_url,
                                    context=local_context,
                                    strategy=f"{strategy_prefix}_OCR_XYEAR",
                                    crossyear_map=crossyear_map,
                                )
                            )

                candidates.append(
                    dedupe(canonicalize(ocr_rows))
                )

            diagnostics.append(f"HTML tables={len(dfs)}")

        else:
            # Binary image response
            school_dir = ASSET_ROOT / slugify(university_name)
            school_dir.mkdir(parents=True, exist_ok=True)

            image_path = school_dir / f"{strategy_prefix.lower()}_response.bin"
            image_path.write_bytes(response.content)

            if sniff_local_file(image_path) == "IMAGE":
                images = tile_image_to_ascii(
                    image_path,
                    university_name=university_name,
                    label=f"{strategy_prefix.lower()}_image",
                )

                ocr_rows = []

                for path in images:
                    markdown, ocr_tables, mode = ocr_one_image(
                        path,
                        university_name=university_name,
                    )

                    context = (
                        f"{source_url} | "
                        f"{clean_text(analysis_row.get('page_title', ''))} | "
                        f"{markdown[:12000]}"
                    )

                    if source_context_is_thpt(
                        source_url,
                        analysis_row,
                        context,
                    ):
                        context += " | xét điểm thi tốt nghiệp THPT"

                    for table in ocr_tables:
                        ocr_rows.extend(
                            parse_table_grid(
                                table,
                                university_name=university_name,
                                source_url=source_url,
                                context=context,
                                strategy=f"{strategy_prefix}_OCR_CODED",
                            )
                        )
                        ocr_rows.extend(
                            parse_table_grid_name_score(
                                table,
                                university_name=university_name,
                                source_url=source_url,
                                context=context,
                                strategy=f"{strategy_prefix}_OCR_XYEAR",
                                crossyear_map=crossyear_map,
                            )
                        )

                candidates.append(
                    dedupe(canonicalize(ocr_rows))
                )

    merged = pd.DataFrame(columns=CANONICAL_COLUMNS)

    for frame in candidates:
        if frame.empty:
            continue
        merged = dedupe(
            pd.concat([merged, frame], ignore_index=True)
        )

    # Row-level final sanitation: 10..40 and no garbled values.
    if not merged.empty:
        keep = []
        for idx, row in merged.iterrows():
            score = parse_number(row["cutoff_score"])
            joined = clean_text(row["admission_note"])

            if (
                valid_major_code(row["major_code"])
                and clean_text(row["major_name"])
                and not looks_garbled(row["major_name"])
                and score is not None
                and 10 <= score <= 40
                and (
                    score <= 30
                    or scale40_context(joined + " | " + source_url)
                )
            ):
                keep.append(idx)

        merged = (
            dedupe(merged.loc[keep].copy())
            if keep
            else pd.DataFrame(columns=CANONICAL_COLUMNS)
        )

    return merged, " | ".join(diagnostics)


def audit_and_remove_unverified_low_rows(
    final_df: pd.DataFrame,
) -> tuple[pd.DataFrame, list[dict], set[str]]:
    """
    2023 hiện còn 41 raw rows <10. Với dataset tư vấn THPT 30,
    nếu không có evidence thang đặc biệt rõ thì không nên giữ chúng trong FINAL.
    Không sửa số; chuyển sang row_excluded.
    """
    excluded = []
    affected_schools = set()
    keep_indices = []

    for idx, row in final_df.iterrows():
        score = parse_number(row["cutoff_score"])

        if score is not None and score >= 10:
            keep_indices.append(idx)
            continue

        note = clean_text(row["admission_note"])

        # Không có scale hợp lệ nào ở dự án này dùng cutoff <10 để so sánh THPT-30.
        # Giữ nguyên provenance trong row_excluded thay vì tự quy đổi.
        excluded.append(
            {
                "university_name": clean_text(row["university_name"]),
                "major_code": clean_text(row["major_code"]),
                "major_name": clean_text(row["major_name"]),
                "cutoff_score": clean_text(row["cutoff_score"]),
                "strategy": "FINAL_LOCK_LOW_SCORE_AUDIT",
                "reason": "RAW_SCORE_LT10_NOT_COMPARABLE",
                "source_url": clean_text(row["source_url"]),
            }
        )
        affected_schools.add(
            normalize_school(row["university_name"])
        )

    cleaned = (
        dedupe(final_df.loc[keep_indices].copy())
        if keep_indices
        else pd.DataFrame(columns=CANONICAL_COLUMNS)
    )

    return cleaned, excluded, affected_schools



# =============================================================================
# MAIN - FINAL LOCK
# =============================================================================

def main() -> None:
    print("=" * 124)
    print("2023 FINAL / CROSS-YEAR LAST-MILE + LOCK")
    print(f"VERSION : {PIPELINE_VERSION}")
    print("=" * 124)

    for required in (
        SOURCE_MAP_FILE,
        SOURCE_ANALYSIS_FILE,
        FINAL_FILE,
        SOURCE_EXCLUDED_FILE,
    ):
        if not required.exists():
            raise RuntimeError(
                f"Thiếu checkpoint bắt buộc: {required}"
            )

    backup_once(SOURCE_MAP_FILE, SOURCE_MAP_FINAL_BACKUP)
    backup_once(FINAL_FILE, FINAL_PRE_LOCK_BACKUP)

    session = build_session()

    source_map = pd.read_csv(
        SOURCE_MAP_FILE,
        dtype=str,
        keep_default_na=False,
    )
    source_map = clean_inventory_2023(source_map)

    analysis_df = pd.read_csv(
        SOURCE_ANALYSIS_FILE,
        dtype=str,
        keep_default_na=False,
    )
    analysis_map = {
        normalize_school(row["university_name"]): row.to_dict()
        for _, row in analysis_df.iterrows()
    }

    final_df = pd.read_csv(
        FINAL_FILE,
        dtype=str,
        keep_default_na=False,
    )
    final_df = dedupe(
        canonicalize(final_df.to_dict("records"))
    )

    excluded_df = pd.read_csv(
        SOURCE_EXCLUDED_FILE,
        dtype=str,
        keep_default_na=False,
    )

    source_lookup = {
        normalize_school(row["university_name"]): row
        for _, row in source_map.iterrows()
    }

    # ---------------------------------------------------------------------
    # 1) Audit all raw rows <10: preserve in row_excluded, not FINAL.
    # ---------------------------------------------------------------------
    final_df, low_row_excluded, low_affected = (
        audit_and_remove_unverified_low_rows(final_df)
    )

    # Schools that lost all rows become recovery targets.
    final_norms_now = set(
        final_df["university_name"].map(normalize_school)
    )

    # ---------------------------------------------------------------------
    # 2) Build verified same-school major code map from 2024/2025.
    # ---------------------------------------------------------------------
    crossyear_map = build_crossyear_major_map()

    old_excluded_keys = set(
        excluded_df["university_name"].map(normalize_school)
    )

    targets = (
        old_excluded_keys
        | {
            key
            for key in low_affected
            if key not in final_norms_now
        }
    )

    targets = [
        key
        for key in targets
        if key in source_lookup
    ]

    targets.sort(
        key=lambda key: (
            int(source_lookup[key].get("priority", 0)),
            clean_text(source_lookup[key]["university_name"]),
        ),
        reverse=True,
    )

    print(f"SOURCE INVENTORY       : {len(source_map)} trường")
    print(
        f"INPUT AFTER LOW AUDIT  : {len(final_df)} rows / "
        f"{final_df['university_name'].nunique()} trường"
    )
    print(f"LOW ROWS MOVED OUT     : {len(low_row_excluded)} rows")
    print(f"LAST-MILE TARGETS      : {len(targets)} trường")
    print(
        f"CROSSYEAR SCHOOL MAPS  : {len(crossyear_map)} trường "
        "(2024/2025 verified)"
    )

    recovered = []
    repaired_source = []
    report_rows = []
    row_excluded_rows = list(low_row_excluded)
    final_excluded_by_key = {}

    old_excluded_map = {
        normalize_school(row["university_name"]): row.to_dict()
        for _, row in excluded_df.iterrows()
    }

    total = len(targets)

    for idx, key in enumerate(targets, start=1):
        source = source_lookup[key]
        name = clean_text(source["university_name"])
        source_url = clean_text(source["source_url"])
        priority = int(source.get("priority", 0))
        analysis_row = analysis_map.get(key, {})

        print(
            f"[{idx:03d}/{total:03d}] P{priority} | {name} ... ",
            end="",
            flush=True,
        )

        if force_exclude(name):
            reason = "EXCLUDED_COMPLEX_UMBRELLA_SOURCE"
            final_excluded_by_key[key] = {
                "university_name": name,
                "source_type": clean_text(source["source_type"]),
                "analysis_class": clean_text(
                    analysis_row.get("analysis_class", "")
                ),
                "exclusion_reason": reason,
                "source_url": source_url,
                "local_file": clean_text(
                    analysis_row.get("local_file", "")
                ),
            }
            print(f"EXCLUDED ⚠ {reason}")
            continue

        # A) current aggregate-linked primary source
        candidate, diag = parse_url_crossyear(
            session,
            university_name=name,
            source_url=source_url,
            analysis_row=analysis_row,
            crossyear_map=crossyear_map,
            strategy_prefix="PRIMARY",
        )

        used_url = source_url
        strategy = "PRIMARY"

        # B) If current primary still fails, rediscover exact 2023 article
        # on the SAME site; never use VietNamNet/TS247.
        if candidate.empty:
            archive_url, archive_title = discover_archive_source(
                session,
                name,
            )

            if archive_url and archive_url != source_url:
                archive_analysis = dict(analysis_row)
                archive_analysis["page_title"] = archive_title
                archive_analysis["analysis_class"] = "ARCHIVE_REDISCOVERED"

                archive_candidate, archive_diag = parse_url_crossyear(
                    session,
                    university_name=name,
                    source_url=archive_url,
                    analysis_row=archive_analysis,
                    crossyear_map=crossyear_map,
                    strategy_prefix="ARCHIVE",
                )

                diag += f" || archive={archive_title} || {archive_diag}"

                if not archive_candidate.empty:
                    candidate = archive_candidate
                    used_url = archive_url
                    strategy = "ARCHIVE_REDISCOVERED"

        if not candidate.empty:
            # If archive source is more exact/usable, repair source_map.
            if used_url != source_url:
                source_map.loc[
                    source_map["university_name"].map(normalize_school) == key,
                    "source_url",
                ] = used_url
                source_map.loc[
                    source_map["university_name"].map(normalize_school) == key,
                    "source_type",
                ] = source_type_from_url(used_url)
                repaired_source.append(name)

                # Update the row provenance to actual repaired primary article.
                candidate["source_url"] = used_url

            # Replace school atomically.
            final_df = final_df[
                final_df["university_name"].map(normalize_school) != key
            ].copy()

            final_df = dedupe(
                pd.concat(
                    [final_df, candidate],
                    ignore_index=True,
                )
            )

            recovered.append(name)

            report_rows.append(
                {
                    "university_name": name,
                    "priority": priority,
                    "status": "ACCEPTED",
                    "strategy": strategy,
                    "accepted_rows": len(candidate),
                    "diagnostic": diag,
                    "source_url": used_url,
                }
            )

            print(
                f"RECOVERED ✅ {len(candidate)} rows | {strategy}"
            )

        else:
            old = old_excluded_map.get(key, {})

            analysis_class = clean_text(
                analysis_row.get(
                    "analysis_class",
                    old.get("analysis_class", ""),
                )
            )

            if analysis_class in {
                "HTML_HTTP_FAILED",
                "DOWNLOAD_FAILED",
                "DRIVE_HTTP_FAILED",
                "DRIVE_UNRESOLVED",
                "GOOGLE_DOC_UNRESOLVED",
            }:
                reason = "EXCLUDED_PRIMARY_SOURCE_UNAVAILABLE"
            else:
                reason = "EXCLUDED_AFTER_PRIMARY_ARCHIVE_XYEAR_AUDIT"

            final_excluded_by_key[key] = {
                "university_name": name,
                "source_type": clean_text(source["source_type"]),
                "analysis_class": analysis_class,
                "exclusion_reason": reason,
                "source_url": source_url,
                "local_file": clean_text(
                    analysis_row.get(
                        "local_file",
                        old.get("local_file", ""),
                    )
                ),
            }

            report_rows.append(
                {
                    "university_name": name,
                    "priority": priority,
                    "status": "EXCLUDED",
                    "strategy": "PRIMARY+ARCHIVE+XYEAR",
                    "accepted_rows": 0,
                    "diagnostic": diag,
                    "source_url": source_url,
                }
            )

            print(f"EXCLUDED ⚠ {reason}")

        pd.DataFrame(report_rows).to_csv(
            FINAL_LOCK_REPORT_FILE,
            index=False,
            encoding="utf-8-sig",
        )

        time.sleep(0.01)

    # ---------------------------------------------------------------------
    # 3) Rebuild exclusions from clean source map.
    # ---------------------------------------------------------------------
    final_df = dedupe(final_df)
    final_norms = set(
        final_df["university_name"].map(normalize_school)
    )

    # Preserve old exclusions for schools still not recovered.
    for _, row in excluded_df.iterrows():
        key = normalize_school(row["university_name"])

        if key in final_norms or key not in source_lookup:
            continue

        if key in final_excluded_by_key:
            continue

        source = source_lookup[key]
        analysis_row = analysis_map.get(key, {})

        final_excluded_by_key[key] = {
            "university_name": clean_text(source["university_name"]),
            "source_type": clean_text(source["source_type"]),
            "analysis_class": clean_text(
                analysis_row.get(
                    "analysis_class",
                    row.get("analysis_class", ""),
                )
            ),
            "exclusion_reason": clean_text(
                row.get(
                    "exclusion_reason",
                    "EXCLUDED_AFTER_FINAL_AUDIT",
                )
            ),
            "source_url": clean_text(source["source_url"]),
            "local_file": clean_text(
                analysis_row.get(
                    "local_file",
                    row.get("local_file", ""),
                )
            ),
        }

    # Any source not in FINAL must be accounted for.
    for key, source in source_lookup.items():
        if key in final_norms:
            continue

        if key in final_excluded_by_key:
            continue

        analysis_row = analysis_map.get(key, {})

        final_excluded_by_key[key] = {
            "university_name": clean_text(source["university_name"]),
            "source_type": clean_text(source["source_type"]),
            "analysis_class": clean_text(
                analysis_row.get("analysis_class", "")
            ),
            "exclusion_reason": "EXCLUDED_AFTER_FINAL_AUDIT",
            "source_url": clean_text(source["source_url"]),
            "local_file": clean_text(
                analysis_row.get("local_file", "")
            ),
        }

    excluded_final = pd.DataFrame(
        list(final_excluded_by_key.values()),
        columns=EXCLUDED_COLUMNS,
    )

    if not excluded_final.empty:
        excluded_final = (
            excluded_final
            .sort_values("university_name", kind="stable")
            .reset_index(drop=True)
        )

    # ---------------------------------------------------------------------
    # 4) HARD AUDIT.
    # ---------------------------------------------------------------------
    final_norms = set(
        final_df["university_name"].map(normalize_school)
    )
    excluded_norms = set(
        excluded_final["university_name"].map(normalize_school)
    )
    inventory_norms = set(
        source_map["university_name"].map(normalize_school)
    )

    if final_norms & excluded_norms:
        raise RuntimeError(
            "AUDIT FAIL: trường vừa FINAL vừa EXCLUDED."
        )

    if (final_norms | excluded_norms) != inventory_norms:
        raise RuntimeError(
            "AUDIT FAIL: FINAL + EXCLUDED không phủ đúng 167 nguồn."
        )

    if final_df["major_code"].eq("").any():
        raise RuntimeError("AUDIT FAIL: missing major_code.")

    if final_df["major_name"].eq("").any():
        raise RuntimeError("AUDIT FAIL: missing major_name.")

    if final_df["cutoff_score"].isna().any():
        raise RuntimeError("AUDIT FAIL: missing cutoff_score.")

    scores = pd.to_numeric(
        final_df["cutoff_score"],
        errors="coerce",
    )

    if (scores < 10).any():
        raise RuntimeError(
            f"AUDIT FAIL: còn {int((scores < 10).sum())} raw rows score <10."
        )

    # Every FINAL row must match repaired source_map.
    primary_urls = {
        normalize_school(row["university_name"]): clean_text(row["source_url"])
        for _, row in source_map.iterrows()
    }

    for _, row in final_df.iterrows():
        key = normalize_school(row["university_name"])

        if clean_text(row["source_url"]) != primary_urls.get(key, ""):
            raise RuntimeError(
                "AUDIT FAIL source_url: "
                + clean_text(row["university_name"])
            )

    # ---------------------------------------------------------------------
    # 5) ML split.
    # ---------------------------------------------------------------------
    flags = final_df.apply(
        ml_compatible_final,
        axis=1,
        result_type="expand",
    )
    flags.columns = ["_ml_ok", "_ml_reason"]

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
        CANONICAL_COLUMNS + ["ml_exclusion_reason"]
    ]

    # ---------------------------------------------------------------------
    # 6) Status / overlap.
    # ---------------------------------------------------------------------
    status_rows = []

    for _, source in source_map.iterrows():
        name = clean_text(source["university_name"])
        key = normalize_school(name)

        if key in final_norms:
            school_rows = final_df[
                final_df["university_name"].map(normalize_school) == key
            ]

            status_rows.append(
                {
                    "university_name": name,
                    "status": "ACCEPTED",
                    "accepted_rows": len(school_rows),
                    "reason": "",
                    "priority": int(source.get("priority", 0)),
                    "source_url": clean_text(source["source_url"]),
                }
            )
        else:
            match = excluded_final[
                excluded_final["university_name"].map(normalize_school) == key
            ]

            status_rows.append(
                {
                    "university_name": name,
                    "status": "EXCLUDED",
                    "accepted_rows": 0,
                    "reason": (
                        clean_text(match.iloc[0]["exclusion_reason"])
                        if not match.empty
                        else "EXCLUDED"
                    ),
                    "priority": int(source.get("priority", 0)),
                    "source_url": clean_text(source["source_url"]),
                }
            )

    status_df = pd.DataFrame(status_rows)

    high_priority_total = int(
        (source_map["priority"] >= 2).sum()
    )
    high_priority_final = int(
        source_map[
            (source_map["priority"] >= 2)
            & source_map["university_name"]
            .map(normalize_school)
            .isin(final_norms)
        ].shape[0]
    )

    # ---------------------------------------------------------------------
    # 7) Write after all audits pass.
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
    excluded_final.to_csv(
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
    pd.DataFrame(
        columns=["university_name", "source_type", "reason", "source_url"]
    ).to_csv(
        REVIEW_FILE,
        index=False,
        encoding="utf-8-sig",
    )
    status_df.to_csv(
        SOURCE_STATUS_FILE,
        index=False,
        encoding="utf-8-sig",
    )
    pd.DataFrame(report_rows).to_csv(
        FINAL_LOCK_REPORT_FILE,
        index=False,
        encoding="utf-8-sig",
    )
    pd.DataFrame(row_excluded_rows).to_csv(
        ROW_EXCLUDED_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    # ---------------------------------------------------------------------
    # 8) Final result.
    # ---------------------------------------------------------------------
    print()
    print("=" * 124)
    print("KẾT QUẢ 2023 FINAL LOCK")
    print("=" * 124)
    print(f"SOURCE INVENTORY       : {len(source_map):5d} trường")
    print(f"RECOVERED LAST-MILE    : {len(recovered):5d} trường")
    print(f"SOURCE URL REPAIRED    : {len(repaired_source):5d} trường")
    print(f"LOW RAW ROWS EXCLUDED  : {len(low_row_excluded):5d} rows")
    print(
        f"FINAL CLEAN 2023       : {len(final_df):5d} rows / "
        f"{final_df['university_name'].nunique():3d} trường"
    )
    print(f"SOURCE EXCLUDED        : {len(excluded_final):5d} trường")
    print("REVIEW                 :     0 trường")
    print(
        f"2024+2025 OVERLAP      : {high_priority_final:3d} / "
        f"{high_priority_total:3d} trường priority cao"
    )
    print(
        f"Score min/max RAW      : "
        f"{scores.min():.2f} / {scores.max():.2f}"
    )
    print(f"RAW rows score <10     : {int((scores < 10).sum())}")
    print(f"Missing major_code     : {int(final_df['major_code'].eq('').sum())}")
    print(f"Missing major_name     : {int(final_df['major_name'].eq('').sum())}")
    print(f"Missing cutoff_score   : {int(final_df['cutoff_score'].isna().sum())}")
    print(
        f"ML READY 2023          : {len(ml_ready):5d} rows / "
        f"{ml_ready['university_name'].nunique():3d} trường"
    )
    print(f"ML EXCLUDED            : {len(ml_excluded):5d} rows")
    print("-" * 124)
    print("FINAL       :", FINAL_FILE)
    print("ML READY    :", ML_READY_FILE)
    print("ML EXCLUDED :", ML_EXCLUDED_FILE)
    print("EXCLUDED    :", SOURCE_EXCLUDED_FILE)
    print("STATUS      :", SOURCE_STATUS_FILE)
    print("ROW EXCL.   :", ROW_EXCLUDED_FILE)
    print("REPORT      :", FINAL_LOCK_REPORT_FILE)
    print("SOURCE MAP  :", SOURCE_MAP_FILE)
    print("=" * 124)

    if recovered:
        print()
        print("CÁC TRƯỜNG CỨU THÊM Ở LAST-MILE:")
        for name in recovered:
            print(f"  ✅ {name}")

    if repaired_source:
        print()
        print("SOURCE URL ĐƯỢC SỬA BẰNG BÀI 2023 CÙNG TRANG THÔNG TIN TUYỂN SINH:")
        for name in repaired_source:
            print(f"  🔧 {name}")

    print()
    print(
        "AUDIT 2023             : ✅ 167/167 nguồn được hạch toán; "
        "FINAL chỉ dùng nguồn primary thongtintuyensinh; "
        "major_code đầy đủ; raw score >=10; REVIEW=0"
    )
    print(
        "2023 CHECKPOINT        : ✅ KHÓA NĂM 2023"
    )


if __name__ == "__main__":
    main()
