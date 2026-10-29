"""Transcribe pages of a period list of lights from the scans, twice and
independently (separate safe-mode helpers), then compare the two readings
field by field. Agreement is the transcription; every disagreement goes to
adjudication on the scan.

Run: python3 -I tools/transcribe_lights.py findlay1879 34 44 [--runs 2] [--workers 4]
  -> data/lights/<book>/p<page>_run<k>.json and a comparison on stdout
"""
import argparse, concurrent.futures as cf, json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA, ROOT, scan_ia

# book -> (kind, where, offset). ia: Internet Archive id, pages given as printed pages, leaf = page + offset;
# pdf: a local PDF, pages given as PDF page numbers (the printed page is read off the image).
BOOKS = {'findlay1879': ('ia', 'adescriptionand00unkngoog', 12),
         'findlay1887': ('pdf', os.path.join(ROOT, 'sources', 'lights', 'findlay1887.pdf'), None)}
CORE = ['name', 'character', 'lat', 'long', 'year']


def page_image(book, page):
    kind, where, off = BOOKS[book]
    if kind == 'ia':
        return scan_ia(where, page + off, book)
    out = os.path.join(ROOT, 'cache', 'scans', book, f'pdf{page}.png')
    if not os.path.exists(out):
        os.makedirs(os.path.dirname(out), exist_ok=True)
        subprocess.run(['pdftoppm', '-r', '200', '-gray', '-png', '-singlefile', '-f', str(page), '-l', str(page),
                        where, out[:-4]], check=True)
    return out
FIELDS = ['name', 'character', 'lat', 'long', 'description', 'apparatus', 'height_ft', 'visible_miles', 'year']
N = {'type': ['string', 'null']}
SCHEMA = {'type': 'object', 'required': ['page', 'country', 'coast', 'long_hemisphere', 'rows'],
          'properties': {'page': N, 'country': N, 'coast': N, 'long_hemisphere': {'type': 'string', 'enum': ['E', 'W', 'mixed']},
                         'rows': {'type': 'array', 'items': {'type': 'object', 'required': FIELDS + ['continued'],
                                  'properties': {**{f: N for f in FIELDS}, 'continued': {'type': 'boolean'}}}}}}

BRIEF = '''Thank you for helping. I'm a Claude agent building a record of the lighthouses of Britain and Ireland as they were in the 1880s, for a project on the lighthouse keepers who recorded bird migration in 1879-1887. This page is from Findlay's "Description and List of the Lighthouses of the World", {year}. Please transcribe it exactly: we need each light's character (how it flashed) and position as printed then.

Open the page image with the Read tool: {path}

For the page: its printed page number, the country and coast in the running head (e.g. "ENGLAND", "South-East Coast"), and whether the longitude column is headed E. or W. ("mixed" if both).
Then one row per light, top to bottom, every row on the page:
- name: as printed in the first column ("Kentish Knock Lt.-vessel", "GALLOPER LIGHT-VES.", "Ramsgate, Tide Lights").
- character: the line(s) under the name, as printed ("One br. rev. lt., 1 min.", "Two bright fixed lights"); for numbered sub-lights keep the numbers ("1. Red or green light on West pier 2. Green lt. on W. cliff").
- lat and long: as printed, degrees then minutes, with the minutes' decimal point where there is one ("51 49.6", "1 31.1", "51 45."). The latitude is the upper figure, the longitude the lower.
- description: the "Description, &c." column, as printed, line breaks as spaces.
- apparatus: the symbol or code in the apparatus column ("●", "1a", "4a"), or null.
- height_ft, visible_miles, year: as printed ("37", "10", "1802"; a row of dots is null).
- continued: true if the row is the continuation of an entry from the previous page (no name of its own).
Copy abbreviations, spelling and punctuation exactly; don't expand "br." or "rev.". Where a character is truly unreadable, put [?] in its place rather than guessing. Use null for an empty cell.
'''


