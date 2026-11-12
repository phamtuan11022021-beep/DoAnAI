from django.views.decorators.http import require_POST
from .views import get_profile, json_response, user_payload
from .uploads import clean_image


@require_POST
def avatar_view(request):
    if not request.user.is_authenticated:
        return json_response({'error': 'Bạn cần đăng nhập.'}, status=401)
    upload = request.FILES.get('avatar')
    if not upload:
        return json_response({'error': 'Hãy chọn ảnh đại diện.'}, status=400)
    try:
        image = clean_image(upload, avatar=True)
    except ValueError as exc:
        return json_response({'error': str(exc)}, status=400)
    profile = get_profile(request.user)
    old = profile.avatar.name
    profile.avatar.save(image.name, image)
    if old and old != profile.avatar.name:
        profile.avatar.storage.delete(old)
    return json_response({'success': True, 'user': user_payload(request.user)})
