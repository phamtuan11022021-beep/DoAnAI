"""Restore audited rows only when refreshed API metadata preserves the old score.

Changed cutoffs remain in review; this command never silently replaces them.
"""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd
from scrape_missing_2025_2026 import RECOVERY, PROCESSED, COLUMNS, read, save, safe_api_row, accept_new, legacy

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'data/raw/official_20261106'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    review = read(RECOVERY/'api_formula_review_2026.csv')
    rows, conflicts = [], []
    for old in review.to_dict('records'):
        url = old['source_url']
        params = parse_qs(urlparse(url).query)
        blob = json.loads((RECOVERY/(hashlib.sha256(url.encode()).hexdigest()[:16]+'.json')).read_text(encoding='utf-8'))
        records = blob.get('data', []) if isinstance(blob, dict) else blob
        matches = [r for r in records if safe_api_row(r)
                   and str(r.get('school_id')) in params.get('school_id', [])
                   and str(r.get('year')) == old['year'] and str(r.get('mark_type')) == '1'
                   and str(r.get('display_code') or r.get('code') or '').strip() == old['major_code']]
        if len(matches) != 1:
            continue
        current = matches[0]
        if legacy.parse_thpt_score(current.get('mark')) != float(old['cutoff_score']):
            conflicts.append({'university_name': old['university_name'], 'major_code': old['major_code'],
                              'year': old['year'], 'old_score': old['cutoff_score'],
                              'new_source_score': current.get('mark'), 'source_url': url,
                              'status': 'REQUIRES_PRIMARY_SOURCE_REVIEW'})
            continue
        rows.append({**old, 'major_name': legacy.clean_text(current.get('name')),
                     'combination': current.get('block') or '',
                     'admission_note': 'Historical API 2026; THPT; refreshed combinations; cutoff unchanged'})
    frame = pd.DataFrame(rows, columns=COLUMNS)
    save(frame, OUT/'api_metadata_reconciled.csv')
    (OUT/'api_score_changes_review.json').write_text(json.dumps(conflicts, ensure_ascii=False, indent=2), encoding='utf-8')
    if args.apply:
        path = PROCESSED/'admission_scores_2026_supplemental.csv'
        old = read(path)
        base = pd.concat([read(PROCESSED/'admission_scores_2026_ml_ready.csv'), old], ignore_index=True)
        additions, rejected = accept_new(base, frame)
        if not additions.empty:
            save(pd.concat([old, additions], ignore_index=True).drop_duplicates(), path)
        print(f'Restored unchanged scores with refreshed metadata: {len(additions)}; pending changed scores: {len(conflicts)}')
    else:
        print(f'Metadata-only candidates: {len(rows)}; pending changed scores: {len(conflicts)}')


if __name__ == '__main__':
    main()