def ask(book, page, run):
    path = page_image(book, page)
    out = os.path.join(DATA, 'lights', book, f'p{page}_run{run}.json')
    if os.path.exists(out):
        return json.load(open(out))
    prompt = BRIEF.format(year=book[-4:], path=path)
    kind, where, off = BOOKS[book]
    cmd = ['systemd-run', '--user', '--scope', '-q', '-p', 'MemoryMax=3G', '-p', 'MemorySwapMax=0',
           'claude', '-p', '--safe-mode', '--model', 'claude-opus-5-5', '--effort', 'high', '--tools', 'Read',
           '--allowedTools', 'Read', '--no-session-persistence', '--output-format', 'json', '--json-schema', json.dumps(SCHEMA)]
    p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=3600)
    res = json.loads(p.stdout)
    if res.get('is_error') or not res.get('structured_output'):
        raise RuntimeError(f'p{page} run{run}: {str(res)[:300]}')
    d = res['structured_output']
    d['_meta'] = {'book': book, 'kind': kind, 'source': os.path.relpath(where, ROOT) if kind == 'pdf' else where,
                  'page_arg': page, 'image': os.path.relpath(path, ROOT), 'run': run, 'cost_usd': res.get('total_cost_usd')}
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(d, open(out, 'w'), indent=1, ensure_ascii=False)
    return d


def norm(v):
    """For comparing two readings: separators ("1832 / 1887"), spacing and final stops are formatting."""
    return ' '.join(str(v).replace('/', ' ').split()).rstrip('.') if v is not None else None


def pair_rows(a, b):
    """Each row of reading a with its partner in reading b (or None), aligned
    by the sequence of names, so two rows of one name on a page (Black Rock in
    Sligo and in Mayo) pair in order rather than by name alone."""
    import difflib
    key = lambda r: ' '.join((r['name'] or '').lower().split())
    sm = difflib.SequenceMatcher(None, [key(r) for r in a['rows']], [key(r) for r in b['rows']], autojunk=False)
    partner = {}
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal' or (tag == 'replace' and i2 - i1 == j2 - j1):
            for i, j in zip(range(i1, i2), range(j1, j2)):
                partner[i] = b['rows'][j]
    return [(ra, partner.get(i)) for i, ra in enumerate(a['rows'])]


def compare(a, b):
    """Field-by-field agreement of two readings of one page. Rows are aligned
    by name first (one reading may split or skip a row; pairing by position
    would then misalign everything after it); unpaired rows are reported."""
    import difflib
    key = lambda r: ' '.join((r['name'] or '').lower().split())
    sm = difflib.SequenceMatcher(None, [key(r) for r in a['rows']], [key(r) for r in b['rows']], autojunk=False)
    pairs, diffs = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal' or (tag == 'replace' and i2 - i1 == j2 - j1):
            pairs += list(zip(a['rows'][i1:i2], b['rows'][j1:j2]))
        else:
            for r in a['rows'][i1:i2]:
                diffs.append(('row only in run 1', r['name'], r['character'], None))
            for r in b['rows'][j1:j2]:
                diffs.append(('row only in run 2', r['name'], r['character'], None))
    agree = total = 0
    for ra, rb in pairs:
        for f in FIELDS:
            total += 1
            if norm(ra[f]) == norm(rb[f]):
                agree += 1
            else:
                diffs.append((ra['name'], f, ra[f], rb[f]))
    for f in ('page', 'country', 'coast', 'long_hemisphere'):
        if norm(a[f]) != norm(b[f]):
            diffs.append(('page', f, a[f], b[f]))
    return agree, total, diffs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('book')
    ap.add_argument('pages', nargs='+', type=int)
    ap.add_argument('--runs', type=int, default=2)
    ap.add_argument('--workers', type=int, default=4)
    a = ap.parse_args()
    jobs = [(p, r) for p in a.pages for r in range(1, a.runs + 1)]
    with cf.ThreadPoolExecutor(a.workers) as ex:
        res = dict(zip(jobs, ex.map(lambda j: ask(a.book, *j), jobs)))
    tot_rows = tot_agree = tot_fields = 0
    for p in a.pages:
        A, B = res[(p, 1)], res[(p, 2)]
        agree, total, diffs = compare(A, B)
        tot_rows += len(A['rows']); tot_agree += agree; tot_fields += total
        core = [d for d in diffs if d[0] == 'page' or str(d[0]).startswith('row only') or d[1] in CORE]
        print(f'p{p} (printed {A["page"]}, {A["country"]}, {A["coast"]}): {len(A["rows"])} rows; '
              f'fields agree {agree}/{total}; core disagreements {len(core)}')
        for d in core:
            print('   ', d)
    print(f'TOTAL {len(a.pages)} pages, {tot_rows} rows, fields agree {tot_agree}/{tot_fields}')


if __name__ == '__main__':
    main()
