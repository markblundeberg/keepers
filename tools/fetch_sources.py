"""Fetch the nine Reports on the Migration of Birds (1879-1887) and record provenance.

Each report exists as an Internet Archive scan with OCR text (all nine) and,
for six of them, a Project Gutenberg transcription (cleaner, preferred).
Writes the files under sources/ and a manifest with URLs and sha256 hashes.

Run: python3 -I tools/fetch_sources.py   (from the repo root)
"""
import hashlib, json, os, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'sources')

# report year -> (Internet Archive identifier, Project Gutenberg ebook number or None)
REPORTS = {
    1879: ('reportonmigratio11879harv', 65621),
    1880: ('reportonmigratio21880harv', 65411),
    1881: ('reportonmigratio31881harv', 65471),
    1882: ('reportonmigratio41882harv', 65515),
    1883: ('reportonmigratio51883harv', None),
    1884: ('reportonmigratio61884harv', None),
    1885: ('reportonmigratio71885harv', 65840),
    1886: ('reportonmigratio81886harv', None),
    1887: ('reportonmigratio91887harv', 66152),
}

def get(url, path):
    if not os.path.exists(path):
        req = urllib.request.Request(url, headers={'User-Agent': 'keepers-project/0.1 (research; via Mark Lundeberg)'})
        data = urllib.request.urlopen(req, timeout=120).read()
        with open(path, 'wb') as f:
            f.write(data)
        time.sleep(1.5)
    data = open(path, 'rb').read()
    return {'url': url, 'path': os.path.relpath(path, ROOT), 'bytes': len(data),
            'sha256': hashlib.sha256(data).hexdigest()}

def ia_text_name(ident):
    meta = json.load(urllib.request.urlopen(f'https://archive.org/metadata/{ident}', timeout=60))
    names = [f['name'] for f in meta['files'] if f['name'].endswith('_djvu.txt')]
    return names[0], meta.get('metadata', {})

manifest = {}
for year, (ident, pg) in REPORTS.items():
    entry = {'year': year, 'ia_id': ident,
             'ia_details': f'https://archive.org/details/{ident}',
             'page_image_pattern': f'https://archive.org/download/{ident}/page/n{{index}}.jpg'}
    name, meta = ia_text_name(ident)
    entry['ia_title'] = meta.get('title')
    entry['ia_date'] = meta.get('date')
    entry['ia_ocr'] = get(f'https://archive.org/download/{ident}/{name}',
                          os.path.join(SRC, 'ia', f'{year}_{name}'))
    # leaf index -> printed page number, to link records to the scans
    entry['ia_page_numbers'] = get(f'https://archive.org/download/{ident}/{ident}_page_numbers.json',
                                   os.path.join(SRC, 'ia', f'{year}_{ident}_page_numbers.json'))
    if pg:
        entry['gutenberg_id'] = pg
        entry['gutenberg_txt'] = get(f'https://www.gutenberg.org/cache/epub/{pg}/pg{pg}.txt',
                                     os.path.join(SRC, 'gutenberg', f'{year}_pg{pg}.txt'))
        entry['gutenberg_html'] = get(f'https://www.gutenberg.org/cache/epub/{pg}/pg{pg}-images.html',
                                      os.path.join(SRC, 'gutenberg', f'{year}_pg{pg}.html'))
    manifest[year] = entry
    print(year, ident, 'PG' if pg else '--', entry['ia_ocr']['bytes'], 'bytes OCR')

with open(os.path.join(SRC, 'MANIFEST.json'), 'w') as f:
    json.dump(manifest, f, indent=1)
print('wrote sources/MANIFEST.json')
