"""Reviewed primary admissions tables; preserve method and campus identities."""
import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
import pandas as pd
import pymupdf
from bs4 import BeautifulSoup
from scrape_missing_2025_2026 import COLUMNS, read, save, accept_new
from import_official_gaps import normalize_school_key, normalize_major_code

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'data/raw/recovery_20261108'
VINH='Trường Đại học Sư phạm Kỹ thuật Vinh'
TUEBA='Trường Đại học Kinh tế và Quản trị kinh doanh Thái Nguyên'
VINH_SOURCE='https://vuted.edu.vn/Resources/Document/2026/8/2026-skv_d1_qd_diem-chuan-trung-tuyen.pdf'
PINNED={
 'vuted_2026_0.pdf':'e4229c2f49878061cd023b3a693a0fd0dbd0865d4b15b59692cdf8f83ee2eb2d',
 'vuted_2025.pdf':'578aa96d14a7cafe0d1cf97c8b4f4f5b2e438ed5cef3edb17ad0a73c21c05c4a',
 'tueba_2025_0.pdf':'705955d6b529c829550e627d611267a6c17bcc3a58163778d2c8f0f2d360cd1e',
 'tueba_2026_scores.png':'44e97d9d8664adf5e22b1b4ef6b7b48f5cd0101fd6b47671ef2ab27e749c541f',
 'uit_2025_1.png':'a2850dcb05ae41749b5673bf2787b77772c799ed77591b24b256e69cd2f94e2d',
 'vuted_2026.html':'e09a179e09de7f10676952eb1899080d9186065309b58c85f839607660d002fc',
}

def checked(name):
 blob=(RAW/name).read_bytes()
 if hashlib.sha256(blob).hexdigest()!=PINNED[name]: raise ValueError('Primary source changed: '+name)
 return RAW/name

def method(school,code,name,year,score,label,source,evidence,comparable=False):
 return dict(university_key=normalize_school_key(school),university_name=school,
  school_code='SKV' if school==VINH else 'DTE',city='Nghệ An' if school==VINH else 'Thái Nguyên',
  major_code=code,major_name=name,year=str(year),cutoff_score=float(score),admission_method=label,
  comparable_thpt=comparable,source_url=source,evidence_path=str((RAW/evidence).relative_to(ROOT)).replace('\\','/'))

@lru_cache(maxsize=1)
def vinh_2026():
 with pymupdf.open(checked('vuted_2026_0.pdf')) as doc:
  text=' '.join(p.get_text() for p in doc)
  if not all(x in text for x in ('706/QĐ','2026','2330/QĐ','đổi tên','100','200','402')):
   raise ValueError('Year, decision, former school identity or method missing')
  table=doc[2].find_tables().tables[0].extract()
  if [re.sub(r'\s+','',c) for c in table[1][3:]]!=['Phươngthức:200','Phươngthức:100','Phươngthức:402']:
   raise ValueError('Score column order changed')
  rows=[]
  for ordinal,code,name,hb,thpt,aptitude in table[2:]:
   if int(ordinal)!=len(rows)//3+1 or not re.fullmatch(r'7\d{6}',code): raise ValueError('Shifted program row')
   name=re.sub(r'\s+',' ',name).strip()
   for label,score in [('THPT (PT100)',thpt),('Học bạ (PT200)',hb),('ĐGNL (PT402, điểm trường công bố)',aptitude)]:
    rows.append(method(VINH,code,name,2026,score,label,VINH_SOURCE,'vuted_2026_0.pdf',label=='THPT (PT100)'))
 if len(rows)!=42: raise ValueError('Incomplete Vinh table')
 return rows

def candidates():
 rows=[]
 for r in vinh_2026():
  if not r['comparable_thpt']: continue
  code=r['major_code']
  combos=('A00|A01|B00|D01|D07|X01|X02|X03' if code.startswith('714') else
   'A00|A01|B00|C03|D01|D07|X01|X02' if code.startswith('734') else
   'A00|A01|B00|C01|C02|D01|D07|X02|X03')
  rows.append({**{k:r[k] for k in ('university_name','major_code','major_name','year','cutoff_score','source_url')},
   'admission_method_codes':'THPT','combination':combos,
   'admission_note':'Primary decision 706, 10/08/2026; exact PT100 column (second score column); renamed Công nghệ Kỹ thuật Vinh, former Sư phạm Kỹ thuật Vinh; combinations from appendix by program group'})
 return pd.DataFrame(rows,columns=COLUMNS)

def primary_keys():
 return {(normalize_school_key(r['university_name']),normalize_major_code(r['major_code']),r['year'],
   float(r['cutoff_score']),r['combination']) for r in candidates().to_dict('records')}

