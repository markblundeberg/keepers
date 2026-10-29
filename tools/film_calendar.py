"""Data for movement III of the film: every night of the reports (1879-1887) on a lunar calendar.

Per night (the date its evening falls on): the moon's age in days since the last new moon and its light at local
midnight at the middle of the coasts (lit fraction while above the horizon, else 0; skyfield, DE440s); the stations
with a strike that night (strike_wide, data/weather/nights.csv, as K1 and G1); and the stations reporting at all.
Rows are lunations (new moon to new moon).

Also prints the raw pattern the picture will show, by moon age, so the picture is checked against the numbers
before anyone looks at it: share of reporting station-nights with a strike, in bins of the moon's age.

Run in the venv: .venv/bin/python -I tools/film_calendar.py film/engine/assets/calendar.json
"""
import collections, csv, datetime as dt, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA
from sky import EPH, TS, UTC, moon
from skyfield import almanac

LAT, LON = 53.5, -5.0          # the middle of the coasts the strikes come from (Irish Sea); midnight UT is within
                                # 40 minutes of local midnight everywhere on the lists


def main(out):
    nights = list(csv.DictReader(open(os.path.join(DATA, 'weather', 'nights.csv'))))
    strike, report = collections.defaultdict(list), collections.Counter()
    for n in nights:
        report[n['night']] += 1
        if n['strike_wide'] == '1':
            strike[n['night']].append(n['station'])
    d0 = min(dt.date.fromisoformat(k) for k in report)
    d1 = max(dt.date.fromisoformat(k) for k in report)
    t, y = almanac.find_discrete(TS.utc(d0.year, d0.month, d0.day - 1 if d0.day > 1 else 1) - 31, TS.utc(d1.year, d1.month, d1.day) + 31,
                                 almanac.moon_phases(EPH))
    news = [ti.utc_datetime() for ti, yi in zip(t, y) if yi == 0]
    rows = []
    d = d0
    while d <= d1:
        mid = dt.datetime(d.year, d.month, d.day, tzinfo=UTC) + dt.timedelta(days=1)       # the midnight after the evening
        k = max(i for i, nm in enumerate(news) if nm <= mid)
        age = (mid - news[k]).total_seconds() / 86400
        alt, lit = moon(LAT, LON, mid)
        light = lit if alt > 0 else 0.0
        key = d.isoformat()
        rows.append({'night': key, 'lun': k, 'age': round(age, 2), 'light': round(light, 3), 'alt': round(alt, 1),
                     'reporting': report.get(key, 0), 'struck': sorted(strike.get(key, []))})
        d += dt.timedelta(days=1)
    k0 = rows[0]['lun']
    for r in rows:
        r['lun'] -= k0
    json.dump({'source': 'tools/film_calendar.py', 'where': [LAT, LON], 'nights': rows}, open(out, 'w'), separators=(',', ':'))
    print(f'{out}: {len(rows)} nights, {rows[-1]["lun"] + 1} lunations, {sum(len(r["struck"]) for r in rows)} station-nights with a strike')
    # the raw pattern, by moon age (what the picture shows, before any matching)
    bins = collections.defaultdict(lambda: [0, 0, 0])
    for r in rows:
        b = min(7, int(r['age'] / 29.53 * 8))
        bins[b][0] += r['reporting']; bins[b][1] += len(r['struck']); bins[b][2] += 1
    print('moon age bin (8ths of a lunation; 0 = just after new, 4 = just after full): strikes per 100 reporting station-nights')
    for b in range(8):
        rep, st, nn = bins[b]
        print(f'  {b}  {100 * st / max(rep, 1):5.1f}   ({st} of {rep}; {nn} nights)')
    lit = [r for r in rows if r['light'] > 0.5]
    dark = [r for r in rows if r['light'] <= 0.5]
    for name, g in (('moon > half lit and up at midnight', lit), ('the rest', dark)):
        rep = sum(r['reporting'] for r in g); st = sum(len(r['struck']) for r in g)
        print(f'  {name}: {100 * st / max(rep, 1):.1f} per 100 reporting station-nights ({st} of {rep})')


if __name__ == '__main__':
    main(sys.argv[1])
