from __future__ import annotations

import json

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from .models import Comment, Post, PostLike, SavedPost, PostImage, Notification
from accounts.uploads import avatar_url, clean_image


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


def relative_time(dt) -> str:
    delta = timezone.now() - dt
    seconds = max(
        0,
        int(delta.total_seconds()),
    )

    if seconds < 60:
        return "Vừa xong"

    minutes = seconds // 60

    if minutes < 60:
        return f"{minutes} phút trước"

    hours = minutes // 60

    if hours < 24:
        return f"{hours} giờ trước"

    days = hours // 24

    if days < 7:
        return f"{days} ngày trước"

    return dt.strftime("%d/%m/%Y")


def comment_payload(comment: Comment) -> dict:
    author_name = display_name(
        comment.author
    )

    return {
        "id": comment.id,
        "author": {
            "id": comment.author_id,
            "name": author_name,
            "avatar_url": avatar_url(comment.author),
            "initials": initials(
                author_name
            ),
        },
        "content": comment.content,
        "time":
            relative_time(
                comment.created_at
            ),
        "created_at":
            comment.created_at.isoformat(),
    }


def poll_payload(post, user):
    if not post.poll_options:
        return None
    counts = dict(post.votes.values('option').annotate(total=Count('id')).values_list('option', 'total'))
    mine = post.votes.filter(user=user).first() if user.is_authenticated else None
    return {'options': [{'text': text, 'votes': counts.get(index, 0)}
                         for index, text in enumerate(post.poll_options)],
            'total': sum(counts.values()), 'my_vote': mine.option if mine else None}


def post_payload(post: Post, request) -> dict:
    user = request.user
    author_name = display_name(
        post.author
    )

    liked_by_me = False
    saved_by_me = False

    if user.is_authenticated:
        liked_by_me = post.likes.filter(
            user=user
        ).exists()

        saved_by_me = post.saves.filter(
            user=user
        ).exists()

    top_comments = [
        comment_payload(comment)
        for comment in post.comments
        .select_related("author")
        .order_by("-created_at")[:2]
    ]

    return {
        "id": post.id,
        "images": [{'id': image.id, 'url': image.image.url} for image in post.images.all()],
        "poll": poll_payload(post, user),
        "can_edit": user.is_authenticated and user.id == post.author_id,
        "author": {
            "id": post.author_id,
            "avatar_url": avatar_url(post.author),
            "name": author_name,
            "initials": initials(
                author_name
            ),
            "verified":
                bool(
                    getattr(
                        post.author,
                        "is_staff",
                        False,
                    )
                ),
        },
        "category": post.category,
        "category_label":
            post.get_category_display(),
        "content": post.content,
        "tag": post.tag,
        "time":
            relative_time(
                post.created_at
            ),
        "created_at":
            post.created_at.isoformat(),
        "likes_count":
            post.likes.count(),
        "comments_count":
            post.comments.count(),
        "saves_count":
            post.saves.count(),
        "liked_by_me":
            liked_by_me,
        "saved_by_me":
            saved_by_me,
        "top_comments":
            top_comments,
        "can_delete":
            (
                user.is_authenticated
                and (
                    user.id == post.author_id
                    or user.is_staff
                )
            ),
    }


@require_http_methods(["GET", "POST"])
def posts_view(request):
    if request.method == "GET":
        category = str(
            request.GET.get(
                "category",
                "",
            )
        ).strip()

        queryset = Post.objects.select_related(
            "author"
        )
        if request.GET.get('post'):
            try:
                queryset = queryset.filter(pk=int(request.GET['post']))
            except ValueError:
                return json_response({'error': 'Mã bài viết không hợp lệ.'}, status=400)
        if request.GET.get('q'):
            query = request.GET['q'][:100]
            queryset = queryset.filter(Q(content__icontains=query) | Q(tag__icontains=query))

        if category in dict(
            Post.CATEGORY_CHOICES
        ):
            queryset = queryset.filter(
                category=category
            )

        try:
            limit = int(
                request.GET.get(
                    "limit",
                    "50",
                )
            )
        except ValueError:
            limit = 50

        limit = max(
            1,
            min(
                limit,
                100,
            ),
        )

        posts = [
            post_payload(
                post,
                request,
            )
            for post in queryset[:limit]
        ]

        return json_response(
            {
                "success": True,
                "count": len(posts),
                "posts": posts,
            }
        )

    if not request.user.is_authenticated:
        return json_response(
            {
                "success": False,
                "error":
                    "Bạn cần đăng nhập để đăng bài.",
            },
            status=401,
        )

    try:
        payload = request.POST if request.content_type == 'multipart/form-data' else parse_json(request)
    except ValueError as exc:
        return json_response(
            {
                "success": False,
                "error": str(exc),
            },
            status=400,
        )

    content = str(
        payload.get(
            "content",
            "",
        )
    ).strip()

    category = str(
        payload.get(
            "category",
            Post.CATEGORY_GENERAL,
        )
    ).strip()

    tag = str(
        payload.get(
            "tag",
            "",
        )
    ).strip()[:80]

    if not content:
        return json_response(
            {
                "success": False,
                "error":
                    "Nội dung bài viết không được để trống.",
            },
            status=400,
        )

    if len(content) > 3000:
        return json_response(
            {
                "success": False,
                "error":
                    "Bài viết tối đa 3000 ký tự.",
            },
            status=400,
        )

    valid_categories = dict(
        Post.CATEGORY_CHOICES
    )

    if category not in valid_categories:
        category = Post.CATEGORY_GENERAL

    files = request.FILES.getlist('images')
    try:
        if len(files) > 4:
            raise ValueError('Mỗi bài viết tối đa 4 ảnh.')
        images = [clean_image(image) for image in files]
        options = payload.get('poll_options', [])
        if isinstance(options, str):
            options = json.loads(options)
        if not isinstance(options, list) or (options and (not 2 <= len(options) <= 6
                or any(not isinstance(o, str) or not o.strip() or len(o) > 120 for o in options)
                or len({o.strip().casefold() for o in options}) != len(options))):
            raise ValueError('Bình chọn cần 2–6 lựa chọn khác nhau, tối đa 120 ký tự/lựa chọn.')
    except (ValueError, TypeError) as exc:
        return json_response({'error': str(exc)}, status=400)
    with transaction.atomic():
        post = Post.objects.create(author=request.user, content=content, category=category,
                                   tag=tag, poll_options=[o.strip() for o in options])
        for image in images:
            PostImage.objects.create(post=post, image=image)

    return json_response(
        {
            "success": True,
            "post":
                post_payload(
                    post,
                    request,
                ),
        },
        status=201,
    )


