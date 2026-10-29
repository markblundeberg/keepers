"""G1 and G2 (notes/TESTS.md, stage 5): the great nights, and whether a rush
travels along the east coast within a night.

G1: a night's size is the number of stations with a strike night
(strike_wide, data/weather/nights.csv); beside it the birds recorded killed
(per station-night the larger of the summed numbered parts and any printed
total; "many" counts nothing, so a floor). Check: the share of the top 20
inside the editors' own windows (TESTS.md), against all strike nights of
September-December 1882-1886.

G2: for nights with timed lantern records at 5+ stations on the east coasts
of Great Britain (the two east-coast sections, and a position on that coast:
lat 50.7-61, lon -3.5..2), each station's earliest such time (before noon
counts +24 h); time against latitude with night effects, autumn and spring
apart; shuffle null, resampled nights, and a planted slope.

Run: python3 -I tools/great_nights.py [--top 20] [--plant 0]
"""
import argparse, collections, csv, datetime as dt, os, random, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA

LANTERN = {'struck', 'dead', 'round_lantern'}
WINDOWS = [('1882-10-06', '1882-10-08'), ('1882-10-12', '1882-10-15'), ('1883-09-21', '1883-09-23'), ('1883-10-13', '1883-10-14'),
           ('1883-10-28', '1883-10-30'), ('1884-10-14', '1884-10-20'), ('1884-10-28', '1884-10-28'), ('1884-11-04', '1884-11-04'),
           ('1884-11-11', '1884-11-13'), ('1885-10-14', '1885-10-17'), ('1885-10-22', '1885-10-24'), ('1885-11-11', '1885-11-12'),
           ('1886-10-20', '1886-10-28'), ('1886-12-17', '1886-12-24')]


def in_window(night, pad=1):
    d = dt.date.fromisoformat(night)
    return any(dt.date.fromisoformat(a) - dt.timedelta(days=pad) <= d <= dt.date.fromisoformat(b) + dt.timedelta(days=pad) for a, b in WINDOWS)


def night_of(r):
    """The night a record belongs to, as nights.py has it: a clock time before noon is the night before."""
    d = dt.date.fromisoformat(r['date'])
    if r['time_kind'] == 'clock' and r['t_start_min'] != '' and float(r['t_start_min']) < 720:
        return d - dt.timedelta(days=1)
    return d


def lantern_records():
    pos = {r['id']: (float(r['lat']), float(r['lon'])) for r in csv.DictReader(open(os.path.join(DATA, 'stations', 'positions.csv'))) if r['lat']}
    for r in csv.DictReader(open(os.path.join(DATA, 'records.csv'))):
        ids = r['station_ids'].split()
        if r['source_kind'] != 'primary' or len(ids) != 1 or ids[0] not in pos or len(r['date']) != 10 or r['date_end']:
            continue
        if not (r['behaviour'] in LANTERN or (r['behaviour'] == 'caught' and r['at_light'] == 'True')):
            continue
        d = night_of(r)
        if 1878 <= d.year <= 1888:
            yield r, ids[0], d, pos[ids[0]]


def g1(top):
    nights = list(csv.DictReader(open(os.path.join(DATA, 'weather', 'nights.csv'))))
    by = collections.defaultdict(list)
    for n in nights:
        if n['strike_wide'] == '1':
            by[n['night']].append(n)
    killed = collections.defaultdict(lambda: [0, 0])          # (station, night): summed parts, largest total
    shared = set()
    for r, sid, d, _ in lantern_records():
        if r['behaviour'] == 'dead' and r['count_category'] in ('number', 'range'):     # numbers only: "many" counts nothing
            if r['count_shared'] == 'True':                 # one count copied onto each kind it covers: count it once
                key = (sid, d, r['quote'], r['count_raw'])
                if key in shared:
                    continue
                shared.add(key)
            k = killed[(sid, d.isoformat())]
            if r['total'] == 'True':
                k[1] = max(k[1], int(float(r['count_lo'])))
            else:
                k[0] += int(float(r['count_lo']))
    rows = []
    for night, ns in by.items():
        k = sum(max(killed[(n['station'], night)]) for n in ns)
        coasts = collections.Counter(n['coast'].split(',')[0].split(':')[0].title() for n in ns)
        rows.append((len(ns), k, night, coasts, np.mean([float(n['moon_lit']) for n in ns])))
    rows.sort(key=lambda t: (-t[0], -t[1]))
    print(f'G1: {len(rows)} nights with a strike somewhere; top {top} by stations with a strike:')
    for i, (n, k, night, coasts, lit) in enumerate(rows[:top], 1):
        cs = ', '.join(f'{c} {m}' for c, m in coasts.most_common())
        print(f'  {i:2}. {night}  {n:2} stations, {k:5} killed (floor)  moon {lit:.0%} lit  {"[editors] " if in_window(night) else ""}{cs}')
    t = [r for r in rows[:top]]
    base = [r for r in rows if r[2][:4] in ('1882', '1883', '1884', '1885', '1886') and r[2][5:7] in ('09', '10', '11', '12')]
    tin = sum(in_window(r[2]) for r in t)
    bin_ = sum(in_window(r[2]) for r in base)
    print(f'   check: {tin} of the top {top} in the editors\' windows (a day either side); '
          f'all strike nights Sep-Dec 1882-86: {bin_} of {len(base)} ({bin_ / len(base):.0%})')
    t82 = [r for r in rows if r[2][:4] in ('1882', '1883', '1884', '1885', '1886')][:top]
    print(f'   the same within 1882-86 only (the years the windows cover): {sum(in_window(r[2]) for r in t82)} of {top}')
    by_k = sorted(rows, key=lambda t: -t[1])[:10]
    print('   the ten nights with most birds recorded killed:')
    for n, k, night, coasts, lit in by_k:
        print(f'      {night}  {k:5} killed at {n} stations')


