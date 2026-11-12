"""Merge reviewed location additions; never infer cities from school names."""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def main():
    target = ROOT / 'data/dataset/university_locations.csv'
    frame = pd.read_csv(target, dtype=str, keep_default_na=False)
    for path in sorted((ROOT / 'data/verified').glob('locations_expansion_*.csv')):
        patch = pd.read_csv(path, dtype=str, keep_default_na=False)
        if patch.university_key.duplicated().any() or not patch.source_url.str.startswith('https://').all():
            raise ValueError(f'Invalid reviewed locations: {path.name}')
        # Explicit reviewed rows replace prior metadata for that exact school key.
        frame = pd.concat([frame[~frame.university_key.isin(patch.university_key)], patch], ignore_index=True)
    frame.sort_values('university_key').to_csv(target, index=False, encoding='utf-8-sig')
    print(f'Reviewed school location keys: {len(frame)}')


if __name__ == '__main__':
    main()
