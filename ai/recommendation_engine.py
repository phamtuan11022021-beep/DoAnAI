from __future__ import annotations

import argparse
import json
import math
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd


# =============================================================================
# UniConnect AI - RECOMMENDATION ENGINE 2027
# =============================================================================
#
# Dữ liệu sử dụng:
#   - predicted_cutoff_2027.csv
#   - cutoff_predictions_2026_holdout.csv
#   - cutoff_model_metrics_2026_holdout.csv
#   - admission_scores_test_features_2026.csv
#   - best_cutoff_model_metadata.json
#
# Đầu vào:
#   - Điểm THPT của học sinh
#   - Tổ hợp xét tuyển
#   - Ngành / mã ngành mong muốn
#   - Thành phố (chỉ khi có metadata trường đã xác minh)
#
# Đầu ra:
#   - Danh sách trường/ngành phù hợp
#   - Điểm chuẩn dự đoán 2027
#   - Khoảng chênh điểm
#   - Mức: AN TOÀN / PHÙ HỢP / THỬ SỨC / RỦI RO CAO
#   - Độ tin cậy dữ liệu lịch sử
#
# QUAN TRỌNG:
# - Recommendation level KHÔNG phải xác suất đỗ.
# - Ngưỡng phân loại được hiệu chỉnh bằng sai số holdout 2026, không hard-code
#   tùy ý.
# - Tổ hợp mặc định kiểm tra STRICT: nếu source gần nhất không xác nhận tổ hợp,
#   chương trình đó không được đưa vào danh sách chính.
# - Không tự suy diễn tỉnh/thành. Nếu user dùng --city mà chưa có
#   university_locations.csv thì dừng rõ ràng.
# =============================================================================

ROOT_DIR = Path(__file__).resolve().parents[1]
DATASET_DIR = ROOT_DIR / "data" / "dataset"
MODEL_DIR = ROOT_DIR / "ai" / "models"

PREDICTION_FILE = DATASET_DIR / "predicted_cutoff_2027.csv"
HOLDOUT_PRED_FILE = DATASET_DIR / "cutoff_predictions_2026_holdout.csv"
METRICS_FILE = DATASET_DIR / "cutoff_model_metrics_2026_holdout.csv"
TEST_FEATURE_FILE = DATASET_DIR / "admission_scores_test_features_2026.csv"
MODEL_META_FILE = MODEL_DIR / "best_cutoff_model_metadata.json"

# Optional metadata. Chỉ dùng nếu bạn đã tạo/kiểm chứng file này sau.
LOCATION_FILE = DATASET_DIR / "university_locations.csv"

OUTPUT_FILE = DATASET_DIR / "recommendations_latest.csv"

EXPECTED_PREDICTION_COLUMNS = [
    "program_key",
    "university_name",
    "major_code_key",
    "major_name",
    "target_year",
    "history_count",
    "last_year",
    "last_score",
    "mean_score",
    "trend_per_year",
    "last_eligible_combinations",
    "predicted_cutoff_2027",
]


# =============================================================================
# TEXT HELPERS
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


def normalize_text(value: str) -> str:
    text = strip_accents(clean_text(value)).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_combination(value: str) -> str:
    value = clean_text(value).upper().replace("O", "0")

    if not re.fullmatch(r"[A-Z]\d{2}", value):
        raise ValueError(
            "Tổ hợp phải có dạng như A00, A01, B00, C00, D01..."
        )

    return value


def normalize_major_code(value: str) -> str:
    return re.sub(
        r"\s+",
        "",
        clean_text(value).upper(),
    )


# =============================================================================
# FILE LOADERS
# =============================================================================

def require_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(
            f"Thiếu file bắt buộc: {path}"
        )


