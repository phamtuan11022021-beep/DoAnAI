"""Resume missing-program recovery (2023-2026) with year/method/source audits.

python scraper/scrape_missing_2025_2026.py --years 2025 2026 --limit 20
python scraper/scrape_missing_2025_2026.py --api-only --include-index --years 2023 2024 2025 2026 --limit 0
Accepted supplements are consumed by ai/prepare_dataset_4years_FINAL.py.
Locked original datasets are never overwritten.
"""
from __future__ import annotations
import argparse
import hashlib
import os
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import run_2025_pipeline as legacy

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / 'data/processed'
RECOVERY = ROOT / 'data/raw/supplemental_recovery'
COLUMNS = legacy.CANONICAL_COLUMNS


def read(path):
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def save(frame, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    frame.to_csv(temp, index=False, encoding='utf-8-sig')
    temp.replace(path)


def accept_new(base, candidates):
    """Only absent program-years; quarantine conflicting cutoffs, never pick one."""
    if candidates.empty:
        return pd.DataFrame(columns=COLUMNS), pd.DataFrame(columns=COLUMNS)
    candidates = candidates[COLUMNS].fillna('').copy()
    candidates['cutoff_score'] = pd.to_numeric(candidates.cutoff_score, errors='coerce')
    valid = (candidates.cutoff_score.between(10, 30)
             & candidates.admission_method_codes.eq('THPT')
             & candidates.major_code.str.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{1,39}')
             & candidates.major_name.str.len().gt(2))
    rejected = candidates[~valid].copy()
    work = candidates[valid].copy()
    keys = ['university_name', 'major_code', 'year']
    for frame in (base, work):
        frame['year'] = frame.year.astype(str)
    existing = set(map(tuple, base[keys].to_numpy()))
    absent = pd.Series([tuple(row) not in existing for row in work[keys].to_numpy()], index=work.index, dtype=bool)
    work = work.loc[absent]
    if not work.empty:
        conflict = work.groupby(keys).cutoff_score.transform('nunique').gt(1)
        rejected = pd.concat([rejected, work[conflict]], ignore_index=True)
        work = work[~conflict].drop_duplicates(keys + ['combination', 'cutoff_score'])
    return work[COLUMNS], rejected[COLUMNS]


def page_school_id(html, school_code):
    """Prefer a school_id explicitly paired with the requested alias/code.

    Pages may embed admission tables of other schools. Never choose a numeric
    ID by frequency or position; an exact sibling schoolAliasCode is required.
    """
    parts = []
    # Only decode literal inline script bodies; avoid building the entire DOM
    # (some cached score pages contain several MB of duplicated table markup).
    for raw in re.findall(r'<script\b[^>]*>(.*?)</script\s*>', html, flags=re.S | re.I):
        raw = raw.strip()
        if not raw.startswith('self.__next_f.push('):
            continue
        try:
            block = json.loads(raw[len('self.__next_f.push('):-1])
            if isinstance(block, list) and len(block) > 1 and isinstance(block[1], str):
                parts.append(block[1])
        except (ValueError, TypeError):
            continue
    blob = ''.join(parts)
    pattern = (r'"school_id":\s*(\d+)\s*\}\s*,\s*"schoolAliasCode":\s*\{\s*'
               r'"alias":\s*"[^"\\]*"\s*,\s*"code":\s*"' + re.escape(school_code) + r'"\s*\}')
    paired = set(re.findall(pattern, blob, flags=re.I))
    ids = paired or set(re.findall(r'"school_id":([0-9]+)', blob))
    return ids.pop() if len(ids) == 1 else None


def recover_2025_api(name, index, year=2025):
    """Public historical endpoint; legacy function name kept for compatibility."""
    item, _ = legacy.match_tuyensinh247_school(name, index)
    if item is None:
        return [], 'No verified school identity'
    if legacy.normalize_school(name) in {legacy.normalize_school(n) for n in legacy.TS247_FORCE_REVIEW_SCHOOLS}:
        return [], 'School requires manual campus/score-scale review'
    page = legacy.get_url(item['score_url'])
    ok, reason = legacy.validate_ts247_page_identity(
        requested_university_name=name, matched_item=item, html_text=page.text, url=item['score_url'])
    if not ok:
        return [], reason
    school_id = page_school_id(page.text, item['school_code'])
    if not school_id:
        return [], 'Ambiguous or absent source school ID'
    url = legacy.TS247_BASE + '/api/common/cutoff-score?school_id=' + school_id + '&method_id=1&year=' + str(year)
    response = legacy.get_url(url)
    body = response.json()
    (RECOVERY / (hashlib.sha256(url.encode()).hexdigest()[:16]+'.json')).write_text(
        json.dumps(body, ensure_ascii=False), encoding='utf-8')
    if isinstance(body, dict):
        body = body.get('data', body.get('results', []))
    if not isinstance(body, list):
        return [], 'Unexpected historical endpoint response'
    rows = []
    for row in body:
        if (not isinstance(row, dict) or str(row.get('year')) != str(year)
                or str(row.get('mark_type')) != '1' or str(row.get('school_id')) != school_id):
            continue
        note = legacy.clean_text(row.get('introtext'))
        formula = str(row.get('formula') or '')
        if not safe_api_row(row):
            continue
        score = legacy.parse_thpt_score(row.get('mark'))
        code = str(row.get('display_code') or row.get('code') or '').strip()
        if score is None or not code:
            continue
        rows.append({'university_name': name, 'major_code': code,
                     'major_name': legacy.clean_text(row.get('name')), 'year': str(year),
                     'admission_method_codes': 'THPT', 'combination': row.get('block') or '',
                     'cutoff_score': score, 'admission_note': f'Historical API {year}; THPT; '+note,
                     'source_url': url})
    return rows, f'Public historical endpoint; explicit year={year}, mark_type=1; unconverted scores'


def safe_api_row(row):
    """Require explicit unconverted THPT; reject unknown/weighted score formulas."""
    if (row.get('is_converted_score') not in (0, False)
            or row.get('admission_alias') != 'diem-thi-thpt'
            or legacy._ts247_row_note_is_unsafe(legacy.clean_text(row.get('introtext')))):
        return False
    formula = re.sub(r'\s+', '', str(row.get('formula') or '')).upper()
    if formula:
        # Permit only additive three-subject totals plus declared bonuses.
        terms = formula.replace('(', '').replace(')', '').split('+')
        if sorted(t for t in terms if t.startswith('MON_')) != ['MON_1', 'MON_2', 'MON_3']:
            return False
        if any(t not in ('MON_1', 'MON_2', 'MON_3', 'UT', 'KK') for t in terms):
            return False
    return True


def bulk_api_recovery(args, index, names):
    """Read public school/year endpoints concurrently; only the main thread writes CSVs."""
    if args.include_index:
        known_codes = set()
        for name in names:
            match, _ = legacy.match_tuyensinh247_school(name, index)
            if match:
                known_codes.add(match['school_code'])
        for item in index:
            name = item['school_name']
            norm = legacy.normalize_match_name(name)
            if (item['school_code'] not in known_codes and
                    ('dai hoc' in norm or 'hoc vien' in norm) and 'cao dang' not in norm):
                names.append(name)
                known_codes.add(item['school_code'])
    names = sorted(set(names))
    inventory_years = sorted(set(args.years) | {
        int(path.stem.rsplit('_', 1)[-1]) for path in RECOVERY.glob('api_report_*.csv')
        if path.stem.rsplit('_', 1)[-1].isdigit()})
    (RECOVERY / 'school_inventory.json').write_text(json.dumps(
        {'years': inventory_years, 'schools': names, 'source_index': legacy.TS247_INDEX_URL},
        ensure_ascii=False, indent=2), encoding='utf-8')
    bases, supplements, reports = {}, {}, {}
    for year in args.years:
        locked = PROCESSED / f'admission_scores_{year}_ml_ready.csv'
        out = PROCESSED / f'admission_scores_{year}_supplemental.csv'
        supplements[year] = read(out) if out.exists() else pd.DataFrame(columns=COLUMNS)
        bases[year] = pd.concat([read(locked), supplements[year]], ignore_index=True)
        report = RECOVERY / f'api_report_{year}.csv'
        reports[year] = read(report).to_dict('records') if report.exists() else []
    latest = {year: {r['university_name']: r for r in reports[year]} for year in args.years}
    jobs = [(name, year) for name in names for year in args.years
            if args.refresh or name not in latest[year] or
            (args.retry_reason and args.retry_reason in latest[year][name]['reason'])]
    if args.limit:
        selected = set(name for name, _ in jobs[:args.limit * len(args.years)])
        jobs = [(name, year) for name, year in jobs if name in selected]
    print(f'Historical API: {len(names)} schools; {len(jobs)} school-year requests; workers={args.workers}', flush=True)
    def fetch(name, year):
        try:
            rows, reason = recover_2025_api(name, index, year=year)
            return rows, reason
        except Exception as exc:
            return [], f'ERROR: {type(exc).__name__}: {exc}'
        finally:
            time.sleep(max(0, args.delay))
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(fetch, name, year): (name, year) for name, year in jobs}
        for count, future in enumerate(as_completed(futures), 1):
            name, year = futures[future]
            rows, reason = future.result()
            raw = pd.DataFrame(rows, columns=COLUMNS)
            slug = legacy.normalize_match_name(name).replace(' ', '_')
            save(raw, RECOVERY / f'api_{year}_{slug}.csv')
            additions, rejected = accept_new(bases[year].copy(), raw)
            if not rejected.empty:
                save(rejected, RECOVERY / f'api_{year}_{slug}_review.csv')
            if not additions.empty:
                supplements[year] = pd.concat([supplements[year], additions], ignore_index=True).drop_duplicates()
                bases[year] = pd.concat([bases[year], additions], ignore_index=True)
                save(supplements[year][COLUMNS], PROCESSED / f'admission_scores_{year}_supplemental.csv')
            reports[year].append({'university_name': name, 'year': year, 'fetched': len(rows),
                'added': len(additions), 'rejected': len(rejected), 'reason': reason})
            save(pd.DataFrame(reports[year]), RECOVERY / f'api_report_{year}.csv')
            print(f'[{count}/{len(jobs)}] {year} {name}: fetched={len(rows)} added={len(additions)} rejected={len(rejected)} {reason}', flush=True)
    for year in args.years:
        audit_api_supplement(year)


