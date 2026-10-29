"""Leaves, printed pages and scan images, read from the scans' own OCR.

IA's page_numbers.json guesses a printed page per leaf, and the /page/nN.jpg
images count only the leaves in the access copy (scandata.xml marks the
rest: covers, colour cards, and in 1880 two plates). So: the image of a
leaf is its leaf number less the skipped leaves before it; the printed page
of a leaf is read from its running head in IA's per-leaf OCR
(hocr_searchtext + hocr_pageindex), smoothed along the book. Checks: every
Gutenberg page marker's first words are found on the leaf this map gives
its page (Gutenberg years); every leaf's opening words are found in the
OCR text in order (OCR years), which places the leaf in that text.

Run: python3 -I tools/leaves.py [years]  ->  data/pages/<year>_leaves.json
"""
import bisect, difflib, gzip, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA, MANIFEST, ROOT

HEAD_NUM = [re.compile(r'^\s*(\d{1,3})\s+REPORT\b', re.I), re.compile(r'^\s*[A-Z][A-Za-z ,.&\'’-]{6,60}?[.,]?\s+(\d{1,3})\s*$'),
            re.compile(r'^\s*(\d{1,3})\s*$')]


def load(year):
    t = gzip.open(os.path.join(ROOT, MANIFEST[str(year)]['ia_hocr_searchtext']['path']), 'rt', encoding='utf-8').read()
    pi = json.loads(gzip.open(os.path.join(ROOT, MANIFEST[str(year)]['ia_hocr_pageindex']['path']), 'rt').read())
    x = open(os.path.join(ROOT, MANIFEST[str(year)]['ia_scandata']['path']), encoding='utf-8', errors='replace').read()
    skipped = sorted(int(n) for n, b in re.findall(r'<page leafNum="(\d+)">(.*?)</page>', x, re.S) if '<addToAccessFormats>false' in b)
    return t, pi, skipped


def detect(text):
    """A printed page number from a leaf's first two or last line, or None."""
    lines = [l for l in text.split('\n') if l.strip()]
    for l in lines[:2] + lines[-1:]:
        for rx in HEAD_NUM:
            m = rx.match(l)
            if m and 1 <= int(m.group(1)) <= 400:
                return int(m.group(1))
    return None


