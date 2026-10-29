"""Data for the public explorer (docs/explorer/): every night of the reports, its entries and tallies, the keepers'
winds beside the reanalysis, the moon; and every station with its light, keepers and record, year by year.

Writes docs/data/:
  coast.json            the coast (Natural Earth 10 m land, clipped and thinned as sketch 1)
  calendar.json         every night: moon's age and light at midnight, stations reporting, stations with a strike
                        (film/engine/assets/calendar.json, made by tools/film_calendar.py)
  stations.json         every station: name, kind, position; per year its printed light character (and the cycle
                        by sketch 1's stated rule), keepers, records, nights reported and strike nights
  nights/<year>.json    per night (the date its evening falls on): entries and tallies (sketch_night.entries), the
                        keepers' printed winds with the 20CRv3 wind at the same place and time (data/weather/winds.csv),
                        and the moon every two hours at the middle of the coasts

Run in the venv: .venv/bin/python -I tools/explorer_data.py
"""
import collections, csv, datetime as dt, json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA, ROOT
from great_nights import night_of
import sketch_night
from sketch_night import RULE, coast, entries, resolve
from sky import moon

OUT = os.path.join(ROOT, 'docs', 'data')


def dump(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(obj, open(path, 'w'), separators=(',', ':'), ensure_ascii=False)
    return os.path.getsize(path)


def stations():
    pos = {r['id']: r for r in csv.DictReader(open(os.path.join(DATA, 'stations', 'positions.csv'))) if r['lat']}
    names = {s['id']: s.get('name') or s['id'] for s in json.load(open(os.path.join(DATA, 'stations', 'stations.json')))}
    patterns = json.load(open(os.path.join(DATA, 'stations', 'patterns.json')))
    years = collections.defaultdict(lambda: collections.defaultdict(dict))
    for r in csv.DictReader(open(os.path.join(DATA, 'stations', 'characters.csv'))):
        y = years[r['id']][int(r['year'])]
        if 'character' not in y or r['source'] == f'findlay{r["year"]}':      # the year's own Findlay where there is one
            pat = patterns.get(r['pattern_key'])
            y['character'] = r['character']
            y['light'] = resolve(pat['lights'][0]) if pat and pat['lights'] else None
    keepers = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in csv.DictReader(open(os.path.join(DATA, 'keepers.csv'))):
        keepers[r['station_id']][int(r['year'])].append(r['keeper_printed'].strip())
    scot = {'Lochindaul: Islay': 'loch-indaal', 'Dhuheartach': 'dubh-artach', 'North Ronaldshay': 'north-ronaldsay', 'Lamlash': 'holy-isle', 'Rona': 'rona'}
    by_name = {v.lower(): k for k, v in names.items()}
    unmatched = []
    for r in csv.DictReader(open(os.path.join(DATA, 'keepers_1887_scotland.csv'))):
        sid = scot.get(r['station']) or by_name.get(r['station'].lower())
        if not sid:
            unmatched.append(r['station'])
            continue
        keepers[sid][1887].append(r['keeper_printed'].strip() or 'unsigned')
    rec = collections.Counter()
    for r in csv.DictReader(open(os.path.join(DATA, 'records.csv'))):
        ids = r['station_ids'].split()
        if r['source_kind'] == 'primary' and len(ids) == 1:
            rec[(ids[0], int(r['report_year']))] += 1
    nights = collections.Counter(); strikes = collections.Counter()
    for n in csv.DictReader(open(os.path.join(DATA, 'weather', 'nights.csv'))):
        k = (n['station'], int(n['night'][:4]))
        nights[k] += 1
        strikes[k] += n['strike_wide'] == '1'
    out = []
    ids = set(pos) & ({s for s, _ in rec} | set(keepers) | {s for s, _ in nights})
    for sid in sorted(ids, key=lambda s: names.get(s, s)):
        ys = {}
        for y in range(1879, 1888):
            row = dict(years[sid].get(y, {}))
            if keepers[sid].get(y):
                row['keepers'] = keepers[sid][y]
            if rec[(sid, y)]:
                row['records'] = rec[(sid, y)]
            if nights[(sid, y)]:
                row['nights'] = nights[(sid, y)]; row['strikes'] = strikes[(sid, y)]
            if row:
                ys[y] = row
        out.append({'id': sid, 'name': names.get(sid, sid), 'kind': pos[sid]['kind'], 'lat': round(float(pos[sid]['lat']), 4),
                    'lon': round(float(pos[sid]['lon']), 4), 'years': ys})
    return out, unmatched


def main():
    if os.path.isdir(os.path.join(OUT, 'nights')):
        shutil.rmtree(os.path.join(OUT, 'nights'))
    sketch_night.BOX = (-24.0, 43.0, 24.0, 67.0)    # wider than sketch 1's: the chart frames each year's lights, Stevns (12.5 E) included,
    n = dump(coast(), os.path.join(OUT, 'coast.json'))   # and the clipped edges must stay off it
    print(f'coast.json {n // 1024} kB')
    cal = json.load(open(os.path.join(ROOT, 'film', 'engine', 'assets', 'calendar.json')))
    print(f'calendar.json {dump(cal, os.path.join(OUT, "calendar.json")) // 1024} kB')
    st, unmatched = stations()
    print(f'stations.json {dump({"rule": RULE, "stations": st}, os.path.join(OUT, "stations.json")) // 1024} kB, {len(st)} stations; '
          f'1887 Scottish names not placed: {unmatched or "none"}')
    # records grouped by night once, then each night's entries as sketch 1 makes them
    by_night = collections.defaultdict(list)
    for r in csv.DictReader(open(os.path.join(DATA, 'records.csv'))):
        if r['source_kind'] == 'primary' and len(r['date']) == 10 and not r['date_end']:
            by_night[night_of(r).isoformat()].append(r)
    winds = collections.defaultdict(list)
    for w in csv.DictReader(open(os.path.join(DATA, 'weather', 'winds.csv'))):
        if w['ut']:
            ut = dt.datetime.fromisoformat(w['ut'])
            night = (ut - dt.timedelta(hours=12)).date().isoformat()             # noon to noon, as the chart runs
            at = round((ut - dt.datetime.fromisoformat(night + 'T12:00')).total_seconds() / 60)
        else:                                                                   # no time printed: the day's mean wind
            night, at = w['date'], None
        f = lambda k: None if w[k] in ('', 'nan') else round(float(w[k]), 1)
        winds[night].append({'station': w['station'], 'at': at if w['time_how'] == 'at the printed time' else None,
                             'printed': w['wind_raw'], 'keeper': f('keeper_deg'), 'force': w['force_bft'] or None,
                             'reanalysis': f('r_deg'), 'speed': f('r_speed')})
    per_year = collections.defaultdict(dict)
    counted = 0
    for c in cal['nights']:
        key = c['night']
        rows = by_night.get(key, [])
        if not rows and not winds.get(key):
            continue
        es, tallies = entries(dt.date.fromisoformat(key), rows)
        if not es and not winds.get(key):
            continue
        noon = dt.datetime.fromisoformat(key + 'T12:00')
        mo = [moon(54.0, -4.0, noon + dt.timedelta(hours=h)) for h in range(0, 25, 2)]
        per_year[key[:4]][key] = {'entries': es, 'tallies': tallies, 'winds': winds.get(key, []),
                                  'moon': [[round(a, 1), round(l, 3)] for a, l in mo]}
        counted += 1
    total = 0
    for y, nights in sorted(per_year.items()):
        total += dump(nights, os.path.join(OUT, 'nights', f'{y}.json'))
    print(f'nights/: {counted} nights in {len(per_year)} files, {total // 1024} kB')


if __name__ == '__main__':
    main()
