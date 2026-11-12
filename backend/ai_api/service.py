from __future__ import annotations

import importlib.util
import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENGINE_FILE = PROJECT_ROOT / "ai" / "recommendation_engine.py"


class RecommendationInputError(ValueError):
    pass


@lru_cache(maxsize=1)
def _engine():
    if not ENGINE_FILE.exists():
        raise FileNotFoundError(
            f"Không tìm thấy recommendation engine: {ENGINE_FILE}"
        )

    spec = importlib.util.spec_from_file_location(
        "uniconnect_recommendation_engine",
        ENGINE_FILE,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(
            f"Không load được module AI từ {ENGINE_FILE}"
        )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _clean_text(value: Any) -> str:
    if value is None:
        return ""

    text = str(value).replace("\xa0", " ").strip()

    if text.lower() in {"nan", "none", "<na>"}:
        return ""

    return re.sub(r"\s+", " ", text)


def _number(
    value: Any,
    *,
    field: str,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise RecommendationInputError(
            f"{field} phải là số."
        )

    if not math.isfinite(number):
        raise RecommendationInputError(
            f"{field} không hợp lệ."
        )

    if minimum is not None and number < minimum:
        raise RecommendationInputError(
            f"{field} phải >= {minimum}."
        )

    if maximum is not None and number > maximum:
        raise RecommendationInputError(
            f"{field} phải <= {maximum}."
        )

    return number


def _integer(
    value: Any,
    *,
    field: str,
    minimum: int = 1,
    maximum: int = 100,
) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise RecommendationInputError(
            f"{field} phải là số nguyên."
        )

    if number < minimum or number > maximum:
        raise RecommendationInputError(
            f"{field} phải nằm trong [{minimum}, {maximum}]."
        )

    return number


def _safe_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _safe_value(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            _safe_value(item)
            for item in value
        ]

    if isinstance(value, tuple):
        return [
            _safe_value(item)
            for item in value
        ]

    if pd.isna(value):
        return None

    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass

    return value


def _records(
    frame: pd.DataFrame,
    *,
    limit: int | None = None,
) -> list[dict]:
    if frame is None or frame.empty:
        return []

    if limit is not None:
        frame = frame.head(limit)

    return [
        _safe_value(record)
        for record in frame.to_dict(
            orient="records"
        )
    ]


def _run(
    *,
    score: float,
    combination: str,
    major: str,
    major_code: str,
    city: str,
    top: int,
    allow_unspecified: bool = False,
    allow_stale: bool = False,
):
    engine = _engine()

    return engine.recommend(
        score=score,
        combination=combination,
        major_query=major,
        major_code=major_code,
        city=city,
        top_n=top,
        allow_unspecified_combination=allow_unspecified,
        allow_stale_history=allow_stale,
    )


def _available_combination_counts(
    *,
    major: str,
    major_code: str,
) -> list[dict]:
    """
    Chỉ dùng để giải thích/gợi ý tổ hợp.
    Không biến tổ hợp này thành điều kiện đủ để tư vấn trường.
    """
    engine = _engine()

    predictions = engine.load_predictions()

    matched = engine.filter_major(
        predictions,
        major_query=major,
        major_code=major_code,
    )

    if matched.empty:
        return []

    # Ưu tiên metadata gần nhất/current trước.
    fresh = matched[
        pd.to_numeric(
            matched["last_year"],
            errors="coerce",
        ).eq(2026)
    ].copy()

    source = fresh if not fresh.empty else matched

    counts = Counter()

    for value in source[
        "last_eligible_combinations"
    ]:
        text = _clean_text(value).upper()

        for code in set(
            re.findall(
                r"\b[A-Z]\d{2}\b",
                text,
            )
        ):
            counts[code] += 1

    return [
        {
            "combination": code,
            "program_count": count,
        }
        for code, count
        in sorted(
            counts.items(),
            key=lambda item: (
                -item[1],
                item[0],
            ),
        )[:12]
    ]


def _major_diagnostics(
    *,
    major: str,
    major_code: str,
    combination: str,
    city: str,
) -> dict:
    engine = _engine()

    predictions = engine.load_predictions()

    matched = engine.filter_major(
        predictions,
        major_query=major,
        major_code=major_code,
    )

    diagnostics = {
        "major_match_count":
            int(len(matched)),
        "fresh_2026_count":
            0,
        "verified_combination_count":
            0,
        "verified_combination_fresh_count":
            0,
        "available_combinations":
            _available_combination_counts(
                major=major,
                major_code=major_code,
            ),
        "city_requested":
            city,
    }

    if matched.empty:
        return diagnostics

    last_year = pd.to_numeric(
        matched["last_year"],
        errors="coerce",
    )

    diagnostics[
        "fresh_2026_count"
    ] = int(
        last_year.eq(2026).sum()
    )

    statuses = matched[
        "last_eligible_combinations"
    ].map(
        lambda value:
            engine.combination_status(
                value,
                combination,
            )
    )

    verified = statuses.eq(
        "VERIFIED"
    )

    diagnostics[
        "verified_combination_count"
    ] = int(
        verified.sum()
    )

    diagnostics[
        "verified_combination_fresh_count"
    ] = int(
        (
            verified
            & last_year.eq(2026)
        ).sum()
    )

    return diagnostics


def _dedupe(
    records: list[dict],
    *,
    exclude_keys: set[str] | None = None,
) -> list[dict]:
    seen = set(
        exclude_keys
        or set()
    )
    output = []

    for item in records:
        key = (
            f"{item.get('university_name','')}||"
            f"{item.get('major_code','')}"
        )

        if key in seen:
            continue

        seen.add(key)
        output.append(item)

    return output


def _record_keys(
    records: list[dict],
) -> set[str]:
    return {
        (
            f"{item.get('university_name','')}||"
            f"{item.get('major_code','')}"
        )
        for item in records
    }


def _fallbacks(
    *,
    score: float,
    combination: str,
    major: str,
    major_code: str,
    city: str,
    top: int,
    strict_records: list[dict],
) -> dict:
    """
    Không thay thế strict results.
    Chỉ tạo các nhóm mở rộng có nhãn rõ ràng để UI không bị 'trống'.
    """
    remaining = max(
        5,
        min(
            top,
            12,
        ),
    )

    used = _record_keys(
        strict_records
    )

    alternatives = {
        "same_city_unverified_combination": [],
        "nationwide_verified": [],
        "same_city_historical": [],
        "related_major_name": [],
    }

    # A) Cùng thành phố + cùng ngành + current 2026,
    # nhưng tổ hợp ở source gần nhất bị UNSPECIFIED.
    if city:
        try:
            frame, _ = _run(
                score=score,
                combination=combination,
                major=major,
                major_code=major_code,
                city=city,
                top=remaining,
                allow_unspecified=True,
                allow_stale=False,
            )

            records = [
                row
                for row in _records(
                    frame
                )
                if row.get(
                    "combination_status"
                ) == "UNVERIFIED"
            ]

            records = _dedupe(
                records,
                exclude_keys=used,
            )

            alternatives[
                "same_city_unverified_combination"
            ] = records[
                :remaining
            ]

            used.update(
                _record_keys(
                    records
                )
            )
        except Exception:
            pass

    # B) Giữ ngành + tổ hợp VERIFIED + current 2026,
    # bỏ riêng điều kiện thành phố.
    try:
        frame, _ = _run(
            score=score,
            combination=combination,
            major=major,
            major_code=major_code,
            city="",
            top=remaining,
            allow_unspecified=False,
            allow_stale=False,
        )

        records = _dedupe(
            _records(
                frame
            ),
            exclude_keys=used,
        )

        alternatives[
            "nationwide_verified"
        ] = records[
            :remaining
        ]

        used.update(
            _record_keys(
                records
            )
        )
    except Exception:
        pass

    # C) Cùng thành phố + VERIFIED combination,
    # cho phép lịch sử gần nhất trước 2026.
    if city:
        try:
            frame, _ = _run(
                score=score,
                combination=combination,
                major=major,
                major_code=major_code,
                city=city,
                top=remaining,
                allow_unspecified=False,
                allow_stale=True,
            )

            records = [
                row
                for row in _records(
                    frame
                )
                if int(
                    row.get(
                        "last_actual_year"
                    )
                    or 0
                ) < 2026
            ]

            records = _dedupe(
                records,
                exclude_keys=used,
            )

            alternatives[
                "same_city_historical"
            ] = records[
                :remaining
            ]

            used.update(
                _record_keys(
                    records
                )
            )
        except Exception:
            pass

    # D) Nếu Career Quiz truyền một mã quá cụ thể/campus code,
    # thử tên ngành như một nhóm gần tên. Vẫn bắt buộc VERIFIED + 2026.
    if major_code and major:
        try:
            frame, _ = _run(
                score=score,
                combination=combination,
                major=major,
                major_code="",
                city="",
                top=remaining,
                allow_unspecified=False,
                allow_stale=False,
            )

            records = _dedupe(
                _records(
                    frame
                ),
                exclude_keys=used,
            )

            alternatives[
                "related_major_name"
            ] = records[
                :remaining
            ]
        except Exception:
            pass

    return alternatives


def other_admission_methods(*, city, major, major_code=''):
    from catalog.official import official_rows
    return [row for row in official_rows(city=city, major=major, major_code=major_code)
            if not row['comparable_thpt']]


def recommend_for_api(
    payload: dict,
) -> dict:
    if not isinstance(
        payload,
        dict,
    ):
        raise RecommendationInputError(
            "Body JSON phải là object."
        )

    score = _number(
        payload.get(
            "score"
        ),
        field="Điểm THPT",
        minimum=0,
        maximum=30,
    )

    combination = _clean_text(
        payload.get(
            "combination"
        )
    ).upper()

    major = _clean_text(
        payload.get(
            "major"
        )
    )

    major_code = _clean_text(
        payload.get(
            "major_code"
        )
    )

    city = _clean_text(
        payload.get(
            "city"
        )
    )

    top = _integer(
        payload.get(
            "top",
            20,
        ),
        field="top",
        minimum=1,
        maximum=100,
    )

    if not combination:
        raise RecommendationInputError(
            "Vui lòng chọn tổ hợp."
        )

    if not major and not major_code:
        raise RecommendationInputError(
            "Vui lòng nhập ngành hoặc mã ngành."
        )

    try:
        strict_frame, strict_meta = _run(
            score=score,
            combination=combination,
            major=major,
            major_code=major_code,
            city=city,
            top=top,
            allow_unspecified=False,
            allow_stale=False,
        )
    except ValueError as exc:
        raise RecommendationInputError(
            str(exc)
        ) from exc

    strict_records = _records(
        strict_frame
    )

    # Chỉ mở rộng khi strict quá ít.
    alternatives = {
        "same_city_unverified_combination": [],
        "nationwide_verified": [],
        "same_city_historical": [],
        "related_major_name": [],
    }

    if city or len(strict_records) < min(
        5,
        top,
    ):
        alternatives = _fallbacks(
            score=score,
            combination=combination,
            major=major,
            major_code=major_code,
            city=city,
            top=top,
            strict_records=strict_records,
        )

    diagnostics = _major_diagnostics(
        major=major,
        major_code=major_code,
        combination=combination,
        city=city,
    )

    calibration = (
        strict_meta.get(
            "global_calibration"
        )
        or strict_meta
    )

    model_info = {
        "method":
            calibration.get(
                "best_method",
                strict_meta.get(
                    "best_method",
                    "",
                ),
            ),
        "holdout_samples":
            calibration.get(
                "n",
                strict_meta.get(
                    "holdout_n",
                    0,
                ),
            ),
        "error_q50":
            calibration.get(
                "q50",
                strict_meta.get(
                    "global_q50",
                ),
            ),
        "error_q80":
            calibration.get(
                "q80",
                strict_meta.get(
                    "global_q80",
                ),
            ),
        "error_q90":
            calibration.get(
                "q90",
                strict_meta.get(
                    "global_q90",
                ),
            ),
    }

    return {
        "success": True,
        "other_admission_methods": other_admission_methods(city=city, major=major, major_code=major_code),
        "target_year": 2027,
        "input": {
            "score":
                score,
            "combination":
                combination,
            "major":
                major,
            "major_code":
                major_code,
            "city":
                city,
            "top":
                top,
        },
        "result_count":
            len(
                strict_records
            ),
        "results":
            strict_records,
        "reason":
            strict_meta.get(
                "reason",
                "OK"
                if strict_records
                else "NO_RESULTS",
            ),
        "diagnostics":
            diagnostics,
        "alternatives":
            alternatives,
        "model_info":
            model_info,
        "disclaimer": (
            "Kết quả strict yêu cầu ngành + tổ hợp đã xác minh + "
            "khu vực (nếu chọn) + dữ liệu thực tế gần nhất năm 2026. "
            "Các nhóm mở rộng được gắn nhãn riêng và không được coi "
            "là kết quả strict. Mức AN TOÀN/PHÙ HỢP/THỬ SỨC là mức "
            "tư vấn theo mô hình, không phải xác suất đỗ."
        ),
    }
