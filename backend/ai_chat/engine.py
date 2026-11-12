from __future__ import annotations

import json
import math
import re
import unicodedata
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from ai_api.service import recommend_for_api


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROGRAM_YEAR_FILE = (
    PROJECT_ROOT
    / "data"
    / "dataset"
    / "admission_scores_2023_2026_program_year.csv"
)
LOCATION_FILE = (
    PROJECT_ROOT
    / "data"
    / "dataset"
    / "university_locations.csv"
)
MODEL_META_FILE = (
    PROJECT_ROOT
    / "ai"
    / "models"
    / "best_cutoff_model_metadata.json"
)
MODEL_METRICS_FILE = (
    PROJECT_ROOT
    / "data"
    / "dataset"
    / "cutoff_model_metrics_2026_holdout.csv"
)

YEARS = [2023, 2024, 2025, 2026]

COMMON_MAJOR_ALIASES = {
    "cntt": "Công nghệ thông tin",
    "it": "Công nghệ thông tin",
    "cong nghe thong tin": "Công nghệ thông tin",
    "khoa hoc may tinh": "Khoa học máy tính",
    "khmt": "Khoa học máy tính",
    "ky thuat phan mem": "Kỹ thuật phần mềm",
    "ktpm": "Kỹ thuật phần mềm",
    "ngon ngu anh": "Ngôn ngữ Anh",
    "nna": "Ngôn ngữ Anh",
    "marketing": "Marketing",
    "ke toan": "Kế toán",
    "quan tri kinh doanh": "Quản trị kinh doanh",
    "qtkd": "Quản trị kinh doanh",
    "luat": "Luật",
    "luat kinh te": "Luật kinh tế",
    "thuong mai dien tu": "Thương mại điện tử",
    "tmdt": "Thương mại điện tử",
    "logistics": "Logistics và Quản lý chuỗi cung ứng",
    "tri tue nhan tao": "Trí tuệ nhân tạo",
}

CITY_ALIASES = {
    "tp hcm": "Hồ Chí Minh",
    "tphcm": "Hồ Chí Minh",
    "tp.hcm": "Hồ Chí Minh",
    "ho chi minh": "Hồ Chí Minh",
    "sai gon": "Hồ Chí Minh",
    "ha noi": "Hà Nội",
    "da nang": "Đà Nẵng",
    "hai phong": "Hải Phòng",
    "thai nguyen": "Thái Nguyên",
    "quang ninh": "Quảng Ninh",
    "ninh binh": "Ninh Bình",
    "hung yen": "Hưng Yên",
    "dong thap": "Đồng Tháp",
    "vinh long": "Vinh Long",
    "ha tinh": "Hà Tĩnh",
    "hue": "Huế",
    "can tho": "Cần Thơ",
    "binh duong": "Bình Dương",
    "dak lak": "Đắk Lắk",
    "gia lai": "Gia Lai",
    "khanh hoa": "Khánh Hòa",
    "nghe an": "Nghệ An",
    "tay ninh": "Tây Ninh",
}

UNSUPPORTED_KEYWORDS = {
    "hoc phi": "học phí",
    "ky tuc xa": "ký túc xá",
    "ti le choi": "tỉ lệ chọi",
    "ty le choi": "tỉ lệ chọi",
    "chi tieu": "chỉ tiêu tuyển sinh",
    "hoc bong": "học bổng",
}

GENERIC_SCHOOL_TOKENS = {
    "truong",
    "dai",
    "hoc",
    "dh",
    "hoc",
    "vien",
    "hv",
    "quoc",
    "gia",
    "viet",
    "nam",
}

for _city_alias in CITY_ALIASES:
    GENERIC_SCHOOL_TOKENS.update(
        normalize_token
        for normalize_token
        in re.sub(
            r"[^a-z0-9]+",
            " ",
            unicodedata.normalize(
                "NFD",
                _city_alias.lower(),
            )
        )
        .replace("d", "d")
        .split()
        if normalize_token
    )


def clean_text(value: Any) -> str:
    if value is None:
        return ""

    text = str(value).replace("\xa0", " ").strip()

    if text.lower() in {"nan", "none", "<na>"}:
        return ""

    return re.sub(r"\s+", " ", text)


def normalize(value: Any) -> str:
    text = clean_text(value).lower()
    text = unicodedata.normalize(
        "NFD",
        text,
    )
    text = "".join(
        char
        for char in text
        if unicodedata.category(char) != "Mn"
    )
    text = text.replace("đ", "d")
    text = re.sub(
        r"[^a-z0-9]+",
        " ",
        text,
    )
    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


def safe_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): safe_json_value(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            safe_json_value(item)
            for item in value
        ]

    if isinstance(value, tuple):
        return [
            safe_json_value(item)
            for item in value
        ]

    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass

    return value


@lru_cache(maxsize=4)
def _load_program_year_cached(
    mtime_ns: int,
) -> pd.DataFrame:
    del mtime_ns

    if not PROGRAM_YEAR_FILE.exists():
        return pd.DataFrame()

    df = pd.read_csv(
        PROGRAM_YEAR_FILE,
        dtype=str,
        keep_default_na=False,
    )

    if "year" in df.columns:
        df["year"] = pd.to_numeric(
            df["year"],
            errors="coerce",
        )

    if "cutoff_score" in df.columns:
        df["cutoff_score"] = pd.to_numeric(
            df["cutoff_score"],
            errors="coerce",
        )

    return df


def load_program_year() -> pd.DataFrame:
    if not PROGRAM_YEAR_FILE.exists():
        return pd.DataFrame()

    return _load_program_year_cached(
        PROGRAM_YEAR_FILE.stat().st_mtime_ns
    ).copy()


@lru_cache(maxsize=4)
def _load_location_cached(
    mtime_ns: int,
) -> pd.DataFrame:
    del mtime_ns

    if not LOCATION_FILE.exists():
        return pd.DataFrame()

    return pd.read_csv(
        LOCATION_FILE,
        dtype=str,
        keep_default_na=False,
    )


def load_locations() -> pd.DataFrame:
    if not LOCATION_FILE.exists():
        return pd.DataFrame()

    return _load_location_cached(
        LOCATION_FILE.stat().st_mtime_ns
    ).copy()


