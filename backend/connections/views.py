from __future__ import annotations

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Case, IntegerField, Value, When
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from .models import UserFollow
from accounts.uploads import avatar_url
from social.models import Notification


def json_response(data: dict, status: int = 200) -> JsonResponse:
    return JsonResponse(
        data,
        status=status,
        json_dumps_params={"ensure_ascii": False},
    )


def display_name(user: User) -> str:
    return (
        user.get_full_name().strip()
        or user.first_name.strip()
        or user.username
    )


def initials(name: str) -> str:
    words = [
        part
        for part in str(name).split()
        if part
    ]

    if not words:
        return "U"

    if len(words) == 1:
        return words[0][:2].upper()

    return (
        words[0][0]
        + words[-1][0]
    ).upper()


def user_card(user: User, request_user=None) -> dict:
    profile = getattr(
        user,
        "uniconnect_profile",
        None,
    )

    followed_by_me = False

    if (
        request_user is not None
        and request_user.is_authenticated
    ):
        followed_by_me = UserFollow.objects.filter(
            follower=request_user,
            following=user,
        ).exists()

    role = (
        profile.role
        if profile is not None
        else "student"
    )

    target_major = (
        profile.target_major
        if profile is not None
        else ""
    )

    city = (
        profile.city
        if profile is not None
        else ""
    )

    name = display_name(user)

    return {
        "id": user.id,
        "avatar_url": avatar_url(user),
        "name": name,
        "initials": initials(name),
        "role": role,
        "target_major": target_major,
        "city": city,
        "is_staff": bool(user.is_staff),
        "followers_count":
            user.uniconnect_followers.count(),
        "following_count":
            user.uniconnect_following.count(),
        "followed_by_me":
            followed_by_me,
    }


@require_GET
def suggestions_view(request):
    queryset = (
        User.objects
        .filter(
            is_active=True
        )
        .select_related(
            "uniconnect_profile"
        )
    )

    if request.user.is_authenticated:
        queryset = queryset.exclude(
            id=request.user.id
        )

    # Mentor first, then staff, then remaining users.
    queryset = queryset.annotate(
        mentor_priority=Case(
            When(
                uniconnect_profile__role="mentor",
                then=Value(0),
            ),
            When(
                is_staff=True,
                then=Value(1),
            ),
            default=Value(2),
            output_field=IntegerField(),
        )
    ).order_by(
        "mentor_priority",
        "-date_joined",
        "id",
    )

    try:
        limit = int(
            request.GET.get(
                "limit",
                "8",
            )
        )
    except ValueError:
        limit = 8

    limit = max(
        1,
        min(
            limit,
            30,
        ),
    )

    users = [
        user_card(
            user,
            request.user,
        )
        for user in queryset[:limit]
    ]

    return json_response(
        {
            "success": True,
            "count": len(users),
            "users": users,
        }
    )


@require_GET
def following_view(request):
    if not request.user.is_authenticated:
        return json_response(
            {
                "success": False,
                "error":
                    "Bạn cần đăng nhập để xem danh sách đang theo dõi.",
            },
            status=401,
        )

    relations = (
        UserFollow.objects
        .filter(
            follower=request.user
        )
        .select_related(
            "following",
            "following__uniconnect_profile",
        )
        .order_by(
            "-created_at"
        )
    )

    users = [
        user_card(
            relation.following,
            request.user,
        )
        for relation in relations
    ]

    return json_response(
        {
            "success": True,
            "count": len(users),
            "users": users,
        }
    )


@require_POST
def follow_toggle_view(
    request,
    user_id: int,
):
    if not request.user.is_authenticated:
        return json_response(
            {
                "success": False,
                "error":
                    "Bạn cần đăng nhập để kết nối.",
            },
            status=401,
        )

    target = get_object_or_404(
        User,
        id=user_id,
        is_active=True,
    )

    if target.id == request.user.id:
        return json_response(
            {
                "success": False,
                "error":
                    "Bạn không thể tự theo dõi chính mình.",
            },
            status=400,
        )

    with transaction.atomic():
        relation = UserFollow.objects.filter(
            follower=request.user,
            following=target,
        ).first()

        if relation:
            relation.delete()
            following = False
        else:
            UserFollow.objects.create(
                follower=request.user,
                following=target,
            )
            following = True
            Notification.objects.get_or_create(recipient=target, actor=request.user, kind='follow', post=None)

    return json_response(
        {
            "success": True,
            "following": following,
            "target": user_card(
                target,
                request.user,
            ),
        }
    )
