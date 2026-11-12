from django.contrib.admin.apps import AdminConfig
from django.apps import AppConfig


class OperationsConfig(AppConfig):
    name = 'config'
    verbose_name = 'Vận hành'


class UniConnectAdminConfig(AdminConfig):
    default_site = 'config.admin_site.UniConnectAdminSite'