def audit_api_supplement(year=2025):
    """Recheck persisted API evidence, including score formulas, without network."""
    path = PROCESSED / f'admission_scores_{year}_supplemental.csv'
    if not path.exists():
        return
    frame = read(path)
    keep, rejected = [], []
    for row in frame.to_dict('records'):
        url = row['source_url']
        if '/api/common/cutoff-score?' not in url:
            keep.append(row)
            continue
        evidence = RECOVERY / (hashlib.sha256(url.encode()).hexdigest()[:16]+'.json')
        body = json.loads(evidence.read_text(encoding='utf-8')) if evidence.exists() else {}
        records = body.get('data', []) if isinstance(body, dict) else body
        matches = [r for r in records if str(r.get('display_code') or r.get('code') or '').strip() == row['major_code']
                   and str(r.get('year')) == str(year) and str(r.get('mark_type')) == '1'
                   and str(r.get('block') or '') == row['combination']
                   and legacy.parse_number(r.get('mark')) == float(row['cutoff_score'])]
        safe = bool(matches) and all(safe_api_row(r) for r in matches)
        (keep if safe else rejected).append(row)
    save(pd.DataFrame(keep, columns=COLUMNS), path)
    if rejected:
        review_path = RECOVERY / f'api_formula_review_{year}.csv'
        previous = read(review_path) if review_path.exists() else pd.DataFrame(columns=COLUMNS)
        save(pd.concat([previous, pd.DataFrame(rejected, columns=COLUMNS)], ignore_index=True).drop_duplicates(), review_path)
    print(f'{year} API evidence audit: kept={len(keep)}, formula/evidence review={len(rejected)}', flush=True)


