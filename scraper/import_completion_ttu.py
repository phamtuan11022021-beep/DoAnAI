"""Join two same-year TTU primary sources using reviewed DOM field identities."""
import argparse
import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup
from import_verified_ai2 import ttu_methods
from scrape_missing_2025_2026 import COLUMNS, read, save, accept_new
from import_official_gaps import normalize_school_key, normalize_major_code

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/raw/completion_20261106'
TTU_NOTICE='https://ttu.edu.vn/truong-dai-hoc-tan-tao-cong-bo-diem-chuan-trung-tuyen-dai-hoc-chinh-quy-nam-2026/'
PROGRAMS='https://tuyensinh2026.ttu.edu.vn/'
DOM_SHA='65843ca53d6dd1d0b7763805ff328214c1479dab9106f6e62b41183eed793e3c'
# Name/code field IDs reviewed against the 2026 school program listing.
FIELDS=[(466,467,'7720101'),(469,568,'7720301'),(472,569,'7720601'),
 (475,570,'7340101'),(478,571,'7340120'),(484,573,'7340201'),(481,572,'7340301'),
 (487,574,'7340115'),(603,604,'7510605'),(601,606,'7320104'),(623,625,'7380101'),
 (591,611,'7380107'),(493,576,'7480101'),(496,577,'7480107'),(500,578,'7460108'),
 (589,610,'7480201'),(503,579,'7420201'),(585,608,'7620118'),
 (490,575,'7220201'),(583,607,'7220204'),(587,609,'7220210')]
# Unambiguous reference combinations from the published PT100 image, also
# present in the same-year listing. No copying combinations from older years.
COMBINATIONS=['A02|B00|B08','A00|A02|B00|B08|D07','A00|A02|B00|B08|D07',
 'A00|A01|C01|D01|D07|X01','A00|A01|C01|D01|D07|X01',
 'A00|A01|C01|D01|D07|X01','A00|A01|C01|D01|D07|X01',
 'A00|A01|C01|D01|D07|X01','A00|A01|D01|D07|X01|X26',
 'A00|A01|C00|C01|C03|C04|C14|D01|D14|D15|X01',
 'A00|A01|C00|C03|D01','A00|A01|C00|C03|D01|D14|X01',
 'A00|A01|D01|D07|X07|X25|X26|X27|X56',
 'A00|A01|D01|D07|X07|X25|X26|X27|X56',
 'A00|A01|D01|D07|X07|X25|X26|X27|X56',
 'A00|A01|D01|X07|X25|X26|X27|X56',
 'A02|B00|B03|B08|X14|X16','A00|A02|B00|B08|D07|X16']


@lru_cache(maxsize=1)
def reviewed():
    blob=(OUT/'ttu_programs_2026.html').read_bytes()
    if hashlib.sha256(blob).hexdigest()!=DOM_SHA:
        raise ValueError('TTU program listing changed: review required')
    soup=BeautifulSoup(blob,'html.parser')
    published=ttu_methods().to_dict('records')  # verifies the visually read score image hash
    result=[]
    for index,(name_id,code_id,code) in enumerate(FIELDS):
        name=soup.select_one(f'#HEADLINE{name_id} h3').get_text(' ',strip=True)
        actual=soup.select_one(f'#HEADLINE{code_id} h3').get_text(' ',strip=True)
        if actual!=code or not name:
            raise ValueError('TTU reviewed name/code cell changed')
        item=published[index]
        item.update(major_code=code, admission_method='Xét điểm thi TN THPT (PT100); mã ngành xác minh từ trang tuyển sinh 2026',
                    comparable_thpt=index<18, city='Tây Ninh')
        # The image and the landing page use specialization names differently;
        # retain the exact score-image name, and keep the paired field in audit.
        item['program_listing_name']=name
        result.append(item)
    return result


def candidates():
    return pd.DataFrame([dict(university_name=r['university_name'],major_code=r['major_code'],
        major_name=r['major_name'],year='2026',admission_method_codes='THPT',
        combination=COMBINATIONS[i],cutoff_score=r['cutoff_score'],source_url=TTU_NOTICE,
        admission_note='Reviewed PT100 image + same-year code field; reference combinations only; code source: '+PROGRAMS)
        for i,r in enumerate(reviewed()[:18])],columns=COLUMNS)


@lru_cache(maxsize=1)
def primary_keys():
    return {(normalize_school_key(r['university_name']),normalize_major_code(r['major_code']),
             str(r['year']),float(r['cutoff_score']),r['combination']) for r in candidates().to_dict('records')}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    frame=candidates()
    path=ROOT/'data/processed/admission_scores_2026_supplemental.csv'
    old=read(path)
    base=pd.concat([read(ROOT/'data/processed/admission_scores_2026_ml_ready.csv'),old],ignore_index=True)
    identity=base.copy()
    identity['university_name']=identity.university_name.map(normalize_school_key)
    identity['major_code']=identity.major_code.map(normalize_major_code)
    normalized=frame.copy()
    normalized['university_name']=normalized.university_name.map(normalize_school_key)
    normalized['major_code']=normalized.major_code.map(normalize_major_code)
    accepted,_=accept_new(identity,normalized)
    codes=set(accepted.major_code)
    selected=frame[frame.major_code.isin(codes)]
    save(selected,OUT/'ttu_new_thpt.csv')
    save(pd.DataFrame(reviewed()),OUT/'ttu_reviewed_codes.csv')
    if args.apply:
        save(pd.concat([old,selected],ignore_index=True).drop_duplicates(),path)
        method_path=ROOT/'data/dataset/admissions_official_methods.csv'
        methods=read(method_path)
        methods=methods[~(methods.source_url.eq(TTU_NOTICE)&methods.year.eq('2026'))]
        save(pd.concat([methods,pd.DataFrame(reviewed()).assign(year='2026')],ignore_index=True),method_path)
        address='Đại lộ Đại học Tân Tạo, Tân Đức E.City, Xã Đức Hòa, Tỉnh Tây Ninh'
        if address not in BeautifulSoup((OUT/'ttu_programs_2026.html').read_bytes(),'html.parser').get_text(' ',strip=True):
            raise ValueError('Verified TTU footer address changed')
        location_path=ROOT/'data/dataset/university_locations.csv'
        locations=read(location_path)
        locations=locations[~locations.university_key.eq('dai hoc tan tao')]
        location=dict(university_key='dai hoc tan tao',university_name='Trường ĐH Tân Tạo',city='Tây Ninh',
                      address=address,location_scope='MAIN_CAMPUS',source_url=PROGRAMS,verified_year='2026')
        save(pd.concat([locations,pd.DataFrame([location])],ignore_index=True),location_path)
    report={'codes_verified':21,'new_thpt_rows':len(selected),'language_rows_kept_separate':3,
            'source_url':TTU_NOTICE,'program_code_source':PROGRAMS,'applied':args.apply,
            'thanhdong':'No training import: published columns say threshold >=; existing dataset requires separate review.',
            'thanhdo':'14 existing 2026 codes; no additional missing program-year in this notice.'}
    (OUT/('import_report.json' if args.apply else 'validation_report.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    main()
