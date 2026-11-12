from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Create administration groups without granting privileges to any user.'

    def handle(self, **options):
        roles = {
            'Biên tập dữ liệu tuyển sinh': {
                'catalog': ['view_admissionrelease','add_admissionrelease','change_admissionrelease','publish_admissionrelease'],
            },
            'Kiểm duyệt cộng đồng': {
                'social': ['view_post', 'change_post', 'delete_post', 'view_comment',
                           'change_comment', 'delete_comment', 'view_postimage', 'view_pollvote',
                           'delete_postlike', 'delete_savedpost', 'delete_pollvote'],
            },
            'Theo dõi tư vấn': {
                'ai_chat': ['view_aichatsession', 'view_aichatmessage'],
                'career': ['view_careerassessment'],
            },
        }
        for name, app_permissions in roles.items():
            group, _ = Group.objects.get_or_create(name=name)
            # Add only: preserve any permissions deliberately granted by an owner.
            for app_label, codenames in app_permissions.items():
                group.permissions.add(*Permission.objects.filter(
                    content_type__app_label=app_label, codename__in=codenames))
        self.stdout.write(self.style.SUCCESS('Administration groups ready. No user privileges changed.'))
