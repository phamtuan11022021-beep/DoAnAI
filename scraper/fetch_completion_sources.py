"""Save primary sources for the next reviewed import, without touching datasets."""
import hashlib
import json
from pathlib import Path
from urllib.parse import urljoin

import requests
import truststore
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'data/raw/completion_20261106'
SOURCES = {
    'ttu_programs_2026':'https://tuyensinh2026.ttu.edu.vn/',
    'thanhdong_2026':'https://thanhdong.edu.vn/khoa-co-ban/chinh-thuc-diem-chuan-dai-hoc-thanh-dong-2026.html',
    'thanhdo_2026':'https://tuyensinh.thanhdo.edu.vn/truong-dai-hoc-thanh-do-chinh-thuc-cong-bo-diem-chuan-trung-tuyen-dai-hoc-chinh-quy-nam-2026/',
}


def main():
    truststore.inject_into_ssl()
    OUT.mkdir(parents=True,exist_ok=True)
    records=[]
    for name,url in SOURCES.items():
        record={'id':name,'url':url}
        try:
            response=requests.get(url,timeout=(10,45))
            response.raise_for_status()
            blob=response.content
            soup=BeautifulSoup(blob,'html.parser')
            (OUT/f'{name}.html').write_bytes(blob)
            (OUT/f'{name}.txt').write_text(soup.get_text('\n',strip=True),encoding='utf-8')
            record.update(sha256=hashlib.sha256(blob).hexdigest(),title=soup.title.get_text(),images=[])
            if name not in {'ttu_programs_2026','hict_identity_2025'}:
                for img in soup.find_all('img'):
                    src=urljoin(url,img.get('src') or img.get('data-src') or '')
                    if not any(s in src.lower() for s in ('2025','2026','diem-chuan')): continue
                    asset=requests.get(src,timeout=(10,45))
                    asset.raise_for_status()
                    suffix=Path(src.split('?')[0]).suffix.lower()
                    if suffix not in ('.jpg','.jpeg','.png','.webp'): continue
                    path=OUT/f'{name}_{len(record["images"])}{suffix}'
                    path.write_bytes(asset.content)
                    record['images'].append({'url':src,'path':str(path.relative_to(ROOT)),
                                             'sha256':hashlib.sha256(asset.content).hexdigest()})
            print(name,record['title'],len(record['images']),flush=True)
        except requests.RequestException as exc:
            record['error']=type(exc).__name__
            print(name,record['error'],flush=True)
        records.append(record)
        (OUT/'manifest.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':
    import sys
    if '--additional-2025' in sys.argv:
        OUT=ROOT/'data/raw/completion_20261106/additional_2025'
        SOURCES={
            'hict_2025':'https://hict.edu.vn/thong-bao-diem-trung-tuyen-nam-2025.htm',
            'dntu_2025':'https://dntu.edu.vn/thong-tin-tuyen-sinh/truong-dai-hoc-cong-nghe-dong-nai-cong-bo-diem-chuan-trung-tuyen-dai-hoc-chinh-quy-nam-2025-dntu',
        }
    if '--hict-identity' in sys.argv:
        OUT=ROOT/'data/raw/completion_20261106/hict_identity'
        SOURCES={'hict_identity_2025':'https://hict.edu.vn/thong-tin-ve-ma-truong-ma-nganh-dao-tao-nam-2025-de-thi-sinh-dang-ky-xet-tuyen-tren-cong-cua-bo-gd-dt.htm'}
    sys.stdout.reconfigure(encoding='utf-8')
    main()
