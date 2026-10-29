"""Resolve the station words the extraction copies ("_Flambro'_ L.H.",
"Spurn L.V.", "the Fastnet", "Great Yarmouth") to station ids.

1. exact: the words, normalised, equal a printed name of a station
   (data/stations/stations.json), with the light-vessel/lighthouse type
   kept apart (Spurn L.H. is not Spurn L.V.);
2. helpers: the remaining distinct (words, coast) pairs, with the stations
   of that coast to choose from, are resolved twice by independent helpers
   to a station id, a land place ("place:great-yarmouth"), or none; the two
   runs are compared and disagreements listed.

Run: python3 -I tools/resolve_stations.py exact | ask [--refresh] | compare | build
  (ask: two runs per coast; --refresh adds names that appeared since, as a new generation)
  -> data/stations/aliases.csv  (words, coast, station_id, how)
"""
import collections, csv, functools, glob, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA, obs_paths
from station_lists import run_helper

ST = os.path.join(DATA, 'stations')
TYPE = re.compile(r"\b(l\.?\s?h|l\.?\s?v|lt\.?-?\s?ship|light-?ship|light-?vessel|lightvessel|lighthouse|lt\.?-?\s?ves(?:sel)?|lt\.?-?\s?v)\b\.?", re.I)


def kind_of(words):
    w = (words or '').lower()
    if re.search(r'\bl\.?\s?v\b|ship|vessel|lt\.?-?\s?v\b', w):
        return 'light-vessel'
    if re.search(r'\bl\.?\s?h\b|lighthouse', w):
        return 'lighthouse'
    return None


def norm(words):
    w = re.sub(r'[_\[\]\d*†‡]', ' ', words or '')
    w = TYPE.sub(' ', w)
    w = re.sub(r"[^A-Za-z' ]", ' ', w).lower()
    w = re.sub(r'^(?:at|the|from|off|near)\s+', '', ' '.join(w.split()))
    return w.strip(" '")


def exact_table():
    """normalised name -> {kind: {ids}} from every printed name."""
    t = collections.defaultdict(lambda: collections.defaultdict(set))
    for s in json.load(open(os.path.join(ST, 'stations.json'))):
        for p in s['printed'] + [s['name']]:
            t[norm(p)][s['kind'] if s['kind'] != 'other' else 'lighthouse'].add(s['id'])
    return t


def collect():
    """Every (station words, coast, year) the extraction produced, with counts."""
    out = collections.Counter()
    for path in obs_paths():
        year = int(os.path.basename(path)[:4])
        chunks = {json.loads(l)['id']: json.loads(l) for l in open(os.path.join(DATA, 'chunks', f'{year}.jsonl'))}
        for l in open(path):
            r = json.loads(l)
            for o in r['obs'] or []:
                if o['station']:
                    out[(o['station'].strip(), chunks[r['chunk']]['coast'], year)] += 1
    return out


ROMAN = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100}


def roman(r):
    r = r.upper().replace(' ', '')
    if not r or not re.fullmatch(r'[IVXLC]+', r):
        return None
    v = 0
    for a, b in zip(r, r[1:] + ' '):
        v += -ROMAN[a] if b != ' ' and ROMAN[b] > ROMAN[a] else ROMAN[a]
    return v


def numbered(year):
    """{map number: station id} in the numbering nearest the given year (the
    master and section lists print numbers like '27@1885')."""
    by_year = collections.defaultdict(dict)
    for s in json.load(open(os.path.join(ST, 'stations.json'))):
        for n in s['numbers']:
            num, y = n.split('@')
            m = re.match(r'(\d+)\s*([A-Za-z_*]*)', num)
            if m:
                key_ = m.group(1) + m.group(2).replace('_', '').lower()
                by_year[int(y)][key_] = s['id']
    ys = sorted(by_year, key=lambda y: (abs(y - year), -y))
    out = {}
    for y in reversed(ys):                 # nearer years overwrite farther ones
        out.update(by_year[y])
    return out


