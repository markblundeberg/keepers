"""Shared helpers for the keepers tools: paths, sources, normalisation, pages.

Offsets everywhere are character offsets (Unicode code points) into the
UTF-8-decoded source file named in sources/MANIFEST.json.
"""
import bisect, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
MANIFEST = json.load(open(os.path.join(ROOT, 'sources', 'MANIFEST.json')))

def obs_path(year):
    """The observations of a year: the two readings merged (tools/second_reading.py) where they exist, else the first."""
    m = os.path.join(DATA, 'obs', f'{year}_v4m.jsonl')
    return m if os.path.exists(m) else os.path.join(DATA, 'obs', f'{year}_v4.jsonl')


def obs_paths():
    return [obs_path(y) for y in range(1879, 1888) if os.path.exists(os.path.join(DATA, 'obs', f'{y}_v4.jsonl'))]


MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July',
          'August', 'September', 'October', 'November', 'December']
MONTH_NUM = {m: i + 1 for i, m in enumerate(MONTHS)}


def source_path(year, kind='gutenberg_txt'):
    return os.path.join(ROOT, MANIFEST[str(year)][kind]['path'])


def read_source(year, kind='gutenberg_txt'):
    return open(source_path(year, kind), encoding='utf-8').read()


def norm_with_map(s):
    """Normalise text for matching across editions: drop underscores (italics),
    unify dashes and quotes, lowercase, collapse whitespace. Returns the
    normalised string and, for each of its characters, the offset in s."""
    out, idx, prev_space = [], [], True
    for i, ch in enumerate(s):
        if ch == '_':
            continue
        rep = {'—': '--', '–': '-', '‘': "'", '’': "'",
               '“': '"', '”': '"'}.get(ch, ch)
        for c in rep:
            if c.isspace():
                if prev_space:
                    continue
                c, prev_space = ' ', True
            else:
                prev_space = False
            out.append(c.lower())
            idx.append(i)
    return ''.join(out), idx


class Pages:
    """Printed page at a source offset, and the scan image for a printed page.
    Built by tools/pages.py into data/pages/<year>.json."""

    def __init__(self, year):
        d = json.load(open(os.path.join(DATA, 'pages', f'{year}.json')))
        self.markers = [m for m in d['markers'] if m['txt_offset'] is not None]
        self.offsets = [m['txt_offset'] for m in self.markers]
        self.pattern = d['image_pattern']

    def at(self, offset):
        i = bisect.bisect_right(self.offsets, offset) - 1
        return self.markers[i] if i >= 0 else None

    def page(self, offset):
        m = self.at(offset)
        return m['page'] if m else None

    def image(self, offset):
        m = self.at(offset)
        return self.pattern.format(index=m['image_index']) if m and m['image_index'] is not None else None


def ws_norm_with_map(s):
    """Collapse whitespace runs to single spaces (and trim), keeping a map from
    each output character to its offset in s. Only whitespace changes."""
    out, idx, prev_space = [], [], True
    for i, ch in enumerate(s):
        if ch.isspace():
            if prev_space:
                continue
            ch, prev_space = ' ', True
        else:
            prev_space = False
        out.append(ch)
        idx.append(i)
    if out and out[-1] == ' ':
        out.pop()
        idx.pop()
    return ''.join(out), idx


def ws_norm(s):
    return ' '.join(s.split())


def scan(year, index):
    """Local path of a scan image (IA page/n<index>.jpg), fetched once into cache/scans/."""
    import time, urllib.request
    path = os.path.join(ROOT, 'cache', 'scans', str(year), f'n{index}.jpg')
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        url = MANIFEST[str(year)]['page_image_pattern'].format(index=index)
        req = urllib.request.Request(url, headers={'User-Agent': 'keepers-project/0.1 (research; via Mark Lundeberg)'})
        data = urllib.request.urlopen(req, timeout=120).read()
        with open(path, 'wb') as f:
            f.write(data)
        time.sleep(1.0)
    return path


def scan_ia(ident, index, sub='other'):
    """Local path of any Internet Archive page image, fetched once into cache/scans/<sub>/."""
    import time, urllib.request
    path = os.path.join(ROOT, 'cache', 'scans', sub, f'n{index}.jpg')
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        req = urllib.request.Request(f'https://archive.org/download/{ident}/page/n{index}.jpg',
                                     headers={'User-Agent': 'keepers-project/0.1 (research; via Mark Lundeberg)'})
        data = urllib.request.urlopen(req, timeout=120).read()
        with open(path, 'wb') as f:
            f.write(data)
        time.sleep(1.0)
    return path


def ocr_leaf(year, offset, _cache={}):
    """For an OCR-only year: (printed page or None, image index) of the leaf holding a text offset, from
    data/pages/<year>_leaves.json (leaves placed in the OCR text by their opening words; tools/leaves.py)."""
    if year not in _cache:
        lv = json.load(open(os.path.join(DATA, 'pages', f'{year}_leaves.json')))['leaves']
        placed = [l for l in lv if l.get('ocr_start') is not None]
        _cache[year] = ([l['ocr_start'] for l in placed], placed)
    starts, placed = _cache[year]
    i = bisect.bisect_right(starts, offset) - 1
    if i < 0:
        return None, None
    return placed[i].get('page'), placed[i]['image_index']
