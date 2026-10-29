"""Match each station to its row(s) in Findlay's list of lights, 1879 and
1887 editions, by country: two independent helpers per (country, edition),
then checks that don't depend on either helper.

  ask:     -> data/stations/findlay/<edition>_<country>_run<r>.json
  compare: the two runs, station by station
  checks:  positions agree between editions (lights don't move; vessels a
           little); consecutive stations in each printed list are near
           neighbours on the chart; the reports' own words for a light's
           character (1879-80 lists) agree with Findlay's

Run: python3 -I tools/match_findlay.py ask | compare | checks
"""
import argparse, concurrent.futures as cf, csv, json, math, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA, ROOT
from station_lists import run_helper

ST = os.path.join(DATA, 'stations')
OUT = os.path.join(ST, 'findlay')
EDITIONS = ['findlay1879', 'findlay1887']
COUNTRIES = ['ENGLAND', 'SCOTLAND', 'IRELAND']


def country_of(st):
    r = set(st['regions'])
    if r & {'england_east', 'england_west', 'isle_of_man'}:
        return 'ENGLAND'
    if r & {'scotland_east', 'scotland_west'}:
        return 'SCOTLAND'
    if 'ireland' in r:
        return 'IRELAND'
    return None


def findlay_rows(ed):
    return list(csv.DictReader(open(os.path.join(DATA, 'lights', f'{ed}.csv'))))


def by_id(ed):
    return {r['row_id']: r for r in findlay_rows(ed)}


def inputs(ed, country):
    """Write the two tables a helper reads: the stations of a country and the
    Findlay rows of that country (row = index in data/lights/<ed>.csv)."""
    os.makedirs(OUT, exist_ok=True)
    stations = [s for s in json.load(open(os.path.join(ST, 'stations.json'))) if country_of(s) == country]
    nm = {int(r['idx']): r for r in csv.DictReader(open(os.path.join(ST, 'names.csv')))}
    sp = os.path.join(OUT, f'stations_{country}.csv')
    with open(sp, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['id', 'name', 'kind', 'printed_names', 'regions', 'years', 'map_numbers', 'neighbours_in_a_list'])
        for s in stations:
            nb = max((nm[i]['neighbours'] for i in s['members']), key=len)
            w.writerow([s['id'], s['name'], s['kind'], ' ; '.join(s['printed']), ' '.join(s['regions']), ' '.join(s['seen']),
                        ' '.join(s['numbers']), nb.split(' || ')[0]])
    fp = os.path.join(OUT, f'{ed}_{country}.csv')
    with open(fp, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['row', 'page', 'country', 'coast', 'name', 'character', 'lat', 'long', 'hemisphere', 'description', 'year'])
        for r in findlay_rows(ed):
            if country in r['country'].upper():
                w.writerow([r['row_id'], r['printed_page'] or r['page_arg'], r['country'], r['coast'], r['name'], r['character'], r['lat'],
                            r['long'], r['hemisphere'], (r['description'] or '')[:160], r['year']])
    return sp, fp, len(stations)


SCHEMA = {'type': 'object', 'required': ['matches', 'notes'], 'properties': {
    'matches': {'type': 'array', 'items': {'type': 'object', 'required': ['id', 'row', 'extra_rows', 'confidence', 'note'],
                'properties': {'id': {'type': 'string'}, 'row': {'type': ['string', 'null']},
                               'extra_rows': {'type': 'array', 'items': {'type': 'string'}},
                               'confidence': {'type': 'string', 'enum': ['high', 'medium', 'low']},
                               'note': {'type': ['string', 'null']}}}},
    'notes': {'type': 'string'}}}

BRIEF = '''Thank you for helping. I'm a Claude agent rebuilding the records of the lighthouse keepers who reported bird migration to a British Association committee, 1879-1887. I need each of their stations matched to its entry in Findlay's "Description and List of the Lighthouses of the World", {year} edition, so the project can take each light's position and character from it.

Two tables (CSV; open each with the Read tool):
- {stations}: the {n} stations on the coasts of {country_words}, as the reports print them: an id, a usual modern name, kind (lighthouse, light-vessel, other), every name and type as printed in the reports' lists, the coasts and years, map numbers ("30@1887"), and the names printed just before and after it in one list ("previous < > next"; the lists run in coast order).
- {findlay}: Findlay's {year} entries for {country_word} (country and coast from the running head; name, character, latitude and longitude as printed; the start of the description; the year established, sometimes with an alteration year). "row" is the id I need ("p55r13"). Some minor lights (pier and harbour lights) have no character or position of their own: their light is described in the description column.

For each station, give the Findlay row that describes it (row), or null if Findlay {year} has no entry for it (a light not yet built, a light-vessel not yet placed, an observer's station that is not a light). Where Findlay gives a station's lights in more than one row (a high and a low light printed separately) put the main one in row and the others in extra_rows; where one Findlay row covers two of the stations (a pair printed together), give that row to both. Watch for: names that differ between the sources (Findlay prints "EILEAN GLAS" where the reports print "Island Glass"; "Happisburgh" for "Hasbro'"), two places with one name (Start Point in Orkney and in Devon), and a lighthouse and the light-vessel off it (Spurn Point and Spurn Lightvessel). Use the positions and the coast order to decide. Say how sure you are (high, medium, low), and in note give the reason for anything not obvious. In notes, list anything I should check.'''


