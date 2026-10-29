"""The stations: one row per light or light-vessel, with every name it goes by
in the reports' station lists, its map numbers by year, and (later steps) its
Findlay rows and position.

  names:   the distinct names in data/stations/list_rows.csv, with context
           (region, type, years, numbers, neighbours in the list)
                                         -> data/stations/names.csv
  group:   two independent helpers group the names into stations
                                         -> data/stations/group_run<r>.json
  compare: the two groupings compared name by name; disagreements listed

Run: python3 -I tools/stations.py names | group | compare
"""
import argparse, concurrent.futures as cf, csv, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA, ROOT
from station_lists import run_helper

ST = os.path.join(DATA, 'stations')
OUTLYING = re.compile(r'^(iceland|do\.?|faroe|heligoland|stevns|malm)', re.I)


def region(r):
    sec, coast, name = r['section'].upper(), (r['coast'] or '').lower(), r['name']
    if r['list_kind'] == 'master':
        if OUTLYING.match(name.strip()) or 'outlying' in coast:
            return 'outlying'
        for k, v in (('scotland--east', 'scotland_east'), ('england--east', 'england_east'), ('scotland--west', 'scotland_west'),
                     ('isle of man', 'isle_of_man'), ('england--west', 'england_west'), ('ireland', 'ireland')):
            if k in coast:
                return v
        return 'scotland_east'          # the unheaded rows before "Scotland--East Coast" (Fair Isle)
    if 'IRISH' in sec:
        return 'ireland'
    if 'ISLE OF MAN' in (r['place'] or '').upper() or 'isle of man' in coast:
        return 'isle_of_man'
    for k, v in (('EAST COAST OF SCOTLAND', 'scotland_east'), ('EAST COAST OF ENGLAND', 'england_east'),
                 ('WEST COAST OF SCOTLAND', 'scotland_west'), ('WEST COAST OF ENGLAND', 'england_west')):
        if k in sec:
            return v
    return 'unknown'    # a section head garbled by the OCR ('HAST COAST', 'KAST COAST', 'TRISH COAST', 1883-84);
                        # the grouping placed these names by name and neighbours, so names.csv keeps them as read


def key(r):
    clean = lambda s: ' '.join(re.sub(r'[_*†‡{}]', ' ', s or '').split()).strip(' .,;:').lower()
    return region(r), clean(r['name']), clean(r['type'])


def names():
    rows = list(csv.DictReader(open(os.path.join(ST, 'list_rows.csv'))))
    by_list = {}
    for r in rows:
        by_list.setdefault((r['year'], r['list']), []).append(r)
    out = {}
    for (year, lst), rs in by_list.items():
        for i, r in enumerate(rs):
            k = key(r)
            e = out.setdefault(k, {'region': k[0], 'name': r['name'].strip(), 'type': r['type'] or '', 'places': set(), 'seen': [],
                                   'numbers': set(), 'neighbours': set()})
            e['seen'].append(f"{year}{'m' if r['list_kind'] == 'master' else ''}")
            if r['number']:
                e['numbers'].add(f"{r['number'].strip(' .')}@{year}")
            if r['place']:
                e['places'].add(r['place'].strip(' .,'))
            prev = rs[i - 1]['name'].strip() if i else '(first)'
            nxt = rs[i + 1]['name'].strip() if i + 1 < len(rs) else '(last)'
            e['neighbours'].add(f'{prev} < > {nxt}')
    cols = ['idx', 'region', 'name', 'type', 'places', 'seen', 'numbers', 'neighbours']
    path = os.path.join(ST, 'names.csv')
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, cols)
        w.writeheader()
        for i, (k, e) in enumerate(sorted(out.items(), key=lambda kv: (kv[0][0], kv[0][1]))):
            w.writerow({'idx': i, 'region': e['region'], 'name': e['name'], 'type': e['type'], 'places': '; '.join(sorted(e['places'])),
                        'seen': ' '.join(sorted(set(e['seen']))), 'numbers': ' '.join(sorted(e['numbers'])),
                        'neighbours': ' || '.join(sorted(e['neighbours'])[:3])})
    print(f'{len(out)} distinct names from {len(rows)} list rows -> {os.path.relpath(path, ROOT)}')


GROUP_SCHEMA = {'type': 'object', 'required': ['stations', 'notes'], 'properties': {
    'stations': {'type': 'array', 'items': {'type': 'object', 'required': ['id', 'name', 'kind', 'members', 'note'], 'properties': {
        'id': {'type': 'string'}, 'name': {'type': 'string'},
        'kind': {'type': 'string', 'enum': ['lighthouse', 'light-vessel', 'other']},
        'members': {'type': 'array', 'items': {'type': 'integer'}}, 'note': {'type': ['string', 'null']}}}},
    'notes': {'type': 'string'}}}