def audit_2026_supplement():
    path = PROCESSED / 'admission_scores_2026_supplemental.csv'
    if not path.exists():
        return
    frame = read(path)
    accepted, rejected = [], []
    for url, group in frame.groupby('source_url'):
        if '/api/common/cutoff-score?' in url:
            accepted.append(group)
            continue
        # Dedicated primary-column parsers can safely inspect a THPT column in
        # a notice that also contains other methods or conversion tables.
        from import_official_gaps import SOURCES, OLD_UDN_SOURCE, validate_primary_row
        if url in SOURCES.values() or url == OLD_UDN_SOURCE or url in ('https://vuted.edu.vn/Resources/Document/2026/8/2026-skv_d1_qd_diem-chuan-trung-tuyen.pdf', 'https://ttu.edu.vn/truong-dai-hoc-tan-tao-cong-bo-diem-chuan-trung-tuyen-dai-hoc-chinh-quy-nam-2026/'):
            verified = group.apply(lambda record: validate_primary_row(record.to_dict()), axis=1)
            if verified.any():
                accepted.append(group[verified])
            if (~verified).any():
                rejected.append(group[~verified])
            continue
        digest = hashlib.sha256(url.encode()).hexdigest()[:16]
        pdf = RECOVERY / (digest + '.pdf')
        html = RECOVERY / (digest + '.html')
        if pdf.exists():
            with legacy.pymupdf.open(pdf) as doc:
                text = '\n'.join(page.get_text() for page in doc)
        elif html.exists():
            text = BeautifulSoup(html.read_text(encoding='utf-8'), 'html.parser').get_text(' ', strip=True)
        else:
            text = ''
        norm = legacy.normalize_match_name(text)
        ambiguous = not text.strip() or any(term in norm for term in (
            'quy doi', 'hoc ba', 'dgnl', 'danh gia nang luc', 'danh gia tu duy'))
        (rejected if ambiguous else accepted).append(group)
    save(pd.concat(accepted, ignore_index=True) if accepted else pd.DataFrame(columns=COLUMNS), path)
    if rejected:
        save(pd.concat(rejected, ignore_index=True), RECOVERY / 'mixed_method_review_2026.csv')
    print('2026 evidence audit: kept=' + str(sum(len(g) for g in accepted))
          + ', review=' + str(sum(len(g) for g in rejected)), flush=True)


