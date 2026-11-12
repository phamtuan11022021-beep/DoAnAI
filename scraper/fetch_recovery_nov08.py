"""Archive targeted official admissions notices and linked score assets."""
import hashlib
import json
import sys
from pathlib import Path
from urllib.parse import urljoin
import requests
import truststore
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/raw/recovery_20261108'
SOURCES = {
 'tueba_2025': 'https://tuyensinh.tueba.edu.vn/bai-viet/Thong-Bao-Diem-Trung-Tuyen-Dai-Hoc-Chinh-Quy-Nam-2025-Dot-1-111.html',
 'tueba_2026': 'https://tuyensinh.tueba.edu.vn/bai-viet/Thong-Bao-Diem-Chuan-Trung-Tuyen-Dai-Hoc-Chinh-Quy-Dot-1-Nam-2026-151.html',
 'ufba_2025': 'https://media.ufba.edu.vn/Media/2_TH1064/FolderFunc/202508/Documents/ds-trung-tuyen-dot-1-in-qd-1-20250822090452-e.pdf',
 'vuted_2025': 'https://vuted.edu.vn/Resources/Document/2025/8/2025-qd-diem-tt-dh-d1.pdf',
 'tueba_2026_scores': 'https://tuyensinh.tueba.edu.vn//uploads/2024/ảnh%204-1104673735.png',
 'vuted_index': 'https://vuted.edu.vn/thong-bao-17',
 'vuted_2026': 'https://vuted.edu.vn/tin-tuc-17/cong-bo-diem-chuan-trung-tuyen-dai-hoc-chinh-quy-nam-2026-dot-3753',
 'uit_2025': 'https://tuyensinh.uit.edu.vn/node/4147',
 'uit_history': 'https://tuyensinh.uit.edu.vn/sites/default/files/uploads/images/202601/diem_chuan_uit_2021-2025.png',
}

def main():
 truststore.inject_into_ssl()
 OUT.mkdir(parents=True, exist_ok=True)
 previous={r['id']:r for r in json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))} if (OUT/'manifest.json').exists() else {}
 records=[]
 for name,url in SOURCES.items():
  if '--only' in sys.argv and name not in sys.argv[sys.argv.index('--only')+1:]:
   if name in previous: records.append(previous[name])
   continue
  saved=previous.get(name,{})
  if saved.get('status')==200 and hashlib.sha256((ROOT/saved['path']).read_bytes()).hexdigest()==saved['sha256']:
   records.append(saved)
   continue
  record={'id':name, 'url':url, 'assets':[]}
  try:
   response=requests.get(url, timeout=(10,45)); response.raise_for_status()
   suffix='.pdf' if response.content.startswith(b'%PDF') else ('.png' if 'image/png' in response.headers.get('Content-Type','') else '.html')
   path=OUT/(name+suffix); path.write_bytes(response.content)
   record.update(path=str(path.relative_to(ROOT)),sha256=hashlib.sha256(response.content).hexdigest(),status=response.status_code)
   if suffix=='.html':
    soup=BeautifulSoup(response.content,'html.parser')
    (OUT/(name+'.txt')).write_text(soup.get_text('\n',strip=True),encoding='utf-8')
    record['title']=soup.title.get_text(' ',strip=True)
    urls=set()
    for node in soup.select('a[href],img[src],iframe[src],embed[src]'):
     asset=urljoin(response.url,node.get('href') or node.get('src'))
     if '.pdf' in asset.lower() or (node.name=='img' and any(x in asset.lower() for x in ('2025','2026','diem'))): urls.add(asset)
    for i,asset in enumerate(sorted(urls)):
     try:
      fetched=requests.get(asset,timeout=(10,45)); fetched.raise_for_status()
      ext='.pdf' if fetched.content.startswith(b'%PDF') else Path(asset.split('?')[0]).suffix.lower()
      if ext not in ('.pdf','.png','.jpg','.jpeg','.webp'): continue
      target=OUT/f'{name}_{i}{ext}'; target.write_bytes(fetched.content)
      record['assets'].append({'url':asset,'path':str(target.relative_to(ROOT)),'sha256':hashlib.sha256(fetched.content).hexdigest()})
     except requests.RequestException as exc: record['assets'].append({'url':asset,'error':type(exc).__name__})
  except requests.RequestException as exc: record['error']=type(exc).__name__
  records.append(record)
  (OUT/'manifest.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
  print(name,record.get('status',record.get('error')),len(record['assets']),flush=True)

if __name__=='__main__': main()
