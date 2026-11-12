from __future__ import annotations

import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .service import RecommendationInputError, recommend_for_api


def _json_response(data: dict, *, status: int = 200) -> JsonResponse:
    return JsonResponse(
        data,
        status=status,
        json_dumps_params={"ensure_ascii": False},
    )


@csrf_exempt
@require_POST
def recommend_view(request):
    """
    POST /api/ai/recommend/

    Body JSON:
    {
        "score": 28,
        "combination": "A01",
        "major": "Công nghệ thông tin",
        "city": "Đà Nẵng",
        "top": 20
    }

    Không decode request.body thủ công bằng UTF-8.
    json.loads() nhận bytes trực tiếp và tự xử lý UTF-8/UTF-16/UTF-32/BOM,
    ổn định hơn khi gọi từ Windows PowerShell.
    """

    raw_body = request.body

    if not raw_body:
        return _json_response(
            {
                "success": False,
                "error": "Body JSON đang rỗng.",
            },
            status=400,
        )

    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return _json_response(
            {
                "success": False,
                "error": "Body phải là JSON hợp lệ.",
                "detail": str(exc),
            },
            status=400,
        )

    if not isinstance(payload, dict):
        return _json_response(
            {
                "success": False,
                "error": "Body JSON phải là một object.",
            },
            status=400,
        )

    try:
        response = recommend_for_api(payload)
        return _json_response(response)

    except RecommendationInputError as exc:
        return _json_response(
            {
                "success": False,
                "error": str(exc),
            },
            status=400,
        )

    except FileNotFoundError as exc:
        return _json_response(
            {
                "success": False,
                "error": f"Thiếu dữ liệu AI: {exc}",
            },
            status=500,
        )

    except Exception as exc:
        return _json_response(
            {
                "success": False,
                "error": f"{type(exc).__name__}: {exc}",
            },
            status=500,
        )