def recover_2026(name, sources, parser, crossyear):
    rows = []
    notes = []
    def parse_asset(url, content):
        digest = hashlib.sha256(url.encode()).hexdigest()[:16]
        if content.startswith(b'%PDF'):
            path = RECOVERY / (digest + '.pdf')
            path.write_bytes(content)
            # Multi-method conversion tables need a dedicated audited column mapper.
            with legacy.pymupdf.open(path) as document:
                visible = '\n'.join(page.get_text() for page in document)
            normalized = legacy.normalize_match_name(visible)
            if any(term in normalized for term in ('quy doi', 'hoc ba', 'dgnl', 'danh gia nang luc', 'danh gia tu duy')):
                notes.append('REVIEW: mixed methods or converted-score PDF')
                return
            frame, context, diagnostic = parser.parse_pdf_source(
                path, university_name=name, source_url=url, crossyear_map=crossyear)
            notes.append(diagnostic)
            if '2026' not in context:
                return
            for row in frame.to_dict('records'):
                if parser.ml_compatible(pd.Series(row))[0]:
                    rows.append(row)
    for source in sources[sources.university_name.eq(name)].to_dict('records'):
        if str(source.get('linked_from_aggregate', '')).lower() != 'true':
            continue
        for url in source['source_urls'].split(';'):
            url = url.strip()
            if not url or source.get('source_type') in ('UNLINKED', 'GOOGLE_DRIVE'):
                continue
            response = legacy.get_url(url, timeout=30)
            if response.content.startswith(b'%PDF'):
                parse_asset(url, response.content)
                continue
            soup = BeautifulSoup(response.text, 'html.parser')
            context = soup.get_text(' ', strip=True)
            norm = legacy.normalize_match_name(context)
            if any(term in norm for term in ('quy doi', 'hoc ba', 'dgnl', 'danh gia nang luc', 'danh gia tu duy')):
                notes.append('REVIEW: mixed-method HTML requires column audit')
                continue
            if '2026' not in context:
                notes.append('No explicit 2026 year in source')
                continue
            for table in soup.find_all('table'):
                # Feed source cells to the audited 2026 method/scale parser.
                grid = [[cell.get_text(' ', strip=True) for cell in tr.find_all(['th','td'])]
                        for tr in table.find_all('tr')]
                parsed = parser.parse_table_grid(grid, university_name=name, source_url=url,
                    context=context[:22000], strategy='SUPPLEMENTAL_HTML', crossyear_map=crossyear)
                for row in parsed:
                    if parser.ml_compatible(pd.Series(row))[0]:
                        rows.append(row)
            pdf_urls = {urljoin(url, a['href']) for a in soup.find_all('a', href=True)
                        if '.pdf' in a['href'].lower()}
            for pdf_url in sorted(pdf_urls)[:5]:
                asset = legacy.get_url(pdf_url, timeout=30)
                parse_asset(pdf_url, asset.content)
    return rows, '; '.join(notes) or 'Official linked sources; explicit THPT-30 only; images need OCR review'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--years', type=int, nargs='+', choices=[2023, 2024, 2025, 2026], default=[2025, 2026])
    parser.add_argument('--limit', type=int, default=20, help='Schools per year; 0 = all')
    parser.add_argument('--delay', type=float, default=1.5)
    parser.add_argument('--audit-only', action='store_true', help='Recheck saved API evidence without network')
    parser.add_argument('--refresh', action='store_true', help='Retry previously attempted schools')
    parser.add_argument('--schools', nargs='+', help='Exact school names to recover; missing names are rejected')
    parser.add_argument('--api-only', action='store_true', help='Recover any supported year using audited public historical endpoints')
    parser.add_argument('--include-index', action='store_true', help='Also audit university/academy entries absent from the current dataset')
    parser.add_argument('--workers', type=int, default=3, choices=range(1, 5))
    parser.add_argument('--retry-reason', help='In API mode, retry completed requests whose reason contains this text')
    args = parser.parse_args()
    RECOVERY.mkdir(parents=True, exist_ok=True)
    if args.audit_only:
        for year in args.years:
            audit_api_supplement(year)
        audit_2026_supplement()
        return
    if not args.api_only and any(year < 2025 for year in args.years):
        parser.error('Years 2023/2024 require --api-only')
    if args.include_index and (not args.api_only or args.schools):
        parser.error('--include-index requires --api-only and cannot be combined with --schools')
    history = pd.concat([read(PROCESSED / f'admission_scores_{y}_ml_ready.csv') for y in range(2023, 2027)])
    names = sorted(history.university_name.unique())
    if args.schools:
        unknown = set(args.schools) - set(names)
        if unknown:
            raise ValueError('Unknown school names: ' + ', '.join(sorted(unknown)))
        names = [n for n in names if n in args.schools]
    original_get = legacy.get_url
    def cached_get(url, timeout=45):
        response = original_get(url, timeout=timeout)
        digest = hashlib.sha256(url.encode()).hexdigest()[:16]
        if 'html' in response.headers.get('Content-Type', '').lower():
            (RECOVERY / f'{digest}.html').write_text(response.text, encoding='utf-8')
        (RECOVERY / f'{digest}.url.txt').write_text(url, encoding='utf-8')
        return response
    legacy.get_url = cached_get
    index = legacy.load_tuyensinh247_school_index() if args.api_only or 2025 in args.years else []
    if (args.api_only or 2025 in args.years) and not index:
        raise RuntimeError('Cannot load source index; check network and retry.')
    if args.api_only:
        bulk_api_recovery(args, index, names)
        return
    for year in args.years:
        output = PROCESSED / f'admission_scores_{year}_supplemental.csv'
        base = read(PROCESSED / f'admission_scores_{year}_ml_ready.csv')
        old = read(output) if output.exists() else pd.DataFrame(columns=COLUMNS)
        base = pd.concat([base, old], ignore_index=True)
        report_path = RECOVERY / f'report_{year}.csv'
        reports = read(report_path).to_dict('records') if report_path.exists() else []
        attempted = {r['university_name'] for r in reports} if not args.refresh else set()
        counts = base.groupby('university_name').size().to_dict()
        expected = history.groupby(['university_name', 'year']).size().groupby(level=0).max().to_dict()
        sources = read(ROOT / 'data/raw/source_map_2026.csv') if year == 2026 else None
        if year == 2026:
            os.environ['SCRAPER_SKIP_OCR'] = '1'
            import run_2026_pipeline as parser_2026
            crossyear = parser_2026.build_crossyear_major_map()
        targets = sorted(names, key=lambda n: (counts.get(n, 0) / max(1, expected[n]), n))
        targets = [n for n in targets if n not in attempted]
        if args.limit:
            targets = targets[:args.limit]
        for name in targets:
            print(f'[{year}] {name}', flush=True)
            rows, reason = [], ''
            try:
                if year == 2025:
                    result = legacy.parse_tuyensinh247_fallback(name, index)
                    rows, reason = result.rows, result.reason
                    if not rows and 'không có section' in reason:
                        rows, reason = recover_2025_api(name, index)
                else:
                    rows, reason = recover_2026(name, sources, parser_2026, crossyear)
                for row in rows:
                    row['year'] = str(row['year'])
                    if row['year'] != str(year):
                        raise ValueError('Source parser returned a different year')
                raw = pd.DataFrame(rows, columns=COLUMNS)
                save(raw, RECOVERY / f'{year}_{legacy.normalize_match_name(name).replace(" ", "_")}.csv')
                additions, rejected = accept_new(base.copy(), raw)
                if not rejected.empty:
                    save(rejected, RECOVERY / f'{year}_{legacy.normalize_match_name(name).replace(" ", "_")}_review.csv')
                if not additions.empty:
                    old = pd.concat([old, additions], ignore_index=True).drop_duplicates()
                    base = pd.concat([base, additions], ignore_index=True)
                    save(old[COLUMNS], output)
                reports.append({'university_name': name, 'year': year, 'fetched': len(rows),
                                'added': len(additions), 'rejected': len(rejected), 'reason': reason})
                print(f'  fetched={len(rows)} added={len(additions)} rejected={len(rejected)} {reason}', flush=True)
            except Exception as exc:
                reports.append({'university_name': name, 'year': year, 'fetched': 0,
                                'added': 0, 'rejected': 0, 'reason': f'ERROR: {exc}'})
                print(f'  ERROR: {exc}', flush=True)
            save(pd.DataFrame(reports), report_path)
            time.sleep(max(0, args.delay))
        if year == 2025:
            audit_api_supplement()
        else:
            audit_2026_supplement()
        print(f'{year}: supplemental rows={len(old)}; report={report_path}', flush=True)


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
