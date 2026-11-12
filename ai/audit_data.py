"""Report observed coverage; missing observations are never fabricated."""
from pathlib import Path
import json
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]

def main():
    dataset = ROOT / 'data/dataset'
    frame = pd.read_csv(dataset / 'admission_scores_2023_2026_program_year.csv')
    counts = frame.groupby(['university_key', 'university_name', 'year']).size().unstack(fill_value=0)
    counts = counts.reindex(columns=[2023, 2024, 2025, 2026], fill_value=0)
    counts['years_observed'] = counts.gt(0).sum(axis=1)
    counts.to_csv(dataset / 'coverage_by_school_year.csv', encoding='utf-8-sig')
    programs = frame.groupby('program_key').year.nunique()
    summary = {'program_year_rows': len(frame), 'schools': int(frame.university_key.nunique()),
               'programs': len(programs), 'programs_all_4_years': int(programs.eq(4).sum()),
               'programs_at_least_2_years': int(programs.ge(2).sum()),
               'rows_by_year': {str(k): int(v) for k,v in frame.year.value_counts().sort_index().items()},
               'note': 'No observations means missing evidence, not zero cutoff or no admission.'}
    (dataset / 'coverage_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
