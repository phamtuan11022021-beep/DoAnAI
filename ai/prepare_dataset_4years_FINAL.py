from __future__ import annotations

import math
import sys
import re
import statistics
import unicodedata
from pathlib import Path

import pandas as pd


# =============================================================================
# UniConnect AI - FINAL PREP DATASET 4 NĂM (2023-2026)
# =============================================================================
#
# Thiết kế sau audit thực tế:
# - Longitudinal key dùng school + major_code (PROGRAM), KHÔNG dùng nguyên danh
#   sách tổ hợp làm series key vì tổ hợp công bố có thể thay đổi theo từng năm.
# - Tổ hợp được giữ như metadata để lọc điều kiện tư vấn, không dùng để chia nhỏ
#   chuỗi điểm chuẩn theo năm.
# - Mã ngành hiển nhiên bị parser lấy nhầm thành điểm (17.0, 24.5, 33.04, ...)
#   hoặc tổ hợp (A00-A01) bị quarantine.
# - Nếu cùng school + major_code + year có NHIỀU cutoff khác nhau, KHÔNG average,
#   KHÔNG min/max: quarantine cả program-year đó.
# - Nếu nhiều dòng chỉ khác tổ hợp nhưng cùng cutoff, collapse an toàn thành 1
#   program-year và union danh sách tổ hợp.
# - Tạo feature history theo thời gian:
#       train target = 2024/2025
#       holdout test = 2026
#       prediction features = 2027
#
# CHƯA TRAIN MODEL trong file này.
# =============================================================================

YEARS = (2023, 2024, 2025, 2026)

ROOT_DIR = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
DATASET_DIR = ROOT_DIR / "data" / "dataset"
DATASET_DIR.mkdir(parents=True, exist_ok=True)

INPUT_FILES = {
    year: PROCESSED_DIR / f"admission_scores_{year}_ml_ready.csv"
    for year in YEARS
}

MERGED_AUDITED_FILE = (
    DATASET_DIR / "admission_scores_2023_2026_ml_audited.csv"
)
PROGRAM_YEAR_FILE = (
    DATASET_DIR / "admission_scores_2023_2026_program_year.csv"
)
PROGRAM_AUDIT_FILE = (
    DATASET_DIR / "admission_scores_2023_2026_program_final_audit.csv"
)
INVALID_CODE_FILE = (
    DATASET_DIR / "admission_scores_2023_2026_quarantine_invalid_code.csv"
)
AMBIGUOUS_PROGRAM_YEAR_FILE = (
    DATASET_DIR / "admission_scores_2023_2026_quarantine_ambiguous_program_year.csv"
)
FEATURE_ROWS_FILE = (
    DATASET_DIR / "admission_scores_2023_2026_model_features.csv"
)
TRAIN_FILE = (
    DATASET_DIR / "admission_scores_train_features_2024_2025.csv"
)
TEST_FILE = (
    DATASET_DIR / "admission_scores_test_features_2026.csv"
)
PREDICT_2027_FILE = (
    DATASET_DIR / "admission_scores_predict_features_2027.csv"
)
SUMMARY_FILE = (
    DATASET_DIR / "admission_scores_2023_2026_final_summary.txt"
)

