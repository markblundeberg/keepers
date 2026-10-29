"""Positions for the stations. A standing lighthouse takes its modern
position from Wikidata (CC0): Findlay's printed positions move between
editions by up to 8 km (Fladda), while the tower did not. A light-vessel
takes Findlay's position for each edition (they were moved). Two independent
helpers pick each lighthouse's Wikidata item from the candidates near its
Findlay positions (or found by name); a check measures the pick against
both editions.

  ask:     -> data/stations/wikidata_run<r>.json
  compare: the two runs, and distances to Findlay
  build:   -> data/stations/positions.csv

Run: python3 -I tools/positions.py ask | compare | build
"""
import argparse, concurrent.futures as cf, csv, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA, ROOT
from station_lists import run_helper
from match_findlay import agreed, by_id, km, pos

ST = os.path.join(DATA, 'stations')
WD = os.path.join(ROOT, 'sources', 'lights', 'wikidata_lighthouses_2026-10-27.csv')
RADIUS_KM = 12


def wikidata():
    out = []
    for w in csv.DictReader(open(WD)):
        lon, lat = (float(x) for x in w['coord'].replace('Point(', '').replace(')', '').split())
        out.append({'qid': w['item'].rsplit('/', 1)[1], 'label': w['itemLabel'], 'country': w['countryLabel'], 'lat': lat,
                    'lon': lon, 'inception': (w['inception'] or '')[:4]})
    return out


def findlay_positions(sid, M, R):
    out = {}
    for ed in ('findlay1879', 'findlay1887'):
        row = M.get(sid, {}).get(ed, (None,))[0]
        if row and pos(R[ed][row]):
            out[ed] = pos(R[ed][row])
    return out


def candidates():
    """For each station that isn't a light-vessel: Wikidata lighthouses within
    RADIUS_KM of either Findlay position, plus any whose label shares a word
    of four letters or more with one of the station's names."""
    S = json.load(open(os.path.join(ST, 'stations.json')))
    M, R, W = agreed(), {ed: by_id(ed) for ed in ('findlay1879', 'findlay1887')}, wikidata()
    stop = {'light', 'lighthouse', 'lighthouses', 'point', 'head', 'island', 'isle', 'rock', 'harbour', 'pier', 'north', 'south',
            'east', 'west', 'high', 'lower', 'upper', 'sound', 'bank', 'sand', 'vessel', 'ship', 'bay', 'ness'}
    out = []
    for s in S:
        if s['kind'] == 'light-vessel':
            continue
        fp = findlay_positions(s['id'], M, R)
        words = {w for n in s['printed'] + [s['name']] for w in re.findall(r"[a-z']{4,}", n.lower())} - stop
        cand = []
        for w in W:
            d = min((km(p, (w['lat'], w['lon'])) for p in fp.values()), default=None)
            by_name = bool(words & set(re.findall(r"[a-z']{4,}", w['label'].lower())))
            if (d is not None and d <= RADIUS_KM) or (by_name and (d is None or d <= 60)):
                cand.append({**w, 'km_from_findlay': round(d, 2) if d is not None else None})
        cand.sort(key=lambda c: (c['km_from_findlay'] is None, c['km_from_findlay'] or 0))
        out.append({'id': s['id'], 'name': s['name'], 'kind': s['kind'], 'printed': s['printed'], 'seen': s['seen'],
                    'findlay': {ed: {'row': M[s['id']][ed][0], 'name': R[ed][M[s['id']][ed][0]]['name'], 'pos': fp.get(ed)}
                                for ed in ('findlay1879', 'findlay1887') if M.get(s['id'], {}).get(ed, (None,))[0]},
                    'candidates': cand[:12]})
    return out


SCHEMA = {'type': 'object', 'required': ['picks', 'notes'], 'properties': {
    'picks': {'type': 'array', 'items': {'type': 'object', 'required': ['id', 'qid', 'confidence', 'note'], 'properties': {
        'id': {'type': 'string'}, 'qid': {'type': ['string', 'null']},
        'confidence': {'type': 'string', 'enum': ['high', 'medium', 'low']}, 'note': {'type': ['string', 'null']}}}},
    'notes': {'type': 'string'}}}