def extract_score(
    message: str,
) -> float | None:
    # Keep decimal punctuation; normalize() deliberately removes punctuation.
    normalized = unicodedata.normalize("NFD", str(message).lower().replace("đ", "d"))
    normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")

    patterns = [
        r"\b(\d{1,2}(?:[.,]\d{1,2})?)\s*diem\b",
        r"\bdiem\s*(\d{1,2}(?:[.,]\d{1,2})?)\b",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            normalized,
        )

        if match:
            try:
                value = float(
                    match.group(1).replace(",", ".")
                )
            except ValueError:
                continue

            if 0 <= value <= 30:
                return value

    return None


def extract_combination(
    message: str,
) -> str:
    match = re.search(
        r"\b([A-Z]\d{2})\b",
        str(message).upper(),
    )

    return (
        match.group(1)
        if match
        else ""
    )


def extract_years(
    message: str,
) -> list[int]:
    years = sorted(
        {
            int(year)
            for year
            in re.findall(
                r"\b(20\d{2})\b",
                message,
            )
        }
    )

    for start, end in re.findall(r'\b(20\d{2})\s*(?:đến|tới|[-–—])\s*(?:năm\s*)?(20\d{2})\b', message.lower()):
        if 0 <= int(end) - int(start) <= 20:
            years = sorted(set(years) | set(range(int(start), int(end) + 1)))
    return years


def extract_city(
    message: str,
) -> str:
    normalized = normalize(message)

    for alias, city in sorted(
        CITY_ALIASES.items(),
        key=lambda item: -len(item[0]),
    ):
        if re.search(rf"\b{re.escape(alias)}\b", normalized):
            return city

    locations = load_locations()

    if not locations.empty and "city" in locations.columns:
        for city in sorted(
            {
                clean_text(item)
                for item in locations["city"]
                if clean_text(item)
            },
            key=len,
            reverse=True,
        ):
            if re.search(rf"\b{re.escape(normalize(city))}\b", normalized):
                return city

    return ""


def _major_names() -> list[str]:
    df = load_program_year()

    if df.empty or "major_name" not in df.columns:
        return []

    return sorted(
        {
            clean_text(value)
            for value in df["major_name"]
            if clean_text(value)
        }
    )


def extract_major(
    message: str,
) -> str:
    normalized = normalize(message)
    # Read the subject following "ngành" before matching aliases from school
    # names or comparing the entire sentence with long program descriptions.
    subject = re.search(r'\b(?:nganh|muon hoc|chon hoc)\s+(.+?)(?=\s+(?:o|tai|truong|dai hoc|hoc vien|dhqg|nam|khoi|to hop)\b|[,?.!]|$)', normalized)
    if subject:
        phrase = subject.group(1).strip()
        for alias,canonical in sorted(COMMON_MAJOR_ALIASES.items(),key=lambda item:-len(item[0])):
            if phrase == alias:
                return canonical
        exact = [name for name in _major_names() if normalize(name) == phrase]
        if exact:
            return min(exact,key=len)
    # Read the subject following "ngành" before matching aliases from school
    # names or comparing the entire sentence with long program descriptions.
    subject = re.search(r'\b(?:nganh|muon hoc|chon hoc)\s+(.+?)(?=\s+(?:o|tai|truong|dai hoc|hoc vien|dhqg|nam|khoi|to hop)\b|[,?.!]|$)', normalized)
    if subject:
        phrase = subject.group(1).strip()
        for alias,canonical in sorted(COMMON_MAJOR_ALIASES.items(),key=lambda item:-len(item[0])):
            if phrase == alias:
                return canonical
        exact = [name for name in _major_names() if normalize(name) == phrase]
        if exact:
            return min(exact,key=len)

    for alias, canonical in sorted(
        COMMON_MAJOR_ALIASES.items(),
        key=lambda item: -len(item[0]),
    ):
        if re.search(
            rf"\b{re.escape(alias)}\b",
            normalized,
        ):
            return canonical

    explicit = re.search(
        r"(?:nganh|chon|hoc)\s+(.+?)(?:\s+(?:o|tai|truong|khoi|to hop)\b|[,?.!]|$)",
        normalized,
    )

    explicit_text = (
        explicit.group(1).strip()
        if explicit
        else ""
    )

    names = _major_names()

    contained = [name for name in names if len(normalize(name).split()) >= 2
                 and re.search(rf'\b{re.escape(normalize(name))}\b', normalized)]
    if contained:
        return max(contained,key=lambda name:len(normalize(name)))

    contained = [name for name in names if len(normalize(name).split()) >= 2
                 and re.search(rf'\b{re.escape(normalize(name))}\b', normalized)]
    if contained:
        return max(contained,key=lambda name:len(normalize(name)))

    if explicit_text:
        best = max(
            names,
            key=lambda name:
                SequenceMatcher(
                    None,
                    normalize(name),
                    explicit_text,
                ).ratio(),
            default="",
        )

        if best:
            score = SequenceMatcher(
                None,
                normalize(best),
                explicit_text,
            ).ratio()

            if score >= 0.58:
                return best

    message_tokens = set(
        normalized.split()
    )

    candidates = []

    for name in names:
        n = normalize(name)
        tokens = set(n.split())

        if not tokens:
            continue

        overlap = len(
            tokens & message_tokens
        ) / max(
            1,
            len(tokens),
        )

        if overlap >= 0.7:
            candidates.append(
                (
                    overlap,
                    len(tokens),
                    name,
                )
            )

    if candidates:
        candidates.sort(
            key=lambda item: (
                -item[0],
                -item[1],
                item[2],
            )
        )
        return candidates[0][2]

    return ""


def _school_catalog() -> list[dict]:
    df = load_program_year()

    if df.empty:
        return []

    required = {
        "university_key",
        "university_name",
    }

    if not required.issubset(
        set(df.columns)
    ):
        return []

    rows = []

    for key, group in df.groupby(
        "university_key",
        sort=False,
    ):
        names = [
            clean_text(value)
            for value in group[
                "university_name"
            ]
            if clean_text(value)
        ]

        name = max(
            names,
            key=len,
            default=clean_text(key),
        )

        rows.append(
            {
                "university_key":
                    clean_text(key),
                "university_name":
                    name,
            }
        )

    return rows


