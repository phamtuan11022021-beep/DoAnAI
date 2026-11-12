"""Snapshot selected primary notices before reviewing their exact table columns."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import urljoin

import requests
try:
    import truststore
except ImportError:
    truststore = None
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/raw/official_20261106'
SOURCES = {
    'udn_2023': 'https://ts.udn.vn/DHCD/Chinhquy/diemchuan/10452',
    'udn_2024': 'https://ts.udn.vn/DHCD/Chinhquy/diemchuan/13365',
    'udn_2025': 'https://ts.udn.vn/DHCD/Chinhquy/diemchuan/15062',
    'uneti_2025': 'https://tuyensinh.uneti.edu.vn/thong-bao-diem-trung-tuyen-dai-hoc-he-chinh-quy-nam-2025.html',
    'cmc_2025': 'https://cmcu.edu.vn/diem-chuan-trung-tuyen-theo-cac-phuong-thuc-xet-tuyen-cua-truong-dai-hoc-cmc-nam-2025/',
    'cmc_2026': 'https://cmcu.edu.vn/diem-chuan-trung-tuyen-theo-cac-phuong-thuc-xet-tuyen-cua-truong-dai-hoc-cmc-nam-2026/',
    'vimaru_2025': 'https://tuyensinh.vimaru.edu.vn/tuyensinh/2025-thong-bao-diem-trung-tuyen-dai-hoc-he-chinh-quy-nam-2025.vmu',
    'vimaru_2026': 'https://tuyensinh.vimaru.edu.vn/tuyensinh/2026-thong-bao-diem-trung-tuyen-dai-hoc-he-chinh-quy-nam-2026.vmu',
}


def main():
    if truststore is not None:
        truststore.inject_into_ssl()
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    for name, url in SOURCES.items():
        record = {'id': name, 'url': url, 'retrieved_at': datetime.now(timezone.utc).isoformat()}
        try:
            response = requests.get(url, timeout=(10, 45))
            response.raise_for_status()
            (OUT / f'{name}.html').write_bytes(response.content)
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            (OUT / f'{name}.txt').write_text(soup.get_text(' ', strip=True), encoding='utf-8')
            record.update(status=response.status_code, resolved_url=response.url,
                          sha256=hashlib.sha256(response.content).hexdigest(),
                          tables=len(soup.find_all('table')),
                          images=sorted({urljoin(response.url, img.get('src') or img.get('data-src') or '')
                                         for img in soup.select('img[src],img[data-src]')}),
                          attachments=sorted({urljoin(response.url, a['href']) for a in soup.select('a[href]')
                                              if any(ext in a['href'].lower() for ext in ('.pdf', '.xlsx', '.doc'))}))
            if name.startswith('cmc_'):
                record['score_images'] = []
                for image_url in record['images']:
                    if image_url.startswith('https://cmcu.edu.vn/') and ('diem-chuan' in image_url or 'diem_chuan' in image_url):
                        asset = requests.get(image_url, timeout=(10, 45))
                        asset.raise_for_status()
                        suffix = Path(image_url).suffix
                        asset_path = OUT / (name + suffix)
                        asset_path.write_bytes(asset.content)
                        record['score_images'].append({'url': image_url, 'path': str(asset_path.relative_to(ROOT)),
                                                       'sha256': hashlib.sha256(asset.content).hexdigest()})
            print(f'{name}: HTTP {response.status_code}, tables={record["tables"]}', flush=True)
        except requests.RequestException as exc:
            record.update(error=f'{type(exc).__name__}: {exc}')
            print(f'{name}: {type(exc).__name__}', flush=True)
        manifest.append(record)
        (OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
