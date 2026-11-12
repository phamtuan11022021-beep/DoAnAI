from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods, require_POST
from .models import DirectMessage, Notification, Post, PollVote
from .views import json_response, parse_json, display_name, post_payload, poll_payload, relative_time
from accounts.uploads import avatar_url


def auth_error(request):
    if not request.user.is_authenticated:
        return json_response({'error': 'Bạn cần đăng nhập.'}, status=401)


@require_http_methods(['PATCH', 'DELETE'])
def post_detail(request, post_id):
    error = auth_error(request)
    if error: return error
    post = get_object_or_404(Post, pk=post_id)
    if post.author_id != request.user.id:
        return json_response({'error': 'Bạn chỉ được sửa hoặc xóa bài của mình.'}, status=403)
    if request.method == 'DELETE':
        images = [(i.image.storage, i.image.name) for i in post.images.all()]
        post.delete()
        for storage, name in images:
            storage.delete(name)
        return json_response({'success': True})
    try:
        data = parse_json(request)
        content = data.get('content', '')
        if not isinstance(content, str) or not 1 <= len(content.strip()) <= 3000:
            raise ValueError('Nội dung cần có từ 1 đến 3000 ký tự.')
    except ValueError as exc:
        return json_response({'error': str(exc)}, status=400)
    post.content = content.strip()
    post.save(update_fields=['content', 'updated_at'])
    return json_response({'success': True, 'post': post_payload(post, request)})


@require_POST
def vote(request, post_id):
    error = auth_error(request)
    if error: return error
    post = get_object_or_404(Post, pk=post_id)
    try:
        option = parse_json(request).get('option')
        if type(option) is not int or not 0 <= option < len(post.poll_options):
            raise ValueError('Lựa chọn không hợp lệ.')
    except ValueError as exc:
        return json_response({'error': str(exc)}, status=400)
    PollVote.objects.update_or_create(post=post, user=request.user, defaults={'option': option})
    return json_response({'success': True, 'poll': poll_payload(post, request.user)})


@require_http_methods(['GET', 'POST'])
def notifications(request):
    error = auth_error(request)
    if error: return error
    queryset = Notification.objects.filter(recipient=request.user)
    if request.method == 'POST':
        try:
            data = parse_json(request)
            if data.get('id') is not None:
                queryset = queryset.filter(pk=int(data['id']))
        except (ValueError, TypeError):
            return json_response({'error': 'Mã thông báo không hợp lệ.'}, status=400)
        queryset.update(read=True)
        return json_response({'success': True})
    labels = {'like': 'đã thích bài viết của bạn', 'comment': 'đã bình luận bài viết của bạn',
              'follow': 'đã kết nối với bạn'}
    return json_response({'unread': queryset.filter(read=False).count(), 'notifications': [
        {'id': n.id, 'text': f'{display_name(n.actor)} {labels.get(n.kind, "đã tương tác")}',
         'post_id': n.post_id, 'actor_id': n.actor_id, 'read': n.read,
         'time': relative_time(n.created_at)}
        for n in queryset.select_related('actor')[:50]]})


def person(user):
    return {'id': user.id, 'name': display_name(user), 'avatar_url': avatar_url(user)}


@require_http_methods(['GET'])
def inbox(request):
    error = auth_error(request)
    if error: return error
    queryset = DirectMessage.objects.filter(Q(sender=request.user) | Q(recipient=request.user))
    threads, seen = [], set()
    for message in queryset.select_related('sender', 'recipient').order_by('-created_at', '-id'):
        other = message.recipient if message.sender_id == request.user.id else message.sender
        if other.id in seen: continue
        seen.add(other.id)
        threads.append({'user': person(other), 'content': message.content,
                        'time': relative_time(message.created_at),
                        'unread': DirectMessage.objects.filter(sender=other, recipient=request.user, read=False).count()})
        if len(threads) >= 50: break
    return json_response({'threads': threads, 'unread': queryset.filter(recipient=request.user, read=False).count()})


@require_http_methods(['GET', 'POST'])
def messages(request, user_id):
    error = auth_error(request)
    if error: return error
    other = get_object_or_404(User, pk=user_id, is_active=True)
    if other == request.user:
        return json_response({'error': 'Hãy chọn một thành viên khác.'}, status=400)
    if request.method == 'POST':
        try:
            content = parse_json(request).get('content', '')
            if not isinstance(content, str) or not 1 <= len(content.strip()) <= 2000:
                raise ValueError('Tin nhắn cần có từ 1 đến 2000 ký tự.')
        except ValueError as exc:
            return json_response({'error': str(exc)}, status=400)
        DirectMessage.objects.create(sender=request.user, recipient=other, content=content.strip())
    queryset = DirectMessage.objects.filter(
        Q(sender=request.user, recipient=other) | Q(sender=other, recipient=request.user))
    # Reading is a separate POST so a GET doesn't change read state.
    if request.method == 'POST':
        queryset.filter(recipient=request.user, read=False).update(read=True)
    rows = list(queryset.order_by('-created_at', '-id')[:100])
    return json_response({'user': person(other), 'messages': [
        {'id': m.id, 'content': m.content, 'mine': m.sender_id == request.user.id,
         'created_at': m.created_at.isoformat(), 'time': relative_time(m.created_at)}
        for m in reversed(rows)]})


@require_POST
def read_messages(request, user_id):
    error = auth_error(request)
    if error: return error
    DirectMessage.objects.filter(sender_id=user_id, recipient=request.user, read=False).update(read=True)
    return json_response({'success': True})