REGIONS = {  # the registered test, and (added after it found no nights) the one coast with timed lantern records at many stations
    'east coasts of Great Britain': lambda c, lat, lon: c.startswith('EAST COAST') and 50.7 <= lat <= 61 and -3.5 <= lon <= 2,
    'west coast of England and Wales (added)': lambda c, lat, lon: c.startswith('WEST COAST OF ENGLAND') and 49.8 <= lat <= 55.5 and -6.5 <= lon <= -2.5,
}


def g2(plant, region, need=5):
    first = {}
    keep = REGIONS[region]
    for r, sid, d, (lat, lon) in lantern_records():
        if not keep(r['coast'], lat, lon):
            continue
        if r['time_kind'] != 'clock' or r['t_start_min'] == '':
            continue
        t = float(r['t_start_min'])
        t = t + 1440 if t < 720 else t
        k = (d.isoformat(), sid)
        if k not in first or t < first[k][0]:
            first[k] = (t, lat)
    by = collections.defaultdict(list)
    for (night, sid), (t, lat) in first.items():
        by[night].append([t + plant * (58 - lat), lat, sid])        # planted: later by `plant` minutes per degree south of 58 N
    for season, months in (('autumn', ('08', '09', '10', '11', '12')), ('spring', ('02', '03', '04', '05', '06'))):
        ns = {n: v for n, v in by.items() if len(v) >= need and n[5:7] in months}
        if len(ns) < 3:
            print(f'G2 {region}, {season}: {len(ns)} nights with {need}+ timed stations; too few')
            continue

        def slope(groups):
            x = np.concatenate([[p[1] - np.mean([q[1] for q in g]) for p in g] for g in groups])
            y = np.concatenate([[p[0] - np.mean([q[0] for q in g]) for p in g] for g in groups])
            return -float(np.sum(x * y) / np.sum(x * x))          # minutes later per degree further south
        groups = list(ns.values())
        s = slope(groups)
        rng = random.Random(2)
        null = []
        for _ in range(1000):
            sh = []
            for g in groups:
                ts = [p[0] for p in g]
                rng.shuffle(ts)
                sh.append([[t, p[1], p[2]] for t, p in zip(ts, g)])
            null.append(slope(sh))
        bs = [slope([rng.choice(groups) for _ in groups]) for _ in range(1000)]
        span = np.mean([max(p[1] for p in g) - min(p[1] for p in g) for g in groups])
        print(f'G2 {region}, {season}: {len(groups)} nights with {need}+ timed stations ({sum(len(g) for g in groups)} station-nights; '
              f'mean span {span:.1f} deg of latitude)')
        print(f'   slope {s:+.1f} min later per degree further south (resampled nights 95% {np.percentile(bs, 2.5):+.1f} to {np.percentile(bs, 97.5):+.1f}); '
              f'shuffle null 95% {np.percentile(null, 2.5):+.1f} to {np.percentile(null, 97.5):+.1f}')
        if s > 0:
            print(f'   as a speed southward: {111 * 60 / s:.0f} km/h')
        for g in sorted(groups, key=len, reverse=True)[:3]:
            night = next(n for n, v in ns.items() if v is g)
            pts = ', '.join(f'{p[2]} {int(p[0]) // 60 % 24:02d}:{int(p[0]) % 60:02d}' for p in sorted(g, key=lambda p: -p[1]))
            print(f'   {night} (north to south): {pts}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--top', type=int, default=20)
    ap.add_argument('--plant', type=float, default=0.0, help='a check: add this many minutes per degree south to every time')
    a = ap.parse_args()
    if not a.plant:
        g1(a.top)
    for region in REGIONS:
        g2(a.plant, region)


if __name__ == '__main__':
    main()
