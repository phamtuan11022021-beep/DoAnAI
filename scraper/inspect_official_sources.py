"""Snapshot primary admissions notices for human image/table verification."""
import hashlib
import json
from pathlib import Path
from urllib.parse import urljoin
import requests
import truststore
from bs4 import BeautifulSoup

SOURCES = {
    'udn_2026': 'https://ts.udn.vn/DHCD/Chinhquy/diemchuan/19567',
    'vku_2026': 'https://tuyensinh.vku.udn.vn/thong-bao/6a79472c0619ded1f20e9b44',
    'ute_2026': 'https://ute.udn.vn/TinTuc/10231/1/Ron-rang-Ngay-hoi-don-tan-sinh-vien-khoa-2026-tai-Truong-Dai-hoc-Su-pham-Ky-thuat--Dai-hoc-Da-Nang.aspx',
}
ROOT = Path(__file__).resolve().parents[1] / 'data/raw/official_20261030'


def main():
    truststore.inject_into_ssl()
    ROOT.mkdir(parents=True, exist_ok=True)
    for name, url in SOURCES.items():
        try:
            response = requests.get(url, timeout=(10, 45))
            response.raise_for_status()
            response.encoding = 'utf-8'
            (ROOT / f'{name}.html').write_text(response.text, encoding='utf-8')
            soup = BeautifulSoup(response.text, 'html.parser')
            assets = sorted(set(urljoin(response.url, item.get('src') or item.get('data-src') or '')
                                 for item in soup.select('img[src],img[data-src]')))
            links = [{'text': a.get_text(' ', strip=True), 'url': urljoin(response.url, a['href'])}
                     for a in soup.select('a[href]')]
            manifest = {'source_url': url, 'resolved_url': response.url,
                        'sha256': hashlib.sha256(response.content).hexdigest(),
                        'images': assets, 'links': links}
            (ROOT / f'{name}.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
            (ROOT / f'{name}.txt').write_text(soup.get_text(' ', strip=True), encoding='utf-8')
            print(name, 'HTTP', response.status_code, 'image_count:', len(assets), flush=True)
        except requests.RequestException as exc:
            print(name, type(exc).__name__, flush=True)


if __name__ == '__main__':
    main()
