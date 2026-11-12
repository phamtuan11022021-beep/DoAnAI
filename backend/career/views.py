from __future__ import annotations

import json
import unicodedata
from functools import lru_cache
from pathlib import Path

import pandas as pd
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from .models import CareerAssessment


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROGRAM_YEAR_FILE = (
    PROJECT_ROOT
    / "data"
    / "dataset"
    / "admission_scores_2023_2026_program_year.csv"
)

DIMENSION_ORDER = [
    "R",
    "I",
    "A",
    "S",
    "E",
    "C",
]

DIMENSION_META = {
    "R": {
        "name": "Realistic",
        "label": "Kỹ thuật – Thực hành",
        "description": (
            "Thường hứng thú với hoạt động thực hành, kỹ thuật, "
            "máy móc, công cụ và tạo ra sản phẩm cụ thể."
        ),
    },
    "I": {
        "name": "Investigative",
        "label": "Nghiên cứu – Phân tích",
        "description": (
            "Thường hứng thú với phân tích, giải quyết vấn đề, "
            "khoa học, dữ liệu và tìm hiểu cách sự vật vận hành."
        ),
    },
    "A": {
        "name": "Artistic",
        "label": "Sáng tạo – Nghệ thuật",
        "description": (
            "Thường hứng thú với sáng tạo, thiết kế, ngôn ngữ, "
            "truyền thông và cách biểu đạt cá nhân."
        ),
    },
    "S": {
        "name": "Social",
        "label": "Xã hội – Hỗ trợ",
        "description": (
            "Thường hứng thú với giảng dạy, hỗ trợ, chăm sóc, "
            "tư vấn và làm việc trực tiếp với con người."
        ),
    },
    "E": {
        "name": "Enterprising",
        "label": "Kinh doanh – Lãnh đạo",
        "description": (
            "Thường hứng thú với kinh doanh, thuyết phục, "
            "quản lý, dẫn dắt và tạo ảnh hưởng."
        ),
    },
    "C": {
        "name": "Conventional",
        "label": "Tổ chức – Quy trình",
        "description": (
            "Thường hứng thú với dữ liệu có cấu trúc, quy trình, "
            "tài chính, hồ sơ và công việc cần tính chính xác."
        ),
    },
}

