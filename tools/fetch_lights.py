"""Fetch the period lists of lights (stage 2) from the Internet Archive and
record provenance in sources/lights/MANIFEST.json. Page images are fetched
on demand into cache/ by kp.scan_ia().

Run: python3 -I tools/fetch_lights.py
"""
import hashlib, json, os, time, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get(url, path):     # as in fetch_sources.py (which runs on import, so not imported)
    if not os.path.exists(path):
        req = urllib.request.Request(url, headers={'User-Agent': 'keepers-project/0.1 (research; via Mark Lundeberg)'})
        data = urllib.request.urlopen(req, timeout=120).read()
        with open(path, 'wb') as f:
            f.write(data)
        time.sleep(1.5)
    data = open(path, 'rb').read()
    return {'url': url, 'path': os.path.relpath(path, ROOT), 'bytes': len(data),
            'sha256': hashlib.sha256(data).hexdigest()}

BOOKS = {
    # Findlay, A Description and List of the Lighthouses of the World, 19th ed., 1879.
    # Leaf n = printed page + 12; England to p. 45, Scotland 46-51, Ireland from 52.
    'findlay1879': 'adescriptionand00unkngoog',
    # E. Price Edwards, Our Seamarks, 1884: principal lights corrected to March 1884.
    'edwards1884': 'edwards-1884-our-seamarks-a-plain-account-of-the-ligh',
}
OUT = os.path.join(ROOT, 'sources', 'lights')

manifest = {}
for key, ident in BOOKS.items():
    meta = json.load(urllib.request.urlopen(f'https://archive.org/metadata/{ident}', timeout=60))
    e = {'ia_id': ident, 'ia_details': f'https://archive.org/details/{ident}',
         'page_image_pattern': f'https://archive.org/download/{ident}/page/n{{index}}.jpg',
         'ia_title': meta['metadata'].get('title'), 'ia_date': meta['metadata'].get('date')}
    for f in meta['files']:
        n = f['name']
        for suffix, field in (('_djvu.txt', 'ia_ocr'), ('_page_numbers.json', 'ia_page_numbers')):
            if n.endswith(suffix):
                e[field] = get(f'https://archive.org/download/{ident}/{urllib.parse.quote(n)}',
                               os.path.join(OUT, f'{key}{suffix}'))
    manifest[key] = e
    print(key, ident, {k: v['bytes'] for k, v in e.items() if isinstance(v, dict)})
json.dump(manifest, open(os.path.join(OUT, 'MANIFEST.json'), 'w'), indent=1)
print('wrote sources/lights/MANIFEST.json')
