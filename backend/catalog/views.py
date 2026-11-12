from __future__ import annotations
from .official import official_rows

from functools import lru_cache
from pathlib import Path

import pandas as pd
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from .models import SavedUniversity


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = PROJECT_ROOT / "data" / "dataset"

PROGRAM_YEAR_FILE = (
    DATASET_DIR
    / "admission_scores_2023_2026_program_year.csv"
)

LOCATION_FILE = (
    DATASET_DIR
    / "university_locations.csv"
)

YEARS = [2023, 2024, 2025, 2026]


def json_response(data: dict, status: int = 200) -> JsonResponse:
    return JsonResponse(
        data,
        status=status,
        json_dumps_params={"ensure_ascii": False},
    )


def clean_text(value) -> str:
    if value is None:
        return ""

    text = str(value).strip()

    if text.lower() in {
        "nan",
        "none",
        "<na>",
    }:
        return ""

    return " ".join(text.split())


def require_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(
            f"Thiếu file: {path}"
        )


@lru_cache(maxsize=4)
def _load_program_year_cached(
    mtime_ns: int,
) -> pd.DataFrame:
    del mtime_ns

    df = pd.read_csv(
        PROGRAM_YEAR_FILE,
        dtype={
            "university_key": str,
            "university_name": str,
            "major_code": str,
            "major_code_key": str,
            "major_name": str,
            "program_key": str,
        },
        keep_default_na=False,
    )

    required = {
        "university_key",
        "university_name",
        "major_code",
        "major_name",
        "year",
        "cutoff_score",
        "eligible_combinations",
        "source_urls",
    }

    missing = sorted(
        required - set(df.columns)
    )

    if missing:
        raise RuntimeError(
            "program_year.csv thiếu cột: "
            + ", ".join(missing)
        )

    df["year"] = pd.to_numeric(
        df["year"],
        errors="coerce",
    )

    df["cutoff_score"] = pd.to_numeric(
        df["cutoff_score"],
        errors="coerce",
    )

    df = df.dropna(
        subset=[
            "year",
            "cutoff_score",
        ]
    ).copy()

    df["year"] = df[
        "year"
    ].astype(int)

    df = df[
        df["year"].isin(YEARS)
    ].copy()

    return df


def load_program_year() -> pd.DataFrame:
    require_file(
        PROGRAM_YEAR_FILE
    )

    return _load_program_year_cached(
        PROGRAM_YEAR_FILE.stat().st_mtime_ns
    ).copy()


@lru_cache(maxsize=4)
def _load_locations_cached(
    mtime_ns: int,
) -> pd.DataFrame:
    del mtime_ns

    if not LOCATION_FILE.exists():
        return pd.DataFrame(
            columns=[
                "university_key",
                "university_name",
                "city",
                "address",
                "location_scope",
                "source_url",
                "verified_year",
            ]
        )

    return pd.read_csv(
        LOCATION_FILE,
        dtype=str,
        keep_default_na=False,
    )


def load_locations() -> pd.DataFrame:
    if not LOCATION_FILE.exists():
        return _load_locations_cached(
            0
        ).copy()

    return _load_locations_cached(
        LOCATION_FILE.stat().st_mtime_ns
    ).copy()


def school_location_map() -> dict[str, dict]:
    locations = load_locations()

    result = {}

    for _, row in locations.iterrows():
        key = clean_text(
            row.get(
                "university_key"
            )
        )

        if not key:
            continue

        result[key] = {
            "city":
                clean_text(
                    row.get("city")
                ),
            "address":
                clean_text(
                    row.get("address")
                ),
            "location_scope":
                clean_text(
                    row.get(
                        "location_scope"
                    )
                ),
            "location_source_url":
                clean_text(
                    row.get(
                        "source_url"
                    )
                ),
            "location_verified_year":
                clean_text(
                    row.get(
                        "verified_year"
                    )
                ),
        }

    return result


def school_summary_rows(
    program_year: pd.DataFrame,
) -> list[dict]:
    locations = school_location_map()

    rows = []

    for university_key, group in program_year.groupby(
        "university_key",
        sort=True,
    ):
        university_name = max(
            (
                clean_text(value)
                for value in group[
                    "university_name"
                ]
            ),
            key=len,
            default=university_key,
        )

        years = sorted(
            {
                int(year)
                for year in group[
                    "year"
                ]
            }
        )

        scores = group[
            "cutoff_score"
        ].astype(float)

        location = locations.get(
            university_key,
            {},
        )

        rows.append(
            {
                "university_key":
                    university_key,
                "university_name":
                    university_name,
                "city":
                    location.get(
                        "city",
                        "",
                    ),
                "address":
                    location.get(
                        "address",
                        "",
                    ),
                "location_verified":
                    bool(location),
                "available_years":
                    years,
                "year_count":
                    len(years),
                "program_count":
                    int(
                        group[
                            "program_key"
                        ].nunique()
                    )
                    if "program_key"
                    in group.columns
                    else int(
                        group[
                            "major_code"
                        ].nunique()
                    ),
                "program_year_rows":
                    int(len(group)),
                "score_min":
                    round(
                        float(
                            scores.min()
                        ),
                        2,
                    ),
                "score_max":
                    round(
                        float(
                            scores.max()
                        ),
                        2,
                    ),
            }
        )

    return rows


