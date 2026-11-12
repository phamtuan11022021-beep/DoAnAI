"""Read reviewed primary table columns; stage first, --apply to merge missing rows."""
import argparse
import hashlib
import json
import re
import sys
from functools import lru_cache
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

from fetch_official_gaps import SOURCES
from import_udn_official import SCHOOLS
from import_udn_official import SOURCE as OLD_UDN_SOURCE, parse as parse_old_udn
from scrape_missing_2025_2026 import COLUMNS, accept_new, read, save

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw/official_20261106'
sys.path.insert(0, str(ROOT / 'ai'))
from prepare_dataset_4years_FINAL import normalize_school_key, normalize_major_code, normalize_basic


def source_soup(name):
    record = next(r for r in json.loads((RAW/'manifest.json').read_text(encoding='utf-8')) if r['id'] == name)
    blob = (RAW/f'{name}.html').read_bytes()
    if record.get('status') != 200 or hashlib.sha256(blob).hexdigest() != record['sha256']:
        raise ValueError(f'Invalid primary snapshot: {name}')
    soup = BeautifulSoup(blob, 'html.parser')
    year = name.rsplit('_', 1)[1]
    titles = ([soup.title] if soup.title else []) + list(soup.find_all('h1'))
    if not any(year in heading.get_text(' ', strip=True) and 'diem' in normalize_basic(heading.get_text(' ', strip=True))
               for heading in titles):
        raise ValueError(f'Primary notice title does not confirm {year}: {name}')
    return soup


def row(name, school, code, major, score, combination='', note=''):
    return dict(university_name=school, major_code=code, major_name=major,
                year=name.rsplit('_', 1)[1], admission_method_codes='THPT',
                combination=combination, cutoff_score=float(str(score).replace(',', '.')),
                admission_note='Primary notice; exact THPT column; '+note, source_url=SOURCES[name])


def parse_vimaru(soup, year):
    name = f'vimaru_{year}'
    table = soup.find_all('table')[1]
    rows = []
    if 'PT1' not in soup.get_text(' ', strip=True) or 'D01' not in soup.get_text(' ', strip=True):
        raise ValueError('VIMARU notice must explicitly identify PT1 and D01')
    for tr in table.find_all('tr'):
        cells = [c.get_text(' ', strip=True) for c in tr.find_all(['th', 'td'], recursive=False)]
        if len(cells) != 3 or not re.fullmatch(r'[ADHS]\d{3}', cells[1]):
            continue
        major, code, score = cells
        # 2025 foreign languages explicitly use a 40-point English-weighted
        # scale. Keep both years conservative and never divide those scores.
        if code in {'D124', 'D125'}:
            continue
        major = re.sub(r'^\d+\.\s*', '', major)
        if not re.fullmatch(r'\d{1,2}(?:[.,]\d+)?', score) or not 10 <= float(score.replace(',', '.')) <= 30:
            raise ValueError(f'Unexpected PT1 score: {code}, {score}')
        rows.append(row(name, 'Trường Đại Học Hàng Hải Việt Nam', code, major, score, 'D01',
                        f'PT1; published program code; reference combination D01; table=1; foreign-language scale excluded'))
    if len(rows) < 40:
        raise ValueError('Incomplete VIMARU primary table')
    return rows


def parse_udn(soup, year):
    name = f'udn_{year}'
    if 'thpt' not in normalize_basic(soup.find('h1').get_text(' ', strip=True)):
        raise ValueError('UDN notice does not identify THPT in its title')
    rows, school = [], None
    for tr in soup.find_all('table')[0].find_all('tr'):
        cells = [c.get_text(' ', strip=True) for c in tr.find_all(['th', 'td'], recursive=False)]
        if len(cells) not in (4, 5):
            continue
        ordinal, code, major, score = cells[:4]
        if not ordinal.isdigit():
            if code in SCHOOLS:
                school = code
            elif re.fullmatch(r'[A-Z]{3}', code):
                school = None
            continue
        # Deliberately do not import weighted language/aptitude scores merely
        # because the notice normalizes all results to 30 points.
        if school not in {'DDK', 'DSK', 'VKU', 'DDY'}:
            continue
        if not re.match(r'^(742|744|746|748|751|752|754|772)\d', code):
            continue
        if not re.fullmatch(r'\d{1,2}(?:[.,]\d+)?', score):
            continue
        rows.append(row(name, SCHOOLS[school][1], code, major, score, note=f'school={school}; standard STEM/health program; combinations not specified'))
    if len(rows) < 40:
        raise ValueError('Incomplete UDN primary table')
    return rows