GROUP_BRIEF = '''Thank you for helping. I'm a Claude agent rebuilding the records of the lighthouse keepers who reported bird migration to a British Association committee, 1879-1887. Each annual report lists the lighthouses and light-vessels the committee sent schedules to; I have read those lists, and now need to know which printed names are the same station.

The file {path} has one line per distinct printed name (CSV; open it with the Read tool). Columns: idx; region (the coast of the list it came from); name and type as printed; places printed with it; seen (the report years it appears in, "m" for the master list of all coasts); numbers (its number on the committee's map, by year: "30@1887"); neighbours (the names printed just before and after it in a list: "previous < > next").

Please group the idx values into stations: one group per physical light or light-vessel. The same station is printed many ways: abbreviations and old spellings ("Hasbro'" for Happisburgh, "Flambro'"), Gaelic and English forms ("Island Glass", "Island Ghlais", Eilean Glas), word order ("Farn, Inner", "Inner Farn", "Farne Inner"), misprints ("Bona" for Rona between Barra Head and Kyleakin), and a ditto line ('"     (High)' under Hoy Sound (Low)). Use the neighbours and map numbers: the lists run in coast order, and a number usually means the same station across years of the same numbering. Keep apart what is different: a lighthouse and the light-vessel off it (Spurn Point L.H. and Spurn L.V.), the two lights of a pair where the list gives each its own row (Hoy Sound High and Low; Eagle Island E. and W.), and two places of one name (Start Point in Orkney and Start Point in Devon). Iceland, Faroe and other outlying stations are stations too.

For each station: an id (lowercase slug from its usual modern name, e.g. "eilean-glas", "happisburgh-lv", "start-point-orkney"; add "-lv" for a light-vessel); its usual modern name; its kind (lighthouse, light-vessel, or other for a signal tower or a station that is neither); its members (idx values); and a note where a grouping needs a reason (a misprint, a renamed station, a doubt). Every idx goes in exactly one station. In notes, say anything I should check.'''


def group(run):
    out = os.path.join(ST, f'group_run{run}.json')
    if os.path.exists(out):
        return json.load(open(out))
    d, cost = run_helper(GROUP_BRIEF.format(path=os.path.join(ST, 'names.csv')), GROUP_SCHEMA, 'Read')
    d['_meta'] = {'run': run, 'cost_usd': cost}
    json.dump(d, open(out, 'w'), indent=1, ensure_ascii=False)
    return d


def membership(d):
    return {i: s['id'] for s in d['stations'] for i in s['members']}


def compare():
    """Two groupings: every name in exactly one station (each run), and the
    pairs of names one run puts together and the other doesn't."""
    nm = {int(r['idx']): r for r in csv.DictReader(open(os.path.join(ST, 'names.csv')))}
    A, B = (json.load(open(os.path.join(ST, f'group_run{r}.json'))) for r in (1, 2))
    for tag, d in (('run1', A), ('run2', B)):
        seen = [i for s in d['stations'] for i in s['members']]
        missing, dup = set(nm) - set(seen), {i for i in seen if seen.count(i) > 1}
        print(f'{tag}: {len(d["stations"])} stations; names missing {sorted(missing)}; in two stations {sorted(dup)}')
    ma, mb = membership(A), membership(B)
    groups_a = {}
    for i, s in ma.items():
        groups_a.setdefault(s, set()).add(i)
    groups_b = {}
    for i, s in mb.items():
        groups_b.setdefault(s, set()).add(i)
    pairs_a = {(i, j) for g in groups_a.values() for i in g for j in g if i < j}
    pairs_b = {(i, j) for g in groups_b.values() for i in g for j in g if i < j}
    only_a, only_b = pairs_a - pairs_b, pairs_b - pairs_a
    print(f'pairs together: run1 {len(pairs_a)}, run2 {len(pairs_b)}, both {len(pairs_a & pairs_b)}; '
          f'only run1 {len(only_a)}, only run2 {len(only_b)}')
    show = lambda i: f'{i}:{nm[i]["name"]} {nm[i]["type"]} [{nm[i]["region"]}]'
    for tag, only in (('only run1', only_a), ('only run2', only_b)):
        for i, j in sorted(only)[:60]:
            print(f'  {tag}: {show(i)}  ==  {show(j)}   ({ma.get(i)} / {mb.get(i)})')
    same_ids = sum(groups_a.get(s) == g for s, g in groups_b.items())
    print(f'stations identical in both runs (same members): {same_ids} of {len(groups_b)}')


def finalize():
    """The agreed grouping (both runs must partition the names identically),
    with run 1's ids and names and the reviewed edits in overrides.json
    -> data/stations/stations.json."""
    A, B = (json.load(open(os.path.join(ST, f'group_run{r}.json'))) for r in (1, 2))
    if {frozenset(s['members']) for s in A['stations']} != {frozenset(s['members']) for s in B['stations']}:
        sys.exit('the two groupings differ: resolve them first (compare)')
    ov = json.load(open(os.path.join(ST, 'overrides.json')))
    nm = {int(r['idx']): r for r in csv.DictReader(open(os.path.join(ST, 'names.csv')))}
    out = []
    for s in A['stations']:
        st = {'id': s['id'], 'name': s['name'], 'kind': s['kind'], 'note': s['note'], 'edits': []}
        if s['id'] in ov['rename']:
            st['id'], st['name'], why = ov['rename'][s['id']]
            st['edits'].append(why)
        if s['id'] in ov['kind']:
            st['kind'], why = ov['kind'][s['id']]
            st['edits'].append(why)
        st['members'] = sorted(s['members'])
        st['printed'] = sorted({f"{nm[i]['name']} {nm[i]['type']}".strip() for i in s['members']})
        st['regions'] = sorted({nm[i]['region'] for i in s['members']})
        st['seen'] = sorted({y for i in s['members'] for y in nm[i]['seen'].split()})
        st['numbers'] = sorted({n for i in s['members'] for n in nm[i]['numbers'].split()})
        out.append(st)
    ids = [s['id'] for s in out]
    assert len(ids) == len(set(ids)), 'duplicate ids'
    json.dump(out, open(os.path.join(ST, 'stations.json'), 'w'), indent=1, ensure_ascii=False)
    print(f'{len(out)} stations -> data/stations/stations.json')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('step', choices=['names', 'group', 'compare', 'finalize'])
    a = ap.parse_args()
    if a.step == 'names':
        names()
    elif a.step == 'group':
        with cf.ThreadPoolExecutor(2) as ex:
            for r, d in zip((1, 2), ex.map(group, (1, 2))):
                print(f'run {r}: {len(d["stations"])} stations')
    elif a.step == 'finalize':
        finalize()
    else:
        compare()