def normalize_query(value: str) -> str:
    return clean_text(value).casefold()


@require_GET
def schools_view(request):
    try:
        program_year = load_program_year()
    except (
        FileNotFoundError,
        RuntimeError,
    ) as exc:
        return json_response(
            {
                "success": False,
                "error": str(exc),
            },
            status=500,
        )

    query = normalize_query(
        request.GET.get(
            "q",
            "",
        )
    )

    city = normalize_query(
        request.GET.get(
            "city",
            "",
        )
    )

    try:
        limit = int(
            request.GET.get(
                "limit",
                "250",
            )
        )
    except ValueError:
        limit = 250

    limit = max(
        1,
        min(
            limit,
            500,
        ),
    )

    rows = school_summary_rows(
        program_year
    )

    saved_keys = set()

    if request.user.is_authenticated:
        saved_keys = set(
            SavedUniversity.objects
            .filter(user=request.user)
            .values_list(
                "university_key",
                flat=True,
            )
        )

    for row in rows:
        row["saved_by_me"] = (
            row["university_key"]
            in saved_keys
        )

    if query:
        rows = [
            row
            for row in rows
            if query in normalize_query(
                " ".join(
                    [
                        row[
                            "university_name"
                        ],
                        row[
                            "university_key"
                        ],
                        row.get(
                            "city",
                            "",
                        ),
                    ]
                )
            )
        ]

    if city:
        rows = [
            row
            for row in rows
            if normalize_query(
                row.get(
                    "city",
                    "",
                )
            )
            == city
        ]

    rows.sort(
        key=lambda row: (
            -row["year_count"],
            -row["program_count"],
            row["university_name"],
        )
    )

    return json_response(
        {
            "success": True,
            "count": min(
                len(rows),
                limit,
            ),
            "total_matching":
                len(rows),
            "schools":
                rows[:limit],
            "dataset":
                {
                    "years":
                        YEARS,
                    "scope":
                        (
                            "Điểm chuẩn THPT sạch/comparable "
                            "trong program-year dataset dùng cho AI."
                        ),
                },
        }
    )


@require_GET
def school_detail_view(request):
    university_key = clean_text(
        request.GET.get(
            "university_key",
            "",
        )
    )

    if not university_key:
        return json_response(
            {
                "success": False,
                "error":
                    "Thiếu university_key.",
            },
            status=400,
        )

    try:
        program_year = load_program_year()
    except (
        FileNotFoundError,
        RuntimeError,
    ) as exc:
        return json_response(
            {
                "success": False,
                "error": str(exc),
            },
            status=500,
        )

    school_rows = program_year[
        program_year[
            "university_key"
        ].eq(
            university_key
        )
    ].copy()

    if school_rows.empty:
        return json_response(
            {
                "success": False,
                "error":
                    "Không tìm thấy trường trong program-year dataset.",
            },
            status=404,
        )

    locations = school_location_map()
    location = locations.get(
        university_key,
        {},
    )

    university_name = max(
        (
            clean_text(value)
            for value in school_rows[
                "university_name"
            ]
        ),
        key=len,
        default=university_key,
    )

    programs = []

    group_column = (
        "program_key"
        if "program_key"
        in school_rows.columns
        else "major_code"
    )

    for program_key, group in school_rows.groupby(
        group_column,
        sort=True,
    ):
        major_code = max(
            (
                clean_text(value)
                for value in group[
                    "major_code"
                ]
            ),
            key=len,
            default="",
        )

        major_name = max(
            (
                clean_text(value)
                for value in group[
                    "major_name"
                ]
            ),
            key=len,
            default="",
        )

        history = {}

        for year in YEARS:
            year_group = group[
                group["year"].eq(year)
            ]

            if year_group.empty:
                history[
                    str(year)
                ] = None
                continue

            row = year_group.iloc[0]

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
                "source_urls":
                    clean_text(
                        row.get(
                            "source_urls"
                        )
                    ),
                "admission_notes":
                    clean_text(
                        row.get(
                            "admission_notes"
                        )
                    ),
            }

        available_years = [
            year
            for year in YEARS
            if history[
                str(year)
            ]
            is not None
        ]

        programs.append(
            {
                "program_key":
                    program_key,
                "major_code":
                    major_code,
                "major_name":
                    major_name,
                "available_years":
                    available_years,
                "history":
                    history,
            }
        )

    programs.sort(
        key=lambda item: (
            item[
                "major_name"
            ].casefold(),
            item[
                "major_code"
            ],
        )
    )

    all_scores = school_rows[
        "cutoff_score"
    ].astype(float)

    return json_response(
        {
            "success": True,
            "school": {
                "official_methods": official_rows(university_key=university_key),
                "university_key":
                    university_key,
                "university_name":
                    university_name,
                "city":
                    location.get(
                        "city",
                        "",
                    ),
                "address":
                    location.get(
                        "address",
                        "",
                    ),
                "location_source_url":
                    location.get(
                        "location_source_url",
                        "",
                    ),
                "available_years":
                    sorted(
                        school_rows[
                            "year"
                        ]
                        .astype(int)
                        .unique()
                        .tolist()
                    ),
                "program_count":
                    len(programs),
                "score_min":
                    round(
                        float(
                            all_scores.min()
                        ),
                        2,
                    ),
                "score_max":
                    round(
                        float(
                            all_scores.max()
                        ),
                        2,
                    ),
                "programs":
                    programs,
                "saved_by_me":
                    (
                        request.user.is_authenticated
                        and SavedUniversity.objects.filter(
                            user=request.user,
                            university_key=university_key,
                        ).exists()
                    ),
            },
            "dataset": {
                "years":
                    YEARS,
                "scope":
                    (
                        "Lịch sử điểm chuẩn THPT sạch/comparable "
                        "2023–2026 dùng trong pipeline AI. "
                        "Năm/ngành không có dữ liệu được trả null, "
                        "không tự suy diễn."
                    ),
            },
        }
    )