QUESTIONS = [
    {"id": "R1", "dimension": "R", "text": "Tôi thích lắp ráp, sửa chữa hoặc tìm hiểu cách thiết bị hoạt động."},
    {"id": "R2", "dimension": "R", "text": "Tôi hứng thú với công việc tạo ra một sản phẩm cụ thể bằng công cụ hoặc máy móc."},
    {"id": "R3", "dimension": "R", "text": "Tôi thích các nhiệm vụ thực hành hơn là chỉ đọc lý thuyết."},
    {"id": "R4", "dimension": "R", "text": "Tôi thấy thoải mái khi làm việc với hệ thống kỹ thuật, vật liệu hoặc thiết bị."},

    {"id": "I1", "dimension": "I", "text": "Tôi thích phân tích nguyên nhân của một vấn đề trước khi đưa ra kết luận."},
    {"id": "I2", "dimension": "I", "text": "Tôi hứng thú với toán, khoa học, công nghệ, dữ liệu hoặc thí nghiệm."},
    {"id": "I3", "dimension": "I", "text": "Tôi thích giải những bài toán khó cần suy luận nhiều bước."},
    {"id": "I4", "dimension": "I", "text": "Tôi thường muốn biết vì sao một hệ thống hoạt động theo cách hiện tại."},

    {"id": "A1", "dimension": "A", "text": "Tôi thích tạo ra ý tưởng, hình ảnh, nội dung hoặc cách trình bày mới."},
    {"id": "A2", "dimension": "A", "text": "Tôi hứng thú với thiết kế, ngôn ngữ, viết lách, truyền thông hoặc nghệ thuật."},
    {"id": "A3", "dimension": "A", "text": "Tôi thích công việc cho phép thể hiện phong cách và góc nhìn riêng."},
    {"id": "A4", "dimension": "A", "text": "Tôi thường nghĩ ra nhiều cách khác nhau để trình bày cùng một ý tưởng."},

    {"id": "S1", "dimension": "S", "text": "Tôi thích giải thích kiến thức cho người khác khi họ chưa hiểu."},
    {"id": "S2", "dimension": "S", "text": "Tôi cảm thấy có ý nghĩa khi hỗ trợ người khác giải quyết khó khăn."},
    {"id": "S3", "dimension": "S", "text": "Tôi hứng thú với giáo dục, tư vấn, chăm sóc hoặc công việc cộng đồng."},
    {"id": "S4", "dimension": "S", "text": "Tôi thích làm việc trong môi trường có nhiều tương tác với con người."},

    {"id": "E1", "dimension": "E", "text": "Tôi thích thuyết phục người khác ủng hộ một ý tưởng hoặc kế hoạch."},
    {"id": "E2", "dimension": "E", "text": "Tôi hứng thú với kinh doanh, quản lý, tổ chức dự án hoặc lãnh đạo nhóm."},
    {"id": "E3", "dimension": "E", "text": "Tôi sẵn sàng đưa ra quyết định khi nhóm cần một hướng đi rõ ràng."},
    {"id": "E4", "dimension": "E", "text": "Tôi thích đặt mục tiêu và tìm cách đạt kết quả tốt hơn."},

    {"id": "C1", "dimension": "C", "text": "Tôi thích công việc có quy trình rõ ràng và tiêu chuẩn cụ thể."},
    {"id": "C2", "dimension": "C", "text": "Tôi cẩn thận với số liệu, hồ sơ, bảng biểu hoặc thông tin cần độ chính xác cao."},
    {"id": "C3", "dimension": "C", "text": "Tôi thường sắp xếp công việc theo thứ tự và theo dõi tiến độ chi tiết."},
    {"id": "C4", "dimension": "C", "text": "Tôi hứng thú với tài chính, kế toán, thống kê hoặc quản trị dữ liệu."},
]

MAJOR_KEYWORDS = {
    "R": [
        "ky thuat", "co khi", "dien", "dien tu", "tu dong hoa",
        "xay dung", "o to", "kien truc", "nong nghiep", "cong nghe ky thuat",
    ],
    "I": [
        "cong nghe thong tin", "khoa hoc may tinh", "du lieu", "tri tue nhan tao",
        "toan", "vat ly", "hoa", "sinh", "y khoa", "duoc", "cong nghe sinh hoc",
    ],
    "A": [
        "thiet ke", "kien truc", "ngon ngu", "bao chi", "truyen thong",
        "my thuat", "am nhac", "quan he cong chung", "quang cao",
    ],
    "S": [
        "su pham", "giao duc", "tam ly", "cong tac xa hoi", "dieu duong",
        "y te", "du lich", "quan tri dich vu", "xa hoi hoc",
    ],
    "E": [
        "quan tri kinh doanh", "marketing", "thuong mai", "kinh doanh",
        "luat", "tai chinh", "bat dong san", "kinh te", "logistics",
    ],
    "C": [
        "ke toan", "kiem toan", "tai chinh", "ngan hang", "thong ke",
        "he thong thong tin", "quan ly", "bao hiem", "thue",
    ],
}


def json_response(data: dict, status: int = 200) -> JsonResponse:
    return JsonResponse(
        data,
        status=status,
        json_dumps_params={"ensure_ascii": False},
    )


def parse_json(request) -> dict:
    if not request.body:
        return {}

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"JSON không hợp lệ: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Body JSON phải là object.")

    return payload


def normalize_text(value: str) -> str:
    text = unicodedata.normalize(
        "NFD",
        str(value or ""),
    )

    text = "".join(
        char
        for char in text
        if unicodedata.category(char) != "Mn"
    )

    return (
        " ".join(text.lower().split())
        .replace("đ", "d")
    )