def ask(ed, country, run):
    out = os.path.join(OUT, f'{ed}_{country}_run{run}.json')
    if os.path.exists(out):
        return json.load(open(out))
    sp, fp, n = inputs(ed, country)
    words = {'ENGLAND': ('England, Wales, the Isle of Man and the Channel Islands', 'England (with Wales and the Isle of Man)'),
             'SCOTLAND': ('Scotland, Orkney and Shetland', 'Scotland'), 'IRELAND': ('Ireland', 'Ireland')}[country]
    brief = BRIEF.format(year=ed[-4:], stations=sp, findlay=fp, n=n, country_words=words[0], country_word=words[1])
    d, cost = run_helper(brief, SCHEMA, 'Read')
    d['_meta'] = {'edition': ed, 'country': country, 'run': run, 'cost_usd': cost}
    json.dump(d, open(out, 'w'), indent=1, ensure_ascii=False)
    return d


def runs(ed, country):
    return [json.load(open(os.path.join(OUT, f'{ed}_{country}_run{r}.json'))) for r in (1, 2)]


def compare(verbose=True):
    total = agree = 0
    for ed in EDITIONS:
        rows = by_id(ed)
        for c in COUNTRIES:
            A, B = runs(ed, c)
            ma, mb = {m['id']: m for m in A['matches']}, {m['id']: m for m in B['matches']}
            ids = [s['id'] for s in json.load(open(os.path.join(ST, 'stations.json'))) if country_of(s) == c]
            miss = [i for i in ids if i not in ma or i not in mb]
            dis = [i for i in ids if i in ma and i in mb and (ma[i]['row'], sorted(ma[i]['extra_rows'])) != (mb[i]['row'], sorted(mb[i]['extra_rows']))]
            main_dis = [i for i in dis if ma[i]['row'] != mb[i]['row']]
            total += len(ids)
            agree += len(ids) - len(main_dis) - len(miss)
            print(f'{ed} {c}: {len(ids)} stations; matched by run1 {sum(ma[i]["row"] is not None for i in ids if i in ma)}, '
                  f'run2 {sum(mb[i]["row"] is not None for i in ids if i in mb)}; missing {miss}; main row differs {len(main_dis)}, '
                  f'extra rows differ {len(dis) - len(main_dis)}')
            if verbose:
                for i in dis:
                    show = lambda m: f'{m["row"]}:{rows[m["row"]]["name"]}' if m['row'] is not None else 'None'
                    print(f'    {i}: run1 {show(ma[i])} +{ma[i]["extra_rows"]} ({ma[i]["confidence"]}) | run2 {show(mb[i])} '
                          f'+{mb[i]["extra_rows"]} ({mb[i]["confidence"]})')
    print(f'TOTAL main rows agree {agree}/{total}')


