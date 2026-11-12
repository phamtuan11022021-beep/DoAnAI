from django.conf import settings
from django.shortcuts import render


def privacy(request):
    return render(request,'accounts/privacy.html',{'provider':settings.CHAT_PROVIDER})