def school_match_score(
    school_name: str,
    message: str,
) -> float:
    school_norm = normalize(
        school_name
    )
    message_norm = normalize(
        message
    )

    reduced = re.sub(
        r"\b(?:truong|dai hoc|dh|hoc vien|hv)\b",
        " ",
        school_norm,
    )
    reduced = re.sub(
        r"\s+",
        " ",
        reduced,
    ).strip()

    school_tokens = {
        token
        for token in reduced.split()
        if len(token) > 1
    }

    message_tokens = set(
        message_norm.split()
    )

    overlap_tokens = (
        school_tokens
        & message_tokens
    )

    overlap = (
        len(overlap_tokens)
        / max(
            1,
            len(school_tokens),
        )
    )

    contains = 1.0 if (
        school_norm in message_norm
        or (
            reduced
            and reduced in message_norm
        )
    ) else 0.0

    identity_overlap = {
        token
        for token in overlap_tokens
        if token not in GENERIC_SCHOOL_TOKENS
    }

    # One everyday word (e.g. "được" -> "duoc") is not a school identity.
    if not contains and len(identity_overlap) < 2:
        return 0.0
    if not contains:
        words = reduced.split()
        pair = any(re.search(rf'\b{re.escape(a)} {re.escape(b)}\b',message_norm)
                   and (a in identity_overlap or b in identity_overlap) for a,b in zip(words,words[1:]))
        named_school = re.search(r'\b(?:truong|dai hoc|dh|hoc vien|hv)\b',message_norm)
        if not pair or not named_school:
            return 0.0

    sequence = SequenceMatcher(
        None,
        reduced,
        message_norm,
    ).ratio()

    return (
        contains * 2.0
        + overlap * 1.5
        + len(identity_overlap) * 0.35
        + sequence * 0.25
    )


def match_schools(
    message: str,
    *,
    limit: int = 3,
) -> list[dict]:
    candidates = []

    for school in _school_catalog():
        score = school_match_score(
            school[
                "university_name"
            ],
            message,
        )

        if score >= 0.72:
            candidates.append(
                (
                    score,
                    school,
                )
            )

    candidates.sort(
        key=lambda item: (
            -item[0],
            item[1][
                "university_name"
            ],
        )
    )

    output = []
    seen = set()

    for _, school in candidates:
        key = school[
            "university_key"
        ]

        if key in seen:
            continue

        seen.add(key)
        output.append(
            school
        )

        if len(output) >= limit:
            break

    return output


def detect_unsupported(
    message: str,
) -> list[str]:
    normalized = normalize(
        message
    )

    return [
        label
        for keyword, label
        in UNSUPPORTED_KEYWORDS.items()
        if keyword in normalized
    ]


def detect_intent(
    message: str,
    *,
    context: dict,
) -> str:
    normalized = normalize(
        message
    )

    unsupported = detect_unsupported(
        message
    )

    if unsupported:
        return "unsupported_data"

    if "nguyen vong" in normalized or re.search(r"\bnv\s*\d+\b", normalized):
        return "aspirations"

    if "nguyen vong" in normalized or re.search(r"\bnv\s*\d+\b", normalized):
        return "aspirations"

    if (
        normalized in {
            "hi",
            "hello",
            "xin chao",
            "chao",
            "chao ban",
        }
        or normalized.startswith(
            "xin chao "
        )
        or normalized.startswith(
            "chao ban "
        )
    ):
        return "greeting"

    if (
        "so sanh" in normalized
        or (
            context.get(
                "last_intent"
            ) == "compare"
            and any(
                phrase in normalized
                for phrase in [
                    "truong nao",
                    "thap hon",
                    "cao hon",
                    "on dinh hon",
                    "tot hon",
                ]
            )
        )
    ):
        return "compare"

    if any(
        phrase in normalized
        for phrase in [
            "lich su diem",
            "diem chuan",
            "cac nam",
            "tu 2023",
            "nam 2023",
            "nam 2024",
            "nam 2025",
            "nam 2026",
        ]
    ) and match_schools(
        message,
        limit=1,
    ):
        return "history"

    if any(
        phrase in normalized
        for phrase in [
            "mo hinh",
            "du doan 2027",
            "sai so",
            "gradient boosting",
            "an toan",
            "phu hop",
            "thu suc",
            "r2",
            "rmse",
            "mae",
        ]
    ) and not any(
        phrase in normalized
        for phrase in [
            "truong nao",
            "nen chon",
            "goi y truong",
        ]
    ):
        return "explain_model"

    changed_recommendation_field = any(
        [
            extract_score(
                message
            ) is not None,
            bool(
                extract_combination(
                    message
                )
            ),
            bool(
                extract_city(
                    message
                )
            ),
            bool(
                extract_major(
                    message
                )
            ),
        ]
    )

    if any(
        phrase in normalized
        for phrase in [
            "ke hoach nguyen vong",
            "lap nguyen vong",
            "xep nguyen vong",
            "phan bo nguyen vong",
            "len ke hoach nv",
            "chien luoc nguyen vong",
            "dat nv",
            "nv1 nv2 nv3",
        ]
    ) or (
        any(nv in normalized for nv in ["nv1", "nv2", "nv3"])
        and any(
            phrase in normalized
            for phrase in ["dat", "chon", "xep", "len ke hoach", "phan tich"]
        )
    ):
        return "aspirations"

    if any(
        phrase in normalized
        for phrase in [
            "truong nao",
            "nen chon",
            "goi y truong",
            "tu van",
            "nguyen vong",
            "co the dau",
            "co phu hop",
            "phan tich",
        ]
    ):
        return "recommendation"


    if (
        changed_recommendation_field
        and all(
            context.get(key)
            for key in [
                "score",
                "combination",
                "major",
            ]
        )
    ):
        return "recommendation"

    if any(
        phrase in normalized
        for phrase in [
            "2023",
            "2024",
            "2025",
            "2026",
        ]
    ) and context.get(
        "school_key"
    ):
        return "history"

    return "general"