def load_predictions() -> pd.DataFrame:
    require_file(PREDICTION_FILE)

    df = pd.read_csv(
        PREDICTION_FILE,
        dtype=str,
        keep_default_na=False,
    )

    missing = [
        col
        for col in EXPECTED_PREDICTION_COLUMNS
        if col not in df.columns
    ]

    if missing:
        raise RuntimeError(
            f"{PREDICTION_FILE.name} thiếu cột: {missing}"
        )

    numeric_columns = [
        "target_year",
        "history_count",
        "last_year",
        "last_score",
        "mean_score",
        "trend_per_year",
        "predicted_cutoff_2027",
    ]

    for col in numeric_columns:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce",
        )

    if df[numeric_columns].isna().any().any():
        raise RuntimeError(
            "predicted_cutoff_2027.csv có numeric field NaN."
        )

    if not df[
        "predicted_cutoff_2027"
    ].between(
        10,
        30,
        inclusive="both",
    ).all():
        raise RuntimeError(
            "predicted_cutoff_2027 có điểm ngoài [10,30]."
        )

    df["major_name_norm"] = df[
        "major_name"
    ].map(
        normalize_text
    )

    df["major_code_norm"] = df[
        "major_code_key"
    ].map(
        normalize_major_code
    )

    # predicted_cutoff_2027.csv hiện không lưu riêng university_key.
    # program_key đã có cấu trúc:
    #     university_key||major_code
    # nên tách trực tiếp từ đó để đồng bộ tuyệt đối với
    # university_locations.csv, tránh tự normalize lại tên trường.
    if "university_key" not in df.columns:
        if "program_key" not in df.columns:
            raise RuntimeError(
                "predicted_cutoff_2027.csv thiếu cả university_key và program_key."
            )

        df["university_key"] = (
            df["program_key"]
            .astype(str)
            .str.split("||", n=1, regex=False)
            .str[0]
            .str.strip()
        )

    if df["university_key"].eq("").any():
        raise RuntimeError(
            "predicted_cutoff_2027.csv có university_key rỗng."
        )

    return df


def load_best_method() -> str:
    require_file(METRICS_FILE)

    metrics = pd.read_csv(
        METRICS_FILE
    )

    required = {
        "method",
        "mae",
        "rmse",
    }

    if not required.issubset(
        metrics.columns
    ):
        raise RuntimeError(
            "cutoff_model_metrics_2026_holdout.csv thiếu method/mae/rmse."
        )

    metrics["mae"] = pd.to_numeric(
        metrics["mae"],
        errors="coerce",
    )

    metrics["rmse"] = pd.to_numeric(
        metrics["rmse"],
        errors="coerce",
    )

    metrics = metrics.dropna(
        subset=["mae", "rmse"]
    ).sort_values(
        ["mae", "rmse"],
        ascending=[True, True],
    )

    if metrics.empty:
        raise RuntimeError(
            "Không xác định được best method từ metrics."
        )

    # Calibration must follow the method actually deployed, selected on 2025.
    if MODEL_META_FILE.exists():
        metadata = json.loads(MODEL_META_FILE.read_text(encoding="utf-8"))
        selected = metadata.get("best_overall_method")
        if selected in set(metrics["method"]):
            return clean_text(selected)

    return clean_text(
        metrics.iloc[0]["method"]
    )


# =============================================================================
# ERROR CALIBRATION
# =============================================================================

def quantile(values: pd.Series, q: float) -> float:
    return float(
        values.quantile(
            q,
            interpolation="linear",
        )
    )