BRIEF = '''Thank you for helping. I'm a Claude agent rebuilding the records of the lighthouse keepers who reported bird migration to a British Association committee, 1879-1887. I need a modern position for each of their lighthouses, from Wikidata, so the project can place each station on a chart.

The file {path} (JSON; open it with the Read tool) lists {n} stations that are not light-vessels. For each: an id, a usual modern name, its names as printed in the reports, the years it appears, its entries in Findlay's list of lights (1879 and 1887 editions: name and position as printed then), and up to 12 Wikidata lighthouse items near those positions or sharing a word of its name (label, QID, position, year of inception where Wikidata has one, and distance from Findlay's position in km).

For each station, pick the Wikidata item that is the light the reports mean, as it stood in 1879-1887, or null if none of the candidates is it. Care points: a station may have had two towers (a high and a low light) where the reports name only one row; pick the main light, and say so. A light rebuilt on a new site after 1887 is not the same light: prefer an item for the old tower if there is one (inception years help). Harbour and breakwater lights near a major light are different lights. Stations that are observers' places rather than lights (Fair Isle before 1892, Iceland, Faroe, an inland village) get null. Say how sure you are, and give a reason in note for anything not obvious. In notes, list anything I should check.'''


def ask(run):
    out = os.path.join(ST, f'wikidata_run{run}.json')
    if os.path.exists(out):
        return json.load(open(out))
    path = os.path.join(ST, 'wikidata_candidates.json')
    cands = candidates()
    json.dump(cands, open(path, 'w'), indent=1, ensure_ascii=False)
    d, cost = run_helper(BRIEF.format(path=path, n=len(cands)), SCHEMA, 'Read')
    d['_meta'] = {'run': run, 'cost_usd': cost}
    json.dump(d, open(out, 'w'), indent=1, ensure_ascii=False)
    return d


def compare():
    C = {c['id']: c for c in json.load(open(os.path.join(ST, 'wikidata_candidates.json')))}
    W = {w['qid']: w for w in wikidata()}
    A, B = ({p['id']: p for p in json.load(open(os.path.join(ST, f'wikidata_run{r}.json')))['picks']} for r in (1, 2))
    dis = [i for i in C if A.get(i, {}).get('qid') != B.get(i, {}).get('qid')]
    print(f'{len(C)} stations; picked by run1 {sum(bool(A.get(i, {}).get("qid")) for i in C)}, run2 '
          f'{sum(bool(B.get(i, {}).get("qid")) for i in C)}; runs differ on {len(dis)}')
    for i in dis:
        lab = lambda q: f'{q}:{W[q]["label"]}' if q else 'None'
        print(f'  {i}: run1 {lab(A[i]["qid"])} ({A[i]["confidence"]}) | run2 {lab(B[i]["qid"])} ({B[i]["confidence"]})')
    print('agreed picks more than 1 km from a Findlay position (km to 1879, 1887):')
    for i, c in C.items():
        q = A.get(i, {}).get('qid')
        if q and q == B.get(i, {}).get('qid'):
            w = W[q]
            ds = {ed[-4:]: round(km(f['pos'], (w['lat'], w['lon'])), 2) for ed, f in c['findlay'].items() if f['pos']}
            if ds and min(ds.values()) > 1:
                print(f'  {i}: {w["label"]} {ds}')