def parse_uneti(soup):
    rows = []
    for tr in soup.find('table').find_all('tr'):
        cells = [c.get_text(' ', strip=True) for c in tr.find_all(['th', 'td'], recursive=False)]
        if len(cells) != 7 or not cells[0].isdigit():
            continue
        ordinal, code, major, thpt, transcript, aptitude, thinking = cells
        if normalize_basic(major).startswith('ngon ngu'):
            continue  # includes a truncated language code in the primary HTML
        if not re.fullmatch(r'7\d{6}DK[DK]', code):
            raise ValueError('UNETI campus suffix missing')
        rows.append(row('uneti_2025', 'Trường Đại Học Kinh Tế Kỹ Thuật Công Nghiệp', code,
                        major, thpt, note='column KQ thi TN THPT only; published DKK/DKD campus suffix preserved'))
    if len(rows) != 48:
        raise ValueError('UNETI table structure changed')
    return rows


@lru_cache(maxsize=8)
def primary_keys(source_url):
    if source_url == 'https://vuted.edu.vn/Resources/Document/2026/8/2026-skv_d1_qd_diem-chuan-trung-tuyen.pdf':
        from import_recovery_nov08 import primary_keys as vinh_keys
        return vinh_keys()
    if source_url == 'https://ttu.edu.vn/truong-dai-hoc-tan-tao-cong-bo-diem-chuan-trung-tuyen-dai-hoc-chinh-quy-nam-2026/':
        from import_completion_ttu import primary_keys as ttu_keys
        return ttu_keys()
    if source_url == OLD_UDN_SOURCE:
        path = ROOT/'data/raw/official_20261030/udn_2026.html'
        report = json.loads((ROOT/'docs/UDN_OFFICIAL_IMPORT_20261030.json').read_text(encoding='utf-8'))
        if hashlib.sha256(path.read_bytes()).hexdigest() != report['sha256']:
            raise ValueError('Existing official UDN evidence changed')
        frame = parse_old_udn(path.read_text(encoding='utf-8'))
        return {(r.university_key, normalize_major_code(r.major_code), '2026', float(r.cutoff_score), '')
                for r in frame[frame.comparable_thpt].itertuples()}
    name = next((name for name, url in SOURCES.items() if url == source_url), None)
    if name is None or name.startswith('cmc_'):
        return set()
    year = int(name.rsplit('_', 1)[1])
    soup = source_soup(name)
    if name.startswith('udn_'):
        rows = parse_udn(soup, year)
    elif name.startswith('vimaru_'):
        rows = parse_vimaru(soup, year)
    else:
        rows = parse_uneti(soup)
    return {(normalize_school_key(r['university_name']), normalize_major_code(r['major_code']),
             str(r['year']), float(r['cutoff_score']), r['combination']) for r in rows}


def validate_primary_row(record):
    key = (normalize_school_key(record['university_name']), normalize_major_code(record['major_code']),
           str(record['year']), float(record['cutoff_score']), str(record.get('combination', '')))
    return record['admission_method_codes'] == 'THPT' and key in primary_keys(record['source_url'])


