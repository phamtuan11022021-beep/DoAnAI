from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html, format_html_join

from config.admin_ui import FriendlyAdminMixin
from .models import AIChatMessage, AIChatSession


@admin.register(AIChatSession)
class AIChatSessionAdmin(FriendlyAdminMixin, admin.ModelAdmin):
    change_form_template = 'admin/uniconnect_readonly.html'
    view_title = 'Tư vấn AI'
    view_description = 'Mở một cuộc tư vấn để đọc nội dung trao đổi giữa thành viên và trợ lý AI.'
    search_help_text = 'Tìm theo tiêu đề hoặc tên thành viên.'
    list_select_related = ('user',)
    list_display = ('conversation_title', 'member_name', 'updated_time')
    search_fields = ('user__username', 'user__first_name', 'title')
    readonly_fields = ('updated_time', 'transcript', 'conversation_title', 'member_name')
    fieldsets = (
        ('Cuộc tư vấn', {'fields': ('conversation_title', 'member_name', 'updated_time')}),
        ('Nội dung trao đổi', {'fields': ('transcript',)}),
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description='Cuộc tư vấn', ordering='title')
    def conversation_title(self, obj):
        return obj.title or 'Cuộc tư vấn chưa đặt tên'

    @admin.display(description='Thành viên', ordering='user__username')
    def member_name(self, obj):
        return (obj.user.get_full_name() or obj.user.username) if obj.user_id else 'Khách chưa đăng nhập'

    @admin.display(description='Hội thoại')
    def transcript(self, obj):
        messages = obj.messages.order_by('created_at', 'id')[:200]
        if not messages:
            return 'Chưa có tin nhắn trong cuộc tư vấn này.'
        bubbles = format_html_join('',
            '<div class="uc-chat-bubble {}"><strong>{}</strong><p>{}</p><small>{}</small></div>',
            ((message.role, 'Trợ lý UniConnect AI' if message.role == 'assistant' else 'Người hỏi',
              message.content, timezone.localtime(message.created_at).strftime('%d/%m/%Y %H:%M'))
             for message in messages))
        return format_html('<div class="uc-transcript">{}<p class="help">Hiển thị tối đa 200 tin nhắn đầu tiên theo thời gian.</p></div>', bubbles)


# Retained for existing permission references; not listed in the main menu.
@admin.register(AIChatMessage)
class AIChatMessageAdmin(admin.ModelAdmin):
    readonly_fields = ('conversation', 'role', 'content', 'intent', 'payload', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
