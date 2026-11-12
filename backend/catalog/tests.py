import csv
import io
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import AdmissionRelease
from .official import official_rows
from .releases import FIELDS, parse_upload, change_release


class AdmissionReleaseTests(TestCase):
    def setUp(self):
        self.owner=User.objects.create_superuser('data-owner',password='TestAdmin!982')
        self.member=User.objects.create_user('normal-member')
        self.row=dict(university_key='dai hoc tan tao',university_name='Trường ĐH Tân Tạo',
            major_code='DEMO',major_name='Ngành kiểm thử',year='2026',cutoff_score='19.25',
            admission_method='THPT - test only',source_url='https://ttu.edu.vn/test-notice')

    def upload(self,rows):
        out=io.StringIO()
        writer=csv.DictWriter(out,fieldnames=FIELDS)
        writer.writeheader(); writer.writerows(rows)
        return out.getvalue().encode('utf-8-sig')

    def test_preview_publish_withdraw_and_no_training_side_effect(self):
        release=AdmissionRelease.objects.create(title='Test only',rows=parse_upload(self.upload([self.row])),source_sha256='a'*64)
        self.assertFalse(any(r['major_code']=='DEMO' for r in official_rows()))
        with self.assertRaises(ValidationError): change_release(release.pk,self.member,'publish')
        change_release(release.pk,self.owner,'publish')
        rows=official_rows(university_key=self.row['university_key'],years=[2026])
        new=[r for r in rows if r['major_code']=='DEMO']
        self.assertEqual(len(new),1)
        self.assertFalse(new[0]['comparable_thpt'])
        import json
        json.dumps(rows,allow_nan=False)
        duplicate=AdmissionRelease.objects.create(title='Duplicate',rows=release.rows,source_sha256='b'*64)
        with self.assertRaises(ValidationError): change_release(duplicate.pk,self.owner,'publish')
        change_release(release.pk,self.owner,'withdraw')
        self.assertFalse(any(r['major_code']=='DEMO' for r in official_rows()))
        release.refresh_from_db()
        self.assertEqual(release.reviewed_by,self.owner)
        self.assertEqual(release.status,'withdrawn')

    def test_invalid_score_identity_source_and_duplicates_rejected(self):
        for changes in [dict(cutoff_score='NaN'),dict(cutoff_score='inf'),dict(year='2027'),
                        dict(university_name='Wrong school'),dict(source_url='https://ttu.edu.vn.evil.com/x'),
                        dict(source_url='http://ttu.edu.vn/x')]:
            with self.subTest(changes=changes),self.assertRaises(ValidationError):
                parse_upload(self.upload([{**self.row,**changes}]))
        with self.assertRaises(ValidationError): parse_upload(self.upload([self.row,self.row]))

    def test_admin_upload_requires_review_and_checkbox(self):
        self.client.force_login(self.owner)
        response=self.client.post(reverse('admin:catalog_admissionrelease_add'),
            {'title':'Bản nhập thử','csv_file':SimpleUploadedFile('input.csv',self.upload([self.row])),'_save':'Lưu'})
        self.assertEqual(response.status_code,302)
        release=AdmissionRelease.objects.get()
        self.assertEqual(release.status,'draft')
        url=reverse('admin:catalog_admissionrelease_change',args=[release.pk])
        self.assertContains(self.client.get(url),'Đối chiếu nguồn')
        self.client.post(url,{'_publish':'1'})
        release.refresh_from_db(); self.assertEqual(release.status,'draft')
        self.client.post(url,{'_publish':'1','source_checked':'1'})
        release.refresh_from_db(); self.assertEqual(release.status,'published')

    def test_member_cannot_download_template_or_edit_release(self):
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(reverse('admin:catalog_admissionrelease_template')).status_code,302)
