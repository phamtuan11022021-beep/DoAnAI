"""Import a saved official UDN table, preserving distinct admissions methods."""
from pathlib import Path
import hashlib
import json
import re
import pandas as pd
from bs4 import BeautifulSoup
from scrape_missing_2025_2026 import accept_new, COLUMNS, read, save

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'https://ts.udn.vn/DHCD/Chinhquy/diemchuan/19567'
SCHOOLS = {
    'DDK': ('dai hoc bach khoa dai hoc da nang', 'Trường ĐH Bách khoa - ĐH Đà Nẵng', 'Đà Nẵng'),
    'DDQ': ('dai hoc kinh te dai hoc da nang', 'Trường Đại Học Kinh Tế – Đại Học Đà Nẵng', 'Đà Nẵng'),
    'DDS': ('dai hoc su pham dai hoc da nang', 'Trường Đại Học Sư Phạm - Đại Học Đà Nẵng', 'Đà Nẵng'),
    'DDF': ('dai hoc ngoai ngu da nang', 'Trường Đại Học Ngoại Ngữ Đà Nẵng', 'Đà Nẵng'),
    'DSK': ('dai hoc su pham ky thuat dai hoc da nang', 'Trường Đại học Sư phạm Kỹ thuật - Đại học Đà Nẵng', 'Đà Nẵng'),
    'VKU': ('dai hoc cong nghe thong tin va truyen thong viet han dai hoc da nang', 'Trường Đại học Công nghệ Thông tin và Truyền thông Việt Hàn - Đại học Đà Nẵng', 'Đà Nẵng'),
    'DDY': ('y duoc dai hoc da nang', 'Trường Y Dược - ĐH Đà Nẵng', 'Đà Nẵng'),
    'DDV': ('vien nghien cuu va dao tao viet anh dai hoc da nang', 'Viện nghiên cứu và đào tạo Việt Anh - Đại học Đà Nẵng', 'Đà Nẵng'),
    'DDP': ('phan hieu dai hoc da nang tai kon tum', 'Phân Hiệu Đại Học Đà Nẵng tại Kon Tum', 'Kon Tum'),
}


def parse(html):
    soup = BeautifulSoup(html, 'html.parser')
    if 'năm 2026' not in soup.get_text(' ', strip=True):
        raise ValueError('Source year is not explicit')
    rows, school_code = [], None
    for tr in soup.select('table tr'):
        cells = [c.get_text(' ', strip=True) for c in tr.find_all(['td', 'th'])]
        if len(cells) != 5: continue
        ordinal, code, name, mark, method = cells
        if code in SCHOOLS and not ordinal.isdigit():
            school_code = code; continue
        if not ordinal.isdigit(): continue
        if school_code is None or not re.fullmatch(r'[A-Za-z0-9_.-]{2,40}', code):
            raise ValueError('Unknown school or program code')
        score = float(mark.replace(',', '.'))
        if not 0 <= score <= 30 or method not in (
                'Xét điểm thi THPT', 'Xét kết hợp điểm thi THPT + HB', 'Xét kết hợp HB + tiếng Anh'):
            raise ValueError('Unexpected method or score scale')
        key, school_name, city = SCHOOLS[school_code]
        # A branch program may have a different teaching site: retain its label.
        rows.append(dict(university_key=key, university_name=school_name, school_code=school_code,
                         city=city, major_code=code, major_name=name, year=2026, cutoff_score=score,
                         admission_method=method, comparable_thpt=method=='Xét điểm thi THPT',
                         source_url=SOURCE, evidence_path='data/raw/official_20261030/udn_2026.html'))
    if len(rows) < 200: raise ValueError('Official table unexpectedly incomplete')
    return pd.DataFrame(rows)


def main():
    path = ROOT / 'data/raw/official_20261030/udn_2026.html'
    frame = parse(path.read_text(encoding='utf-8'))
    save(frame, ROOT / 'data/dataset/admissions_official_methods.csv')
    candidates = frame[frame.comparable_thpt].copy()
    candidates['combination'] = ''  # Notice doesn't confirm combinations: never infer them.
    candidates['admission_method_codes'] = 'THPT'
    candidates['admission_note'] = 'Official UDN 2026; exact THPT method; scale 30; combinations not specified'
    processed = ROOT / 'data/processed'
    supplement_path = processed / 'admission_scores_2026_supplemental.csv'
    supplement = read(supplement_path)
    base = pd.concat([read(processed/'admission_scores_2026_ml_ready.csv'), supplement], ignore_index=True)
    additions, rejected = accept_new(base, candidates[COLUMNS])
    if not additions.empty:
        save(pd.concat([supplement, additions], ignore_index=True).drop_duplicates(), supplement_path)
    report = {'source_url': SOURCE, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
              'official_program_method_rows': len(frame), 'pure_thpt': len(candidates),
              'other_methods_not_used_as_thpt': len(frame)-len(candidates), 'added_thpt_rows': len(additions),
              'rejected': len(rejected)}
    (ROOT/'docs/UDN_OFFICIAL_IMPORT_20261030.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