def by_numeral(words, year):
    """'XXVII.' or 'XXVII. (Isle of May)' or 'XXVIII. B.' -> station id by the year's numbering, if the words are
    one numbered station."""
    m = re.fullmatch(r'\s*(?:station\s+)?([IVXLC][IVXLC ]*)[.,]?\s*([Bb])?\.?\s*(?:\(.*\))?\s*', words or '', re.I)
    if not m:
        return None
    n = roman(m.group(1))
    if n is None:
        return None
    return numbered(year).get(f'{n}{(m.group(2) or "").lower()}')


@functools.lru_cache(None)
def _stations():
    return json.load(open(os.path.join(ST, 'stations.json')))


STATIONS = _stations


def by_number(words, year):
    """'102' or '48a' -> station id by that year's own lists (the numbering changed between years, so no neighbour)."""
    m = re.fullmatch(r'\s*(?:no\.\s*)?(\d+)\s*([a-z])?\.?\s*', words or '', re.I)
    if not m:
        return None
    hits = {s['id'] for s in STATIONS() for n in s['numbers']
            if n.endswith(f'@{year}') and re.match(r'(\d+)\s*([A-Za-z_*]*)', n.split('@')[0]) and
            (lambda mm: mm.group(1) + mm.group(2).replace('_', '').lower())(re.match(r'(\d+)\s*([A-Za-z_*]*)', n.split('@')[0]))
            == m.group(1) + (m.group(2) or '').lower()}
    return next(iter(hits)) if len(hits) == 1 else None


def exact():
    t = exact_table()
    res, left = {}, collections.Counter()
    for (w, coast, year), n in collect().items():
        hits = t.get(norm(w), {})
        k = kind_of(w)
        ids = hits.get(k, set()) if k else set().union(*hits.values()) if hits else set()
        num = (by_numeral(w, year) if 'SCOTLAND' in coast.upper() else None) or by_number(w, year)
        if num:
            res[(w, coast, year)] = (num, 'map number')
        elif len(ids) == 1:
            res[(w, coast, year)] = (next(iter(ids)), 'exact')
        else:
            left[(w, coast, year)] = n
    print(f'distinct (words, coast): {len(res) + len(left)}; resolved exactly {len(res)} '
          f'({sum(collect()[k] for k in res)} observations); left {len(left)} ({sum(left.values())} observations)')
    return res, left


R_SCHEMA = {'type': 'object', 'required': ['items', 'notes'], 'properties': {'items': {'type': 'array', 'items': {
    'type': 'object', 'required': ['n', 'kind', 'ids', 'place', 'note'], 'properties': {
        'n': {'type': 'integer'}, 'kind': {'type': 'string', 'enum': ['station', 'stations', 'place', 'none']},
        'ids': {'type': 'array', 'items': {'type': 'string'}}, 'place': {'type': ['string', 'null']}, 'note': {'type': ['string', 'null']}}}},
    'notes': {'type': 'string'}}}

R_BRIEF = """Thank you for helping. I'm a Claude agent turning the British Association's reports on bird migration at lighthouses (1879-1887) back into data. Each observation names where it was made, in the report's own words; I need each of those names resolved.

Two files (open each with the Read tool):
- {stations}: the stations (JSON): id, usual modern name, kind, every name and type the reports' station lists print for it, the coasts it appears on, and the years ('seen') whose lists include it: a name in a year's report most likely means a station listed that year.
- {items}: the names to resolve (JSON): n, the words as printed in an observation, the coast and years of the report sections they come from, how many observations use them, and an example.

For each item, give kind and ids:
- station: one station; ids = [its id]. Expect misspellings, OCR garbles ("Pen land Skerries", "Farn L.H#."), abbreviations ("Flambro'", "Hasbro'"), the station's district or island for its light ("Sanday" for Start Point, Orkney), and type words; a lighthouse and the light-vessel off it are different stations, as are two places of one name on different coasts.
- stations: several stations named together ("Stations VII., VIII., XIV., and XXVII." are map numbers in Roman numerals on the committee's map; the East of Scotland list numbers N. Unst IV, Sumburgh VII, N. Ronaldshay VIII, Pentland Skerries XIV, Isle of May XXVII, and so on): ids = all of them.
- place: not a station of the scheme but a place where someone observed (a town, a village, an estate, a stretch of coast: "Great Yarmouth", "Redcar", "North-East Lincolnshire", "Heligoland"); ids = [] and place = its usual modern name with its county or country ("Great Yarmouth, Norfolk").
- none: not a place at all ("same station", "the lantern", "on board").
Say in note anything uncertain. In notes, list what I should check."""