REQUIRED_COLUMNS = [
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


# =============================================================================
# TEXT / KEY NORMALIZATION
# =============================================================================

def clean_text(value) -> str:
    if value is None:
        return ""

    text = str(value).replace("\xa0", " ").strip()

    if text.lower() in {"nan", "none", "<na>"}:
        return ""

    return re.sub(r"\s+", " ", text)


def strip_accents(value: str) -> str:
    value = str(value).replace("Đ", "D").replace("đ", "d")
    value = unicodedata.normalize("NFD", value)
    value = "".join(
        char
        for char in value
        if unicodedata.category(char) != "Mn"
    )
    return unicodedata.normalize("NFC", value)


def normalize_basic(value: str) -> str:
    text = strip_accents(clean_text(value)).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_school_key(value: str) -> str:
    text = normalize_basic(value)

    replacements = [
        (r"\btruong\b", ""),
        (r"\bdh\b", "dai hoc"),
        (r"\bhv\b", "hoc vien"),
        (r"\bdhqghn\b", "dai hoc quoc gia ha noi"),
        (r"\bdhqg hn\b", "dai hoc quoc gia ha noi"),
        (r"\bdhqghcm\b", "dai hoc quoc gia tp hcm"),
        (r"\bdhqg hcm\b", "dai hoc quoc gia tp hcm"),
        (r"\bdhqg tp hcm\b", "dai hoc quoc gia tp hcm"),
        (r"\btphcm\b", "tp hcm"),
        (r"\bdhtn\b", "dai hoc thai nguyen"),
    ]

    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)

    text = re.sub(r"\s+", " ", text).strip()
    # Reviewed against UNETI's primary 2025 notice: the historical abbreviation
    # 'CN' is the same institution, not a second university. Campus distinctions
    # remain in the published DKK/DKD program codes.
    # HICT's 2025 primary listing explicitly identifies its former Dệt May name:
    # https://hict.edu.vn/thong-tin-ve-ma-truong-ma-nganh-dao-tao-nam-2025-de-thi-sinh-dang-ky-xet-tuyen-tren-cong-cua-bo-gd-dt.htm
    return {'dai hoc kinh te ky thuat cn': 'dai hoc kinh te ky thuat cong nghiep',
            'dai hoc cong nghiep det may hn': 'dai hoc cong nghiep va thuong mai ha noi',
            'dai hoc cong nghiep det may ha noi': 'dai hoc cong nghiep va thuong mai ha noi'}.get(text, text)


def normalize_major_code(value: str) -> str:
    text = clean_text(value).upper()
    text = re.sub(r"\s+", "", text)

    # Safe repair: pandas may turn a genuine 7-digit code into 7140201.0.
    match = re.fullmatch(r"(\d{6,8})\.0", text)

    if match:
        return match.group(1)

    return text


def normalize_program_variant_key(value: str) -> str:
    """
    Keep the default longitudinal key as school + major_code, but split
    explicitly separate program variants that share the same national code.

    Example from the audited data:
      7420201 / Cong nghe sinh hoc - Phat trien thuoc
      7420201 / Cong nghe sinh hoc - Phat trien thuoc (Song bang)

    Those are two different admissions programs, not conflicting cutoffs for
    one program-year.
    """
    text = normalize_basic(value)

    variant_patterns = [
        ("song_bang", r"\bsong bang\b|\bdouble degree\b"),
        ("campus_hue", r"\b(?:cs|co so|phan hieu|hoc tai)\s+hue\b"),
    ]
    return '_'.join(key for key, pattern in variant_patterns if re.search(pattern, text))


def obviously_invalid_major_code(value: str) -> tuple[bool, str]:
    """
    Conservative: only reject patterns that are clearly NOT major/program codes.

    Keep legitimate alphanumeric program codes such as:
      BF-E12, IT1, ARTTECH, ASA_CO-OP, QHT01, 7340101_3.

    Reject:
      17.0 / 24.5 / 33.04  -> score accidentally used as code
      17 / 24 / 202        -> short numeric value
      A00 / B00            -> subject combination used as code
      A00-A01              -> combination list used as code
    """
    text = normalize_major_code(value)

    if not text:
        return True, "MISSING_MAJOR_CODE"

    # Genuine national numeric major codes.
    if text.isdigit():
        if 6 <= len(text) <= 8:
            return False, ""
        return True, "SHORT_NUMERIC_NOT_MAJOR_CODE"

    # Any pure numeric decimal is a strong parser-shift signal.
    if re.fullmatch(r"\d+\.\d+", text):
        return True, "DECIMAL_SCORE_USED_AS_MAJOR_CODE"

    # One or more subject-combination tokens used as code.
    if re.fullmatch(
        r"[A-Z]\d{2}(?:[-/,;|][A-Z]\d{2})+",
        text,
    ):
        return True, "COMBINATION_USED_AS_MAJOR_CODE"

    if re.fullmatch(r"[A-Z]\d{2}", text):
        return True, "SINGLE_COMBINATION_USED_AS_MAJOR_CODE"

    # Otherwise preserve program-specific codes.
    return False, ""