def load_error_calibration() -> tuple[
    dict,
    dict[int, dict],
]:
    """
    Calibrate error against the exact method used as BEST OVERALL on 2026.

    Returns:
      global_quantiles
      quantiles_by_history_count

    Per-history bucket is used only when >= 30 holdout observations.
    Otherwise recommendation falls back to global quantiles.
    """
    require_file(HOLDOUT_PRED_FILE)
    require_file(TEST_FEATURE_FILE)

    best_method = load_best_method()

    prediction_column = (
        f"pred_{best_method}"
    )

    holdout = pd.read_csv(
        HOLDOUT_PRED_FILE,
        dtype=str,
        keep_default_na=False,
    )

    if prediction_column not in holdout.columns:
        raise RuntimeError(
            f"Holdout không có cột {prediction_column}."
        )

    required_holdout = {
        "program_key",
        "actual_cutoff_2026",
        prediction_column,
    }

    if not required_holdout.issubset(
        holdout.columns
    ):
        raise RuntimeError(
            "Holdout predictions thiếu cột cần cho calibration."
        )

    test_features = pd.read_csv(
        TEST_FEATURE_FILE,
        dtype=str,
        keep_default_na=False,
        usecols=[
            "program_key",
            "history_count",
        ],
    )

    holdout[
        "actual_cutoff_2026"
    ] = pd.to_numeric(
        holdout[
            "actual_cutoff_2026"
        ],
        errors="coerce",
    )

    holdout[
        prediction_column
    ] = pd.to_numeric(
        holdout[
            prediction_column
        ],
        errors="coerce",
    )

    holdout = holdout.dropna(
        subset=[
            "actual_cutoff_2026",
            prediction_column,
        ]
    )

    holdout["abs_error"] = (
        holdout[
            "actual_cutoff_2026"
        ]
        - holdout[
            prediction_column
        ]
    ).abs()

    test_features[
        "history_count"
    ] = pd.to_numeric(
        test_features[
            "history_count"
        ],
        errors="coerce",
    )

    calibration = holdout.merge(
        test_features,
        on="program_key",
        how="left",
        validate="many_to_one",
    )

    global_quantiles = {
        "best_method":
            best_method,
        "n":
            int(len(calibration)),
        "q50":
            quantile(
                calibration[
                    "abs_error"
                ],
                0.50,
            ),
        "q80":
            quantile(
                calibration[
                    "abs_error"
                ],
                0.80,
            ),
        "q90":
            quantile(
                calibration[
                    "abs_error"
                ],
                0.90,
            ),
    }

    by_history = {}

    for history_count, group in calibration.groupby(
        "history_count"
    ):
        if pd.isna(history_count):
            continue

        history_count = int(
            history_count
        )

        if len(group) < 30:
            continue

        by_history[
            history_count
        ] = {
            "n":
                int(len(group)),
            "q50":
                quantile(
                    group[
                        "abs_error"
                    ],
                    0.50,
                ),
            "q80":
                quantile(
                    group[
                        "abs_error"
                    ],
                    0.80,
                ),
            "q90":
                quantile(
                    group[
                        "abs_error"
                    ],
                    0.90,
                ),
        }

    return (
        global_quantiles,
        by_history,
    )


def thresholds_for_history(
    history_count: int,
    global_quantiles: dict,
    by_history: dict[int, dict],
) -> dict:
    bucket = by_history.get(
        int(history_count)
    )

    if bucket is None:
        return {
            **global_quantiles,
            "calibration_scope":
                "GLOBAL",
        }

    return {
        **bucket,
        "best_method":
            global_quantiles[
                "best_method"
            ],
        "calibration_scope":
            f"HISTORY_{int(history_count)}",
    }


# =============================================================================
# MAJOR MATCHING
# =============================================================================

def token_set(value: str) -> set[str]:
    return {
        token
        for token in normalize_text(
            value
        ).split()
        if token
    }


def major_similarity(
    query: str,
    major_name: str,
) -> float:
    query_norm = normalize_text(
        query
    )
    name_norm = normalize_text(
        major_name
    )

    if not query_norm or not name_norm:
        return 0.0

    if query_norm == name_norm:
        return 1.0

    if (
        query_norm in name_norm
        or name_norm in query_norm
    ):
        # Avoid giving all substring matches exactly 1.0;
        # exact name remains strongest.
        length_ratio = (
            min(
                len(query_norm),
                len(name_norm),
            )
            / max(
                len(query_norm),
                len(name_norm),
            )
        )

        return min(
            0.98,
            0.88
            + 0.10
            * length_ratio,
        )

    query_tokens = token_set(
        query_norm
    )
    name_tokens = token_set(
        name_norm
    )

    if not query_tokens or not name_tokens:
        return 0.0

    intersection = len(
        query_tokens
        & name_tokens
    )

    token_recall = (
        intersection
        / len(query_tokens)
    )

    token_precision = (
        intersection
        / len(name_tokens)
    )

    token_f1 = (
        2
        * token_precision
        * token_recall
        / max(
            1e-9,
            token_precision
            + token_recall,
        )
    )

    sequence = SequenceMatcher(
        None,
        query_norm,
        name_norm,
    ).ratio()

    return (
        0.60
        * token_f1
        + 0.40
        * sequence
    )


