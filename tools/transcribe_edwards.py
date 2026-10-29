"""Transcribe the appendix of E. Price Edwards, *Our Seamarks* (1884): the
principal lights of the British Isles, "corrected to March 1884", by number,
name, character and range. Read twice by independent helpers off the IA
scans; the two readings are compared row by row. A witness for the lights'
characters between Findlay's 1879 and 1887 editions.

Run: python3 -I tools/transcribe_edwards.py 180 195   ->  data/lights/edwards1884/p<page>_run<r>.json
     python3 -I tools/transcribe_edwards.py merge      ->  data/lights/edwards1884.csv
"""
import concurrent.futures as cf, csv, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA, ROOT, scan_ia
from station_lists import run_helper
from transcribe_lights import pair_rows, norm
from merge_lights import best

IDENT = 'edwards-1884-our-seamarks-a-plain-account-of-the-ligh'
OFFSET = 40          # image index = printed page + 40 (checked: the helpers read the printed page off each image)
OUT = os.path.join(DATA, 'lights', 'edwards1884')
FIELDS = ['number', 'name', 'character', 'range_miles']
N = {'type': ['string', 'null']}
SCHEMA = {'type': 'object', 'required': ['page', 'country', 'is_list', 'rows'], 'properties': {
    'page': N, 'country': N, 'is_list': {'type': 'boolean'},
    'rows': {'type': 'array', 'items': {'type': 'object', 'required': FIELDS + ['continued'],
                                        'properties': {**{f: N for f in FIELDS}, 'continued': {'type': 'boolean'}}}}}}
BRIEF = '''Thank you for helping. I'm a Claude agent building a record of the lighthouses of Britain and Ireland as they were in the 1880s, for a project on the lighthouse keepers who recorded bird migration in 1879-1887. This page is from the appendix of E. Price Edwards's "Our Seamarks" (1884), a list of the principal lights "corrected to March 1884". Please transcribe it exactly: we need each light's character (its colour, how it flashes, and its period) as printed then.

Open the page image with the Read tool: {path}

For the page: its printed page number, the country in the running head or sub-heading ("ENGLAND", "SCOTLAND--continued"), and whether it is part of the list of lights at all (is_list false for a page of prose, an index or a plate; then give no rows).
Then one row per light, top to bottom:
- number: the light's number as printed, or null.
- name: as printed ("Spurn Point--2 lights", "Goodwin light vessel (North Sand)").
- character: the character column as printed, line breaks as spaces ("White, group flashing, 3 flashes every minute"; "Two fixed lights of unequal heights--high, white; low, red").
- range_miles: the range in miles as printed, or null.
- continued: true if the row continues an entry from the previous page.
Copy abbreviations, spelling and punctuation exactly. Where a word is truly unreadable, put [?] in its place rather than guessing.'''


def ask(page, run):
    out = os.path.join(OUT, f'p{page}_run{run}.json')
    if os.path.exists(out):
        return json.load(open(out))
    path = scan_ia(IDENT, page + OFFSET, 'edwards1884')
    d, cost = run_helper(BRIEF.format(path=path), SCHEMA, 'Read')
    d['_meta'] = {'page_arg': page, 'image': os.path.relpath(path, ROOT), 'run': run, 'cost_usd': cost}
    os.makedirs(OUT, exist_ok=True)
    json.dump(d, open(out, 'w'), indent=1, ensure_ascii=False)
    return d


def merge():
    import glob, re
    rows, agree, total = [], 0, 0
    pages = sorted({int(re.search(r'/p(\d+)_run', f).group(1)) for f in glob.glob(os.path.join(OUT, 'p*_run1.json'))})
    for p in pages:
        A, B = (json.load(open(os.path.join(OUT, f'p{p}_run{r}.json'))) for r in (1, 2))
        if not A['is_list']:
            continue
        for k, (ra, rb) in enumerate(pair_rows(A, B)):
            differs = [f for f in FIELDS if rb is None or norm(ra[f]) != norm(rb[f])]
            total += len(FIELDS)
            agree += len(FIELDS) - len(differs)
            rb = rb or ra
            rows.append({'row_id': f'p{p}r{k}', 'page_arg': p, 'printed_page': A['page'], 'country': A['country'],
                         **{f: best(ra[f], rb[f]) for f in FIELDS}, 'differs': ' '.join(differs)})
    with open(os.path.join(DATA, 'lights', 'edwards1884.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, ['row_id', 'page_arg', 'printed_page', 'country'] + FIELDS + ['differs'])
        w.writeheader()
        w.writerows(rows)
    print(f'{len(rows)} lights from {len(pages)} pages; fields agree {agree}/{total}; rows with a difference '
          f'{sum(bool(r["differs"]) for r in rows)}')


if __name__ == '__main__':
    if sys.argv[1] == 'merge':
        merge()
    else:
        a, b = int(sys.argv[1]), int(sys.argv[2])
        jobs = [(p, r) for p in range(a, b + 1) for r in (1, 2)]
        with cf.ThreadPoolExecutor(12) as ex:
            for (p, r), d in zip(jobs, ex.map(lambda j: ask(*j), jobs)):
                print(p, r, d['page'], d['country'], d['is_list'], len(d['rows']), flush=True)