def text_quality(value: str) -> tuple[int, int, int]:
    text = clean_text(value)

    weird_markers = (
        "ä", "ö", "ü", "ë", "ÿ", "þ", "ð",
        "¬", "©", "®", "µ", "ø", "æ", "å",
        "chuyén", "quän", "ngir", "cöng",
    )

    weird = sum(
        text.lower().count(marker)
        for marker in weird_markers
    )

    vietnamese = sum(
        1
        for char in text
        if char in (
            "ăâđêôơư"
            "áàảãạấầẩẫậắằẳẵặ"
            "éèẻẽẹếềểễệ"
            "íìỉĩị"
            "óòỏõọốồổỗộớờởỡợ"
            "úùủũụứừửữự"
            "ýỳỷỹỵ"
            "ĂÂĐÊÔƠƯ"
            "ÁÀẢÃẠẤẦẨẪẬẮẰẲẴẶ"
            "ÉÈẺẼẸẾỀỂỄỆ"
            "ÍÌỈĨỊ"
            "ÓÒỎÕỌỐỒỔỖỘỚỜỞỠỢ"
            "ÚÙỦŨỤỨỪỬỮỰ"
            "ÝỲỶỸỴ"
        )
    )

    # Higher is better.
    return (-weird, vietnamese, len(text))


def best_text(values) -> str:
    candidates = [
        clean_text(value)
        for value in values
        if clean_text(value)
    ]

    if not candidates:
        return ""

    return max(
        candidates,
        key=text_quality,
    )


# =============================================================================
# COMBINATION METADATA
# =============================================================================

def extract_combination_codes(value: str) -> list[str]:
    """
    Extract codes such as A00, B00, D01, X26.

    Safe OCR correction:
      B0O / BO0 / BOO -> B00
    because a THPT combination code is letter + 2 digits.
    """
    text = clean_text(value).upper()

    if not text:
        return []

    tokens = re.findall(
        r"(?<![A-Z0-9])([A-Z][0-9O]{2})(?![A-Z0-9])",
        text,
    )

    output = []

    for token in tokens:
        fixed = token[0] + token[1:].replace("O", "0")

        if re.fullmatch(r"[A-Z]\d{2}", fixed):
            if fixed not in output:
                output.append(fixed)

    return sorted(output)


def union_combinations(values) -> list[str]:
    codes = set()

    for value in values:
        codes.update(
            extract_combination_codes(
                value
            )
        )

    return sorted(codes)


# =============================================================================
# LOAD LOCKED ML READY
# =============================================================================