def filter_major(
    df: pd.DataFrame,
    *,
    major_query: str,
    major_code: str,
) -> pd.DataFrame:
    if major_code:
        code = normalize_major_code(
            major_code
        )

        result = df[
            df[
                "major_code_norm"
            ].eq(
                code
            )
        ].copy()

        result[
            "major_similarity"
        ] = 1.0

        return result

    query = clean_text(
        major_query
    )
    aliases = {"cntt": "Công nghệ thông tin", "it": "Công nghệ thông tin",
               "khmt": "Khoa học máy tính", "ktpm": "Kỹ thuật phần mềm"}
    query = aliases.get(normalize_text(query), query)

    if not query:
        raise ValueError(
            "Phải nhập tên ngành hoặc --major-code."
        )

    result = df.copy()

    result[
        "major_similarity"
    ] = result[
        "major_name"
    ].map(
        lambda name:
            major_similarity(
                query,
                name,
            )
    )

    # Standard degree codes survive OCR errors in names. Only the exact major
    # family is included; never fuzzy-match a neighboring subject by its code.
    standard_codes = {"cong nghe thong tin": "7480201",
                      "khoa hoc may tinh": "7480101",
                      "ky thuat phan mem": "7480103",
                      "quan tri kinh doanh": "7340101",
                      "marketing": "7340115",
                      "ke toan": "7340301",
                      "tai chinh ngan hang": "7340201",
                      "kinh doanh quoc te": "7340120"}
    base_code = standard_codes.get(normalize_text(query))
    if base_code:
        code_match = result["major_code_norm"].str.fullmatch(base_code + r"(?:[A-Z_.-][A-Z0-9_.-]*)?")
        result.loc[code_match, "major_similarity"] = 1.0
        # A valid national code for another major overrides a corrupt OCR name.
        national_code = result["major_code_norm"].str.match(r"^7\d{6}(?:$|[A-Z_.-])")
        result.loc[national_code & ~code_match, "major_similarity"] = 0.0

    # Conservative fuzzy threshold.
    result = result[
        result[
            "major_similarity"
        ] >= 0.68
    ].copy()

    return result


# =============================================================================
# COMBINATION + LOCATION FILTERING
# =============================================================================

def combination_status(
    eligible_value: str,
    combination: str,
) -> str:
    text = clean_text(
        eligible_value
    ).upper()

    if not text or text == "UNSPECIFIED":
        return "UNVERIFIED"

    codes = set(
        re.findall(
            r"\b[A-Z]\d{2}\b",
            text,
        )
    )

    if combination in codes:
        return "VERIFIED"

    return "NOT_ELIGIBLE"


def apply_combination_filter(
    df: pd.DataFrame,
    *,
    combination: str,
    allow_unspecified: bool,
) -> tuple[
    pd.DataFrame,
    dict,
]:
    statuses = df[
        "last_eligible_combinations"
    ].map(
        lambda value:
            combination_status(
                value,
                combination,
            )
    )

    result = df.copy()
    result[
        "combination_status"
    ] = statuses

    counts = statuses.value_counts(
        dropna=False
    ).to_dict()

    allowed = {
        "VERIFIED"
    }

    if allow_unspecified:
        allowed.add(
            "UNVERIFIED"
        )

    result = result[
        result[
            "combination_status"
        ].isin(
            allowed
        )
    ].copy()

    return result, counts