@lru_cache(maxsize=4)
def _program_catalog_cached(mtime_ns: int) -> list[dict]:
    del mtime_ns

    if not PROGRAM_YEAR_FILE.exists():
        return []

    df = pd.read_csv(
        PROGRAM_YEAR_FILE,
        dtype=str,
        keep_default_na=False,
    )

    required = {
        "major_code",
        "major_name",
        "university_key",
    }

    if not required.issubset(df.columns):
        return []

    grouped = (
        df[
            [
                "major_code",
                "major_name",
                "university_key",
            ]
        ]
        .drop_duplicates()
        .groupby(
            [
                "major_code",
                "major_name",
            ],
            as_index=False,
        )
        .agg(
            schools_count=(
                "university_key",
                "nunique",
            )
        )
    )

    return grouped.to_dict(
        orient="records"
    )


def program_catalog() -> list[dict]:
    if not PROGRAM_YEAR_FILE.exists():
        return []

    return _program_catalog_cached(
        PROGRAM_YEAR_FILE.stat().st_mtime_ns
    )


def major_suggestions(
    ranked_dimensions: list[str],
    limit: int = 12,
) -> list[dict]:
    catalog = program_catalog()

    if not catalog:
        return []

    dimension_weight = {
        dimension: (
            len(ranked_dimensions) - index
        )
        for index, dimension
        in enumerate(ranked_dimensions)
    }

    scored = []

    for item in catalog:
        normalized_name = normalize_text(
            item["major_name"]
        )

        total = 0
        matched_dimensions = []

        for dimension in ranked_dimensions:
            matched = any(
                keyword in normalized_name
                for keyword
                in MAJOR_KEYWORDS[
                    dimension
                ]
            )

            if matched:
                total += dimension_weight[
                    dimension
                ]
                matched_dimensions.append(
                    dimension
                )

        if total <= 0:
            continue

        scored.append(
            {
                "major_code":
                    item[
                        "major_code"
                    ],
                "major_name":
                    item[
                        "major_name"
                    ],
                "schools_count":
                    int(
                        item[
                            "schools_count"
                        ]
                    ),
                "match_score":
                    total,
                "matched_dimensions":
                    matched_dimensions,
            }
        )

    scored.sort(
        key=lambda item: (
            -item["match_score"],
            -item["schools_count"],
            normalize_text(
                item[
                    "major_name"
                ]
            ),
            item[
                "major_code"
            ],
        )
    )

    unique_names = set()
    result = []

    for item in scored:
        key = normalize_text(
            item["major_name"]
        )

        if key in unique_names:
            continue

        unique_names.add(key)
        result.append(item)

        if len(result) >= limit:
            break

    return result


def assessment_payload(
    assessment: CareerAssessment,
) -> dict:
    return {
        "id": assessment.id,
        "framework":
            assessment.framework,
        "scores":
            assessment.scores,
        "holland_code":
            assessment.holland_code,
        "suggested_majors":
            assessment.suggested_majors,
        "created_at":
            assessment.created_at.isoformat(),
    }


@require_GET
def questions_view(request):
    return json_response(
        {
            "success": True,
            "framework": "RIASEC",
            "title":
                "Trắc nghiệm hướng nghiệp Holland-style RIASEC",
            "scale": {
                "min": 1,
                "max": 5,
                "labels": {
                    "1": "Rất không giống tôi",
                    "2": "Không giống tôi",
                    "3": "Phân vân / trung lập",
                    "4": "Khá giống tôi",
                    "5": "Rất giống tôi",
                },
            },
            "dimensions":
                DIMENSION_META,
            "questions":
                QUESTIONS,
            "disclaimer": (
                "Đây là công cụ tự đánh giá hướng nghiệp dựa trên "
                "khung RIASEC, không phải bài trắc nghiệm tâm lý "
                "chuẩn hóa hay chẩn đoán chuyên môn."
            ),
        }
    )


