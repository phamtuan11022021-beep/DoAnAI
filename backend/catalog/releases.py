import csv
import io
import math
from urllib.parse import urlparse

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import AdmissionRelease, AdmissionReleaseLock

FIELDS = ['university_key','university_name','major_code','major_name','year',
          'cutoff_score','admission_method','source_url']


def identity(row):
    values = [row.get('university_key',''),row.get('major_code') or row.get('major_name',''),
              row.get('year',''),row.get('admission_method','')]
    return tuple(str(value).strip().casefold() for value in values)


def validate_rows(rows):
    from ai_chat.engine import load_program_year
    catalog = load_program_year()
    schools = {key:set(group.university_name.astype(str).str.strip().str.casefold())
               for key,group in catalog.groupby('university_key')}
    if not 1 <= len(rows) <= 1000:
        raise ValidationError('Mỗi đợt cần từ 1 đến 1.000 dòng.')
    clean, seen = [], set()
    for index, row in enumerate(rows, 2):
        try:
            item = {key:str(row.get(key,'')).strip() for key in FIELDS}
            if any(not item[key] for key in FIELDS if key != 'major_code'):
                raise ValueError('Thiếu trường bắt buộc')
            if any(len(value) > 1000 or '\x00' in value for value in item.values()):
                raise ValueError('Nội dung quá dài hoặc chứa ký tự không hợp lệ')
            if item['university_key'] not in schools:
                raise ValueError('Khóa trường chưa có trong danh mục; cần xác minh danh tính trường')
            if item['university_name'].casefold() not in schools[item['university_key']]:
                raise ValueError('Tên trường không khớp khóa trường trong danh mục')
            item['year'] = int(item['year'])
            if not 2023 <= item['year'] <= timezone.now().year:
                raise ValueError('Năm phải từ 2023 đến năm hiện tại')
            item['cutoff_score'] = float(item['cutoff_score'].replace(',','.'))
            if not math.isfinite(item['cutoff_score']) or not 0 < item['cutoff_score'] <= 1500:
                raise ValueError('Điểm phải là số hữu hạn, lớn hơn 0 và không quá 1500')
            url = urlparse(item['source_url'])
            if url.scheme != 'https' or not url.hostname or not url.hostname.endswith('.edu.vn') or url.username or url.password:
                raise ValueError('Cần URL HTTPS trên tên miền chính thức .edu.vn')
            item.update(comparable_thpt=False, city='', school_code='', evidence_path='')
            key = identity(item)
            if key in seen:
                raise ValueError('Dòng trùng trường/ngành/năm/phương thức trong tệp')
            seen.add(key)
            clean.append(item)
        except (ValueError, TypeError) as exc:
            raise ValidationError(f'Dòng {index}: {exc}.') from exc
    return clean


def parse_upload(blob):
    if len(blob) > 1024*1024:
        raise ValidationError('Tệp tối đa 1 MB.')
    try:
        reader = csv.DictReader(io.StringIO(blob.decode('utf-8-sig')))
        if not set(FIELDS).issubset(reader.fieldnames or []):
            raise ValidationError('Thiếu cột. Hãy tải tệp mẫu và giữ nguyên tiêu đề cột.')
        rows = []
        for row in reader:
            rows.append(row)
            if len(rows)>1000:
                raise ValidationError('Tối đa 1.000 dòng mỗi đợt.')
        return validate_rows(rows)
    except (UnicodeError,csv.Error) as exc:
        raise ValidationError('Tệp phải là CSV mã hóa UTF-8.') from exc


@transaction.atomic
def change_release(pk, user, action):
    if not user.has_perm('catalog.publish_admissionrelease'):
        raise ValidationError('Bạn chưa có quyền duyệt dữ liệu tuyển sinh.')
    AdmissionReleaseLock.objects.get_or_create(pk=1)
    AdmissionReleaseLock.objects.select_for_update().get(pk=1)
    release = AdmissionRelease.objects.select_for_update().get(pk=pk)
    if action == 'publish':
        if release.status != 'draft':
            raise ValidationError('Chỉ đợt chờ đối chiếu mới được công bố.')
        release.rows = validate_rows(release.rows)
        from .official import official_rows
        existing = {identity(row) for row in official_rows()}
        if any(identity(row) in existing for row in release.rows):
            raise ValidationError('Dữ liệu đã tồn tại. Không ghi đè điểm đã công bố; hãy kiểm tra lại nguồn.')
        release.status = 'published'
    elif action == 'withdraw':
        if release.status != 'published':
            raise ValidationError('Chỉ có thể thu hồi đợt đang hiển thị.')
        release.status = 'withdrawn'
    else:
        raise ValidationError('Thao tác không hợp lệ.')
    release.reviewed_by = user
    release.reviewed_at = timezone.now()
    release.save(update_fields=['rows','status','reviewed_by','reviewed_at'])
    return release