def build(year):
    t, pi, skipped = load(year)
    leaves = []
    for leaf, (a, b, *_) in enumerate(pi):
        n = None if leaf in skipped else leaf - bisect.bisect_left(skipped, leaf)
        leaves.append({'leaf': leaf, 'image_index': n, 'text_start': a, 'text_end': b, 'detected': detect(t[a:b]) if b > a else None})
    # smooth: a leaf's page is detected; a detection that breaks the run of (leaf - page) around it by one leaf is a
    # misread ("8" for "3"); leaves with none take the page their neighbours' run implies
    det = [(l['leaf'], l['detected']) for l in leaves if l['detected']]
    offs = {}
    for i, (leaf, p) in enumerate(det):
        nb = [lf - pg for lf, pg in det[max(0, i - 3):i] + det[i + 1:i + 4]]
        if nb and sum(1 for o in nb if o == leaf - p) >= max(1, len(nb) // 3):
            offs[leaf] = leaf - p
    good = sorted(offs)
    for l in leaves:
        if l['image_index'] is None:
            l['page'] = None
            continue
        if l['leaf'] in offs:
            l['page'], l['how'] = l['leaf'] - offs[l['leaf']], 'running head'
            continue
        j = bisect.bisect_left(good, l['leaf'])
        before, after = (good[j - 1] if j else None), (good[j] if j < len(good) else None)
        if before is not None and after is not None and offs[before] == offs[after]:
            l['page'], l['how'] = l['leaf'] - offs[before], 'between heads'
        else:
            l['page'], l['how'] = None, 'unknown'
    return t, leaves


def check_gutenberg(year, t, leaves):
    """Each Gutenberg page marker: are its first words on the leaf this map gives its page? (Word overlap, so
    OCR garbles don't count as misses.) A miss is also looked for on the neighbouring leaves."""
    d = json.load(open(os.path.join(DATA, 'pages', f'{year}.json')))
    src = open(os.path.join(ROOT, MANIFEST[str(year)]['gutenberg_txt']['path']), encoding='utf-8').read()
    by_page = {}
    for l in leaves:
        if l.get('page'):
            by_page.setdefault(l['page'], []).append(l)
    words_of = lambda s: [w for w in re.findall(r'[a-z]{4,}', s.lower())]
    def hit(words, leaf):
        lw = set(words_of(t[leaf['text_start']:leaf['text_end']]))
        return sum(w in lw for w in words) >= 0.6 * len(words)
    ok = n = 0
    bad, off = [], {}
    for m in d['markers']:
        if m['txt_offset'] is None or not m['page'].isdigit():
            continue
        words = words_of(src[m['txt_offset']:m['txt_offset'] + 300].replace('_', ''))[:10]
        if len(words) < 5:
            continue
        n += 1
        p = int(m['page'])
        if any(hit(words, c) for c in by_page.get(p, [])):
            ok += 1
            continue
        near = [dp for dp in (-2, -1, 1, 2) if any(hit(words, c) for c in by_page.get(p + dp, []))]
        bad.append((m['page'], near, ' '.join(words[:6])))
    return ok, n, bad


def place_in_ocr(year, t, leaves):
    """For an OCR year: each leaf's start offset in the djvu text, by finding its opening words in order."""
    src = open(os.path.join(ROOT, MANIFEST[str(year)]['ia_ocr']['path']), encoding='utf-8').read()
    pos, placed = 0, 0
    for l in leaves:
        l['ocr_start'] = None
        if l['image_index'] is None or l['text_end'] <= l['text_start']:
            continue
        body = t[l['text_start']:l['text_end']]
        lines = [x.strip() for x in body.split('\n') if len(x.strip()) > 25]
        for probe in lines[1:6] + lines[:1]:
            i = src.find(probe[:30], pos)
            if 0 <= i < pos + 60000:
                l['ocr_start'] = i
                pos = i
                placed += 1
                break
    return placed, sum(1 for l in leaves if l['image_index'] is not None and l['text_end'] > l['text_start'])


def main(years):
    for y in years:
        t, leaves = build(y)
        out = {'year': y, 'rule': 'image_index = leaf - (leaves left out of the access copy before it, scandata.xml)', 'leaves': leaves}
        msg = f'{y}: {len(leaves)} leaves; pages from running heads {sum(l.get("how") == "running head" for l in leaves)}, between heads ' \
              f'{sum(l.get("how") == "between heads" for l in leaves)}, unknown {sum(l.get("how") == "unknown" for l in leaves)}'
        if 'gutenberg_txt' in MANIFEST[str(y)]:
            ok, n, bad = check_gutenberg(y, t, leaves)
            out['check'] = {'gutenberg_markers_found_on_their_leaf': ok, 'of': n, 'misses': bad}
            msg += f'; Gutenberg page markers found on their leaf: {ok}/{n}'
        else:
            placed, of = place_in_ocr(y, t, leaves)
            out['check'] = {'leaves_placed_in_ocr_text': placed, 'of': of}
            msg += f'; leaves placed in the OCR text: {placed}/{of}'
        json.dump(out, open(os.path.join(DATA, 'pages', f'{y}_leaves.json'), 'w'), indent=1)
        print(msg)
        if out['check'].get('misses'):
            import collections
            print('   misses by where the words are instead:', dict(collections.Counter(str(b[1]) for b in out['check']['misses'])),
                  '| e.g.', out['check']['misses'][:4])


if __name__ == '__main__' and not (len(sys.argv) > 1 and sys.argv[1] == 'apply'):
    main([int(y) for y in sys.argv[1:]] or list(range(1879, 1888)))


def apply(year):
    """Gutenberg years: rewrite data/pages/<year>.json image indices from this map (IA's guess kept as
    image_index_ia). The leaf for a printed page is the one with that page whose words match the marker."""
    lv = json.load(open(os.path.join(DATA, 'pages', f'{year}_leaves.json')))['leaves']
    by_page = {}
    for l in lv:
        if l.get('page') and l['image_index'] is not None:
            by_page.setdefault(l['page'], []).append(l)
    path = os.path.join(DATA, 'pages', f'{year}.json')
    d = json.load(open(path))
    changed = 0
    for m in d['markers']:
        if not m['page'].isdigit():
            continue
        cands = by_page.get(int(m['page']), [])
        if not cands:
            continue
        new = cands[0]['image_index'] if len(cands) == 1 else cands[-1]['image_index']
        if 'image_index_ia' not in m:
            m['image_index_ia'] = m['image_index']
        if m['image_index'] != new:
            changed += 1
        m['image_index'] = new
    d['image_index_note'] = ('image_index from data/pages/<year>_leaves.json (running heads in the IA per-leaf OCR; scandata '
                             'access copy); image_index_ia is the earlier guess from page_numbers.json')
    json.dump(d, open(path, 'w'), indent=1)
    return changed


if __name__ == '__main__' and len(sys.argv) > 1 and sys.argv[1] == 'apply':
    for y in (1879, 1880, 1881, 1882, 1885, 1887):
        print(y, 'markers whose image changed:', apply(y))