def km(a, b):
    (la1, lo1), (la2, lo2) = a, b
    p = math.pi / 180
    h = math.sin((la2 - la1) * p / 2) ** 2 + math.cos(la1 * p) * math.cos(la2 * p) * math.sin((lo2 - lo1) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


def pos(r):
    try:
        return float(r['lat_deg']), float(r['lon_deg'])
    except (TypeError, ValueError):
        return None


def agreed():
    """{station id: {edition: (row, extra_rows)}} where both runs agree (they all do; checked by compare)."""
    out = {}
    for ed in EDITIONS:
        for c in COUNTRIES:
            A, B = runs(ed, c)
            mb = {m['id']: m for m in B['matches']}
            for m in A['matches']:
                if m['row'] == mb[m['id']]['row']:
                    out.setdefault(m['id'], {})[ed] = (m['row'], m['extra_rows'])
    return out


def checks():
    """Independent of the helpers: (1) a lighthouse's position in 1879 and
    1887 (the light doesn't move; a light-vessel may); (2) consecutive
    stations in each printed list lie near each other; (3) the reports' own
    words for a light's character (1879 and 1880 lists) against Findlay 1879."""
    from characters import parse
    ST_ = {s['id']: s for s in json.load(open(os.path.join(ST, 'stations.json')))}
    M = agreed()
    R = {ed: by_id(ed) for ed in EDITIONS}
    P = lambda ed, sid: pos(R[ed][M[sid][ed][0]]) if M.get(sid, {}).get(ed, (None,))[0] else None
    print('(1) position, Findlay 1879 vs 1887, stations matched in both with positions in both:')
    d_lh, d_lv = [], []
    for sid, s in ST_.items():
        a, b = P('findlay1879', sid), P('findlay1887', sid)
        if a and b:
            d = km(a, b)
            (d_lv if s['kind'] == 'light-vessel' else d_lh).append((d, sid))
    for tag, ds in (('lighthouses', d_lh), ('light-vessels', d_lv)):
        ds.sort()
        med = ds[len(ds) // 2][0] if ds else None
        print(f'  {tag}: {len(ds)}; median {med:.2f} km; over 1 km: ' + ', '.join(f'{sid} {d:.1f}' for d, sid in ds if d > 1))
    print('(2) consecutive stations in each printed list (positions from Findlay 1887, else 1879): steps over 60 km')
    rows = list(csv.DictReader(open(os.path.join(ST, 'list_rows.csv'))))
    nm = {int(r['idx']): r for r in csv.DictReader(open(os.path.join(ST, 'names.csv')))}
    from stations import key
    key2sid = {}
    for sid, s in ST_.items():
        for i in s['members']:
            key2sid[(nm[i]['region'], ' '.join(re.sub(r'[_*†‡{}]', ' ', nm[i]['name']).split()).strip(' .,;:').lower(),
                     ' '.join(re.sub(r'[_*†‡{}]', ' ', nm[i]['type']).split()).strip(' .,;:').lower())] = sid
    lists = {}
    for r in rows:
        lists.setdefault((r['year'], r['list']), []).append(key2sid.get(key(r)))
    steps = []
    for (y, k), sids in lists.items():
        here = [(sid, P('findlay1887', sid) or P('findlay1879', sid)) for sid in sids if sid]
        here = [(s, p) for s, p in here if p]
        for (s1, p1), (s2, p2) in zip(here, here[1:]):
            steps.append((km(p1, p2), y, k, s1, s2))
    big = sorted({(round(d), s1, s2) for d, y, k, s1, s2 in steps if d > 60}, reverse=True)
    print(f'  {len(steps)} steps; median {sorted(steps)[len(steps) // 2][0]:.0f} km; distinct pairs over 60 km: {len(big)}')
    for d, s1, s2 in big:
        print(f'    {d} km  {s1} -> {s2}')
    print('(3) characters: the reports\' lists (1879, 1880) against Findlay 1879, by kind and period')
    agree = n = 0
    for r in rows:
        if r['year'] not in ('1879', '1880') or not r['character']:
            continue
        sid = key2sid.get(key(r))
        if not sid or not M.get(sid, {}).get('findlay1879', (None,))[0]:
            continue
        f = R['findlay1879'][M[sid]['findlay1879'][0]]
        rep = parse(r['character'])[0]
        fin = parse(f['character'], f['description'])[0]
        if not rep or not fin:
            continue
        rk = {x['kind'] for x in rep} - {'unknown'}
        fk = {x['kind'] for x in fin} - {'unknown'}
        rp = {x['period_s'] for x in rep} - {None}
        fp = {x['period_s'] for x in fin} - {None}
        rev_like = lambda ks: {('revolving' if k in ('revolving', 'flashing') else k) for k in ks}
        ok_kind = not rk or not fk or bool(rev_like(rk) & rev_like(fk))
        ok_per = not rp or not fp or bool(rp & fp)
        n += 1
        agree += ok_kind and ok_per
        if not (ok_kind and ok_per):
            print(f'    {r["year"]} {sid}: report "{r["character"][:60]}" | Findlay "{f["character"][:50]}" ({(f["description"] or "")[:40]})')
    print(f'  {agree}/{n} agree on kind and period')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('step', choices=['ask', 'compare', 'checks'])
    ap.add_argument('--workers', type=int, default=12)
    a = ap.parse_args()
    if a.step == 'ask':
        jobs = [(ed, c, r) for ed in EDITIONS for c in COUNTRIES for r in (1, 2)]
        with cf.ThreadPoolExecutor(a.workers) as ex:
            futs = {ex.submit(ask, *j): j for j in jobs}
            for f in cf.as_completed(futs):
                try:
                    print(futs[f], len(f.result()['matches']), 'matches', flush=True)
                except Exception as e:
                    print(futs[f], 'FAILED', e, flush=True)
    elif a.step == 'checks':
        checks()
    else:
        compare()