def read_locked_year(year: int) -> pd.DataFrame:
    path = INPUT_FILES[year]

    if not path.exists():
        raise FileNotFoundError(
            f"Thiếu ML READY {year}: {path}"
        )

    df = pd.read_csv(
        path,
        dtype=str,
        keep_default_na=False,
    )

    supplement = PROCESSED_DIR / f"admission_scores_{year}_supplemental.csv"
    if supplement.exists():
        extra = pd.read_csv(supplement, dtype=str, keep_default_na=False)
        if not set(REQUIRED_COLUMNS).issubset(extra.columns):
            raise RuntimeError(f"{supplement.name}: missing canonical columns")
        if not extra["admission_method_codes"].eq("THPT").all():
            raise RuntimeError(f"{supplement.name}: only verified THPT rows allowed")
        df = pd.concat([df, extra], ignore_index=True).drop_duplicates()

    missing = [
        col
        for col in REQUIRED_COLUMNS
        if col not in df.columns
    ]

    if missing:
        raise RuntimeError(
            f"{path.name} thiếu cột {missing}"
        )

    df = df[
        REQUIRED_COLUMNS
    ].copy()

    for col in REQUIRED_COLUMNS:
        if col in {"year", "cutoff_score"}:
            continue

        df[col] = df[col].map(
            clean_text
        )

    # Reviewed metadata patches fix OCR names/missing combinations only. Never
    # replace a cutoff, invent a program-year or carry combinations across years.
    metadata_path = ROOT_DIR / "data/verified/program_metadata.csv"
    if metadata_path.exists():
        metadata = pd.read_csv(metadata_path, dtype=str, keep_default_na=False)
        keys = ["university_name", "year", "major_code"]
        if metadata.duplicated(keys).any():
            raise RuntimeError("Duplicate verified metadata keys")
        for patch in metadata[metadata.year.eq(str(year))].to_dict("records"):
            mask = (df.university_name.eq(patch["university_name"])
                    & df.major_code.eq(patch["major_code"])
                    & df.year.astype(str).eq(str(year)))
            if not mask.any() or not (ROOT_DIR / patch["evidence_path"]).is_file():
                raise RuntimeError("Verified metadata requires matching rows and saved evidence")
            df.loc[mask, "major_name"] = patch["major_name"]
            for existing in df.loc[mask, "combination"]:
                codes = set(re.findall(r"\b[A-Z]\d{2}\b", existing.upper()))
                verified = set(patch["combination"].split("|"))
                if codes and codes != verified:
                    raise RuntimeError("Conflicting combination metadata requires manual review")
            df.loc[mask, "combination"] = patch["combination"]
            df.loc[mask, "admission_note"] += " ; Metadata verified from " + patch["source_url"]

    df["year"] = pd.to_numeric(
        df["year"],
        errors="coerce",
    )

    df["cutoff_score"] = pd.to_numeric(
        df["cutoff_score"],
        errors="coerce",
    )

    if df["year"].isna().any():
        raise RuntimeError(
            f"{path.name}: year invalid."
        )

    if (
        df["year"].astype(int)
        != year
    ).any():
        raise RuntimeError(
            f"{path.name}: có row không thuộc {year}."
        )

    if df["cutoff_score"].isna().any():
        raise RuntimeError(
            f"{path.name}: cutoff_score NaN."
        )

    if not df["cutoff_score"].between(
        10,
        30,
        inclusive="both",
    ).all():
        raise RuntimeError(
            f"{path.name}: ML READY còn score ngoài [10,30]."
        )

    df["year"] = df["year"].astype(int)

    return df


