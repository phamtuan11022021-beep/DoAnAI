from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.utils import timezone
from config.admin_ui import FriendlyAdminMixin

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(FriendlyAdminMixin, admin.ModelAdmin):
    view_title = 'Hồ sơ & mentor'
    view_description = 'Xem mục tiêu học tập và cập nhật vai trò mentor cho thành viên.'
    search_help_text = 'Tìm theo tên, email, ngành quan tâm hoặc khu vực.'
    autocomplete_fields = ('user',)
    list_select_related = ('user',)
    readonly_fields = ('member_name',)
    fieldsets = (
        ('Thành viên', {'fields': ('member_name', 'role', 'avatar', 'bio')}),
        ('Mục tiêu học tập', {'fields': ('expected_score', 'target_combination', 'target_major', 'city')}),
    )
    list_display = (
        'member_name', 'member_role', 'major_name', 'city_name',
    )
    search_fields = (
        "user__username",
        "user__email",
        "user__first_name",
        "target_major",
        "city",
    )
    list_filter = ('role', 'city')

    def has_add_permission(self, request):
        return False

    @admin.display(description='Thành viên', ordering='user__username')
    def member_name(self, obj):
        return obj.user.get_full_name() or obj.user.username

    @admin.display(description='Vai trò', ordering='role')
    def member_role(self, obj):
        return obj.get_role_display()

    @admin.display(description='Ngành quan tâm', ordering='target_major')
    def major_name(self, obj):
        return obj.target_major or 'Chưa cập nhật'

    @admin.display(description='Khu vực', ordering='city')
    def city_name(self, obj):
        return obj.city or 'Chưa cập nhật'


admin.site.unregister(User)


@admin.register(User)
class MemberAdmin(FriendlyAdminMixin, UserAdmin):
    view_title = 'Thành viên'
    view_description = 'Tìm thành viên, xem thông tin và quản lý trạng thái tài khoản.'
    search_help_text = 'Nhập họ tên, email hoặc tên đăng nhập.'
    list_display = ('member_name', 'email', 'account_status', 'account_role', 'joined_time')
    list_display_links = ('member_name',)
    list_filter = ('is_active', 'is_staff')
    ordering = ('-date_joined',)
    readonly_fields = ('last_login', 'date_joined')
    fieldsets = (
        ('Thông tin tài khoản', {'fields': ('username', 'password', 'first_name', 'last_name', 'email', 'is_active')}),
        ('Quyền quản trị · Nâng cao', {'classes': ('collapse',), 'fields': ('is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Lịch sử tài khoản', {'classes': ('collapse',), 'fields': ('last_login', 'date_joined')}),
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset if request.user.is_superuser else queryset.filter(is_staff=False, is_superuser=False)

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if request.user.is_superuser or obj is None:
            return fieldsets
        return tuple(section for section in fieldsets if section[0] != 'Quyền quản trị · Nâng cao')

    @admin.display(description='Thành viên', ordering='username')
    def member_name(self, obj):
        return obj.get_full_name() or obj.username

    @admin.display(description='Trạng thái', ordering='is_active')
    def account_status(self, obj):
        return format_html('<span class="uc-badge {}">{}</span>', '' if obj.is_active else 'uc-badge-inactive', 'Đang hoạt động' if obj.is_active else 'Đã khóa')

    @admin.display(description='Loại tài khoản', ordering='is_staff')
    def account_role(self, obj):
        return 'Quản trị viên' if obj.is_staff else 'Thành viên'

    @admin.display(description='Ngày tham gia', ordering='date_joined')
    def joined_time(self, obj):
        return timezone.localtime(obj.date_joined).strftime('%d/%m/%Y')
