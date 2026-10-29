"""Do the keepers' winds agree with the reanalysis, and by which north?

- agreement: the share of winds within 45 deg of 20CRv3's (one compass
  point either side of a 4-point sector), against a null that pairs each
  wind with the reanalysis at the same station 7-60 days away (same season,
  different weather);
- rotation: the circular mean of keeper minus reanalysis, weighted by the
  reanalysis speed and over winds above 4 m/s (light winds turn freely);
  95% interval by resampling dates (one weather map covers every station
  on a day). A magnetic compass would put the keepers clockwise of true by
  the westerly declination (gufm1: 14-23 deg W across the stations);
- by declination: the rotation in bands of declination; magnetic readings
  would make it follow the declination, true ones wouldn't.

Run: python3 -I tools/wind_test.py [--min-speed 4]
"""
import argparse, collections, csv, math, os, random, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA


def wrap(d):
    return (d + 180) % 360 - 180


def circ_mean(ds, ws=None):
    ws = np.ones(len(ds)) if ws is None else np.asarray(ws)
    r = np.radians(ds)
    return math.degrees(math.atan2(np.sum(ws * np.sin(r)), np.sum(ws * np.cos(r))))


def boot(rows, stat, n=1000, seed=1):
    by = collections.defaultdict(list)
    for r in rows:
        by[r['date']].append(r)
    days = list(by)
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        s = [r for d in (rng.choice(days) for _ in days) for r in by[d]]
        out.append(stat(s))
    return np.percentile(out, [2.5, 97.5])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--min-speed', type=float, default=4.0)
    ap.add_argument('--break-rotate', type=float, default=0.0, help='add this many degrees to every keeper wind (a check)')
    a = ap.parse_args()
    rows = list(csv.DictReader(open(os.path.join(DATA, 'weather', 'winds.csv'))))
    for r in rows:
        r['k'] = float(r['keeper_deg']) + a.break_rotate
        r['r'], r['s'], r['decl'] = float(r['r_deg']), float(r['r_speed']), float(r['declination'])
        r['d'] = wrap(r['k'] - r['r'])
    agree = lambda s: np.mean([abs(r['d']) <= 45 for r in s])
    print(f'{len(rows)} winds; within 45 deg of 20CRv3: {agree(rows):.1%} (95% {boot(rows, agree)[0]:.1%}-{boot(rows, agree)[1]:.1%})')
    # null: the same station's reanalysis at another date
    by_station = collections.defaultdict(list)
    for r in rows:
        by_station[r['station']].append(r)
    rng = random.Random(7)
    import datetime as dt
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from winds import Field, bearing_from, hours
    U, V = Field('uwnd.10m', 'uwnd'), Field('vwnd.10m', 'vwnd')
    null = []
    for rep in range(20):
        hits = []
        for r in rows:
            day = dt.datetime.strptime(r['date'], '%Y-%m-%d') + dt.timedelta(days=rng.choice([-1, 1]) * rng.randint(7, 60), hours=12)
            u, v = U.at(float(r['lat']), float(r['lon']), hours(day)), V.at(float(r['lat']), float(r['lon']), hours(day))
            if not math.isnan(u):
                hits.append(abs(wrap(r['k'] - bearing_from(u, v))) <= 45)
        null.append(np.mean(hits))
    print(f'   null (same station, 7-60 days away; 20 draws): {np.mean(null):.1%} (range {min(null):.1%}-{max(null):.1%}); '
          f'chance for a uniform guess: 25.0%')
    strong = [r for r in rows if r['s'] >= a.min_speed]
    rot = lambda s: circ_mean([r['d'] for r in s], [r['s'] for r in s])
    lo, hi = boot(strong, rot)
    print(f'rotation, keeper minus 20CRv3, winds >= {a.min_speed} m/s (n={len(strong)}): {rot(strong):+.1f} deg (95% {lo:+.1f} to {hi:+.1f}); '
          f'a magnetic compass would give about {-np.mean([r["decl"] for r in strong]):+.1f}')
    bands = [(-30, -21), (-21, -19), (-19, -17), (-17, -10)]
    for b0, b1 in bands:
        s = [r for r in strong if b0 <= r['decl'] < b1]
        if len(s) >= 20:
            lo, hi = boot(s, rot, n=400)
            print(f'   declination {b0}..{b1} deg (n={len(s)}): rotation {rot(s):+.1f} ({lo:+.1f} to {hi:+.1f}); magnetic would be {-np.mean([r["decl"] for r in s]):+.1f}')
    # per station: rotation against minus the declination (magnetic: slope near 1; true: near 0); and whether the
    # stations split into a group near 0 and one near the declination (mixed practice)
    kinds = {r['id']: r['kind'] for r in csv.DictReader(open(os.path.join(DATA, 'stations', 'positions.csv')))}
    by_st = collections.defaultdict(list)
    for r in strong:
        by_st[r['station']].append(r)
    st = [(sid, len(s), rot(s), -np.mean([r['decl'] for r in s]), kinds.get(sid, '')) for sid, s in by_st.items() if len(s) >= 30]
    if len(st) >= 4:
        x, y, w = np.array([t[3] for t in st]), np.array([t[2] for t in st]), np.array([t[1] for t in st], float)
        X = np.vstack([np.ones_like(x), x]).T
        beta = np.linalg.lstsq(X * np.sqrt(w)[:, None], y * np.sqrt(w), rcond=None)[0]
        bs = []
        rng2 = np.random.default_rng(3)
        for _ in range(2000):
            k = rng2.integers(0, len(st), len(st))
            bs.append(np.linalg.lstsq(X[k] * np.sqrt(w[k])[:, None], y[k] * np.sqrt(w[k]), rcond=None)[0][1])
        print(f'per station (>= 30 winds of {a.min_speed}+ m/s; {len(st)} stations): rotation = {beta[0]:+.1f} + {beta[1]:.2f} x (minus declination); '
              f'slope 95% {np.percentile(bs, 2.5):.2f} to {np.percentile(bs, 97.5):.2f} (magnetic 1, true 0)')
        for t in sorted(st, key=lambda t: t[2]):
            print(f'     {t[0]:28} {t[4]:12} n={t[1]:4}  rotation {t[2]:+6.1f}   magnetic would be {t[3]:+5.1f}')
    for kind in ('lighthouse', 'light-vessel'):
        s = [r for r in rows if kinds.get(r['station']) == kind]
        ss = [r for r in s if r['s'] >= a.min_speed]
        if s:
            print(f'   {kind} (n={len(s)}): within 45 deg {agree(s):.1%}; rotation {rot(ss):+.1f} (n={len(ss)})')
    for how in sorted({r['time_how'] for r in strong}):
        s = [r for r in strong if r['time_how'] == how]
        print(f'   {how} (n={len(s)}): within 45 deg {agree(s):.1%}; rotation {rot(s):+.1f}')


if __name__ == '__main__':
    main()