def apply_location_filter(
    df: pd.DataFrame,
    *,
    city: str,
) -> pd.DataFrame:
    city = clean_text(
        city
    )

    if not city:
        return df

    if not LOCATION_FILE.exists():
        raise RuntimeError(
            "Bạn yêu cầu lọc tỉnh/thành nhưng dự án chưa có "
            "data/dataset/university_locations.csv đã xác minh. "
            "Engine cố ý KHÔNG đoán vị trí trường. "
            "Hãy bổ sung metadata địa điểm trước khi dùng --city."
        )

    location = pd.read_csv(
        LOCATION_FILE,
        dtype=str,
        keep_default_na=False,
    )

    required = {
        "university_key",
        "city",
    }

    if not required.issubset(
        location.columns
    ):
        raise RuntimeError(
            "university_locations.csv phải có university_key,city."
        )

    location[
        "city_norm"
    ] = location[
        "city"
    ].map(
        normalize_text
    )

    target = normalize_text(
        city
    )

    location = location[
        location[
            "city_norm"
        ].eq(
            target
        )
    ].copy()

    allowed_keys = set(
        location[
            "university_key"
        ]
    )

    allowed = df["university_key"].isin(allowed_keys)
    # A school's main address does not locate its branch-specific programs.
    # Reviewed rules override the school location, including cities where the
    # institution has no main-campus location row.
    program_locations = DATASET_DIR / "program_location_rules.csv"
    if program_locations.exists():
        rules = pd.read_csv(program_locations, dtype=str, keep_default_na=False)
        codes = df["major_code_key"].map(normalize_major_code)
        for rule in rules.to_dict("records"):
            applies = (df["university_key"].eq(rule["university_key"])
                       & codes.str.fullmatch(rule["major_code_pattern"]))
            if rule.get('major_name_pattern'):
                names = df.get('major_name', pd.Series('', index=df.index)).map(normalize_text)
                applies &= names.str.contains(rule['major_name_pattern'], regex=True, na=False)
            allowed.loc[applies] = normalize_text(rule["city"]) == target
    result = df[allowed].copy()

    return result


# =============================================================================
# RECOMMENDATION LEVEL
# =============================================================================

def history_reliability(
    history_count: int,
) -> str:
    history_count = int(
        history_count
    )

    if history_count >= 4:
        return "CAO"

    if history_count == 3:
        return "KHÁ"

    if history_count == 2:
        return "TRUNG BÌNH"

    return "THẤP"



def data_freshness(last_year: int) -> tuple[str, int]:
    """
    Freshness của dữ liệu thực tế gần nhất.

    2026 -> CURRENT
    2025 -> STALE_1Y
    <=2024 -> STALE_2Y_PLUS
    """
    last_year = int(last_year)

    if last_year >= 2026:
        return "CURRENT_2026", 0

    if last_year == 2025:
        return "STALE_1Y", 1

    return "STALE_2Y_PLUS", 2


def combined_reliability(
    history_count: int,
    last_year: int,
) -> str:
    """
    Reliability = chiều dài lịch sử + độ mới dữ liệu.

    Không để trường có 3 năm lịch sử nhưng dừng ở 2025
    được đánh giá cao hơn trường có dữ liệu thực tế 2026.
    """
    freshness, stale_years = data_freshness(
        last_year
    )

    if stale_years >= 2:
        return "THẤP"

    if stale_years == 1:
        if history_count >= 3:
            return "TRUNG BÌNH"
        return "THẤP"

    # Current through 2026.
    if history_count >= 4:
        return "CAO"

    if history_count == 3:
        return "KHÁ"

    if history_count == 2:
        return "TRUNG BÌNH"

    return "THẤP"


def classify_level(
    *,
    student_score: float,
    predicted_score: float,
    q50: float,
    q80: float,
) -> tuple[str, int]:
    """
    Empirically calibrated categories.

    AN TOÀN:
      score >= prediction + q80

    PHÙ HỢP:
      prediction - q50 <= score < prediction + q80

    THỬ SỨC:
      prediction - q80 <= score < prediction - q50

    RỦI RO CAO:
      below prediction - q80

    Đây là mức tư vấn, KHÔNG phải xác suất trúng tuyển.
    """
    gap = (
        student_score
        - predicted_score
    )

    if gap >= q80:
        return "AN TOÀN", 1

    if gap >= -q50:
        return "PHÙ HỢP", 2

    if gap >= -q80:
        return "THỬ SỨC", 3

    return "RỦI RO CAO", 4


