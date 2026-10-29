"""Merge the two independent readings of each list-of-lights page into one
table. A field both readings agree on (up to formatting) is taken; where
they differ, the row is flagged and the reading kept from run 1 unless it
has [?] or is empty. Positions become signed decimal degrees, using the
per-row hemisphere where a page straddles Greenwich (hemispheres.json).

Run: python3 -I tools/merge_lights.py findlay1887  ->  data/lights/findlay1887.csv
"""
import csv, glob, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA
from transcribe_lights import CORE, FIELDS, compare, norm, pair_rows

COLS = ['row_id', 'book', 'page_arg', 'printed_page', 'country', 'coast', 'name', 'character', 'lat', 'long', 'hemisphere',
        'lat_deg', 'lon_deg', 'description', 'apparatus', 'height_ft', 'visible_miles', 'year', 'readings_agree', 'flag']


def degrees(s):
    """'51 45.1' -> 51.7517; None if it doesn't read as degrees and minutes."""
    m = re.fullmatch(r'\s*(\d{1,3})\s+(\d{1,2}(?:\.\d*)?)\.?\s*', s or '')
    return round(int(m.group(1)) + float(m.group(2)) / 60, 5) if m else None


def best(x, y):
    if norm(x) == norm(y):
        return x if x is not None else y
    for v in (x, y):
        if v and '[?]' not in v:
            return v
    return x or y


def main(book):
    hemi = json.load(open(os.path.join(DATA, 'lights', book, 'hemispheres.json'))) \
        if os.path.exists(os.path.join(DATA, 'lights', book, 'hemispheres.json')) else {}
    rows = []
    pages = sorted({int(re.search(r'/p(\d+)_run', f).group(1)) for f in glob.glob(os.path.join(DATA, 'lights', book, 'p*_run1.json'))})
    for p in pages:
        A = json.load(open(os.path.join(DATA, 'lights', book, f'p{p}_run1.json')))
        B = json.load(open(os.path.join(DATA, 'lights', book, f'p{p}_run2.json')))
        _, _, diffs = compare(A, B)
        flagged = {d[0] for d in diffs if d[1] in CORE}
        for k, (ra, rb) in enumerate(pair_rows(A, B)):
            rb = rb or ra                       # a row only run 1 has: taken as read, and flagged below
            r = {f: best(ra[f], rb[f]) for f in FIELDS}
            if not (r['character'] or r['lat'] or r['long'] or r['description']):
                continue                        # a subheading ("CORK HARBOUR"), not a light
            # (a light whose character is printed in the description column, like Oyster Island in 1879, is kept)
            hp = hemi.get(str(p), {})
            # a row with no name of its own was asked about as "None" (tools/hemispheres.py lists str(name))
            h = hp.get(r['name']) or hp.get(str(r['name'])) or (A['long_hemisphere'] if A['long_hemisphere'] in 'EW' else None)
            lat, lon = degrees(r['lat']), degrees(r['long'])
            rows.append({'row_id': f'p{p}r{k}', 'book': book, 'page_arg': p, 'printed_page': A['page'], 'country': A['country'], 'coast': A['coast'],
                         **r, 'hemisphere': h, 'lat_deg': lat,
                         'lon_deg': (lon if h == 'E' else -lon if h == 'W' else None) if lon is not None else None,
                         'readings_agree': r['name'] not in flagged,
                         'flag': 'core fields differ between readings' if r['name'] in flagged else
                                 ('hemisphere unknown' if lon is not None and h not in ('E', 'W') else '')})
    out = os.path.join(DATA, 'lights', f'{book}.csv')
    with open(out, 'w', newline='') as f:
        w = csv.DictWriter(f, COLS)
        w.writeheader()
        w.writerows(rows)
    print(f'{book}: {len(rows)} lights from {len(pages)} pages; readings differ on core fields for '
          f'{sum(not r["readings_agree"] for r in rows)}; hemisphere unknown for {sum(r["flag"] == "hemisphere unknown" for r in rows)}')


if __name__ == '__main__':
    main(sys.argv[1])