def add_keys(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["university_key"] = df[
        "university_name"
    ].map(
        normalize_school_key
    )

    df["major_code_key"] = df[
        "major_code"
    ].map(
        normalize_major_code
    )

    df["program_variant_key"] = df[
        "major_name"
    ].map(
        normalize_program_variant_key
    )

    df["program_key"] = (
        df["university_key"]
        + "||"
        + df["major_code_key"]
    )

    variant_mask = df[
        "program_variant_key"
    ].ne("")

    df.loc[
        variant_mask,
        "program_key",
    ] = (
        df.loc[
            variant_mask,
            "program_key",
        ]
        + "||"
        + df.loc[
            variant_mask,
            "program_variant_key",
        ]
    )

    invalid_info = df[
        "major_code_key"
    ].map(
        obviously_invalid_major_code
    )

    df["_invalid_code"] = [
        item[0]
        for item in invalid_info
    ]
    df["_invalid_reason"] = [
        item[1]
        for item in invalid_info
    ]

    return df


# =============================================================================
# PROGRAM-YEAR BUILD
# =============================================================================

def build_program_year(
    merged: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    invalid = merged[
        merged["_invalid_code"]
    ].copy()

    clean = merged[
        ~merged["_invalid_code"]
    ].copy()

    accepted_rows = []
    ambiguous_rows = []

    group_columns = [
        "university_key",
        "major_code_key",
        "program_key",
        "year",
    ]

    for key, group in clean.groupby(
        group_columns,
        sort=True,
    ):
        scores = sorted(
            {
                round(float(value), 4)
                for value in group[
                    "cutoff_score"
                ]
            }
        )

        if len(scores) != 1:
            temp = group.copy()
            temp["quarantine_reason"] = (
                "MULTIPLE_CUTOFF_SAME_PROGRAM_YEAR"
            )
            temp["distinct_scores"] = "|".join(
                f"{score:.4f}"
                for score in scores
            )
            ambiguous_rows.append(
                temp
            )
            continue

        combinations = union_combinations(
            group["combination"]
        )

        source_urls = sorted(
            {
                clean_text(url)
                for url in group[
                    "source_url"
                ]
                if clean_text(url)
            }
        )

        notes = sorted(
            {
                clean_text(note)
                for note in group[
                    "admission_note"
                ]
                if clean_text(note)
            }
        )

        major_name_variants = sorted(
            {
                clean_text(name)
                for name in group[
                    "major_name"
                ]
                if clean_text(name)
            }
        )

        university_variants = sorted(
            {
                clean_text(name)
                for name in group[
                    "university_name"
                ]
                if clean_text(name)
            }
        )

        accepted_rows.append(
            {
                "university_name":
                    best_text(
                        university_variants
                    ),
                "university_key":
                    key[0],
                "major_code":
                    key[1],
                "major_code_key":
                    key[1],
                "major_name":
                    best_text(
                        major_name_variants
                    ),
                "major_name_variants":
                    " || ".join(
                        major_name_variants
                    ),
                "program_key":
                    key[2],
                "year":
                    int(key[3]),
                "cutoff_score":
                    scores[0],
                "eligible_combinations":
                    "|".join(
                        combinations
                    )
                    if combinations
                    else "UNSPECIFIED",
                "combination_known":
                    int(bool(combinations)),
                "combination_count":
                    len(combinations),
                "raw_row_count":
                    len(group),
                "source_count":
                    len(source_urls),
                "source_urls":
                    " || ".join(
                        source_urls
                    ),
                "admission_notes":
                    " || ".join(
                        notes
                    ),
            }
        )

    program_year = pd.DataFrame(
        accepted_rows
    )

    ambiguous = (
        pd.concat(
            ambiguous_rows,
            ignore_index=True,
        )
        if ambiguous_rows
        else pd.DataFrame(
            columns=list(merged.columns)
            + [
                "quarantine_reason",
                "distinct_scores",
            ]
        )
    )

    return (
        program_year,
        invalid,
        ambiguous,
    )


# =============================================================================
# PROGRAM AUDIT
# =============================================================================

def build_program_audit(
    program_year: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    for program_key, group in program_year.groupby(
        "program_key",
        sort=True,
    ):
        years = sorted(
            group["year"]
            .astype(int)
            .unique()
            .tolist()
        )

        rows.append(
            {
                "program_key":
                    program_key,
                "university_key":
                    group.iloc[0][
                        "university_key"
                    ],
                "major_code_key":
                    group.iloc[0][
                        "major_code_key"
                    ],
                "university_name":
                    best_text(
                        group[
                            "university_name"
                        ]
                    ),
                "major_name":
                    best_text(
                        group[
                            "major_name"
                        ]
                    ),
                "years_available":
                    ",".join(
                        map(str, years)
                    ),
                "year_count":
                    len(years),
                "has_2023":
                    int(2023 in years),
                "has_2024":
                    int(2024 in years),
                "has_2025":
                    int(2025 in years),
                "has_2026":
                    int(2026 in years),
                "is_4year_program":
                    int(
                        all(
                            year in years
                            for year in YEARS
                        )
                    ),
            }
        )

    return pd.DataFrame(
        rows
    )


# =============================================================================
# HISTORY FEATURES
# =============================================================================

def major_group(code: str) -> str:
    code = normalize_major_code(
        code
    )

    numeric = re.match(
        r"^(\d{3})",
        code,
    )

    if numeric:
        return numeric.group(1)

    alpha = re.match(
        r"^([A-Z]{1,4})",
        code,
    )

    if alpha:
        return alpha.group(1)

    return "OTHER"


def linear_trend(
    years: list[int],
    scores: list[float],
) -> float:
    if len(years) < 2:
        return 0.0

    x_mean = sum(years) / len(years)
    y_mean = sum(scores) / len(scores)

    denominator = sum(
        (x - x_mean) ** 2
        for x in years
    )

    if denominator == 0:
        return 0.0

    numerator = sum(
        (x - x_mean)
        * (y - y_mean)
        for x, y in zip(
            years,
            scores,
        )
    )

    return numerator / denominator


def history_feature_record(
    *,
    program_key: str,
    target_year: int,
    history: pd.DataFrame,
    target_row: pd.Series | None,
) -> dict:
    history = history.sort_values(
        "year"
    )

    years = (
        history["year"]
        .astype(int)
        .tolist()
    )

    scores = (
        history["cutoff_score"]
        .astype(float)
        .tolist()
    )

    last = history.iloc[-1]
    first = history.iloc[0]

    if len(scores) >= 2:
        prev2 = scores[-2]
        prev2_year = years[-2]
        last_delta_per_year = (
            scores[-1] - scores[-2]
        ) / max(
            1,
            years[-1] - years[-2],
        )
    else:
        prev2 = scores[-1]
        prev2_year = years[-1]
        last_delta_per_year = 0.0

    std_score = (
        statistics.pstdev(scores)
        if len(scores) >= 2
        else 0.0
    )

    row = {
        "program_key":
            program_key,
        "university_key":
            last["university_key"],
        "major_code_key":
            last["major_code_key"],
        "major_group":
            major_group(
                last[
                    "major_code_key"
                ]
            ),
        "university_name":
            last["university_name"],
        "major_name":
            last["major_name"],
        "target_year":
            int(target_year),
        "history_count":
            len(scores),
        "first_year":
            int(years[0]),
        "last_year":
            int(years[-1]),
        "gap_years":
            int(
                target_year
                - years[-1]
            ),
        "history_span":
            int(
                years[-1]
                - years[0]
            ),
        "last_score":
            float(scores[-1]),
        "prev2_score":
            float(prev2),
        "prev2_year":
            int(prev2_year),
        "mean_score":
            float(
                sum(scores)
                / len(scores)
            ),
        "min_score":
            float(min(scores)),
        "max_score":
            float(max(scores)),
        "std_score":
            float(std_score),
        "trend_per_year":
            float(
                linear_trend(
                    years,
                    scores,
                )
            ),
        "last_delta_per_year":
            float(
                last_delta_per_year
            ),
        "last_combination_count":
            int(
                last[
                    "combination_count"
                ]
            ),
        "last_combination_known":
            int(
                last[
                    "combination_known"
                ]
            ),
        "last_eligible_combinations":
            last[
                "eligible_combinations"
            ],
    }

    if target_row is not None:
        row["cutoff_score"] = float(
            target_row[
                "cutoff_score"
            ]
        )
        row[
            "target_eligible_combinations"
        ] = target_row[
            "eligible_combinations"
        ]
        row[
            "target_combination_count"
        ] = int(
            target_row[
                "combination_count"
            ]
        )
    else:
        row["cutoff_score"] = ""
        row[
            "target_eligible_combinations"
        ] = ""
        row[
            "target_combination_count"
        ] = ""

    return row


def build_feature_rows(
    program_year: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
]:
    supervised = []
    predict_2027 = []

    for program_key, group in program_year.groupby(
        "program_key",
        sort=True,
    ):
        group = group.sort_values(
            "year"
        ).reset_index(drop=True)

        for idx in range(
            1,
            len(group),
        ):
            target = group.iloc[idx]
            history = group.iloc[:idx]

            supervised.append(
                history_feature_record(
                    program_key=
                        program_key,
                    target_year=
                        int(
                            target[
                                "year"
                            ]
                        ),
                    history=
                        history,
                    target_row=
                        target,
                )
            )

        # 2027 inference row using every accepted historical year through 2026.
        if not group.empty:
            predict_2027.append(
                history_feature_record(
                    program_key=
                        program_key,
                    target_year=
                        2027,
                    history=
                        group,
                    target_row=
                        None,
                )
            )

    return (
        pd.DataFrame(
            supervised
        ),
        pd.DataFrame(
            predict_2027
        ),
    )


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    print("=" * 122)
    print("UNICONNECT AI - FINAL PREP DATASET 2023-2026")
    print("=" * 122)

    frames = []

    for year in YEARS:
        df = read_locked_year(
            year
        )

        print(
            f"{year} ML READY            : "
            f"{len(df):5d} rows / "
            f"{df['university_name'].nunique():3d} trường"
        )

        frames.append(
            df
        )

    merged = pd.concat(
        frames,
        ignore_index=True,
    )

    merged = add_keys(
        merged
    )

    # Exact source-level duplicates only.
    before = len(merged)

    merged = (
        merged.drop_duplicates(
            subset=[
                "university_name",
                "major_code",
                "major_name",
                "year",
                "combination",
                "cutoff_score",
                "source_url",
            ],
            keep="first",
        )
        .reset_index(drop=True)
    )

    exact_removed = (
        before
        - len(merged)
    )

    program_year, invalid_code, ambiguous = build_program_year(
        merged
    )

    program_audit = build_program_audit(
        program_year
    )

    feature_rows, predict_2027 = build_feature_rows(
        program_year
    )

    train = feature_rows[
        feature_rows[
            "target_year"
        ].isin(
            [2024, 2025]
        )
    ].copy()

    test = feature_rows[
        feature_rows[
            "target_year"
        ].eq(2026)
    ].copy()

    # Hard temporal safety audit.
    if not train.empty and (
        train["last_year"]
        >= train["target_year"]
    ).any():
        raise RuntimeError(
            "TEMPORAL LEAK: train last_year >= target_year."
        )

    if not test.empty and (
        test["last_year"]
        >= test["target_year"]
    ).any():
        raise RuntimeError(
            "TEMPORAL LEAK: test last_year >= target_year."
        )

    # 2026 holdout must never be in train.
    if (
        train[
            "target_year"
        ].eq(2026)
    ).any():
        raise RuntimeError(
            "TEMPORAL LEAK: 2026 appeared in training."
        )

    # Save.
    merged.to_csv(
        MERGED_AUDITED_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    program_year.to_csv(
        PROGRAM_YEAR_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    program_audit.to_csv(
        PROGRAM_AUDIT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    invalid_code.to_csv(
        INVALID_CODE_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    ambiguous.to_csv(
        AMBIGUOUS_PROGRAM_YEAR_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    feature_rows.to_csv(
        FEATURE_ROWS_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    train.to_csv(
        TRAIN_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    test.to_csv(
        TEST_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    predict_2027.to_csv(
        PREDICT_2027_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    programs_2plus = int(
        (
            program_audit[
                "year_count"
            ] >= 2
        ).sum()
    )

    programs_3plus = int(
        (
            program_audit[
                "year_count"
            ] >= 3
        ).sum()
    )

    programs_4year = int(
        program_audit[
            "is_4year_program"
        ].sum()
    )

    invalid_programs = (
        invalid_code[
            "program_key"
        ].nunique()
        if not invalid_code.empty
        else 0
    )

    ambiguous_program_years = (
        ambiguous[
            [
                "program_key",
                "year",
            ]
        ].drop_duplicates().shape[0]
        if not ambiguous.empty
        else 0
    )

    summary = [
        "UNICONNECT AI - FINAL DATASET PREP 2023-2026",
        "=" * 80,
        f"INPUT MERGED ROWS                : {len(merged)}",
        f"EXACT DUPLICATES REMOVED         : {exact_removed}",
        f"INVALID-CODE ROWS QUARANTINED    : {len(invalid_code)}",
        f"INVALID-CODE PROGRAMS            : {invalid_programs}",
        f"AMBIGUOUS ROWS QUARANTINED       : {len(ambiguous)}",
        f"AMBIGUOUS PROGRAM-YEARS          : {ambiguous_program_years}",
        f"CLEAN PROGRAM-YEAR ROWS          : {len(program_year)}",
        f"CLEAN PROGRAMS                    : {program_year['program_key'].nunique()}",
        f"PROGRAMS >=2 YEARS               : {programs_2plus}",
        f"PROGRAMS >=3 YEARS               : {programs_3plus}",
        f"PROGRAMS FULL 4 YEARS            : {programs_4year}",
        "",
        f"SUPERVISED FEATURE ROWS          : {len(feature_rows)}",
        f"TRAIN TARGET 2024-2025           : {len(train)}",
        f"TEST HOLDOUT 2026                : {len(test)}",
        f"PREDICTABLE PROGRAMS FOR 2027    : {len(predict_2027)}",
        "",
        "RULES:",
        "- program_key = normalized school + major_code.",
        "- combination is eligibility metadata, not longitudinal series identity.",
        "- no averaging of conflicting cutoff scores in same program-year.",
        "- 2026 is holdout only; no 2026 target row appears in training.",
        "- prediction target after evaluation is 2027.",
    ]

    SUMMARY_FILE.write_text(
        "\n".join(summary),
        encoding="utf-8",
    )

    print()
    print("=" * 122)
    print("KẾT QUẢ FINAL PREP DATASET")
    print("=" * 122)
    print(
        f"INPUT MERGED            : {len(merged):5d} rows"
    )
    print(
        f"EXACT DUP REMOVED       : {exact_removed:5d}"
    )
    print(
        f"INVALID CODE QUARANTINE : {len(invalid_code):5d} rows / "
        f"{invalid_programs:4d} programs"
    )
    print(
        f"AMBIGUOUS QUARANTINE    : {len(ambiguous):5d} rows / "
        f"{ambiguous_program_years:4d} program-years"
    )
    print(
        f"CLEAN PROGRAM-YEAR      : {len(program_year):5d} rows / "
        f"{program_year['program_key'].nunique():4d} programs"
    )
    print(
        f"PROGRAMS >=2 YEARS      : {programs_2plus:5d}"
    )
    print(
        f"PROGRAMS >=3 YEARS      : {programs_3plus:5d}"
    )
    print(
        f"PROGRAMS FULL 4 YEARS   : {programs_4year:5d}"
    )
    print(
        f"FEATURE ROWS            : {len(feature_rows):5d}"
    )
    print(
        f"TRAIN 2024-2025         : {len(train):5d} rows"
    )
    print(
        f"TEST HOLDOUT 2026       : {len(test):5d} rows"
    )
    print(
        f"PREDICT 2027 FEATURES   : {len(predict_2027):5d} programs"
    )
    print("-" * 122)
    print("PROGRAM-YEAR :", PROGRAM_YEAR_FILE)
    print("PROGRAM AUDIT:", PROGRAM_AUDIT_FILE)
    print("INVALID CODE :", INVALID_CODE_FILE)
    print("AMBIGUOUS    :", AMBIGUOUS_PROGRAM_YEAR_FILE)
    print("FEATURES     :", FEATURE_ROWS_FILE)
    print("TRAIN        :", TRAIN_FILE)
    print("TEST 2026    :", TEST_FILE)
    print("PREDICT 2027 :", PREDICT_2027_FILE)
    print("SUMMARY      :", SUMMARY_FILE)
    print("=" * 122)

    print()
    print(
        "FINAL PREP CHECKPOINT   : ✅ PROGRAM-LEVEL + TEMPORAL-SAFE, CHƯA TRAIN"
    )


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
