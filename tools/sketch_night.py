"""Data for a night-chart sketch (stage 6): one night, noon to noon, as JSON.

- coast: Natural Earth 10 m land (world-atlas 2.0.2, sources/coast/), clipped to
  the chart and thinned to about 1 km;
- lights: every station on the 1887 lists, placed (positions.csv), with its
  1887 character (characters.csv -> patterns.json); durations the sources
  don't state are reconstructed by a stated rule (RULE below);
- lamps lit from sunset to sunrise at each station (skyfield);
- entries: the night's primary records in the keepers' printed words, at the
  printed time put on Greenwich time (Irish clocks are Dublin time); a quote
  contained in another of the station's is dropped (the species layout
  repeats one sentence per kind);
- tallies: birds recorded killed (numbers only; a shared count once; the
  printed total where larger), and whether an uncounted "many" was killed;
- wind: 20CRv3 10 m wind, 3-hourly, on the reanalysis's 1-degree grid;
- moon: altitude and lit fraction over the night at the chart's middle.

Run in the venv: .venv/bin/python -I tools/sketch_night.py 1887-10-21 sketches/night-1887-10-21.json
"""
import collections, csv, datetime as dt, json, math, os, re, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA, ROOT
from sky import clock_offset_min, moon, night as twilight
from winds import EPOCH, Field
from great_nights import night_of

BOX = (-14.0, 47.5, 12.0, 63.5)            # lon0, lat0, lon1, lat1: a little beyond the chart, so clipped edges fall outside it
RULE = ('Durations the sources state are used as stated. Where they are silent: a revolving beam lasts 0.3 of the cycle '
        '(shared among its beams) and swells and fades; a flash lasts 2 s (1 s within a group); the dark between flashes '
        'of a group 2 s; an eclipse 3 s; the light between eclipses of a group 2 s; the long step fills the cycle, and where '
        'the long step is stated, the unstated gaps share what is left.')


def coast():
    topo = json.load(open(os.path.join(ROOT, 'sources', 'coast', 'land-10m.json')))
    sx, sy = topo['transform']['scale']
    tx, ty = topo['transform']['translate']
    arcs = []
    for a in topo['arcs']:
        x = y = 0
        pts = []
        for dx, dy in a:
            x += dx
            y += dy
            pts.append((x * sx + tx, y * sy + ty))
        arcs.append(pts)

    def arc(i):
        return arcs[i] if i >= 0 else arcs[~i][::-1]

    def ring(idx):
        out = []
        for i in idx:
            p = arc(i)
            out.extend(p[1:] if out else p)
        return out

    def clip(poly):
        lon0, lat0, lon1, lat1 = BOX
        for inside, cut in ((lambda p: p[0] >= lon0, lambda a, b: (lon0, a[1] + (b[1] - a[1]) * (lon0 - a[0]) / (b[0] - a[0]))),
                            (lambda p: p[0] <= lon1, lambda a, b: (lon1, a[1] + (b[1] - a[1]) * (lon1 - a[0]) / (b[0] - a[0]))),
                            (lambda p: p[1] >= lat0, lambda a, b: (a[0] + (b[0] - a[0]) * (lat0 - a[1]) / (b[1] - a[1]), lat0)),
                            (lambda p: p[1] <= lat1, lambda a, b: (a[0] + (b[0] - a[0]) * (lat1 - a[1]) / (b[1] - a[1]), lat1))):
            out = []
            for k in range(len(poly)):
                a, b = poly[k - 1], poly[k]
                if inside(b):
                    if not inside(a):
                        out.append(cut(a, b))
                    out.append(b)
                elif inside(a):
                    out.append(cut(a, b))
            poly = out
            if not poly:
                break
        return poly

    def thin(poly, tol=0.01):
        out = [poly[0]]
        for p in poly[1:]:
            if abs(p[0] - out[-1][0]) * math.cos(math.radians(p[1])) + abs(p[1] - out[-1][1]) > tol:
                out.append(p)
        return out

    rings = []
    for g in topo['objects']['land']['geometries']:
        polys = g['arcs'] if g['type'] == 'MultiPolygon' else [g['arcs']]
        for poly in polys:
            for k, idx in enumerate(poly):
                r = clip(ring(idx))
                if len(r) >= 3:
                    r = thin(r)
                    if len(r) >= 3:
                        rings.append([[round(x, 3), round(y, 3)] for x, y in r])
    return rings


