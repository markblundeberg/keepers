"""Cut every report's observation sections into chunks for extraction.

One rule for every layout (data/sections/<year>.json gives the sections):
paragraphs (blank-line separated) are gathered into chunks of about
TARGET characters; a paragraph longer than MAX is cut at sentence ends. Each
chunk carries its exact offsets in the source file and a context: up to
CONTEXT characters of the same section just before it, so the extractor
knows which species, station, month or season the chunk continues. The
extractor quotes only from the chunk; a field it takes from the context is
flagged as such, and checked against the context.

Offsets are code points into the source text (Gutenberg where there is one,
else the IA OCR), like everywhere else in the project.

Run: python3 -I tools/chunks.py [years]   ->  data/chunks/<year>.jsonl
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA
from station_lists import source

OUT = os.path.join(DATA, 'chunks')
TARGET, MAX, CONTEXT = 1400, 2200, 700
LAYOUTS = ('diary', 'station', 'species', 'prose', 'table')
SENT_END = re.compile(r'(?<=[.;:!?"”’)])\s+(?=[A-Z_“"(\[])')


def paragraphs(text, a, b):
    """(start, end) offsets of the paragraphs of text[a:b], blank-line separated, whitespace trimmed."""
    out = []
    for m in re.finditer(r'(?:[^\n]|\n(?![ \t]*\n))+', text[a:b]):
        s, e = a + m.start(), a + m.end()
        while s < e and text[s].isspace():
            s += 1
        while e > s and text[e - 1].isspace():
            e -= 1
        if e > s:
            out.append((s, e))
    return out


def cut_long(text, s, e):
    """A paragraph longer than MAX, cut at sentence ends into pieces of about TARGET."""
    if e - s <= MAX:
        return [(s, e)]
    ends = [s + m.start() for m in SENT_END.finditer(text[s:e])]
    pieces, cur = [], s
    for x in ends:
        if x - cur >= TARGET:
            pieces.append((cur, x))
            cur = x
            while cur < e and text[cur].isspace():
                cur += 1
    pieces.append((cur, e))
    out = []
    for a, b in pieces:                      # a sentence longer than MAX: cut at a line end
        while b - a > MAX:
            nl = text.rfind('\n', a, a + TARGET)
            nl = nl if nl > a + TARGET // 2 else a + TARGET
            out.append((a, nl))
            a = nl
            while a < b and text[a].isspace():
                a += 1
        out.append((a, b))
    return out


def chunks_of(year):
    path, kind = source(year)
    text = open(path, encoding='utf-8').read()
    line_off = [0]
    for l in text.split('\n'):
        line_off.append(line_off[-1] + len(l) + 1)
    secs = json.load(open(os.path.join(DATA, 'sections', f'{year}.json')))['sections']
    out = []
    for si, sec in enumerate(secs):
        if sec['layout'] not in LAYOUTS or sec['observations'] == 'none':
            continue
        a, b = line_off[sec['first_line'] - 1], line_off[sec['last_line']]
        pieces = [p for s, e in paragraphs(text, a, b) for p in cut_long(text, s, e)]
        cur = []
        for s, e in pieces:
            if cur and e - cur[0][0] > TARGET:
                out.append((si, sec, cur[0][0], cur[-1][1]))
                cur = []
            cur.append((s, e))
        if cur:
            out.append((si, sec, cur[0][0], cur[-1][1]))
    rows = []
    for k, (si, sec, s, e) in enumerate(out):
        a = line_off[sec['first_line'] - 1]
        cs = max(a, s - CONTEXT)
        nl = text.find('\n', cs, s)             # start the context at a line start where one is near
        cs = nl + 1 if 0 <= nl < s - 200 else cs
        rows.append({'id': f'{year}-{k:05d}', 'year': year, 'source': os.path.basename(path), 'reading': kind, 'section': si,
                     'coast': sec['coast'], 'title': sec['title'], 'layout': sec['layout'], 'season': sec['season'],
                     'observations': sec['observations'], 'start': s, 'end': e, 'context_start': cs,
                     'text': text[s:e], 'context': text[cs:s]})
    return rows


def main(years):
    os.makedirs(OUT, exist_ok=True)
    for y in years:
        rows = chunks_of(y)
        src = open(source(y)[0], encoding='utf-8').read()
        assert all(src[r['start']:r['end']] == r['text'] and src[r['context_start']:r['start']] == r['context'] for r in rows)
        with open(os.path.join(OUT, f'{y}.jsonl'), 'w') as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + '\n')
        from collections import Counter
        sizes = sorted(len(r['text']) for r in rows)
        print(f'{y}: {len(rows)} chunks; {sum(sizes) // 1000}k chars; median {sizes[len(sizes) // 2]}, max {sizes[-1]}; '
              f'{dict(Counter((r["observations"][:4], r["layout"]) for r in rows))}')


if __name__ == '__main__':
    main([int(y) for y in sys.argv[1:]] or list(range(1879, 1888)))
