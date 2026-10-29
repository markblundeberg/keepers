"""Map the Gutenberg text to printed pages, and printed pages to scan images.

The Gutenberg HTML marks every printed page (<span class="pagenum"
id="Page_55">); the plain text, which the records quote, doesn't. Each marker
is anchored into the plain text by the words that follow it (or, failing
that, the words before it). The Internet Archive's page_numbers.json maps
scan leaves to printed page numbers.

Run: python3 -I tools/pages.py 1887 [1885 ...]  ->  data/pages/<year>.json
"""
import html, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA, MANIFEST, ROOT, norm_with_map, read_source

# IA image URLs count leaves from 0 (n0 is the first leaf); page_numbers.json
# counts them from 1. Checked by eye on 1887: see notes/PILOT.md.
LEAF_TO_INDEX = -1

PAGENUM = re.compile(r'<span class="pagenum" id="Page_([^"]+)">.*?</span>', re.S)
BLOCK = re.compile(r'</?(?:p|div|h\d|br|tr|td|li|table|blockquote|hr)\b[^>]*>', re.I)
TAG = re.compile(r'<[^>]+>')


def html_text_with_markers(h):
    """Plain text of the HTML body and the position of each page marker in it."""
    h = h[h.find('<body'):]
    parts = PAGENUM.split(h)
    text, marks = [], []
    for i, part in enumerate(parts):
        if i % 2:
            marks.append((part, sum(len(t) for t in text)))
        else:
            text.append(html.unescape(TAG.sub('', BLOCK.sub(' ', part))))
    return ''.join(text), marks


def build(year):
    e = MANIFEST[str(year)]
    txt = read_source(year)
    N, nidx = norm_with_map(txt)
    H, marks = html_text_with_markers(open(os.path.join(ROOT, e['gutenberg_html']['path']), encoding='utf-8').read())
    # normalise the HTML text too, carrying marker positions through
    Hn, hidx = norm_with_map(H)
    pos_in_Hn = []
    j = 0
    for page, p in marks:
        while j < len(hidx) and hidx[j] < p:
            j += 1
        pos_in_Hn.append(j)

    pn = json.load(open(os.path.join(ROOT, e['ia_page_numbers']['path'])))
    leaf_of = {}
    for pg in pn['pages']:
        if pg['pageNumber'] and pg['pageNumber'] not in leaf_of:
            leaf_of[pg['pageNumber']] = pg['leafNum']

    out, last = [], 0
    for (page, _), k in zip(marks, pos_in_Hn):
        found, how = None, None
        for n in (60, 40, 25):
            a = Hn[k:k + n].strip()
            if len(a) < 15:
                break
            f = N.find(a, last)
            if f >= 0 and N.find(a, f + 1) < 0:      # unique from here on
                found, how = f, f'after:{n}'
                break
        if found is None:
            for n in (60, 40, 25):
                b = Hn[max(0, k - n):k].strip()
                f = N.find(b, last)
                if len(b) >= 15 and f >= 0 and N.find(b, f + 1) < 0:
                    found, how = f + len(b), f'before:{n}'
                    while found < len(N) and N[found] == ' ':
                        found += 1
                    break
        off = nidx[found] if found is not None and found < len(nidx) else None
        if found is not None:
            last = found
        leaf = leaf_of.get(page)
        out.append({'page': page, 'txt_offset': off, 'anchor': how, 'leaf': leaf,
                    'image_index': leaf + LEAF_TO_INDEX if leaf is not None else None})
    d = {'year': year, 'source': e['gutenberg_txt']['path'],
         'image_pattern': e['page_image_pattern'], 'markers': out}
    os.makedirs(os.path.join(DATA, 'pages'), exist_ok=True)
    json.dump(d, open(os.path.join(DATA, 'pages', f'{year}.json'), 'w'), indent=0)
    unres = [m['page'] for m in out if m['txt_offset'] is None]
    noleaf = [m['page'] for m in out if m['leaf'] is None]
    mono = all(a['txt_offset'] < b['txt_offset'] for a, b in zip(out, out[1:])
               if a['txt_offset'] is not None and b['txt_offset'] is not None)
    print(f'{year}: {len(out)} markers, {len(out) - len(unres)} anchored '
          f'({sum(1 for m in out if m["anchor"] and m["anchor"].startswith("before"))} by preceding text), '
          f'unanchored {unres}, no IA leaf {noleaf}, increasing: {mono}')


if __name__ == '__main__':
    for y in sys.argv[1:]:
        build(int(y))