# =============================================================================
# MAIN RECOMMENDER
# =============================================================================

def recommend(
    *,
    score: float,
    combination: str,
    major_query: str = "",
    major_code: str = "",
    city: str = "",
    top_n: int = 20,
    allow_unspecified_combination: bool = False,
    allow_stale_history: bool = False,
) -> tuple[
    pd.DataFrame,
    dict,
]:
    if not (
        0.0 <= float(score) <= 30.0
    ):
        raise ValueError(
            "Điểm THPT phải nằm trong khoảng 0-30."
        )

    combination = normalize_combination(
        combination
    )

    predictions = load_predictions()

    global_quantiles, by_history = (
        load_error_calibration()
    )

    major_filtered = filter_major(
        predictions,
        major_query=major_query,
        major_code=major_code,
    )

    if major_filtered.empty:
        return (
            pd.DataFrame(),
            {
                "reason":
                    "NO_MAJOR_MATCH",
                "global_calibration":
                    global_quantiles,
            },
        )

    combo_filtered, combo_counts = (
        apply_combination_filter(
            major_filtered,
            combination=combination,
            allow_unspecified=
                allow_unspecified_combination,
        )
    )

    if combo_filtered.empty:
        return (
            pd.DataFrame(),
            {
                "reason":
                    "NO_COMBINATION_MATCH",
                "major_match_count":
                    len(
                        major_filtered
                    ),
                "combination_counts":
                    combo_counts,
                "global_calibration":
                    global_quantiles,
            },
        )

    location_filtered = apply_location_filter(
        combo_filtered,
        city=city,
    )

    if location_filtered.empty:
        return (
            pd.DataFrame(),
            {
                "reason":
                    "NO_LOCATION_MATCH",
                "major_match_count":
                    len(
                        major_filtered
                    ),
                "combination_counts":
                    combo_counts,
                "global_calibration":
                    global_quantiles,
            },
        )

    # Production default: chỉ tư vấn chính từ chương trình có actual data 2026.
    # Nếu cần nghiên cứu coverage cũ thì user có thể bật --allow-stale-history.
    if not allow_stale_history:
        freshness_filtered = location_filtered[
            pd.to_numeric(
                location_filtered["last_year"],
                errors="coerce",
            ).eq(2026)
        ].copy()
    else:
        freshness_filtered = location_filtered.copy()

    if freshness_filtered.empty:
        return (
            pd.DataFrame(),
            {
                "reason": "NO_FRESH_2026_HISTORY",
                "major_match_count": len(major_filtered),
                "combination_counts": combo_counts,
                "global_calibration": global_quantiles,
            },
        )

    rows = []

    for _, row in freshness_filtered.iterrows():
        history_count = int(
            row[
                "history_count"
            ]
        )

        thresholds = thresholds_for_history(
            history_count,
            global_quantiles,
            by_history,
        )

        predicted = float(
            row[
                "predicted_cutoff_2027"
            ]
        )

        level, level_rank = classify_level(
            student_score=float(
                score
            ),
            predicted_score=predicted,
            q50=float(
                thresholds[
                    "q50"
                ]
            ),
            q80=float(
                thresholds[
                    "q80"
                ]
            ),
        )

        gap = (
            float(score)
            - predicted
        )

        rows.append(
            {
                "university_name":
                    row[
                        "university_name"
                    ],
                "major_code":
                    row[
                        "major_code_key"
                    ],
                "major_name":
                    row[
                        "major_name"
                    ],
                "major_similarity":
                    round(
                        float(
                            row[
                                "major_similarity"
                            ]
                        ),
                        4,
                    ),
                "student_score":
                    round(
                        float(score),
                        2,
                    ),
                "combination":
                    combination,
                "combination_status":
                    row[
                        "combination_status"
                    ],
                "eligible_combinations":
                    row[
                        "last_eligible_combinations"
                    ],
                "predicted_cutoff_2027":
                    round(
                        predicted,
                        2,
                    ),
                "score_gap":
                    round(
                        gap,
                        2,
                    ),
                "recommendation_level":
                    level,
                "_level_rank":
                    level_rank,
                "history_count":
                    history_count,
                "history_reliability":
                    combined_reliability(
                        history_count,
                        int(row["last_year"]),
                    ),
                "data_freshness":
                    data_freshness(
                        int(row["last_year"])
                    )[0],
                "last_actual_year":
                    int(
                        row[
                            "last_year"
                        ]
                    ),
                "last_actual_cutoff":
                    round(
                        float(
                            row[
                                "last_score"
                            ]
                        ),
                        2,
                    ),
                "historical_mean":
                    round(
                        float(
                            row[
                                "mean_score"
                            ]
                        ),
                        2,
                    ),
                "trend_per_year":
                    round(
                        float(
                            row[
                                "trend_per_year"
                            ]
                        ),
                        3,
                    ),
                "calibrated_error_q50":
                    round(
                        float(
                            thresholds[
                                "q50"
                            ]
                        ),
                        2,
                    ),
                "calibrated_error_q80":
                    round(
                        float(
                            thresholds[
                                "q80"
                            ]
                        ),
                        2,
                    ),
                "calibration_scope":
                    thresholds[
                        "calibration_scope"
                    ],
            }
        )

    result = pd.DataFrame(
        rows
    )

    # Ranking:
    # 1) recommendation level
    # 2) stronger major-name match
    # 3) more historical years
    # 4) smaller absolute distance from a useful decision boundary
    result[
        "_abs_gap"
    ] = result[
        "score_gap"
    ].abs()

    result = (
        result.sort_values(
            [
                "_level_rank",
                "major_similarity",
                "history_count",
                "_abs_gap",
                "predicted_cutoff_2027",
            ],
            ascending=[
                True,
                False,
                False,
                True,
                False,
            ],
            kind="stable",
        )
        .head(
            max(
                1,
                int(top_n),
            )
        )
        .drop(
            columns=[
                "_level_rank",
                "_abs_gap",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    metadata = {
        "reason":
            "OK",
        "best_method":
            global_quantiles[
                "best_method"
            ],
        "holdout_n":
            global_quantiles[
                "n"
            ],
        "global_q50":
            global_quantiles[
                "q50"
            ],
        "global_q80":
            global_quantiles[
                "q80"
            ],
        "global_q90":
            global_quantiles[
                "q90"
            ],
        "major_match_count":
            len(
                major_filtered
            ),
        "combination_counts":
            combo_counts,
        "result_count":
            len(result),
    }

    return result, metadata


# =============================================================================
# CLI
# =============================================================================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "UniConnect AI - tư vấn ngành/trường dựa trên "
            "điểm THPT và cutoff dự đoán 2027."
        )
    )

    parser.add_argument(
        "--score",
        type=float,
        help="Điểm THPT của học sinh, thang 30.",
    )

    parser.add_argument(
        "--combination",
        type=str,
        help="Tổ hợp xét tuyển, ví dụ A00, A01, B00, D01.",
    )

    parser.add_argument(
        "--major",
        type=str,
        default="",
        help='Tên ngành, ví dụ "Công nghệ thông tin".',
    )

    parser.add_argument(
        "--major-code",
        type=str,
        default="",
        help="Mã ngành chính xác, ưu tiên hơn --major.",
    )

    parser.add_argument(
        "--city",
        type=str,
        default="",
        help=(
            "Tỉnh/thành mong muốn. Chỉ hoạt động khi "
            "university_locations.csv đã được xác minh."
        ),
    )

    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Số kết quả tối đa.",
    )

    parser.add_argument(
        "--allow-unspecified-combination",
        action="store_true",
        help=(
            "Cho phép chương trình chưa xác minh tổ hợp. "
            "Mặc định OFF để ưu tiên độ chính xác."
        ),
    )

    parser.add_argument(
        "--allow-stale-history",
        action="store_true",
        help=(
            "Cho phép chương trình không có actual 2026. "
            "Mặc định OFF để danh sách tư vấn chính chỉ dùng dữ liệu cập nhật đến 2026."
        ),
    )

    return parser