def verified_location():
 text=BeautifulSoup(checked('vuted_2026.html').read_bytes(),'html.parser').get_text(' ',strip=True)
 address='117 - Nguyễn Viết Xuân - Phường Trường Vinh – Tỉnh Nghệ An'
 if address not in text: raise ValueError('Vinh primary footer address changed')
 return dict(university_key=normalize_school_key(VINH),university_name=VINH,city='Nghệ An',
  address=address,location_scope='MAIN_CAMPUS',verified_year='2026',
  source_url='https://vuted.edu.vn/tin-tuc-17/cong-bo-diem-chuan-trung-tuyen-dai-hoc-chinh-quy-nam-2026-dot-3753')

def reviewed_methods():
 rows=list(vinh_2026())
 # Scanned 2025 appendix, visually reviewed: PT100, PT200, PT402 order.
 checked('vuted_2025.pdf')
 codes=['7140246','7340301','7340101','7340122','7480108','7480201','7510201','7510202','7510203','7510205','7510206','7510301','7510302','7510303']
 names={r['major_code']:r['major_name'] for r in rows}
 scores=[(19,24,13.33),(16,18,10.60),(16,18,10.60),(16,18,10.60),(16,18,10.60),(17,19,11.75),(17,19,11.75),(17,19,11.75),(17,19,11.75),(18,20,12.89),(16,18,10.60),(19.5,21.5,14.35),(16,18,10.60),(19.5,21.5,14.35)]
 for code,marks in zip(codes,scores):
  for (label,comp),score in zip([('THPT (PT100)',True),('Học bạ (PT200)',False),('ĐGNL (PT402, điểm trường công bố)',False)],marks):
   rows.append(method(VINH,code,names[code],2025,score,label,
    'https://vuted.edu.vn/Resources/Document/2025/8/2025-qd-diem-tt-dh-d1.pdf','vuted_2025.pdf',comp))
 # TUEBA points explicitly include conversion/bonus points: lookup only.
 checked('tueba_2025_0.pdf'); checked('tueba_2026_scores.png')
 manifest={r['id']:r for r in json.loads((RAW/'manifest.json').read_text(encoding='utf-8'))}
 values2025=[
 ('7460108','Khoa học dữ liệu',19),('7340122','Thương mại điện tử',18),('7340301','Kế toán',17.5),('7340101','Quản trị kinh doanh',18),('7340404','Quản trị nhân lực',18),('7340115','Marketing',19),('7510605','Logistics và Quản lý chuỗi cung ứng',18.5),('7340120','Kinh doanh quốc tế',18),('7340403','Quản lý công',17),('7380107','Luật kinh tế',18),('7340201','Tài chính - Ngân hàng',17.5),('7810103','Quản trị kinh doanh khách sạn và du lịch',18),('7310101','Kinh tế',17.5),('7310104','Kinh tế đầu tư',17.5),('7310105','Kinh tế phát triển',17),
 ('7340101-TA','Quản trị kinh doanh (dạy và học bằng tiếng Anh)',19.5),('7340115-TA','Quản trị marketing (dạy và học bằng tiếng Anh)',19.5),('7340201-TA','Tài chính (dạy và học bằng tiếng Anh)',19.5),('7810103-TA','Quản trị du lịch và khách sạn (dạy và học bằng tiếng Anh)',19.5),('7310101-HG','Kinh tế (Phân hiệu ĐHTN tại Hà Giang)',17.5),('7810103-HG','Quản trị kinh doanh khách sạn và du lịch (Phân hiệu ĐHTN tại Hà Giang)',18)]
 values2026=[
 ('7460108','Khoa học dữ liệu',18),('7340205','Công nghệ tài chính',19),('7340122','Thương mại điện tử',19),('7310109','Kinh tế số',17.5),('7340301','Kế toán',18),('7340101A','Kinh doanh số',18),('7340101B','Quản trị kinh doanh',18),('7340404','Quản trị nhân lực',19),('7340115A','Digital Marketing',18.5),('7340115B','Quản trị Marketing',18.5),('7510605','Logistics và Quản lý chuỗi cung ứng',20),('7340120','Kinh doanh quốc tế',18),('7340403','Quản lý công',17.5),('7340201','Tài chính - Ngân hàng',18),('7810103A','Quản trị giải trí và Sự kiện',18),('7810103B','Quản trị kinh doanh khách sạn và Du lịch',18),('7380107','Luật kinh tế',20),('7310101','Kinh tế',17.5),('7310104','Kinh tế đầu tư',17),('7310105','Kinh tế phát triển',17),('7310110','Quản lý kinh tế',17),('7340101TA','Quản trị kinh doanh (dạy và học bằng tiếng Anh)',19),('7340115TA','Quản trị Marketing (dạy và học bằng tiếng Anh)',19),('7340201TA','Tài chính (dạy và học bằng tiếng Anh)',19),('7810103TA','Quản trị du lịch và khách sạn (dạy và học bằng tiếng Anh)',19),('7510605TQ','Logistics Quốc tế (dạy và học bằng tiếng Trung Quốc)',20),('7340122TQ','Thương mại điện tử xuyên biên giới (dạy và học bằng tiếng Trung Quốc)',19),('7340301HG','Kế toán (Phân hiệu ĐHTN tại Hà Giang)',19),('7310110HG','Quản lý kinh tế (Phân hiệu ĐHTN tại Hà Giang)',19)]
 for year,values,evidence in [(2025,values2025,'tueba_2025_0.pdf'),(2026,values2026,'tueba_2026_scores.png')]:
  for code,name,score in values:
   row=method(TUEBA,code,name,year,score,'Điểm quy đổi chung giữa các phương thức; không dùng train THPT thuần',manifest[f'tueba_{year}']['url'],evidence)
   if code.endswith(('HG','-HG')): row['city']='Hà Giang'; row['school_code']='DTE (Phân hiệu Hà Giang)'
   rows.append(row)
 checked('uit_2025_1.png')
 uit='Trường Đại học Công nghệ Thông tin - ĐHQG TPHCM'
 values=[('7320104','Truyền thông đa phương tiện',25),('7340122','Thương mại điện tử',24.57),('7460108','Khoa học dữ liệu',27.70),('7480101','Khoa học máy tính',27.20),('7480102','Mạng máy tính và truyền thông dữ liệu',24),('7480103','Kỹ thuật phần mềm',26),('7480104','Hệ thống thông tin',24.70),('7480104_TT','Hệ thống thông tin (CTTT)',24.20),('7480106','Kỹ thuật máy tính',25.30),('7480107','Trí tuệ nhân tạo',29.60),('7480201','Công nghệ thông tin',26.60),('7480201_VN','Công nghệ thông tin Việt - Nhật',24.20),('7480202','An toàn thông tin',26.27),('75202A1','Thiết kế vi mạch',27)]
 for code,name,score in values:
  row=method(uit,code,name,2025,score,'THPT thang 30, gồm điểm cộng và ưu tiên; mã 75202A1 giữ đúng ảnh thông báo',manifest['uit_2025']['url'],'uit_2025_1.png',True)
  # Keep exactly the key already used by the final catalog; do not normalize
  # this abbreviation a second time (the legacy normalizer is not idempotent).
  row.update(university_key='dai hoc cong nghe thong tin dhqg tp hcm',school_code='QSC',city='Hồ Chí Minh')
  rows.append(row)
 return pd.DataFrame(rows)