@require_http_methods(["GET", "POST"])
def comments_view(
    request,
    post_id: int,
):
    post = get_object_or_404(
        Post,
        pk=post_id,
    )

    if request.method == "GET":
        comments = [
            comment_payload(comment)
            for comment in post.comments
            .select_related("author")
            .all()
        ]

        return json_response(
            {
                "success": True,
                "count":
                    len(comments),
                "comments":
                    comments,
            }
        )

    if not request.user.is_authenticated:
        return json_response(
            {
                "success": False,
                "error":
                    "Bạn cần đăng nhập để bình luận.",
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

    content = str(
        payload.get(
            "content",
            "",
        )
    ).strip()

    if not content:
        return json_response(
            {
                "success": False,
                "error":
                    "Bình luận không được để trống.",
            },
            status=400,
        )

    if len(content) > 1200:
        return json_response(
            {
                "success": False,
                "error":
                    "Bình luận tối đa 1200 ký tự.",
            },
            status=400,
        )

    comment = Comment.objects.create(
        post=post,
        author=request.user,
        content=content,
    )
    if post.author_id != request.user.id:
        Notification.objects.create(recipient=post.author, actor=request.user, post=post, kind='comment')

    return json_response(
        {
            "success": True,
            "comment":
                comment_payload(
                    comment
                ),
        },
        status=201,
    )


@require_POST
def like_view(
    request,
    post_id: int,
):
    if not request.user.is_authenticated:
        return json_response(
            {
                "success": False,
                "error":
                    "Bạn cần đăng nhập để thích bài viết.",
            },
            status=401,
        )

    post = get_object_or_404(
        Post,
        pk=post_id,
    )

    with transaction.atomic():
        like = PostLike.objects.filter(
            post=post,
            user=request.user,
        ).first()

        if like:
            like.delete()
            liked = False
        else:
            PostLike.objects.create(
                post=post,
                user=request.user,
            )
            liked = True
            if post.author_id != request.user.id:
                Notification.objects.get_or_create(recipient=post.author, actor=request.user, post=post, kind='like')

    return json_response(
        {
            "success": True,
            "liked": liked,
            "likes_count":
                post.likes.count(),
        }
    )


@require_POST
def save_view(
    request,
    post_id: int,
):
    if not request.user.is_authenticated:
        return json_response(
            {
                "success": False,
                "error":
                    "Bạn cần đăng nhập để lưu bài viết.",
            },
            status=401,
        )

    post = get_object_or_404(
        Post,
        pk=post_id,
    )

    with transaction.atomic():
        saved = SavedPost.objects.filter(
            post=post,
            user=request.user,
        ).first()

        if saved:
            saved.delete()
            is_saved = False
        else:
            SavedPost.objects.create(
                post=post,
                user=request.user,
            )
            is_saved = True

    return json_response(
        {
            "success": True,
            "saved": is_saved,
            "saves_count":
                post.saves.count(),
        }
    )



@require_http_methods(["GET"])
def saved_posts_view(request):
    if not request.user.is_authenticated:
        return json_response(
            {
                "success": False,
                "error":
                    "Bạn cần đăng nhập để xem bài đã lưu.",
            },
            status=401,
        )

    queryset = (
        Post.objects
        .filter(
            saves__user=request.user
        )
        .select_related(
            "author"
        )
        .distinct()
    )

    posts = [
        post_payload(
            post,
            request,
        )
        for post in queryset[:100]
    ]

    return json_response(
        {
            "success": True,
            "count":
                len(posts),
            "posts":
                posts,
        }
    )