def build():
    """data/stations/positions.csv: one row per station and period."""
    S = json.load(open(os.path.join(ST, 'stations.json')))
    M, R = agreed(), {ed: by_id(ed) for ed in ('findlay1879', 'findlay1887')}
    W = {w['qid']: w for w in wikidata()}
    man = json.load(open(os.path.join(ST, 'positions_manual.json')))
    picks = [{p['id']: p for p in json.load(open(os.path.join(ST, f'wikidata_run{r}.json')))['picks']} for r in (1, 2)]
    rows = []
    for s in S:
        sid, fp = s['id'], findlay_positions(s['id'], M, R)
        base = {'id': sid, 'kind': s['kind'], 'approximate': False, 'note': ''}
        m = man.get(sid, {})
        q = picks[0].get(sid, {}).get('qid')
        agreed_q = q if q and q == picks[1].get(sid, {}).get('qid') else None
        if 'periods' in m:
            for a, b, qid, note in m['periods']:
                w = W[qid]
                rows.append({**base, 'from': a, 'to': b, 'lat': w['lat'], 'lon': w['lon'], 'source': f'wikidata:{qid}', 'note': note})
            continue
        if s['kind'] == 'light-vessel' and m.get('source'):
            ed = m['source']
            p = fp[ed]
            rows.append({**base, 'from': 1879, 'to': 1887, 'lat': p[0], 'lon': p[1], 'source': f'{ed}:{M[sid][ed][0]}', 'note': m['note']})
            continue
        if s['kind'] == 'light-vessel':
            for ed, a, b in (('findlay1879', 1879, 1882), ('findlay1887', 1883, 1887)):
                p = fp.get(ed) or fp.get('findlay1887') or fp.get('findlay1879')
                if p:
                    src = ed if fp.get(ed) else ('findlay1887' if fp.get('findlay1887') else 'findlay1879')
                    moved = round(km(fp['findlay1879'], fp['findlay1887']), 2) if len(fp) == 2 else None
                    rows.append({**base, 'from': a, 'to': b, 'lat': p[0], 'lon': p[1], 'source': f'{src}:{M[sid][src][0]}',
                                 'note': f'light-vessel; Findlay 1879 and 1887 positions {moved} km apart' if moved is not None else
                                         'light-vessel; one Findlay position'})
            if not fp:
                rows.append({**base, 'from': 1879, 'to': 1887, 'lat': None, 'lon': None, 'source': '', 'note': 'no position in Findlay 1879 or 1887'})
            continue
        if m.get('wikidata_extra'):
            X = json.load(open(os.path.join(ROOT, 'sources', 'lights', 'wikidata_extra_2026-10-28.json')))
            hit = next(h for hs in X.values() for h in hs if h['qid'] == m['wikidata_extra'])
            rows.append({**base, 'from': 1879, 'to': 1887, 'lat': hit['lat'], 'lon': hit['lon'], 'source': f'wikidata:{hit["qid"]}',
                         'approximate': m['approximate'], 'note': m['note']})
            continue
        if m.get('source') and s['kind'] != 'light-vessel':
            ed = m['source']
            p = fp[ed]
            rows.append({**base, 'from': 1879, 'to': 1887, 'lat': p[0], 'lon': p[1], 'source': f'{ed}:{M[sid][ed][0]}',
                         'approximate': m.get('approximate', False), 'note': m['note']})
        elif agreed_q:
            w = W[agreed_q]
            rows.append({**base, 'from': 1879, 'to': 1887, 'lat': w['lat'], 'lon': w['lon'], 'source': f'wikidata:{agreed_q}',
                         'note': w['label']})
        elif fp:
            ed = 'findlay1887' if 'findlay1887' in fp else 'findlay1879'
            rows.append({**base, 'from': 1879, 'to': 1887, 'lat': fp[ed][0], 'lon': fp[ed][1], 'source': f'{ed}:{M[sid][ed][0]}',
                         'note': 'no Wikidata item agreed by both helpers'})
        else:
            rows.append({**base, 'from': 1879, 'to': 1887, 'lat': None, 'lon': None, 'source': '',
                         'note': 'no position yet (an observer\'s place, an outlying station, or a light Findlay gives without one)'})
    cols = ['id', 'kind', 'from', 'to', 'lat', 'lon', 'source', 'approximate', 'note']
    with open(os.path.join(ST, 'positions.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, cols)
        w.writeheader()
        w.writerows(rows)
    from collections import Counter
    print(f'{len(rows)} rows for {len(S)} stations; by source: {dict(Counter(r["source"].split(":")[0] for r in rows))}')
    print('no position:', [r['id'] for r in rows if r['lat'] is None])


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('step', choices=['ask', 'compare', 'build'])
    a = ap.parse_args()
    if a.step == 'ask':
        cands = candidates()
        json.dump(cands, open(os.path.join(ST, 'wikidata_candidates.json'), 'w'), indent=1, ensure_ascii=False)
        print(f'{len(cands)} stations; with no candidate: {[c["id"] for c in cands if not c["candidates"]]}')
        with cf.ThreadPoolExecutor(2) as ex:
            for r, d in zip((1, 2), ex.map(ask, (1, 2))):
                print(f'run {r}: {len(d["picks"])} picks')
    elif a.step == 'build':
        build()
    else:
        compare()