def interactive_input(
    args: argparse.Namespace,
) -> argparse.Namespace:
    if args.score is None:
        args.score = float(
            input(
                "Nhập điểm THPT (0-30): "
            ).strip()
        )

    if not args.combination:
        args.combination = input(
            "Nhập tổ hợp (VD A00/A01/B00/D01): "
        ).strip()

    if (
        not args.major
        and not args.major_code
    ):
        args.major = input(
            "Nhập ngành quan tâm: "
        ).strip()

    return args


def print_result(
    result: pd.DataFrame,
    metadata: dict,
) -> None:
    print()
    print("=" * 118)
    print("UNICONNECT AI - KẾT QUẢ TƯ VẤN 2027")
    print("=" * 118)

    if result.empty:
        reason = metadata.get(
            "reason",
            "UNKNOWN",
        )

        print(
            "Không có kết quả đủ điều kiện."
        )

        if reason == "NO_MAJOR_MATCH":
            print(
                "Lý do: chưa tìm thấy ngành/mã ngành khớp đủ chắc chắn."
            )

        elif reason == "NO_COMBINATION_MATCH":
            print(
                "Lý do: có ngành khớp nhưng tổ hợp yêu cầu chưa được "
                "nguồn gần nhất xác nhận."
            )
            print(
                "Thống kê:",
                metadata.get(
                    "combination_counts",
                    {},
                ),
            )

        elif reason == "NO_LOCATION_MATCH":
            print(
                "Lý do: không có chương trình khớp tại tỉnh/thành yêu cầu."
            )

        elif reason == "NO_FRESH_2026_HISTORY":
            print(
                "Lý do: các chương trình khớp không có dữ liệu thực tế đến năm 2026."
            )
            print(
                "Có thể dùng --allow-stale-history để xem tham khảo, nhưng không nên dùng làm danh sách tư vấn chính."
            )

        return

    display_columns = [
        "university_name",
        "major_code",
        "major_name",
        "predicted_cutoff_2027",
        "score_gap",
        "recommendation_level",
        "history_reliability",
        "data_freshness",
        "last_actual_year",
        "eligible_combinations",
    ]

    print(
        result[
            display_columns
        ].to_string(
            index=False
        )
    )

    print("-" * 118)
    print(
        "Best method holdout :",
        metadata[
            "best_method"
        ],
    )
    print(
        "Holdout samples     :",
        metadata[
            "holdout_n"
        ],
    )
    print(
        "Sai số |e| q50/q80/q90:",
        f"{metadata['global_q50']:.2f} / "
        f"{metadata['global_q80']:.2f} / "
        f"{metadata['global_q90']:.2f}",
    )
    print(
        "Lưu ý               : Mức AN TOÀN/PHÙ HỢP/THỬ SỨC "
        "là mức tư vấn theo mô hình, không phải xác suất đỗ."
    )
    print("=" * 118)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    args = interactive_input(
        args
    )

    result, metadata = recommend(
        score=args.score,
        combination=args.combination,
        major_query=args.major,
        major_code=args.major_code,
        city=args.city,
        top_n=args.top,
        allow_unspecified_combination=
            args.allow_unspecified_combination,
        allow_stale_history=
            args.allow_stale_history,
    )

    if not result.empty:
        result.to_csv(
            OUTPUT_FILE,
            index=False,
            encoding="utf-8-sig",
        )

    print_result(
        result,
        metadata,
    )

    print()
    print(
        "OUTPUT:",
        OUTPUT_FILE
        if not result.empty
        else "(không tạo CSV vì không có kết quả)",
    )


if __name__ == "__main__":
    main()