def merge_context(
    *,
    message: str,
    previous: dict,
    ui_context: dict,
) -> dict:
    from .conversation import new_profile_request
    reset = new_profile_request(message)
    context = dict(
        previous
        or {}
    )
    if reset:
        # Empty values intentionally block the previous applicant/sidebar from
        # being reintroduced on the following turn.
        own = any(phrase in normalize(message) for phrase in ['ho so moi','bat dau lai']) or any(phrase in message.casefold() for phrase in ['còn mình','còn tôi'])
        context = dict(score=None,combination='',major='',major_code='',city='',
                       school_key='',school_name='',school_keys=[],profile_subject='self' if own else 'other')

    fallback_fields = [
        "score",
        "combination",
        "major",
        "major_code",
        "city",
    ]

    for field in fallback_fields:
        value = ui_context.get(
            field
        )

        if (
            field not in context
            and value not in (
                None,
                "",
            )
        ):
            context[field] = value

    if any(phrase in normalize(message) for phrase in
           ("ca nuoc", "toan quoc", "khong gioi han thanh pho", "bo loc thanh pho")):
        context["city"] = ""

    if any(phrase in normalize(message) for phrase in
           ("ca nuoc", "toan quoc", "khong gioi han thanh pho", "bo loc thanh pho")):
        context["city"] = ""

    score = extract_score(
        message
    )

    if score is not None:
        context["score"] = score

    combination = extract_combination(
        message
    )

    if combination:
        context[
            "combination"
        ] = combination

    city = extract_city(
        message
    )

    if city:
        context["city"] = city

    major = extract_major(
        message
    )

    if major:
        context["major"] = major
        context["major_code"] = ""

    schools = match_schools(
        message,
        limit=3,
    )

    if schools:
        context[
            "school_key"
        ] = schools[0][
            "university_key"
        ]
        context[
            "school_name"
        ] = schools[0][
            "university_name"
        ]

        context[
            "school_keys"
        ] = [
            school[
                "university_key"
            ]
            for school
            in schools
        ]

    return context


def model_info() -> dict:
    meta = {}

    if MODEL_META_FILE.exists():
        try:
            meta = json.loads(
                MODEL_META_FILE.read_text(
                    encoding="utf-8"
                )
            )
        except Exception:
            meta = {}

    metrics = {}

    if MODEL_METRICS_FILE.exists():
        try:
            df = pd.read_csv(
                MODEL_METRICS_FILE
            )

            method = (
                meta.get("best_overall_method")
                or meta.get(
                    "best_method"
                )
                or meta.get(
                    "method"
                )
                or "GradientBoosting"
            )

            if "method" in df.columns:
                row = df[
                    df["method"].astype(
                        str
                    ).eq(
                        str(method)
                    )
                ]

                if row.empty:
                    row = df[
                        df["method"].astype(
                            str
                        ).eq(
                            "GradientBoosting"
                        )
                    ]

                if not row.empty:
                    metrics = safe_json_value(
                        row.iloc[0].to_dict()
                    )
        except Exception:
            metrics = {}

    return {
        "metadata":
            safe_json_value(
                meta
            ),
        "metrics":
            metrics,
    }


def alternative_cards(result: dict, *, local_only: bool = False) -> list[dict]:
    """Keep source limitations visible even when there are some strict matches."""
    groups = [
        ("same_city_unverified_combination", "CẦN XÁC MINH TỔ HỢP"),
        ("same_city_historical", "DỮ LIỆU CŨ HƠN"),
    ]
    if not local_only:
        groups += [
            ("nationwide_verified", "ĐÚNG TỔ HỢP - NGOÀI KHU VỰC"),
            ("related_major_name", "CÙNG NHÓM TÊN NGÀNH"),
        ]
    return [
        {"kind": "recommendation", **safe_json_value(row), "scope": label}
        for key, label in groups
        for row in (result.get("alternatives", {}).get(key, []) or [])[:4]
    ] + [{"kind": "official_method", "scope": "ĐIỂM CÔNG BỐ THEO PHƯƠNG THỨC", **row}
         for row in result.get('other_admission_methods', [])[:6]]


def recommendation_reply(
    *,
    context: dict,
) -> dict:
    missing = [
        label
        for key, label
        in [
            ("score", "điểm THPT"),
            ("combination", "tổ hợp"),
            ("major", "ngành"),
        ]
        if context.get(key) in (None, "")
    ]

    if missing:
        return {
            "intent": "clarification",
            "text": (
                "Mình cần thêm "
                + ", ".join(missing)
                    + " để tìm lựa chọn phù hợp hơn."
            ),
            "cards": [],
            "suggestions": [
                "Ví dụ: 24 điểm A01 ngành Công nghệ thông tin ở Đà Nẵng",
            ],
        }

    payload = {
        "score": context["score"],
        "combination": context["combination"],
        "major": context["major"],
        "major_code": context.get("major_code", ""),
        "city": context.get("city", ""),
        "top": 10,
    }

    result = recommend_for_api(payload)
    strict = result.get("results", [])
    cards = []

    for row in strict[:5]:
        cards.append({"kind": "recommendation", "scope": "STRICT", **safe_json_value(row)})

    if strict:
        local_alternatives = alternative_cards(result, local_only=True)
        cards.extend(local_alternatives)
        city_phrase = f" tại {context['city']}" if context.get("city") else ""
        # Collect advisory level distribution for richer AI narrative
        level_counts: dict[str, int] = {}
        for row in strict:
            level = row.get("recommendation_level") or ""
            if level:
                level_counts[level] = level_counts.get(level, 0) + 1

        level_summary = ""
        if level_counts:
            parts = [f"{cnt} {lvl}" for lvl, cnt in level_counts.items()]
            level_summary = " (phân bố mức tư vấn: " + ", ".join(parts) + ")"

        text = (
            f"Mình tìm thấy {len(strict)} kết quả phù hợp cho "
            f"{float(context['score']):g} điểm, "
            f"{context['combination']}, "
            f"ngành {context['major']}{city_phrase}{level_summary}. "
            "Các mức AN TOÀN/PHÙ HỢP/THỬ SỨC là mức tư vấn theo mô hình, "
            "không phải xác suất đỗ. Bạn có thể hỏi mình lên kế hoạch nguyện vọng "
            "NV1/NV2/NV3 dựa trên các kết quả này."
        )
        text += (
            " Danh sách chỉ phản ánh dữ liệu đã có, không phải toàn bộ trường đào tạo ngành này."
        )
        if local_alternatives:
            text += " Các lựa chọn cùng khu vực cần kiểm tra thêm được hiển thị riêng, kèm lý do."
        return {
            "intent": "recommendation",
            "text": text,
            "cards": cards,
            "suggestions": [
                "Tôi muốn lên kế hoạch nguyện vọng NV1/NV2/NV3",
                "Giải thích mức An toàn / Phù hợp / Thử sức",
                "Đổi sang tỉnh/thành khác",
                "Cho mình xem điểm chuẩn 2023-2026 của một trường",
            ],
            "diagnostics": result.get("diagnostics", {}),
        }

    cards.extend(alternative_cards(result))

    diagnostics = result.get("diagnostics", {})
    verified = diagnostics.get("verified_combination_fresh_count", 0)
    major_count = diagnostics.get("major_match_count", 0)

    if major_count == 0:
        text = (
            "Mình chưa tìm thấy chương trình khớp đủ rõ với ngành/mã ngành này "
            "trong tập dự đoán hiện tại."
        )
    elif verified == 0:
        text = (
            f"Có chương trình khớp ngành, nhưng hiện chưa có chương trình 2026 "
            f"xác minh tổ hợp {context['combination']} để trả kết quả strict."
        )
    elif context.get("city"):
        text = (
            f"Có chương trình đúng ngành và tổ hợp, nhưng chưa có kết quả strict "
            f"tại {context['city']} trong dữ liệu hiện tại."
        )
    else:
        text = "Chưa có kết quả strict cho bộ điều kiện hiện tại."

    suggestions = [
        f"Thử tổ hợp {item['combination']}"
        for item in diagnostics.get("available_combinations", [])[:5]
    ]

    if cards:
        text += (
            " Mình hiển thị các lựa chọn mở rộng bên dưới và gắn nhãn rõ lý do; "
            "chúng không được coi là kết quả strict."
        )

    return {
        "intent": "recommendation",
        "text": text,
        "cards": cards[:8],
        "suggestions": suggestions,
        "diagnostics": diagnostics,
    }