def items_file(refresh=False):
    """data/stations/aliases/items.json: the names left after the exact pass, one per (words, coast), numbered.
    refresh: add names that have appeared since (the second reading's observations), as a new generation, keeping
    the numbers and answers of the old ones."""
    ip = os.path.join(ST, 'aliases', 'items.json')
    old = json.load(open(ip)) if os.path.exists(ip) else []
    if old and not refresh:
        return old
    os.makedirs(os.path.dirname(ip), exist_ok=True)
    res, left = exact()
    examples = collect_examples()
    by_key = collections.defaultdict(lambda: {'n_obs': 0, 'years': set()})
    for (w, coast, year), n in left.items():
        e = by_key[(w, coast)]
        e['n_obs'] += n
        e['years'].add(year)
    known = {(i['words'], i['coast']): i for i in old}
    gen = max((i.get('gen', 0) for i in old), default=-1) + 1
    nxt = max((i['n'] for i in old), default=-1) + 1
    items = []
    for (w, coast), e in sorted(by_key.items()):
        i = known.get((w, coast))
        if i is None:
            i = {'n': nxt, 'gen': gen, 'words': w, 'coast': coast}
            nxt += 1
        items.append(dict(i, years=sorted(e['years']), observations=e['n_obs'], example=examples.get((w, coast), '')))
    items.sort(key=lambda i: i['n'])
    json.dump(items, open(ip, 'w'), indent=1, ensure_ascii=False)
    print(f'{len(items)} names; new this time: {sum(1 for i in items if i.get("gen", 0) == gen)}')
    return items


def ask(run, coast, gen=0):
    """One run over one coast's names of one generation (a coast at a time keeps each list short enough to read with care)."""
    slug = re.sub(r'[^a-z]+', '-', coast.lower()).strip('-') + (f'_g{gen}' if gen else '')
    out = os.path.join(ST, 'aliases', f'resolve_run{run}_{slug}.json')
    if os.path.exists(out):
        return json.load(open(out))
    items = [i for i in items_file() if i['coast'] == coast and i.get('gen', 0) == gen]
    if not items:
        return {'items': []}
    ip = os.path.join(ST, 'aliases', f'items_{slug}.json')
    json.dump(items, open(ip, 'w'), indent=1, ensure_ascii=False)
    sp = os.path.join(ST, 'aliases', 'stations.json')
    json.dump([{k: s[k] for k in ('id', 'name', 'kind', 'printed', 'regions', 'seen')} for s in json.load(open(os.path.join(ST, 'stations.json')))],
              open(sp, 'w'), indent=1, ensure_ascii=False)
    d, cost = run_helper(R_BRIEF.format(stations=sp, items=ip), R_SCHEMA, 'Read')
    d['_meta'] = {'run': run, 'coast': coast, 'gen': gen, 'cost_usd': cost, 'n_items': len(items)}
    json.dump(d, open(out, 'w'), indent=1, ensure_ascii=False)
    return d


def runs():
    """The two runs' answers, by item number."""
    out = [{}, {}]
    for r in (1, 2):
        for path in glob.glob(os.path.join(ST, 'aliases', f'resolve_run{r}_*.json')):
            for x in json.load(open(path))['items']:
                out[r - 1][x['n']] = x
    return out


