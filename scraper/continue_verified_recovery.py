"""Snapshot the next primary sources without rewriting earlier evidence."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'data/raw/official_20261106_ai2'
SOURCES = {
    'uet_2026': 'https://tuyensinh.uet.vnu.edu.vn/uncategorized/thong-bao-diem-trung-tuyen-dai-hoc-chinh-quy-vao-truong-dai-hoc-cong-nghe-dhqghn-nam-2026/',
    'ttu_2026': 'https://ttu.edu.vn/truong-dai-hoc-tan-tao-cong-bo-diem-chuan-trung-tuyen-dai-hoc-chinh-quy-nam-2026/',
    'thanhdong_2025': 'https://khoayduoc.thanhdong.edu.vn/truong-dai-hoc-thanh-dong-cong-bo-diem-chuan-dai-hoc-chinh-quy-2025-n14698.html',
    'huit_2026': 'https://ts.huit.edu.vn/tin-tuc-hoat-dong/diem-chuan-truong-dai-hoc-cong-thuong-tp-hcm-nam-2026',
    'agu_2026': 'https://tuyensinh.agu.edu.vn/tin-tuc/quyet-dinh-ve-viec-cong-bo-diem-chuan-trung-tuyen-dai-hoc-hinh-thuc-giao-duc-chinh-quy-nam-2026',
}


def fetch():
    try:
        import truststore
        truststore.inject_into_ssl()
    except ImportError:
        pass
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    for name, url in SOURCES.items():
        record = {'id': name, 'url': url, 'retrieved_at': datetime.now(timezone.utc).isoformat()}
        try:
            response = requests.get(url, timeout=(10, 45))
            response.raise_for_status()
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            (OUT/f'{name}.html').write_bytes(response.content)
            (OUT/f'{name}.txt').write_text(soup.get_text(' ', strip=True), encoding='utf-8')
            record.update(status=200, sha256=hashlib.sha256(response.content).hexdigest(),
                          tables=len(soup.find_all('table')),
                          images=sorted({urljoin(response.url, image.get('src') or image.get('data-src') or '')
                                         for image in soup.select('img[src],img[data-src]')}),
                          attachments=sorted({urljoin(response.url, a['href']) for a in soup.select('a[href]')
                                              if any(x in a['href'].lower() for x in ('.pdf', '.doc', '.xls'))}))
            if name == 'ttu_2026':
                image_url = next((url for url in record['images'] if '/2026/08/bang-diem-chuan-' in url), None)
                if image_url:
                    image = requests.get(image_url, timeout=(10, 45))
                    image.raise_for_status()
                    (OUT/'ttu_2026.jpg').write_bytes(image.content)
                    record['score_image'] = {'url': image_url, 'sha256': hashlib.sha256(image.content).hexdigest()}
            print(f'{name}: HTTP 200; tables={record["tables"]}', flush=True)
        except requests.RequestException as exc:
            record['error'] = f'{type(exc).__name__}: {exc}'
            print(f'{name}: {type(exc).__name__}', flush=True)
        manifest.append(record)
        (OUT/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    fetch()