def analyze_aspirations_reply(
    *,
    context: dict,
) -> dict:
    """Phân tích và gợi ý chiến lược đặt nguyện vọng NV1/NV2/NV3.

    Dựa trên kết quả Recommendation Engine, phân loại các trường/ngành thành
    ba nhóm mức tư vấn; thứ tự nguyện vọng cần hỏi sở thích người dùng.
    cùng lời khuyên cụ thể để người dùng lên kế hoạch đặt nguyện vọng.
    """
    missing = [
        label
        for key, label in [
            ("score", "điểm THPT"),
            ("combination", "tổ hợp"),
            ("major", "ngành"),
        ]
        if context.get(key) in (None, "")
    ]

    if missing:
        return {
            "intent": "aspirations",
            "text": (
                "Để lên kế hoạch nguyện vọng, mình cần biết thêm "
                + ", ".join(missing)
                + ". Bạn cung cấp nhé?"
            ),
            "cards": [],
            "suggestions": [
                "Ví dụ: 24 điểm A01 ngành Công nghệ thông tin ở Đà Nẵng",
            ],
        }

    payload = {
        "score": context["score"],
        "combination": context["combination"],
        "major": context["major"],
        "major_code": context.get("major_code", ""),
        "city": context.get("city", ""),
        "top": 15,
    }

    result = recommend_for_api(payload)
    strict = result.get("results", [])

    if not strict:
        return {"intent": "aspirations",
                "text": "Chưa đủ dữ liệu đã xác minh để xếp nhóm rủi ro. Các lựa chọn cần kiểm tra thêm có nhãn riêng; thiếu dữ liệu không có nghĩa là không có trường phù hợp.",
                "cards": alternative_cards(result),
                "diagnostics": result.get("diagnostics", {}),
                "suggestions": ["Kiểm tra dữ liệu các trường trong khu vực", "Tư vấn không giới hạn thành phố"]}

    # Map advisory levels to NV slots
    _LEVEL_SLOT = {
        "AN TOÀN": "AN TOÀN",
        "PHÙ HỢP": "PHÙ HỢP",
        "THỬ SỨC": "THỬ SỨC",
        "RỦI RO CAO": "RỦI RO CAO",
    }
    # Fallback slot assignment by score gap when advisory_level is absent
    buckets: dict[str, list] = {level: [] for level in _LEVEL_SLOT}
    for row in strict:
        level = (row.get("recommendation_level") or row.get("advisory_level") or "").upper().strip()
        slot = _LEVEL_SLOT.get(level)
        if slot is None:
            # The recommendation engine owns calibrated risk labels.
            continue
        buckets[slot].append(row)

    cards = []
    slot_labels = [
        ("AN TOÀN", "AN TOÀN", "Điểm cao hơn mốc dự đoán ít nhất bằng sai số q80; không đảm bảo trúng tuyển"),
        ("PHÙ HỢP", "PHÙ HỢP", "Mức phù hợp theo sai số mô hình đã hiệu chỉnh"),
        ("THỬ SỨC", "THỬ SỨC", "Mức thử sức theo sai số mô hình đã hiệu chỉnh"),
        ("RỦI RO CAO", "RỦI RO CAO", "Điểm thấp hơn mốc dự đoán quá sai số q80"),
    ]
    for slot, level, description in slot_labels:
        for row in buckets[slot][:2]:
            cards.append({
                "kind": "aspirations",
                "slot": slot,
                "advisory_level": level,
                "slot_description": description,
                **safe_json_value(row),
            })

    filled_slots = [slot for slot, _, _ in slot_labels if buckets[slot]]
    missing_slots = [slot for slot, _, _ in slot_labels[:3] if not buckets[slot]]
    cards.extend(alternative_cards(result, local_only=True))

    city_phrase = f" tại {context['city']}" if context.get("city") else ""
    text = (
        f"Dựa trên {len(strict)} kết quả tìm được cho "
        f"{float(context['score']):g} điểm, {context['combination']}, "
        f"ngành {context['major']}{city_phrase}, "
        f"mình đã xếp nguyện vọng vào {len(filled_slots)} nhóm: "
        + ", ".join(filled_slots) + ". "
    )
    if missing_slots:
        text += (
            f"Nhóm {', '.join(missing_slots)} chưa có đủ dữ liệu — "
            "bạn có thể bỏ bộ lọc thành phố hoặc thử tổ hợp khác để bổ sung. "
        )
    text += (
        "Các nhóm trên là mức tư vấn của mô hình, không đảm bảo trúng tuyển. "
        "Bạn hãy cho biết thứ tự trường/ngành yêu thích để mình hỗ trợ lập nguyện vọng."
    )

    return {
        "intent": "aspirations",
        "text": text,
        "cards": cards,
        "suggestions": [
            "Xem điểm chuẩn 2023-2026 của một trường trong danh sách",
            "Đổi sang tỉnh/thành khác để tìm thêm lựa chọn",
            "Giải thích mức An toàn / Phù hợp / Thử sức",
            "Tư vấn trường thêm với hồ sơ này",
        ],
        "diagnostics": result.get("diagnostics", {}),
    }


