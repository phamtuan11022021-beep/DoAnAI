from django.conf import settings
from django.contrib.auth import views
from django.shortcuts import render
from django.urls import reverse_lazy


class PasswordResetView(views.PasswordResetView):
    template_name='accounts/password_reset_form.html'
    email_template_name='accounts/password_reset_email.txt'
    subject_template_name='accounts/password_reset_subject.txt'
    success_url=reverse_lazy('password_reset_done')

    def dispatch(self,request,*args,**kwargs):
        if not settings.PASSWORD_RESET_ENABLED:
            return render(request,'accounts/password_reset_unavailable.html',status=503)
        return super().dispatch(request,*args,**kwargs)
