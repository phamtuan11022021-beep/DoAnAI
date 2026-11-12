"""Audit historical API evidence and expose remaining school-year gaps offline."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import pandas as pd
from scrape_missing_2025_2026 import safe_api_row, legacy, page_school_id
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw/supplemental_recovery'
OUT = ROOT / 'data/dataset'
sys.path.insert(0, str(ROOT / 'ai'))
from prepare_dataset_4years_FINAL import normalize_school_key


def read(path):
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def refresh_coverage():
    """Refresh derived coverage after normalization without rechecking unchanged sources."""
    summary_path = OUT / 'recovery_evidence_summary.json'
    summary = json.loads(summary_path.read_text(encoding='utf-8'))
    if summary['evidence_failures']:
        raise SystemExit('Resolve evidence failures before refreshing coverage')
    supplements = list((ROOT / 'data/processed').glob('*_supplemental.csv'))
    if any(p.stat().st_mtime_ns > summary_path.stat().st_mtime_ns for p in supplements):
        raise SystemExit('Supplemental data changed; run full evidence audit again')
    inventory = json.loads((RAW / 'school_inventory.json').read_text(encoding='utf-8'))
    dataset_path = OUT / 'admission_scores_2023_2026_program_year.csv'
    dataset = read(dataset_path)
    observed = dataset.groupby(['university_key', 'year']).size().to_dict()
    rows = []
    for year in inventory['years']:
        reports = read(RAW / f'api_report_{year}.csv').drop_duplicates('university_name', keep='last')
        by_name = {r['university_name']: r for r in reports.to_dict('records')}
        for name in inventory['schools']:
            record = by_name.get(name, {})
            count = int(observed.get((normalize_school_key(name), str(year)), 0))
            rows.append({'university_name': name, 'year': year, 'program_year_rows': count,
                         'api_fetched': int(record.get('fetched', 0)), 'raw_added': int(record.get('added', 0)),
                         'reason': record.get('reason', 'NOT_ATTEMPTED'),
                         'status': 'HAS_DATA' if count else 'MISSING_DATASET_ROWS'})
    coverage = pd.DataFrame(rows)
    coverage.to_csv(OUT / 'recovery_inventory_coverage.csv', index=False, encoding='utf-8-sig')
    gaps = coverage[coverage.program_year_rows.eq(0)]
    gaps.to_csv(OUT / 'recovery_school_year_gaps.csv', index=False, encoding='utf-8-sig')
    summary.update(school_years_without_dataset_rows=len(gaps), dataset_refresh_required=False,
                   final_dataset_sha256=hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
                   supplemental_sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                        for p in supplements})
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Coverage refreshed: {len(coverage)} school-years; {len(gaps)} gaps; prior evidence audit passed.')


def audit():
    inventory = json.loads((RAW / 'school_inventory.json').read_text(encoding='utf-8'))
    gaps, coverage, years, invalid = [], [], {}, []
    dataset_path = OUT / 'admission_scores_2023_2026_program_year.csv'
    dataset = read(dataset_path)
    observed = dataset.groupby(['university_key', 'year']).size().to_dict()
    # Resolve identities from the saved index and pages, never make audit calls.
    index_file = RAW / (hashlib.sha256(legacy.TS247_INDEX_URL.encode()).hexdigest()[:16] + '.html')
    original_get = legacy.get_url
    try:
        legacy.get_url = lambda url, **kwargs: SimpleNamespace(text=index_file.read_text(encoding='utf-8'))
        index = legacy.load_tuyensinh247_school_index()
    finally:
        legacy.get_url = original_get
    identities = {}
    def identity_ok(name, school_id):
        if name not in identities:
            item, _ = legacy.match_tuyensinh247_school(name, index)
            if not item:
                identities[name] = None
            else:
                page_path = RAW / (hashlib.sha256(item['score_url'].encode()).hexdigest()[:16] + '.html')
                if not page_path.exists():
                    identities[name] = None
                else:
                    html = page_path.read_text(encoding='utf-8')
                    identity_html = ''.join(re.findall(r'<(?:title|h1|h2)\b[^>]*>.*?</(?:title|h1|h2)\s*>',
                                                       html, flags=re.S | re.I))
                    ok, _ = legacy.validate_ts247_page_identity(requested_university_name=name,
                        matched_item=item, html_text=identity_html, url=item['score_url'])
                    identities[name] = page_school_id(html, item['school_code']) if ok else None
        return identities[name] == school_id
    for year in inventory['years']:
        report_path = RAW / f'api_report_{year}.csv'
        reports = read(report_path).drop_duplicates('university_name', keep='last') if report_path.exists() else pd.DataFrame()
        by_school = {r['university_name']: r for r in reports.to_dict('records')}
        for name in inventory['schools']:
            record = by_school.get(name)
            count = int(observed.get((normalize_school_key(name), str(year)), 0))
            row = {'university_name': name, 'year': year, 'program_year_rows': count,
                   'api_fetched': int(record['fetched']) if record else 0,
                   'raw_added': int(record['added']) if record else 0,
                   'reason': record['reason'] if record else 'NOT_ATTEMPTED',
                   'status': 'HAS_DATA' if count else 'MISSING_DATASET_ROWS'}
            coverage.append(row)
            if not count:
                gaps.append(row)
        path = ROOT / f'data/processed/admission_scores_{year}_supplemental.csv'
        frame = read(path) if path.exists() else pd.DataFrame(columns=['source_url'])
        api = frame[frame.source_url.str.contains('/api/common/cutoff-score?', regex=False)]
        valid = 0
        for url, group in api.groupby('source_url'):
            evidence = RAW / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.json')
            try:
                payload = json.loads(evidence.read_text(encoding='utf-8'))
                records = payload.get('data', []) if isinstance(payload, dict) else payload
                params = parse_qs(urlparse(url).query)
                assert params.get('year') == [str(year)] and params.get('method_id') == ['1']
                assert isinstance(records, list)
                source_rows = {
                    (str(r.get('display_code') or r.get('code') or '').strip(),
                     str(r.get('block') or ''), legacy.parse_thpt_score(r.get('mark')))
                    for r in records if isinstance(r, dict) and safe_api_row(r)
                    and str(r.get('year')) == str(year) and str(r.get('mark_type')) == '1'
                    and str(r.get('school_id')) in params.get('school_id', [])
                    and legacy.parse_thpt_score(r.get('mark')) is not None}
                for row in group.to_dict('records'):
                    key = row['major_code'], row['combination'], float(row['cutoff_score'])
                    own_school = identity_ok(row['university_name'], params.get('school_id', [''])[0])
                    if own_school and key in source_rows and row['year'] == str(year) and row['admission_method_codes'] == 'THPT':
                        valid += 1
                    else:
                        invalid.append({**row, 'audit_reason': 'SCHOOL_IDENTITY_NOT_CONFIRMED' if not own_school
                                        else 'ROW_NOT_IN_SAFE_YEAR_METHOD_EVIDENCE'})
            except (OSError, ValueError, KeyError, TypeError, AssertionError):
                invalid.extend({**row, 'audit_reason': 'MISSING_OR_INVALID_EVIDENCE'} for row in group.to_dict('records'))
        years[str(year)] = {'schools_attempted': len(reports), 'inventory_schools': len(inventory['schools']),
            'rows_fetched': int(pd.to_numeric(reports.fetched).sum()) if not reports.empty else 0,
            'rows_added_before_final_normalization': int(pd.to_numeric(reports.added).sum()) if not reports.empty else 0,
            'supplemental_api_rows': len(api), 'evidence_passed': valid}
    OUT.mkdir(exist_ok=True)
    fields = ['university_name', 'year', 'program_year_rows', 'api_fetched', 'raw_added', 'reason', 'status']
    pd.DataFrame(coverage, columns=fields).to_csv(OUT / 'recovery_inventory_coverage.csv', index=False, encoding='utf-8-sig')
    pd.DataFrame(gaps, columns=fields).to_csv(
        OUT / 'recovery_school_year_gaps.csv', index=False, encoding='utf-8-sig')
    pd.DataFrame(invalid, columns=[*legacy.CANONICAL_COLUMNS, 'audit_reason']).to_csv(
        OUT / 'recovery_evidence_failures.csv', index=False, encoding='utf-8-sig')
    refresh_required = any(p.stat().st_mtime_ns > dataset_path.stat().st_mtime_ns
        for p in (ROOT / 'data/processed').glob('*_supplemental.csv'))
    summary = {'source_index': inventory['source_index'], 'inventory_school_names': len(inventory['schools']),
        'years': years, 'school_years_without_dataset_rows': len(gaps), 'evidence_failures': len(invalid),
        'dataset_refresh_required': refresh_required,
        'note': 'Inventory is a public secondary-source list, not proof of nationwide completeness. '
                'Zero fetched rows means missing acceptable evidence, not no admissions. '
                'Added raw rows can decrease after normalization and conflict quarantine.'}
    (OUT / 'recovery_evidence_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if invalid:
        raise SystemExit('Evidence failures must be resolved before training')


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh-coverage-only', action='store_true')
    args = parser.parse_args()
    if args.refresh_coverage_only:
        refresh_coverage()
    else:
        audit()