def _school_summary_lookup() -> dict[str, dict]:
    program_year = load_program_year()

    return {
        row["university_key"]: row
        for row in school_summary_rows(
            program_year
        )
    }


@require_GET
def saved_universities_view(request):
    if not request.user.is_authenticated:
        return json_response(
            {
                "success": False,
                "error":
                    "Bạn cần đăng nhập để xem trường đã lưu.",
            },
            status=401,
        )

    try:
        school_map = _school_summary_lookup()
    except (
        FileNotFoundError,
        RuntimeError,
    ) as exc:
        return json_response(
            {
                "success": False,
                "error": str(exc),
            },
            status=500,
        )

    saved_rows = (
        SavedUniversity.objects
        .filter(user=request.user)
        .order_by("-created_at")
    )

    schools = []

    stale_keys = []

    for saved in saved_rows:
        school = school_map.get(
            saved.university_key
        )

        if school is None:
            stale_keys.append(
                saved.university_key
            )
            continue

        item = dict(school)
        item["saved_by_me"] = True
        item["saved_at"] = (
            saved.created_at.isoformat()
        )
        schools.append(item)

    return json_response(
        {
            "success": True,
            "count": len(schools),
            "schools": schools,
            "stale_keys": stale_keys,
        }
    )


@require_POST
def toggle_saved_university_view(request):
    if not request.user.is_authenticated:
        return json_response(
            {
                "success": False,
                "error":
                    "Bạn cần đăng nhập để lưu trường.",
            },
            status=401,
        )

    import json

    try:
        payload = json.loads(
            request.body.decode("utf-8")
            or "{}"
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        return json_response(
            {
                "success": False,
                "error":
                    "Body phải là JSON hợp lệ.",
            },
            status=400,
        )

    university_key = clean_text(
        payload.get(
            "university_key",
            ""
        )
    )

    if not university_key:
        return json_response(
            {
                "success": False,
                "error":
                    "Thiếu university_key.",
            },
            status=400,
        )

    try:
        school_map = _school_summary_lookup()
    except (
        FileNotFoundError,
        RuntimeError,
    ) as exc:
        return json_response(
            {
                "success": False,
                "error": str(exc),
            },
            status=500,
        )

    school = school_map.get(
        university_key
    )

    if school is None:
        return json_response(
            {
                "success": False,
                "error":
                    "Trường không tồn tại trong dataset sạch hiện tại.",
            },
            status=404,
        )

    saved = SavedUniversity.objects.filter(
        user=request.user,
        university_key=university_key,
    ).first()

    if saved is not None:
        saved.delete()
        is_saved = False
    else:
        SavedUniversity.objects.create(
            user=request.user,
            university_key=university_key,
        )
        is_saved = True

    item = dict(school)
    item["saved_by_me"] = is_saved

    return json_response(
        {
            "success": True,
            "saved": is_saved,
            "school": item,
        }
    )