def _history_for_program(
    group: pd.DataFrame,
) -> dict:
    history = {}

    for year in YEARS:
        year_rows = group[
            pd.to_numeric(
                group["year"],
                errors="coerce",
            ).eq(year)
        ]

        if year_rows.empty:
            history[
                str(year)
            ] = None
            continue

        row = year_rows.iloc[0]

        history[
            str(year)
        ] = {
            "cutoff_score":
                round(
                    float(
                        row[
                            "cutoff_score"
                        ]
                    ),
                    2,
                ),
            "eligible_combinations":
                clean_text(
                    row.get(
                        "eligible_combinations"
                    )
                ),
            "source_urls": clean_text(row.get("source_urls")),
        }

    return history


def history_reply(
    *,
    message: str,
    context: dict,
) -> dict:
    from catalog.official import official_rows
    requested_years = extract_years(message)
    df = load_program_year()

    if df.empty:
        return {
            "intent":
                "history",
            "text":
                "Không đọc được dataset program-year 2023-2026.",
            "cards": [],
            "suggestions": [],
        }

    school_key = context.get(
        "school_key",
        "",
    )

    if not school_key:
        schools = match_schools(
            message,
            limit=1,
        )

        if not schools:
            return {
                "intent":
                    "clarification",
                "text":
                    "Bạn cho mình tên trường cụ thể để tra lịch sử điểm chuẩn 2023-2026.",
                "cards": [],
                "suggestions": [
                    "Ví dụ: Điểm CNTT của Đại học Kiến trúc Đà Nẵng từ 2023 đến 2026",
                ],
            }

        school_key = schools[0][
            "university_key"
        ]

    rows = df[
        df["university_key"].astype(
            str
        ).eq(
            str(
                school_key
            )
        )
    ].copy()

    major_query = extract_major(message) or (
        context.get('major', '') if context.get('last_intent') in {'history', 'recommendation'} else '')
    official = [{"kind": "official_method", "scope": "ĐIỂM CÔNG BỐ THEO PHƯƠNG THỨC", **row}
                for row in official_rows(university_key=school_key, major=major_query,
                                         years=requested_years or None) if not row['comparable_thpt']]
    context['school_key'] = school_key
    if major_query:
        context['major'] = major_query
    if official:
        context['school_name'] = official[0]['university_name']
    if requested_years:
        rows = rows[pd.to_numeric(rows.year, errors='coerce').isin(requested_years)]

    if rows.empty:
        return {
            "intent":
                "history",
            "text":
                ("Có điểm công bố theo phương thức bên dưới; chưa có chuỗi THPT đủ điều kiện ghép để dự đoán."
                 if official else "Chưa có điểm chuẩn đã xác minh cho trường/ngành trong năm bạn hỏi.")
                 + (" Điểm năm 2027 là dự đoán, không phải điểm chuẩn công bố." if 2027 in requested_years else ''),
            "cards": official[:8],
            "suggestions": [],
        }

    school_name = max(
        [
            clean_text(value)
            for value in rows[
                "university_name"
            ]
            if clean_text(value)
        ],
        key=len,
        default=context.get(
            "school_name",
            "",
        ),
    )

    major_query = extract_major(
        message
    )

    if (
        not major_query
        and context.get(
            "last_intent"
        ) in {
            "history",
            "recommendation",
        }
    ):
        major_query = context.get(
            "major",
            "",
        )

    if major_query:
        major_norm = normalize(
            major_query
        )

        scored = []

        for (
            major_code,
            major_name,
        ), group in rows.groupby(
            [
                "major_code",
                "major_name",
            ],
            sort=False,
        ):
            score = SequenceMatcher(
                None,
                normalize(
                    major_name
                ),
                major_norm,
            ).ratio()

            if (
                major_norm in normalize(
                    major_name
                )
                or normalize(
                    major_name
                ) in major_norm
            ):
                score += 0.6

            scored.append(
                (
                    score,
                    clean_text(
                        major_code
                    ),
                    clean_text(
                        major_name
                    ),
                    group,
                )
            )

        scored.sort(
            key=lambda item: (
                -item[0],
                item[2],
            )
        )

        exact = [item for item in scored if normalize(item[2]) == major_norm]
        selected = exact or [
            item
            for item in scored
            if item[0] >= 0.68
        ][:5]
    else:
        selected = []

        for (
            major_code,
            major_name,
        ), group in rows.groupby(
            [
                "major_code",
                "major_name",
            ],
            sort=False,
        ):
            selected.append(
                (
                    0,
                    clean_text(
                        major_code
                    ),
                    clean_text(
                        major_name
                    ),
                    group,
                )
            )

        selected = selected[:8]

    if not selected:
        return {
            "intent":
                "history",
            "text":
                (
                    f"Mình tìm thấy {school_name}, nhưng chưa tìm thấy ngành "
                    f"'{major_query}' trong chuỗi THPT đủ điều kiện ghép của trường."
                    + (" Có điểm công bố riêng theo phương thức bên dưới." if official else '')
                ),
            "cards": official[:8],
            "suggestions": [
                "Hỏi điểm chuẩn toàn trường",
            ],
        }

    cards = []

    for _, major_code, major_name, group in selected:
        cards.append(
            {
                "kind":
                    "history",
                "university_name":
                    school_name,
                "major_code":
                    major_code,
                "major_name":
                    major_name,
                "history": {year: value for year, value in _history_for_program(group).items()
                            if not requested_years or int(year) in requested_years},
                "requested_years": requested_years or YEARS,
            }
        )

    if major_query:
        text = (
            f"Đây là lịch sử điểm chuẩn THPT sạch/comparable của "
            f"{school_name} cho nhóm ngành khớp '{major_query}'. "
            "Dấu '-' nghĩa là dataset sạch không có dữ liệu năm đó."
        )
    else:
        text = (
            f"Dưới đây là dữ liệu THPT đã xác minh của {school_name}. "
            "Mình hiển thị một số ngành bên dưới; bạn có thể hỏi tiếp tên ngành cụ thể."
        )

    context[
        "school_key"
    ] = school_key
    context[
        "school_name"
    ] = school_name

    if major_query:
        context[
            "major"
        ] = major_query

    if requested_years:
        available = {int(year) for card in cards for year, value in card['history'].items() if value is not None}
        available.update(int(card['year']) for card in official)
        missing = sorted(set(requested_years) - available)
        if missing:
            text += ' Chưa có điểm công bố đã xác minh cho năm: ' + ', '.join(map(str, missing)) + '.'
        if 2027 in requested_years:
            text += ' Điểm 2027 là dự đoán, không phải điểm chuẩn công bố.'

    return {
        "intent":
            "history",
        "text":
            text,
        "cards":
            cards + official[:8],
        "suggestions": [
            "So sánh với một trường khác",
            "Dùng ngành này để tư vấn nguyện vọng",
        ],
    }


