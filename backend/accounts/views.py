from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .models import Profile


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


def normalize_email(value: str) -> str:
    return str(value or "").strip().lower()


def get_profile(user: User) -> Profile:
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile


def user_payload(user: User) -> dict:
    profile = get_profile(user)

    return {
        "id": user.id,
        "name": user.get_full_name().strip() or user.username,
        "email": user.email,
        "avatar_url": profile.avatar.url if profile.avatar else '',
        "is_staff": user.is_staff,
        "profile": {
            "role": profile.role,
            "expected_score": (
                float(profile.expected_score)
                if profile.expected_score is not None
                else None
            ),
            "target_combination": profile.target_combination,
            "target_major": profile.target_major,
            "city": profile.city,
            "bio": profile.bio,
        },
    }


@ensure_csrf_cookie
@require_GET
def csrf_view(request):
    return json_response(
        {
            "success": True,
            "message": "CSRF cookie ready.",
        }
    )


@require_POST
def register_view(request):
    try:
        payload = parse_json(request)
    except ValueError as exc:
        return json_response(
            {"success": False, "error": str(exc)},
            status=400,
        )

    name = str(payload.get("name", "")).strip()
    email = normalize_email(payload.get("email"))
    password = str(payload.get("password", ""))
    password_confirm = str(payload.get("password_confirm", ""))

    if len(name) < 2:
        return json_response(
            {"success": False, "error": "Họ tên phải có ít nhất 2 ký tự."},
            status=400,
        )

    try:
        validate_email(email)
    except ValidationError:
        return json_response(
            {"success": False, "error": "Email không hợp lệ."},
            status=400,
        )

    if password != password_confirm:
        return json_response(
            {"success": False, "error": "Mật khẩu xác nhận không khớp."},
            status=400,
        )

    if User.objects.filter(username__iexact=email).exists() or User.objects.filter(email__iexact=email).exists():
        return json_response(
            {"success": False, "error": "Email này đã được đăng ký."},
            status=409,
        )

    try:
        validate_password(password)
    except ValidationError as exc:
        return json_response(
            {
                "success": False,
                "error": "Mật khẩu chưa đạt yêu cầu.",
                "details": list(exc.messages),
            },
            status=400,
        )

    user = User.objects.create_user(
        username=email,
        email=email,
        password=password,
        first_name=name,
    )
    Profile.objects.create(user=user)

    login(request, user)

    return json_response(
        {
            "success": True,
            "user": user_payload(user),
        },
        status=201,
    )


@require_POST
def login_view(request):
    try:
        payload = parse_json(request)
    except ValueError as exc:
        return json_response(
            {"success": False, "error": str(exc)},
            status=400,
        )

    # Keep existing email clients compatible while allowing the same login form
    # to authenticate staff usernames. Usernames retain their original casing.
    identifier = str(payload.get("identifier", payload.get("email", ""))).strip()
    if '@' in identifier:
        identifier = normalize_email(identifier)
    password = str(payload.get("password", ""))

    user = authenticate(
        request,
        username=identifier,
        password=password,
    )

    if user is None:
        return json_response(
            {
                "success": False,
                "error": "Email, tên đăng nhập hoặc mật khẩu không đúng.",
            },
            status=401,
        )

    if not user.is_active:
        return json_response(
            {
                "success": False,
                "error": "Tài khoản đã bị khóa.",
            },
            status=403,
        )

    login(request, user)

    return json_response(
        {
            "success": True,
            "user": user_payload(user),
        }
    )


@require_POST
def logout_view(request):
    logout(request)

    return json_response(
        {
            "success": True,
        }
    )


@require_http_methods(["GET", "PATCH"])
def me_view(request):
    if not request.user.is_authenticated:
        return json_response(
            {
                "success": False,
                "authenticated": False,
                "error": "Bạn chưa đăng nhập.",
            },
            status=401,
        )

    if request.method == "GET":
        return json_response(
            {
                "success": True,
                "authenticated": True,
                "user": user_payload(request.user),
            }
        )

    try:
        payload = parse_json(request)
    except ValueError as exc:
        return json_response(
            {"success": False, "error": str(exc)},
            status=400,
        )

    user = request.user
    profile = get_profile(user)

    if "name" in payload:
        name = str(payload.get("name", "")).strip()
        if len(name) < 2:
            return json_response(
                {"success": False, "error": "Họ tên phải có ít nhất 2 ký tự."},
                status=400,
            )
        user.first_name = name

    if "expected_score" in payload:
        raw_score = payload.get("expected_score")

        if raw_score in ("", None):
            profile.expected_score = None
        else:
            try:
                score = Decimal(str(raw_score))
            except (InvalidOperation, ValueError):
                return json_response(
                    {"success": False, "error": "Điểm dự kiến không hợp lệ."},
                    status=400,
                )

            if score < 0 or score > 30:
                return json_response(
                    {"success": False, "error": "Điểm dự kiến phải từ 0 đến 30."},
                    status=400,
                )

            profile.expected_score = score

    if "target_combination" in payload:
        combination = str(payload.get("target_combination", "")).strip().upper()

        if combination and not re.fullmatch(r"[A-Z]\d{2}", combination):
            return json_response(
                {"success": False, "error": "Tổ hợp phải có dạng A00, A01, B00, D01..."},
                status=400,
            )

        profile.target_combination = combination

    if "target_major" in payload:
        profile.target_major = str(payload.get("target_major", "")).strip()[:200]

    if "city" in payload:
        profile.city = str(payload.get("city", "")).strip()[:120]

    if "bio" in payload:
        profile.bio = str(payload.get("bio", "")).strip()[:300]

    user.save(update_fields=["first_name"])
    profile.save()

    return json_response(
        {
            "success": True,
            "user": user_payload(user),
        }
    )