@require_POST
def submit_view(request):
    if not request.user.is_authenticated:
        return json_response(
            {
                "success": False,
                "error":
                    "Bạn cần đăng nhập để lưu kết quả hướng nghiệp.",
            },
            status=401,
        )

    try:
        payload = parse_json(request)
    except ValueError as exc:
        return json_response(
            {
                "success": False,
                "error": str(exc),
            },
            status=400,
        )

    answers = payload.get(
        "answers",
        {},
    )

    if not isinstance(
        answers,
        dict,
    ):
        return json_response(
            {
                "success": False,
                "error":
                    "answers phải là object.",
            },
            status=400,
        )

    valid_ids = {
        question["id"]:
            question["dimension"]
        for question
        in QUESTIONS
    }

    missing = [
        question_id
        for question_id
        in valid_ids
        if question_id not in answers
    ]

    if missing:
        return json_response(
            {
                "success": False,
                "error":
                    "Bạn cần trả lời đủ tất cả câu hỏi.",
                "missing":
                    missing,
            },
            status=400,
        )

    dimension_values = {
        dimension: []
        for dimension
        in DIMENSION_ORDER
    }

    normalized_answers = {}

    for question_id, dimension in valid_ids.items():
        try:
            value = int(
                answers[
                    question_id
                ]
            )
        except (
            TypeError,
            ValueError,
        ):
            return json_response(
                {
                    "success": False,
                    "error":
                        f"Câu {question_id} có giá trị không hợp lệ.",
                },
                status=400,
            )

        if value < 1 or value > 5:
            return json_response(
                {
                    "success": False,
                    "error":
                        f"Câu {question_id} phải từ 1 đến 5.",
                },
                status=400,
            )

        normalized_answers[
            question_id
        ] = value

        dimension_values[
            dimension
        ].append(value)

    scores = {}

    for dimension in DIMENSION_ORDER:
        raw_score = sum(
            dimension_values[
                dimension
            ]
        )

        max_score = (
            len(
                dimension_values[
                    dimension
                ]
            )
            * 5
        )

        percent = round(
            raw_score
            / max_score
            * 100,
            1,
        )

        scores[
            dimension
        ] = {
            "raw":
                raw_score,
            "percent":
                percent,
            **DIMENSION_META[
                dimension
            ],
        }

    ranked_dimensions = sorted(
        DIMENSION_ORDER,
        key=lambda dimension: (
            -scores[
                dimension
            ][
                "percent"
            ],
            DIMENSION_ORDER.index(
                dimension
            ),
        )
    )

    top_three = ranked_dimensions[
        :3
    ]

    holland_code = "".join(
        top_three
    )

    suggestions = major_suggestions(
        top_three,
        limit=12,
    )

    assessment = CareerAssessment.objects.create(
        user=request.user,
        framework="RIASEC",
        answers=
            normalized_answers,
        scores=scores,
        holland_code=
            holland_code,
        suggested_majors=
            suggestions,
    )

    return json_response(
        {
            "success": True,
            "assessment":
                assessment_payload(
                    assessment
                ),
            "top_dimensions": [
                {
                    "code":
                        dimension,
                    **scores[
                        dimension
                    ],
                }
                for dimension
                in top_three
            ],
            "disclaimer": (
                "Kết quả dùng để định hướng khám phá ngành, "
                "không thay thế tư vấn hướng nghiệp chuyên môn."
            ),
        },
        status=201,
    )


@require_GET
def history_view(request):
    if not request.user.is_authenticated:
        return json_response(
            {
                "success": False,
                "error":
                    "Bạn cần đăng nhập để xem lịch sử.",
            },
            status=401,
        )

    assessments = (
        CareerAssessment.objects
        .filter(
            user=request.user
        )[:10]
    )

    return json_response(
        {
            "success": True,
            "count":
                len(assessments),
            "assessments": [
                assessment_payload(
                    assessment
                )
                for assessment
                in assessments
            ],
        }
    )
