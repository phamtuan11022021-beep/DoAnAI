from django.contrib import admin
from django.db import transaction
from django.utils.html import format_html
from config.admin_ui import FriendlyAdminMixin

from .models import Comment, Post, PostImage, PostLike, SavedPost, PollVote


class PostImageInline(admin.TabularInline):
    model = PostImage
    template = 'admin/uniconnect_post_images.html'
    verbose_name = 'Ảnh đính kèm'
    verbose_name_plural = 'Ảnh đính kèm'
    extra = 0
    fields = ('preview',)
    readonly_fields = ('preview',)
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description='Ảnh đính kèm')
    def preview(self, obj):
        if obj.image:
            return format_html('<a href="{}" target="_blank" rel="noopener noreferrer"><img src="{}" alt="Ảnh bài viết" style="max-width:180px;max-height:120px"></a>', obj.image.url, obj.image.url)
        return '—'


@admin.register(Post)
class PostAdmin(FriendlyAdminMixin, admin.ModelAdmin):
    view_title = 'Bài viết cộng đồng'
    view_description = 'Tìm theo nội dung hoặc người đăng. Mở một bài viết để kiểm tra và chỉnh sửa.'
    search_help_text = 'Nhập nội dung, tên người đăng hoặc hashtag.'
    inlines = [PostImageInline]
    list_select_related = ('author',)
    autocomplete_fields = ('author',)
    readonly_fields = ('author_name', 'created_time', 'updated_time', 'poll_summary')
    fieldsets = (
        ('Nội dung bài viết', {'fields': ('content', 'category', 'tag')}),
        ('Thông tin bài viết', {'fields': ('author_name', 'created_time', 'updated_time', 'poll_summary')}),
    )
    list_display = (
        'content_preview', 'author_name', 'category_name', 'created_time',
    )
    list_filter = (
        "category",
        "created_at",
    )
    search_fields = (
        "author__username",
        "author__first_name",
        "content",
        "tag",
    )

    def has_add_permission(self, request):
        return False

    @admin.display(description='Nội dung bài viết', ordering='content')
    def content_preview(self, obj):
        return format_html('<span class="uc-excerpt">{}</span>', obj.content)

    @admin.display(description='Người đăng', ordering='author__username')
    def author_name(self, obj):
        return obj.author.get_full_name() or obj.author.username

    @admin.display(description='Chuyên mục', ordering='category')
    def category_name(self, obj):
        return obj.get_category_display()

    @admin.display(description='Bình chọn')
    def poll_summary(self, obj):
        return ' / '.join(str(option) for option in obj.poll_options) if obj.poll_options else 'Không có bình chọn'

    def _delete_with_images(self, queryset):
        files = [(item.image.storage, item.image.name)
                 for item in PostImage.objects.filter(post__in=queryset) if item.image]
        queryset.delete()
        for storage, name in files:
            transaction.on_commit(lambda storage=storage, name=name: storage.delete(name))

    def delete_model(self, request, obj):
        self._delete_with_images(Post.objects.filter(pk=obj.pk))

    def delete_queryset(self, request, queryset):
        self._delete_with_images(queryset)


@admin.register(Comment)
class CommentAdmin(FriendlyAdminMixin, admin.ModelAdmin):
    view_title = 'Bình luận'
    view_description = 'Tìm bình luận cần xử lý và xem bài viết liên quan.'
    search_help_text = 'Nhập nội dung bình luận hoặc tên người viết.'
    list_select_related = ('author', 'post')
    autocomplete_fields = ('author', 'post')
    list_filter = ('created_at',)
    readonly_fields = ('author_name', 'post_preview', 'created_time')
    fields = ('content', 'author_name', 'post_preview', 'created_time')
    list_display = (
        'content_preview', 'author_name', 'post_preview', 'created_time',
    )
    search_fields = (
        "author__username",
        "author__first_name",
        "content",
    )

    def has_add_permission(self, request):
        return False

    @admin.display(description='Bình luận', ordering='content')
    def content_preview(self, obj):
        return format_html('<span class="uc-excerpt">{}</span>', obj.content)

    @admin.display(description='Người viết', ordering='author__username')
    def author_name(self, obj):
        return obj.author.get_full_name() or obj.author.username

    @admin.display(description='Bài viết liên quan')
    def post_preview(self, obj):
        return obj.post.content[:65]


@admin.register(PostLike)
class PostLikeAdmin(admin.ModelAdmin):
    list_display = (
        "post",
        "user",
        "created_at",
    )


@admin.register(SavedPost)
class SavedPostAdmin(admin.ModelAdmin):
    list_display = (
        "post",
        "user",
        "created_at",
    )


@admin.register(PollVote)
class PollVoteAdmin(admin.ModelAdmin):
    list_display = ('post', 'user', 'option')
    list_select_related = ('post', 'user')
    search_fields = ('post__content', 'user__username')
    readonly_fields = ('post', 'user', 'option')

    def has_add_permission(self, request):
        return False