def collect_examples():
    out = {}
    for path in obs_paths():
        year = int(os.path.basename(path)[:4])
        chunks = {json.loads(l)['id']: json.loads(l) for l in open(os.path.join(DATA, 'chunks', f'{year}.jsonl'))}
        for l in open(path):
            r = json.loads(l)
            for o in r['obs'] or []:
                if o['station']:
                    out.setdefault((o['station'].strip(), chunks[r['chunk']]['coast']), o['quote'][:120])
    return out


def compare():
    items = {i['n']: i for i in json.load(open(os.path.join(ST, 'aliases', 'items.json')))}
    A, B = runs()
    dis = [n for n in items if (A.get(n, {}).get('kind'), sorted(A.get(n, {}).get('ids', []))) !=
           (B.get(n, {}).get('kind'), sorted(B.get(n, {}).get('ids', [])))]
    obs_dis = sum(items[n]['observations'] for n in dis)
    print(f'{len(items)} names ({sum(i["observations"] for i in items.values())} observations); runs differ on {len(dis)} '
          f'({obs_dis} observations)')
    for n in dis:
        print(f"  {n} {items[n]['words']!r} [{items[n]['coast'][:24]}] x{items[n]['observations']}: run1 {A.get(n, {}).get('kind')} "
              f"{A.get(n, {}).get('ids')} {A.get(n, {}).get('place')} | run2 {B.get(n, {}).get('kind')} {B.get(n, {}).get('ids')} "
              f"{B.get(n, {}).get('place')}")


def build():
    """data/stations/aliases.csv: every (words, coast, year) -> station ids (or a place), and how it was resolved."""
    res, left = exact()
    ip = os.path.join(ST, 'aliases', 'items.json')          # absent before the helpers have run: exact matches only
    items = {i['n']: i for i in json.load(open(ip))} if os.path.exists(ip) else {}
    A, B = runs()
    rev_path = os.path.join(ST, 'aliases', 'reviewed.json')
    rev = json.load(open(rev_path)) if os.path.exists(rev_path) else {}
    key2n = {(i['words'], i['coast']): n for n, i in items.items()}
    rows = []
    for (w, coast, year), (sid, how) in res.items():
        rows.append({'words': w, 'coast': coast, 'year': year, 'kind': 'station', 'ids': sid, 'place': '', 'how': how})
    for (w, coast, year) in left:
        n = key2n.get((w, coast))
        a, b = A.get(n), B.get(n)
        if str(n) in rev:
            x, how = rev[str(n)], 'reviewed'
        elif a and b and (a['kind'], sorted(a['ids'])) == (b['kind'], sorted(b['ids'])):
            x, how = a, 'helpers agree'
        else:
            x, how = {'kind': 'unresolved', 'ids': [], 'place': None}, 'helpers differ' if a or b else 'not asked'
        rows.append({'words': w, 'coast': coast, 'year': year, 'kind': x['kind'], 'ids': ' '.join(x['ids']), 'place': x.get('place') or '',
                     'how': how})
    with open(os.path.join(ST, 'aliases.csv'), 'w', newline='') as f:
        wr = csv.DictWriter(f, ['words', 'coast', 'year', 'kind', 'ids', 'place', 'how'])
        wr.writeheader()
        wr.writerows(rows)
    print(f'{len(rows)} aliases; by how: {dict(collections.Counter(r["how"] for r in rows))}; '
          f'by kind: {dict(collections.Counter(r["kind"] for r in rows))}')


if __name__ == '__main__':
    step = sys.argv[1]
    if step == 'ask':
        import concurrent.futures as cf
        items = items_file(refresh='--refresh' in sys.argv)
        jobs = sorted({(r, i['coast'], i.get('gen', 0)) for r in (1, 2) for i in items})
        with cf.ThreadPoolExecutor(8) as ex:
            for (r, c, g), d in zip(jobs, ex.map(lambda j: ask(*j), jobs)):
                print(f'run {r} {c} gen {g}: {len(d["items"])} items', flush=True)
    elif step == 'compare':
        compare()
    elif step == 'build':
        build()
    if step == 'exact':
        res, left = exact()
        for (w, c, y), n in left.most_common(40):
            print(f'   {n:4} {w!r} [{c}, {y}]')