def resolve(L):
    """One light's cycle as steps [on, colour, seconds, stated], by RULE."""
    kind, C, steps = L['kind'], L['cycle_s'], L['steps']
    if kind == 'fixed' or not C:
        return {'kind': 'fixed', 'cycle': None, 'steps': [[1, steps[0]['colour'] or 'white', 1, True]]}
    group = L.get('group') or 0
    n_light = sum(1 for s in steps if s['light'])
    sec = [s['seconds'] for s in steps]
    filler = []
    occ = kind in ('occulting', 'group_occulting')
    first_light = next(i for i, s in enumerate(steps) if s['light'])
    last_dark = max((i for i, s in enumerate(steps) if not s['light']), default=None)
    for i, s in enumerate(steps):
        if sec[i] is not None:
            continue
        if occ:
            if not s['light']:
                sec[i] = 3.0
            elif group and i != first_light:
                sec[i] = 2.0
            else:
                filler.append(i)
        else:
            if s['light']:
                sec[i] = 0.3 * C / n_light if kind == 'revolving' else (1.0 if group else 2.0)
            elif group and i != last_dark:
                sec[i] = 2.0
            else:
                filler.append(i)
    unstated = [i for i, s in enumerate(steps) if s['seconds'] is None]
    if not filler:                                  # the long step is stated: the gaps the sources leave out take up the rest
        filler = [i for i in unstated if steps[i]['light'] == occ]
    stated_sum = sum(s['seconds'] for s in steps if s['seconds'] is not None)
    nominal = [i for i in unstated if i not in filler]
    rest = C - stated_sum - sum(sec[i] for i in nominal)
    if filler and rest >= 0.5 * len(filler):
        w = [sec[i] or 1.0 for i in filler]
        for i, wi in zip(filler, w):
            sec[i] = rest * wi / sum(w) if all(sec[j] for j in filler) else rest / len(filler)
    else:                                           # too little room: shrink the unstated steps to fit the cycle
        room = C - stated_sum
        for i in filler:
            sec[i] = 0.5
        k = max(room - 0.5 * len(filler), 0.1 * len(nominal)) / max(sum(sec[i] for i in nominal), 1e-9) if nominal else 1
        for i in nominal:
            sec[i] *= k
    return {'kind': kind, 'cycle': C, 'steps': [[int(s['light']), s['colour'] or 'white', round(v, 2), bool(s['stated'])]
                                                for s, v in zip(steps, sec)]}


def lights(night):
    pos = {r['id']: r for r in csv.DictReader(open(os.path.join(DATA, 'stations', 'positions.csv'))) if r['lat']}
    names = {s['id']: s.get('name') or s['id'] for s in json.load(open(os.path.join(DATA, 'stations', 'stations.json')))}
    patterns = json.load(open(os.path.join(DATA, 'stations', 'patterns.json')))
    year = night.year
    listed = {r['station_id'] for r in csv.DictReader(open(os.path.join(DATA, 'keepers.csv'))) if int(r['year']) == year}
    for r in csv.DictReader(open(os.path.join(DATA, 'records.csv'))):      # and every station reporting that year (keepers.csv
        ids = r['station_ids'].split()                                       # has no Scottish lists for 1887)
        if r['source_kind'] == 'primary' and int(r['report_year']) == year and len(ids) == 1:
            listed.add(ids[0])
    chars = collections.defaultdict(list)
    for r in csv.DictReader(open(os.path.join(DATA, 'stations', 'characters.csv'))):
        if int(r['year']) == year:
            chars[r['id']].append(r)
    out = []
    for sid in sorted(listed):
        if sid not in pos:
            continue
        rows = chars.get(sid, [])
        row = next((r for r in rows if r['source'] == f'findlay{year}'), rows[-1] if rows else None)
        pat = patterns.get(row['pattern_key']) if row else None
        L = resolve(pat['lights'][0]) if pat and pat['lights'] else None
        lat, lon = float(pos[sid]['lat']), float(pos[sid]['lon'])
        tw = twilight(lat, lon, night)
        out.append({'id': sid, 'name': names.get(sid, sid), 'kind': pos[sid]['kind'], 'lat': lat, 'lon': lon,
                    'character': row['character'] if row else None, 'light': L,
                    'sunset': tw['sunset'] and tw['sunset'].isoformat(timespec='minutes'),
                    'sunrise': tw['sunrise'] and tw['sunrise'].isoformat(timespec='minutes')})
    return out


