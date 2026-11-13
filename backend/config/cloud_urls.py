"""Serve uploaded images in the demo; collectstatic/WhiteNoise serves code assets."""
from django.conf import settings
from django.urls import re_path
from django.views.static import serve

from .urls import urlpatterns

urlpatterns = [*urlpatterns, re_path(r'^media/(?P<path>.*)$', serve,
                                   {'document_root': settings.MEDIA_ROOT})]