def reviewed_cmc_2026():
    # Transcribed from cmc_2026.jpg after visual column/year verification.
    # The notice also publishes a THPT-40 column: retain its declared 30-point
    # column separately, without asserting unweighted comparability for training.
    values = [
        ('AI', 'Trí tuệ Nhân tạo', 20.18), ('IT', 'Công nghệ Thông tin', 18.98),
        ('NS', 'An ninh Mạng', 19.95), ('CS', 'Khoa học Máy tính', 20.18),
        ('SE', 'Kỹ thuật Phần mềm', 18.98), ('ET', 'Công nghệ Kỹ thuật Điện tử - Viễn thông (Thiết kế vi mạch bán dẫn)', 20.18),
        ('BA', 'Quản trị Kinh doanh', 18), ('IB', 'Kinh doanh Quốc tế', 18),
        ('LS', 'Logistics và Quản lý chuỗi cung ứng', 19.05), ('MK', 'Digital Marketing', 18),
        ('EM', 'Thương mại Điện tử', 18), ('MC', 'Truyền thông Đa phương tiện', 18),
        ('PR', 'Quan hệ Công chúng', 18), ('GD', 'Thiết kế Đồ họa', 17.63),
        ('GA', 'Đồ họa Game', 17.63), ('DA', 'Thiết kế Mỹ thuật số', 17.63),
        ('CL', 'Ngôn ngữ Trung Quốc', 17.03), ('CB', 'Tiếng Trung Thương mại', 17.03),
        ('CL-IP', 'Ngôn ngữ Trung Quốc (CT 2+2 giữa CMC và CNU)', 17.03), ('KL', 'Ngôn ngữ Hàn Quốc', 17.03),
    ]
    record = next(r for r in json.loads((RAW/'manifest.json').read_text(encoding='utf-8')) if r['id'] == 'cmc_2026')
    image = next(asset for asset in record['score_images'] if asset['path'].endswith('.jpg'))
    if hashlib.sha256((ROOT/image['path']).read_bytes()).hexdigest() != image['sha256']:
        raise ValueError('CMC reviewed image changed')
    return [dict(university_key='dai hoc cmc', university_name='Trường ĐH CMC', school_code='CMC',
                 city='', major_code=code, major_name=major, year=2026, cutoff_score=score,
                 admission_method='THPT - cột thang 30 do trường công bố; không dùng train THPT thuần',
                 comparable_thpt=False, source_url=SOURCES['cmc_2026'], evidence_path=image['path'])
            for code, major, score in values]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    candidates = []
    for year in [2023, 2024, 2025]:
        candidates.extend(parse_udn(source_soup(f'udn_{year}'), year))
    for year in [2025, 2026]:
        candidates.extend(parse_vimaru(source_soup(f'vimaru_{year}'), year))
    candidates.extend(parse_uneti(source_soup('uneti_2025')))
    frame = pd.DataFrame(candidates, columns=COLUMNS)
    save(frame, RAW/'reviewed_thpt_candidates.csv')
    methods = pd.DataFrame(reviewed_cmc_2026())
    save(methods, RAW/'reviewed_cmc_methods.csv')
    summary = {'primary_candidates': len(frame), 'cmc_published_methods_separate': len(methods), 'years': {}}
    for year, group in frame.groupby('year'):
        base_path = ROOT/f'data/processed/admission_scores_{year}_ml_ready.csv'
        extra_path = ROOT/f'data/processed/admission_scores_{year}_supplemental.csv'
        old = read(extra_path) if extra_path.exists() else pd.DataFrame(columns=COLUMNS)
        base = pd.concat([read(base_path), old], ignore_index=True)
        # Match exact normalized institution/program identity before deduplication.
        identity = base.copy()
        identity['university_name'] = identity.university_name.map(normalize_school_key)
        identity['major_code'] = identity.major_code.map(normalize_major_code)
        normalized = group.copy()
        normalized['university_name'] = normalized.university_name.map(normalize_school_key)
        normalized['major_code'] = normalized.major_code.map(normalize_major_code)
        accepted, rejected = accept_new(identity, normalized)
        keys = set(zip(accepted.university_name, accepted.major_code, accepted.year.astype(str)))
        selected = group[[ (normalize_school_key(r.university_name), normalize_major_code(r.major_code), str(r.year)) in keys
                           for r in group.itertuples() ]].drop_duplicates()
        if not all(validate_primary_row(record) for record in selected.to_dict('records')):
            raise ValueError('Primary cell evidence mismatch; no write allowed')
        summary['years'][str(year)] = {'candidates': len(group), 'new_rows': len(selected), 'rejected': len(rejected)}
        save(selected, RAW/f'new_thpt_{year}.csv')
        if args.apply and not selected.empty:
            save(pd.concat([old, selected], ignore_index=True).drop_duplicates(), extra_path)
    if args.apply:
        existing = read(ROOT/'data/dataset/admissions_official_methods.csv')
        keys = ['university_key', 'major_code', 'year', 'admission_method']
        save(pd.concat([existing, methods.assign(year=methods.year.astype(str))], ignore_index=True).drop_duplicates(keys),
             ROOT/'data/dataset/admissions_official_methods.csv')
    (RAW/'import_report.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