def entries(night, rows=None):
    """The night's entries and tallies; rows: the records to look in (default: all of records.csv)."""
    pos = {r['id']: r for r in csv.DictReader(open(os.path.join(DATA, 'stations', 'positions.csv'))) if r['lat']}
    noon = dt.datetime(night.year, night.month, night.day, 12)
    by = collections.defaultdict(list)
    killed = collections.defaultdict(lambda: {'parts': 0, 'total': 0, 'uncounted': False, 'when': None})
    shared = set()
    for r in (rows if rows is not None else csv.DictReader(open(os.path.join(DATA, 'records.csv')))):
        ids = r['station_ids'].split()
        if r['source_kind'] != 'primary' or len(ids) != 1 or ids[0] not in pos or len(r['date']) != 10 or r['date_end']:
            continue
        if night_of(r) != night or r['behaviour'] == 'same_as':           # a cross-reference ("see under yesterday") is no event
            continue
        sid = ids[0]
        when = None
        if r['time_kind'] == 'clock' and r['t_start_min'] != '':
            m = float(r['t_start_min'])
            day = night + dt.timedelta(days=1) if m < 720 else night
            t = dt.datetime(day.year, day.month, day.day) + dt.timedelta(minutes=m + clock_offset_min(r['coast'], float(pos[sid]['lon'])))
            when = round((t - noon).total_seconds() / 60)                       # minutes after noon GMT
        q = re.sub(r'\s+', ' ', r['quote']).strip()
        by[(sid, when)].append({'quote': q, 'time': r['time_raw'] and re.sub(r'\s+', ' ', r['time_raw']), 'behaviour': r['behaviour'],
                                'page': r['page'], 'scan': r['scan'], 'year': r['report_year']})
        if r['behaviour'] == 'dead':
            k = killed[sid]
            if k['when'] is None or (when is not None and when < k['when']):
                k['when'] = when
            if r['count_category'] in ('number', 'range'):
                if r['count_shared'] == 'True':
                    key = (sid, q, r['count_raw'])
                    if key in shared:
                        continue
                    shared.add(key)
                n = int(float(r['count_lo']))
                if r['total'] == 'True':
                    k['total'] = max(k['total'], n)
                else:
                    k['parts'] += n
            else:
                k['uncounted'] = True
    out = []
    for (sid, when), es in by.items():
        qs = sorted({e['quote'] for e in es}, key=lambda q: (-len(q), q))       # ties by text, not by set order
        words = lambda q: set(re.findall(r"[a-z0-9]+", q.lower())) - {'21st', '22d', '22nd', '20th'}
        keep = [q for i, q in enumerate(qs) if not any(words(q) <= words(p) for p in qs[:i])]   # one sentence per kind, once
        e0 = es[0]
        out.append({'station': sid, 'at': when, 'time': e0['time'], 'quotes': keep,
                    'behaviours': sorted({e['behaviour'] for e in es}), 'page': e0['page'], 'scan': e0['scan'], 'report': e0['year']})
    out.sort(key=lambda e: (e['at'] is None, e['at'] or 0))
    tallies = [{'station': s, 'killed': max(k['parts'], k['total']), 'uncounted': k['uncounted'], 'at': k['when']} for s, k in killed.items()]
    return out, tallies


def wind(night):
    U, V = Field('uwnd.10m', 'uwnd'), Field('vwnd.10m', 'vwnd')
    t0 = (dt.datetime(night.year, night.month, night.day, 12) - EPOCH).total_seconds() / 3600
    frames = []
    for k in range(9):
        h = t0 + 3 * k
        i = int(np.argmin(np.abs(U.t - h)))
        frames.append({'at': 180 * k, 'u': np.round(U.x[i], 1).tolist(), 'v': np.round(V.x[i], 1).tolist()})
    return {'lat': U.lat.tolist(), 'lon': U.lon.tolist(), 'frames': frames}


def moon_track(night):
    out = []
    for k in range(0, 25):
        t = dt.datetime(night.year, night.month, night.day, 12) + dt.timedelta(hours=k)
        alt, lit = moon(54.0, -4.0, t)
        out.append({'at': 60 * k, 'alt': round(alt, 1), 'lit': round(lit, 3)})
    return out


def main(night_s, out):
    night = dt.date.fromisoformat(night_s)
    es, tallies = entries(night)
    data = {'night': night_s, 'clock': 'Greenwich mean time; minutes after noon', 'rule': RULE,
            'sources': {'coast': 'Natural Earth 10 m land via world-atlas 2.0.2 (public domain)',
                        'wind': 'NOAA/CIRES/DOE 20th Century Reanalysis v3, 10 m wind, 3-hourly',
                        'characters': 'Findlay 1887 and Edwards 1884, data/stations/characters.csv',
                        'entries': 'Reports on the Migration of Birds, British Association, 1879-1887'},
            'coast': coast(), 'lights': lights(night), 'entries': es, 'tallies': tallies, 'wind': wind(night), 'moon': moon_track(night)}
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    json.dump(data, open(out, 'w'), separators=(',', ':'), ensure_ascii=False)
    print(f'{out}: {os.path.getsize(out) // 1024} kB; {len(data["coast"])} coast rings, {sum(len(r) for r in data["coast"])} points; '
          f'{len(data["lights"])} lights ({sum(1 for l in data["lights"] if l["light"])} with a character); {len(es)} entries '
          f'({sum(1 for e in es if e["at"] is not None)} timed); {len(tallies)} stations with dead, {sum(t["killed"] for t in tallies)} counted')


if __name__ == '__main__':
    main(*sys.argv[1:3])