def compare_reply(
    *,
    message: str,
    context: dict,
) -> dict:
    schools = match_schools(
        message,
        limit=3,
    )

    if len(schools) < 2:
        previous_keys = context.get(
            "school_keys",
            [],
        )

        if (
            isinstance(
                previous_keys,
                list,
            )
            and len(
                previous_keys
            ) >= 2
        ):
            by_key = {
                school[
                    "university_key"
                ]: school
                for school
                in _school_catalog()
            }

            schools = [
                by_key[key]
                for key
                in previous_keys
                if key in by_key
            ][:3]

    if len(schools) < 2:
        return {
            "intent":
                "clarification",
            "text":
            "Bạn hãy ghi rõ ít nhất 2 tên trường cần so sánh.",
            "cards": [],
            "suggestions": [
                "Ví dụ: So sánh Đại học Kiến trúc Đà Nẵng và Đại học Duy Tân ngành CNTT",
            ],
        }

    df = load_program_year()

    if df.empty:
        return {
            "intent":
                "compare",
            "text":
                "Không đọc được dataset program-year để so sánh.",
            "cards": [],
            "suggestions": [],
        }

    major = extract_major(
        message
    )

    if (
        not major
        and context.get(
            "last_intent"
        ) in {
            "compare",
            "history",
            "recommendation",
        }
    ):
        major = context.get(
            "major",
            "",
        )

    cards = []

    for school in schools:
        rows = df[
            df[
                "university_key"
            ].astype(
                str
            ).eq(
                school[
                    "university_key"
                ]
            )
        ].copy()

        if rows.empty:
            continue

        score_min = pd.to_numeric(
            rows[
                "cutoff_score"
            ],
            errors="coerce",
        ).min()

        score_max = pd.to_numeric(
            rows[
                "cutoff_score"
            ],
            errors="coerce",
        ).max()

        years = sorted(
            {
                int(year)
                for year
                in pd.to_numeric(
                    rows["year"],
                    errors="coerce",
                ).dropna()
            }
        )

        card = {
            "kind":
                "compare",
            "university_key":
                school[
                    "university_key"
                ],
            "university_name":
                school[
                    "university_name"
                ],
            "program_count":
                int(
                    rows[
                        "major_code"
                    ].nunique()
                ),
            "available_years":
                years,
            "score_min":
                (
                    round(
                        float(
                            score_min
                        ),
                        2,
                    )
                    if pd.notna(
                        score_min
                    )
                    else None
                ),
            "score_max":
                (
                    round(
                        float(
                            score_max
                        ),
                        2,
                    )
                    if pd.notna(
                        score_max
                    )
                    else None
                ),
            "major":
                None,
        }

        if major:
            major_norm = normalize(
                major
            )

            candidates = []

            for (
                major_code,
                major_name,
            ), group in rows.groupby(
                [
                    "major_code",
                    "major_name",
                ],
                sort=False,
            ):
                score = SequenceMatcher(
                    None,
                    normalize(
                        major_name
                    ),
                    major_norm,
                ).ratio()

                if (
                    major_norm
                    in normalize(
                        major_name
                    )
                ):
                    score += 0.6

                candidates.append(
                    (
                        score,
                        clean_text(
                            major_code
                        ),
                        clean_text(
                            major_name
                        ),
                        group,
                    )
                )

            candidates.sort(
                key=lambda item:
                    -item[0]
            )

            if (
                candidates
                and candidates[
                    0
                ][0] >= 0.52
            ):
                best = candidates[
                    0
                ]

                card[
                    "major"
                ] = {
                    "major_code":
                        best[1],
                    "major_name":
                        best[2],
                    "history":
                        _history_for_program(
                            best[3]
                        ),
                }

        cards.append(
            card
        )

    context[
        "school_keys"
    ] = [
        school[
            "university_key"
        ]
        for school
        in schools
    ]

    if major:
        context[
            "major"
        ] = major

    text = (
        f"Mình đang so sánh {len(cards)} trường bằng dataset điểm chuẩn "
        "THPT sạch/comparable 2023-2026."
    )

    if major:
        text += (
            f" Phần ngành được đối chiếu theo '{major}'."
        )

    return {
        "intent":
            "compare",
        "text":
            text,
        "cards":
            cards,
        "suggestions": [
            "Trường nào có xu hướng điểm ổn định hơn?",
            "Dùng một trường để tra chi tiết 2023-2026",
        ],
    }


