from django.contrib import admin
from django import forms
from django.core.exceptions import ValidationError, PermissionDenied
from django.http import HttpResponse
from django.urls import path
from django.template.response import TemplateResponse
from django.core.paginator import Paginator
from pathlib import Path
import csv
from django.utils.html import format_html_join
import hashlib

from .models import SavedUniversity, AdmissionRelease
from .releases import FIELDS, parse_upload, change_release


class AdmissionReleaseForm(forms.ModelForm):
    csv_file = forms.FileField(label='Tệp điểm tuyển sinh (CSV UTF-8)', required=False)

    class Meta:
        model = AdmissionRelease
        fields = ['title']

    def clean_csv_file(self):
        upload = self.cleaned_data.get('csv_file')
        if not self.instance.pk and not upload:
            raise ValidationError('Chọn tệp CSV để xem trước dữ liệu.')
        if upload:
            if self.instance.pk:
                raise ValidationError('Không thay tệp của đợt đã lưu. Hãy tạo đợt mới.')
            if upload.size > 1024*1024:
                raise ValidationError('Tệp tối đa 1 MB.')
            blob = upload.read()
            self.reviewed_rows = parse_upload(blob)
            self.source_sha = hashlib.sha256(blob).hexdigest()
        return upload


@admin.register(AdmissionRelease)
class AdmissionReleaseAdmin(admin.ModelAdmin):
    form = AdmissionReleaseForm
    change_form_template = 'admin/catalog/admissionrelease/change_form.html'
    change_list_template = 'admin/catalog/admissionrelease/change_list.html'
    list_display = ['title','status','row_count','created_by','created_at','reviewed_by']
    list_filter = ['status','created_at']
    search_fields = ['title']
    readonly_fields = ['status','created_by','created_at','reviewed_by','reviewed_at','source_sha256','preview']

    @admin.display(description='Số dòng')
    def row_count(self,obj):
        return len(obj.rows)

    def get_fields(self,request,obj=None):
        return ['title','csv_file'] if obj is None else ['title',*self.readonly_fields]

    def get_readonly_fields(self,request,obj=None):
        return [*self.readonly_fields,'title'] if obj else self.readonly_fields

    def has_delete_permission(self,request,obj=None):
        return False

    def save_model(self,request,obj,form,change):
        if not change:
            obj.rows = form.reviewed_rows
            obj.source_sha256 = form.source_sha
            obj.created_by = request.user
        super().save_model(request,obj,form,change)

    @admin.display(description='Xem trước (tối đa 100 dòng)')
    def preview(self,obj):
        return format_html_join('', '<p><strong>{} · {} · {}</strong><br>{} — {} điểm<br><a href="{}" target="_blank" rel="noopener noreferrer">Đối chiếu nguồn ↗</a></p>',
            ((r['university_name'],r['major_name'],r['year'],r['admission_method'],r['cutoff_score'],r['source_url']) for r in obj.rows[:100]))

    def change_view(self,request,object_id,form_url='',extra_context=None):
        extra = {'can_publish':request.user.has_perm('catalog.publish_admissionrelease')}
        return super().change_view(request,object_id,form_url,{**extra,**(extra_context or {})})

    def response_change(self,request,obj):
        action = 'publish' if '_publish' in request.POST else 'withdraw' if '_withdraw' in request.POST else ''
        if action:
            try:
                if not request.POST.get('source_checked'):
                    raise ValidationError('Hãy xác nhận đã đối chiếu nguồn trước khi thực hiện.')
                change_release(obj.pk,request.user,action)
                self.log_change(request,obj,'Công bố dữ liệu' if action=='publish' else 'Thu hồi dữ liệu')
                self.message_user(request,'Đã công bố; dữ liệu có thể tra cứu trên web.' if action=='publish' else 'Đã thu hồi; dữ liệu gốc được giữ nguyên.')
            except ValidationError as exc:
                self.message_user(request,'; '.join(exc.messages),level='ERROR')
        return super().response_change(request,obj)

    def get_urls(self):
        return [path('template.csv',self.admin_site.admin_view(self.sample),name='catalog_admissionrelease_template'),
                path('schools.csv',self.admin_site.admin_view(self.schools),name='catalog_admissionrelease_schools'),
                path('coverage/',self.admin_site.admin_view(self.coverage),name='catalog_admissionrelease_coverage')]+super().get_urls()

    def schools(self,request):
        if not self.has_view_permission(request): raise PermissionDenied
        from ai_chat.engine import load_program_year
        response=HttpResponse(content_type='text/csv; charset=utf-8')
        response.write('\ufeff')
        response['Content-Disposition']='attachment; filename="danh-muc-truong.csv"'
        writer=csv.writer(response)
        writer.writerow(['university_key','university_name'])
        for row in load_program_year()[['university_key','university_name']].drop_duplicates().itertuples(index=False):
            writer.writerow(row)
        return response

    def coverage(self,request):
        if not self.has_view_permission(request): raise PermissionDenied
        file=Path(__file__).resolve().parents[2]/'data/dataset/recovery_school_year_gaps.csv'
        rows=[]
        if file.exists():
            with file.open(encoding='utf-8-sig',newline='') as stream:
                rows=list(csv.DictReader(stream))
        year=request.GET.get('year','')
        if year in {'2023','2024','2025','2026'}: rows=[row for row in rows if row['year']==year]
        context={**self.admin_site.each_context(request),'title':'Trường còn thiếu dữ liệu',
                 'page':Paginator(rows,50).get_page(request.GET.get('page')),'selected_year':year,
                 'years':['2023','2024','2025','2026'],'total':len(rows),'opts':self.model._meta}
        return TemplateResponse(request,'admin/catalog/admissionrelease/coverage.html',context)

    def sample(self,request):
        if not self.has_add_permission(request): raise PermissionDenied
        response=HttpResponse('\ufeff'+','.join(FIELDS)+'\r\n',content_type='text/csv; charset=utf-8')
        response['Content-Disposition']='attachment; filename="diem-tuyen-sinh-mau.csv"'
        return response


@admin.register(SavedUniversity)
class SavedUniversityAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "university_key",
        "created_at",
    )
    search_fields = (
        "user__username",
        "user__first_name",
        "university_key",
    )
    list_filter = (
        "created_at",
    )