def main():
 parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--apply',action='store_true'); args=parser.parse_args()
 frame=candidates(); methods=reviewed_methods(); location=verified_location()
 old=read(ROOT/'data/processed/admission_scores_2026_supplemental.csv')
 base=pd.concat([read(ROOT/'data/processed/admission_scores_2026_ml_ready.csv'),old],ignore_index=True)
 for data in (base,frame):
  data['university_name']=data.university_name.map(normalize_school_key)
  data['major_code']=data.major_code.map(normalize_major_code)
 added,rejected=accept_new(base,frame)
 selected=candidates()[candidates().major_code.isin(added.major_code)]
 save(selected,RAW/'new_thpt_rows.csv'); save(rejected,RAW/'conflicts_for_review.csv'); save(methods,RAW/'reviewed_methods.csv')
 report={'primary_thpt_candidates':len(frame),'new_thpt_rows':len(selected),'conflicts':len(rejected),'official_method_rows':len(methods),'applied':args.apply}
 if args.apply:
  stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'); backup=ROOT/'backups'/('recovery_'+stamp)
  for folder in ('data/dataset','ai/models','data/qa'):
   shutil.copytree(ROOT/folder,backup/folder)
  target=ROOT/'data/processed/admission_scores_2026_supplemental.csv'
  (backup/'data/processed').mkdir(parents=True,exist_ok=True); shutil.copy2(target,backup/'data/processed'/target.name)
  save(pd.concat([old,selected],ignore_index=True).drop_duplicates(),target)
  path=ROOT/'data/dataset/admissions_official_methods.csv'; previous=read(path)
  previous=previous[~previous.source_url.isin(methods.source_url)]
  save(pd.concat([previous,methods],ignore_index=True),path)
  path=ROOT/'data/dataset/university_locations.csv'; previous=read(path)
  save(pd.concat([previous[~previous.university_key.eq(location['university_key'])],pd.DataFrame([location])],ignore_index=True),path)
  report['backup']=str(backup.relative_to(ROOT))
 (RAW/('import_report.json' if args.apply else 'validation_report.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