def explain_model_reply() -> dict:
    info = model_info()
    metrics = info.get(
        "metrics",
        {},
    )
    meta = info.get(
        "metadata",
        {},
    )

    method = (
        metrics.get(
            "method"
        )
        or meta.get(
            "best_method"
        )
        or meta.get(
            "method"
        )
        or "mô hình đã lưu"
    )

    parts = [
        (
            f"Phương pháp dự đoán cutoff hiện tại là {method}. "
            + ("Phương pháp này dùng điểm công bố gần nhất làm mốc dự báo. "
               "Nó được chọn trên dữ liệu 2025 và kiểm tra riêng trên 2026; "
               "đây là dự báo tham khảo, không phải điểm công bố 2027."
               if str(method).startswith("Baseline_") else
               "Mô hình được chọn trên validation 2025, kiểm tra riêng trên 2026, "
               "sau đó fit lại dữ liệu đến 2026 để dự đoán 2027.")
        )
    ]

    if metrics:
        readable = []

        for key, label in [
            (
                "mae",
                "MAE",
            ),
            (
                "rmse",
                "RMSE",
            ),
            (
                "r2",
                "R²",
            ),
            (
                "within_1_point",
                "trong ±1 điểm",
            ),
            (
                "within_2_points",
                "trong ±2 điểm",
            ),
        ]:
            value = metrics.get(
                key
            )

            if value is None:
                continue

            try:
                number = float(
                    value
                )
            except (
                TypeError,
                ValueError,
            ):
                continue

            if key.startswith(
                "within_"
            ):
                readable.append(
                    f"{label}: {number * 100:.1f}%"
                )
            else:
                readable.append(
                    f"{label}: {number:.3f}"
                )

        if readable:
            parts.append(
                "Holdout 2026: "
                + "; ".join(
                    readable
                )
                + "."
            )

    parts.append(
        "Mức AN TOÀN/PHÙ HỢP/THỬ SỨC là nhãn tư vấn dựa trên "
        "chênh lệch điểm và sai số holdout, không phải xác suất trúng tuyển."
    )

    return {
        "intent":
            "explain_model",
        "text":
            " ".join(
                parts
            ),
        "cards": [],
        "suggestions": [
            "Giải thích MAE và RMSE để hiểu hơn",
            "Tư vấn thử một hồ sơ cụ thể",
        ],
    }


def unsupported_reply(
    message: str,
) -> dict:
    unsupported = detect_unsupported(
        message
    )

    labels = (
        ", ".join(
            unsupported
        )
        if unsupported
        else "thông tin này"
    )

    return {
        "intent":
            "unsupported_data",
        "text":
            (
                f"Dataset hiện tại của UniConnect AI chưa có nguồn chuẩn cho {labels}. "
                "Mình không tự bịa số liệu. Hiện chat có thể trả lời chính xác về "
                "điểm chuẩn 2023-2026, dự đoán cutoff 2027, tổ hợp, ngành, "
                "so sánh trường và kết quả Recommendation Engine."
            ),
        "cards": [],
        "suggestions": [
            "Tra điểm chuẩn 2023-2026",
            "Tư vấn trường theo điểm",
            "So sánh 2 trường",
        ],
    }


def general_reply(
    *,
    context: dict,
    message: str = '',
) -> dict:
    enough = all(
        context.get(
            key
        ) not in (
            None,
            "",
        )
        for key in [
            "score",
            "combination",
            "major",
        ]
    )

    if enough and any(phrase in normalize(message) for phrase in ['ho so hien tai','ho so cua toi','dang nho gi']):
        return {
            "intent":
                "general",
            "text":
                (
                    "Mình đang nhớ hồ sơ hiện tại: "
                    f"{float(context['score']):g} điểm, "
                    f"{context['combination']}, "
                    f"ngành {context['major']}"
                    + (
                        f", khu vực {context['city']}"
                        if context.get(
                            "city"
                        )
                        else ""
                    )
                    + ". Bạn có thể nói 'tư vấn trường', 'đổi sang Đà Nẵng', "
                    "'đổi A00', hoặc hỏi lịch sử điểm của một trường."
                ),
            "cards": [],
            "suggestions": [
                "Tư vấn trường cho hồ sơ này",
                "Giải thích mức An toàn / Phù hợp / Thử sức",
            ],
        }

    return {
        "intent":
            "general",
        "text":
            (
                "Bạn muốn mình giúp chọn ngành, tìm trường theo điểm hay tra điểm chuẩn? "
                "Ví dụ: '24 điểm A01, thích CNTT ở Đà Nẵng thì nên chọn trường nào?'"
            ),
        "cards": [],
        "suggestions": [
            "24 điểm A01 ngành CNTT ở Đà Nẵng nên chọn trường nào?",
            "Điểm CNTT của Đại học Kiến trúc Đà Nẵng 2023-2026",
        ],
    }


def respond(
    *,
    message: str,
    previous_context: dict,
    ui_context: dict,
) -> dict:
    context = merge_context(
        message=message,
        previous=previous_context,
        ui_context=ui_context,
    )

    from .conversation import quick_reply
    quick = quick_reply(message,context)
    if quick:
        if quick.pop('_preserve_profile',False):
            quick['context'] = merge_context(message='',previous=previous_context,ui_context=ui_context)
        quick['context']['last_intent'] = quick['intent']
        return quick

    intent = detect_intent(
        message,
        context=context,
    )

    if intent == "recommendation":
        response = recommendation_reply(
            context=context,
        )
    elif intent == "aspirations":
        response = analyze_aspirations_reply(context=context)
    elif intent == "aspirations":
        response = analyze_aspirations_reply(context=context)
    elif intent == "history":
        response = history_reply(
            message=message,
            context=context,
        )
    elif intent == "compare":
        response = compare_reply(
            message=message,
            context=context,
        )
    elif intent == "explain_model":
        response = explain_model_reply()
    elif intent == "unsupported_data":
        response = unsupported_reply(
            message
        )
    elif intent == "greeting":
        response = {
            "intent":
                "greeting",
            "text":
                (
                    "Chào bạn! Mình có thể giúp bạn chọn ngành, tìm trường và tra điểm chuẩn. Bạn đang muốn tìm hiểu điều gì?"
                ),
            "cards": [],
            "suggestions": [
                "Tư vấn trường theo điểm",
                "Tra lịch sử điểm chuẩn",
                "So sánh trường",
            ],
        }
    else:
        response = general_reply(
            context=context,
            message=message,
        )

    context[
        "last_intent"
    ] = response.get(
        "intent",
        intent,
    )

    return {
        **response,
        "context":
            safe_json_value(
                context
            ),
    }
