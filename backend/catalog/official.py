"""Primary-source cutoffs stay separate from comparable THPT training data."""
from pathlib import Path
import pandas as pd

FILE = Path(__file__).resolve().parents[2] / 'data/dataset/admissions_official_methods.csv'


def official_rows(*, university_key='', city='', major='', major_code='', years=None):
    from .models import AdmissionRelease
    base = pd.read_csv(FILE, keep_default_na=False) if FILE.exists() else pd.DataFrame()
    extra = [row for rows in AdmissionRelease.objects.filter(status='published').values_list('rows',flat=True) for row in rows]
    frame = pd.concat([base, pd.DataFrame(extra)], ignore_index=True)
    if frame.empty: return []
    if university_key:
        frame = frame[frame.university_key.eq(university_key)]
    if city:
        frame = frame[frame.city.eq(city)]
    if years is not None:
        frame = frame[pd.to_numeric(frame.year, errors='coerce').isin(years)]
    frame = frame.copy()
    # CSV strings such as "False" must never become truthy by accident.
    frame['comparable_thpt'] = frame.comparable_thpt.astype(str).str.lower().eq('true')
    if major or major_code:
        from ai_api.service import _engine
        engine = _engine()
        frame['major_code_norm'] = frame.major_code.map(engine.normalize_major_code)
        frame = engine.filter_major(frame, major_query=major, major_code=major_code)
    return frame.drop(columns=['major_code_norm', 'major_similarity'], errors='ignore').fillna('').to_dict('records')
