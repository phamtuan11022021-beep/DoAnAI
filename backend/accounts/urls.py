from django.urls import path
from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy
from .password_reset import PasswordResetView
from .media_views import avatar_view

from .views import (
    csrf_view,
    login_view,
    logout_view,
    me_view,
    register_view,
)


urlpatterns = [
    path('password-reset/',PasswordResetView.as_view(),name='password_reset'),
    path('password-reset/done/',auth_views.PasswordResetDoneView.as_view(template_name='accounts/password_reset_done.html'),name='password_reset_done'),
    path('reset/<uidb64>/<token>/',auth_views.PasswordResetConfirmView.as_view(template_name='accounts/password_reset_confirm.html',success_url=reverse_lazy('password_reset_complete')),name='password_reset_confirm'),
    path('reset/complete/',auth_views.PasswordResetCompleteView.as_view(template_name='accounts/password_reset_complete.html'),name='password_reset_complete'),
    path('avatar/', avatar_view, name='auth-avatar'),
    path("csrf/", csrf_view, name="auth-csrf"),
    path("register/", register_view, name="auth-register"),
    path("login/", login_view, name="auth-login"),
    path("logout/", logout_view, name="auth-logout"),
    path("me/", me_view, name="auth-me"),
]
