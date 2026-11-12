"""Offline, hash-checked import of reviewed TTU image and UET conflict evidence."""
import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup
from scrape_missing_2025_2026 import COLUMNS, RECOVERY, accept_new, read, save, safe_api_row, legacy
from continue_verified_recovery import SOURCES, OUT

ROOT = Path(__file__).resolve().parents[1]


def checked(name):
    record = next(r for r in json.loads((OUT/'manifest.json').read_text(encoding='utf-8')) if r['id'] == name)
    blob = (OUT/f'{name}.html').read_bytes()
    if record.get('status') != 200 or hashlib.sha256(blob).hexdigest() != record['sha256']:
        raise ValueError(f'Invalid primary snapshot: {name}')
    soup = BeautifulSoup(blob, 'html.parser')
    if not soup.title or '2026' not in soup.title.get_text():
        raise ValueError('Wrong notice year')
    return soup, record


def uet_candidates():
    soup, _ = checked('uet_2026')
    primary = {}
    for tr in soup.find('table').find_all('tr'):
        cells = [c.get_text(' ', strip=True) for c in tr.find_all(['td', 'th'])]
        for code in ('CN3', 'CN4'):
            if code in cells:
                i = cells.index(code)
                primary[code] = float(cells[i+1].replace(',', '.'))
    if primary != {'CN3': 25.41, 'CN4': 26.13}:
        raise ValueError('Reviewed primary UET cells changed')
    conflicts = json.loads((ROOT/'data/raw/official_20261106/api_score_changes_review.json').read_text(encoding='utf-8'))
    result = []
    for conflict in conflicts:
        url, code = conflict['source_url'], conflict['major_code']
        payload = json.loads((RECOVERY/(hashlib.sha256(url.encode()).hexdigest()[:16]+'.json')).read_text(encoding='utf-8'))
        matches = [r for r in payload['data'] if safe_api_row(r)
                   and str(r.get('school_id')) == '311' and str(r.get('year')) == '2026'
                   and str(r.get('mark_type')) == '1'
                   and str(r.get('display_code') or r.get('code')) == code]
        if len(matches) != 1 or legacy.parse_thpt_score(matches[0].get('mark')) != primary[code]:
            raise ValueError('Primary/API cross-check failed')
        current = matches[0]
        result.append(dict(university_name=conflict['university_name'], major_code=code,
            major_name=legacy.clean_text(current['name']), year='2026', admission_method_codes='THPT',
            combination=current.get('block') or '', cutoff_score=primary[code], source_url=url,
            admission_note='Unconverted additive THPT API; cutoff independently confirmed in primary notice: '+SOURCES['uet_2026']))
    if len(result) != 2:
        raise ValueError('Expected exactly two reviewed conflicts')
    return pd.DataFrame(result, columns=COLUMNS)


def ttu_methods():
    _, record = checked('ttu_2026')
    image = OUT/'ttu_2026.jpg'
    reviewed_sha = '4b26a64bbb58f98626017ea41e4d1cbf5a64cd6ea021d7492c479f4d9bf77cf3'
    if hashlib.sha256(image.read_bytes()).hexdigest() != reviewed_sha or record['score_image']['sha256'] != reviewed_sha:
        raise ValueError('Visually reviewed TTU image changed')
    # Visually transcribed ONLY PT100, never the adjacent transcript/aptitude columns.
    # The image does not publish program codes: leave them blank; no inferred code
    # or merge with historical programs is allowed in the training dataset.
    values = [('Y khoa (Bác sĩ Đa khoa)',22), ('Điều dưỡng',18),
        ('Kỹ thuật xét nghiệm Y học',18), ('Quản trị kinh doanh',15),
        ('Kinh doanh quốc tế',15), ('Tài chính - Ngân hàng',15), ('Kế toán',15),
        ('Marketing (Chuyên ngành Digital Marketing)',15),
        ('Logistic và Quản lý chuỗi cung ứng',15), ('Truyền thông đa phương tiện',15),
        ('Luật',20), ('Luật Kinh tế',20), ('Khoa học máy tính',15),
        ('Trí tuệ nhân tạo',15), ('Khoa học dữ liệu',15), ('Công nghệ thông tin',15),
        ('Công nghệ sinh học',15), ('Nông nghiệp (Chuyên ngành Nông nghiệp Công nghệ cao)',15),
        ('Ngôn ngữ Anh',15), ('Ngôn ngữ Trung Quốc',15), ('Ngôn ngữ Hàn Quốc',15)]
    return pd.DataFrame([dict(university_key='dai hoc tan tao', university_name='Trường ĐH Tân Tạo',
        school_code='TTU', city='', major_code='', major_name=major, year=2026, cutoff_score=score,
        admission_method='Xét điểm thi TN THPT (PT100); chưa xác minh mã ngành 2026 để ghép dữ liệu huấn luyện',
        comparable_thpt=False, source_url=SOURCES['ttu_2026'], evidence_path=str(image.relative_to(ROOT)).replace('\\','/'))
        for major, score in values])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    candidates, methods = uet_candidates(), ttu_methods()
    extra = ROOT/'data/processed/admission_scores_2026_supplemental.csv'
    old = read(extra)
    base = pd.concat([read(ROOT/'data/processed/admission_scores_2026_ml_ready.csv'), old], ignore_index=True)
    accepted, rejected = accept_new(base, candidates)
    save(candidates, OUT/'reviewed_uet_candidates.csv')
    save(methods, OUT/'reviewed_ttu_methods.csv')
    report = {'uet_primary_confirmed':len(candidates), 'new_training_rows':len(accepted),
        'ttu_published_pt100_rows_separate':len(methods),
        'excluded_sources':{'thanhdong_2025':'Redirected homepage; notice identity not confirmed',
                            'agu_2026':'HTTP error; no usable primary evidence'},
        'huit_2026':'44 published codes already present; no missing code added',
        'ttu_training_exclusion':'Official image has no program codes. Do not infer identity from older years.'}
    if args.apply:
        save(pd.concat([old, accepted], ignore_index=True).drop_duplicates(), extra)
        path = ROOT/'data/dataset/admissions_official_methods.csv'
        existing = read(path)
        save(pd.concat([existing, methods.assign(year='2026')], ignore_index=True)
             .drop_duplicates(['university_key','major_code','major_name','year','admission_method']), path)
    report['applied'] = args.apply
    report_name = 'import_report.json' if args.apply else 'validation_report.json'
    (OUT/report_name).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    main()
