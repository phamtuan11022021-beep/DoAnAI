from django.contrib import admin

from .models import UserFollow


@admin.register(UserFollow)
class UserFollowAdmin(admin.ModelAdmin):
    list_display = (
        "follower",
        "following",
        "created_at",
    )
    search_fields = (
        "follower__username",
        "follower__first_name",
        "following__username",
        "following__first_name",
    )
