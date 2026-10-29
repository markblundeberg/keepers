"""K1 (notes/TESTS.md): are strike nights less moonlit and more overcast than
other reporting nights at the same station in the same month?

- unit: a station-night with any primary record (data/weather/nights.csv);
- outcome: strike_wide (the amended K1 outcome), and the registered one
  (`strike`, at_light required) beside it;
- matched: conditional logistic regression within station x year-month
  (every comparison is between nights of one station in one month), on
  moonlit, reanalysis total cloud (per 10%) and rain (20CRv3 3-h
  precipitation > 0.1 mm); a second model adds the night's passage (the
  number of stations on that coast reporting that night, log) and the
  station's own number of records (log);
- intervals: resampling nights by date (one weather map per date);
- nulls: the moon of 14-15 days away (phase reversed), the cloud of 7-60
  days away; each must erase its effect;
- the keepers' own weather letters, where printed: the share of strike and
  other nights carrying each, matched within station x year-month.

Run in the venv: .venv/bin/python -I tools/strike_test.py [--outcome strike_wide] [--boot 200] [--plant]
"""
import argparse, collections, csv, datetime as dt, math, os, random, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA


def load(outcome):
    rows = list(csv.DictReader(open(os.path.join(DATA, 'weather', 'nights.csv'))))
    passage = collections.Counter((r['coast'], r['night']) for r in rows)
    out = []
    for r in rows:
        if r['tcdc'] == '' or r['apcp'] == '':
            continue
        out.append({'station': r['station'], 'night': r['night'], 'coast': r['coast'], 'kind': r['kind'],
                    'lat': float(r['lat']), 'lon': float(r['lon']),
                    'group': f"{r['station']}|{r['night'][:7]}", 'y': int(r[outcome]),
                    'moonlit': int(r['moonlit']), 'cloud': float(r['tcdc']) / 10, 'rain': int(float(r['apcp']) > 0.1),
                    'passage': math.log(passage[(r['coast'], r['night'])]), 'records': math.log(int(r['records'])),
                    'letters': r['letters']})
    # only groups with both a strike night and another night carry information in a matched comparison
    g = collections.defaultdict(set)
    for r in out:
        g[r['group']].add(r['y'])
    return out, [r for r in out if len(g[r['group']]) == 2]


def clogit(rows, xs):
    from statsmodels.discrete.conditional_models import ConditionalLogit
    X = np.array([[r[x] for x in xs] for r in rows], float)
    y = np.array([r['y'] for r in rows])
    gr = np.array([r['group'] for r in rows])
    res = ConditionalLogit(y, X, groups=gr).fit(disp=0)
    return np.asarray(res.params), np.asarray(res.bse)


def boot(rows, xs, n, seed=1):
    by = collections.defaultdict(list)
    for r in rows:
        by[r['night']].append(r)
    days = list(by)
    rng = random.Random(seed)
    bs = []
    for _ in range(n):
        s = [r for d in (rng.choice(days) for _ in days) for r in by[d]]
        try:
            bs.append(clogit(s, xs)[0])
        except Exception:
            pass
    return np.percentile(np.array(bs), [2.5, 97.5], axis=0)


def show(name, rows, xs, nboot):
    b, se = clogit(rows, xs)
    ci = boot(rows, xs, nboot) if nboot else None
    print(f'{name} ({len(rows)} nights in {len({r["group"] for r in rows})} station-months; {sum(r["y"] for r in rows)} strike nights)')
    for k, x in enumerate(xs):
        c = f'; resampled dates {math.exp(ci[0][k]):.2f}-{math.exp(ci[1][k]):.2f}' if ci is not None else ''
        print(f'   {x:9} odds ratio {math.exp(b[k]):.2f} (model 95% {math.exp(b[k] - 1.96 * se[k]):.2f}-{math.exp(b[k] + 1.96 * se[k]):.2f}{c})')
    return b


def matched_means(rows, key):
    """Within each station-month, strike-night mean minus other-night mean; averaged over station-months, weighted
    by the number of strike nights."""
    g = collections.defaultdict(lambda: ([], []))
    for r in rows:
        g[r['group']][r['y']].append(r[key])
    num = den = 0
    for a, s in g.values():
        if a and s:
            num += len(s) * (np.mean(s) - np.mean(a))
            den += len(s)
    return num / den


def calendar(outcome):
    """Added after the first run: strike nights per calendar night, moonlit against not, within station-month
    (Mantel-Haenszel), over every night of each station-month with a strike night. Free of which nights a keeper
    chose to report: if moonlit nights only drew more non-strike reports, this ratio would be near 1."""
    from sky import EARTH, MOON, TS, clock_offset_min
    from skyfield import almanac
    from skyfield.api import wgs84
    from sky import EPH
    rows = list(csv.DictReader(open(os.path.join(DATA, 'weather', 'nights.csv'))))
    strike = {(r['station'], r['night']) for r in rows if r[outcome] == '1'}
    meta = {r['station']: (float(r['lat']), float(r['lon']), r['coast'], r['kind']) for r in rows}
    months = collections.defaultdict(set)
    for s_, n in strike:
        months[s_].add(n[:7])
    num = den = 0.0
    per_station = collections.defaultdict(lambda: [0.0, 0.0])
    tab = collections.Counter()
    by_kind = collections.defaultdict(lambda: [0.0, 0.0])
    for s_, ms in months.items():
        lat, lon, coast, kind = meta[s_]
        days = []
        for ym in sorted(ms):
            y, mo = map(int, ym.split('-'))
            d = dt.date(y, mo, 1)
            while d.month == mo:
                days.append(d)
                d += dt.timedelta(days=1)
        off = clock_offset_min(coast, lon)
        t = TS.from_datetimes([dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc) + dt.timedelta(days=1, minutes=off) for d in days])
        alt = (EARTH + wgs84.latlon(lat, lon)).at(t).observe(MOON).apparent().altaz()[0].degrees
        lit = almanac.fraction_illuminated(EPH, 'moon', t)
        cells = collections.defaultdict(lambda: [0, 0, 0, 0])      # per month: strike&lit, lit, strike&dark, dark
        for d, a_, l_ in zip(days, alt, lit):
            c = cells[d.isoformat()[:7]]
            m_ = l_ > 0.5 and a_ > 0
            k = (s_, d.isoformat()) in strike
            c[0 if m_ else 2] += k
            c[1 if m_ else 3] += 1
        for sl, nl, sd, nd in cells.values():
            n = nl + nd
            num += sl * (nd - sd) / n
            den += sd * (nl - sl) / n
            per_station[s_][0] += sl * (nd - sd) / n
            per_station[s_][1] += sd * (nl - sl) / n
            by_kind[kind][0] += sl * (nd - sd) / n
            by_kind[kind][1] += sd * (nl - sl) / n
            tab['strike lit'] += sl; tab['lit'] += nl; tab['strike dark'] += sd; tab['dark'] += nd
    print(f'calendar check (added): {tab["strike lit"]} strike nights in {tab["lit"]} moonlit calendar nights ({tab["strike lit"] / tab["lit"]:.1%}), '
          f'{tab["strike dark"]} in {tab["dark"]} others ({tab["strike dark"] / tab["dark"]:.1%}); Mantel-Haenszel odds ratio within station-month '
          f'{num / den:.2f}; ' + ', '.join(f'{k} {v[0] / v[1]:.2f}' for k, v in sorted(by_kind.items())))
    st = list(per_station.values())
    rng = np.random.default_rng(4)
    bs = []
    for _ in range(2000):
        k = rng.integers(0, len(st), len(st))
        bs.append(sum(st[i][0] for i in k) / sum(st[i][1] for i in k))
    print(f'   95% by resampling stations ({len(st)}): {np.percentile(bs, 2.5):.2f}-{np.percentile(bs, 97.5):.2f}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--outcome', default='strike_wide')
    ap.add_argument('--boot', type=int, default=200)
    ap.add_argument('--plant', action='store_true', help='a check: unmark half the moonlit strike nights; the moon odds ratio must fall by about half')
    a = ap.parse_args()
    allrows, rows = load(a.outcome)
    if a.plant:
        rng = random.Random(11)
        for r in allrows:
            if r['y'] and r['moonlit'] and rng.random() < 0.5:
                r['y'] = 0
        g = collections.defaultdict(set)
        for r in allrows:
            g[r['group']].add(r['y'])
        rows = [r for r in allrows if len(g[r['group']]) == 2]
    print(f'outcome {a.outcome}: {len(allrows)} station-nights with reanalysis weather, {sum(r["y"] for r in allrows)} strike nights; '
          f'{len(rows)} nights in station-months with both kinds')
    # plain matched differences first, in the units a reader can see
    for key, unit in (('moonlit', 'share moonlit'), ('cloud', 'total cloud (tenths)'), ('rain', 'share with rain')):
        print(f'   strike minus other nights, same station-month: {unit} {matched_means(rows, key):+.3f}  '
              f'(means: strike {np.mean([r[key] for r in rows if r["y"]]):.3f}, other {np.mean([r[key] for r in rows if not r["y"]]):.3f})')
    xs = ['moonlit', 'cloud', 'rain']
    show('model 1', rows, xs, a.boot)
    show('model 2 (+ passage, + records)', rows, xs + ['passage', 'records'], a.boot)
    for kind in ('lighthouse', 'light-vessel'):
        s = [r for r in rows if r['kind'] == kind]
        g = collections.defaultdict(set)
        for r in s:
            g[r['group']].add(r['y'])
        s = [r for r in s if len(g[r['group']]) == 2]
        if len(s) > 100:
            show(f'model 1, {kind}s', s, xs, 0)
    # nulls: moon of 14-15 days away; cloud of 7-60 days away (same station)
    from sky import clock_offset_min, moon
    from winds import EPOCH, Field
    rng = random.Random(5)
    tc = Field('tcdc.eatm', 'tcdc')
    shifted = []
    for r in rows:
        d = dt.date.fromisoformat(r['night'])
        m = dt.datetime(d.year, d.month, d.day) + dt.timedelta(days=1 + rng.choice([-1, 1]) * rng.choice([14, 15]),
                                                               minutes=clock_offset_min(r['coast'], r['lon']))
        alt, lit = moon(r['lat'], r['lon'], m)
        c = dt.datetime(d.year, d.month, d.day) + dt.timedelta(days=1 + rng.choice([-1, 1]) * rng.randint(7, 60),
                                                               minutes=clock_offset_min(r['coast'], r['lon']))
        cl = tc.at(r['lat'], r['lon'], (c - EPOCH).total_seconds() / 3600)
        shifted.append(dict(r, moonlit=int(lit > 0.5 and alt > 0), cloud=(cl / 10 if not math.isnan(cl) else r['cloud'])))
    show('null: moon of 14-15 days away, cloud of 7-60 days away', shifted, xs, 0)
    # added after the first run (not in the plan): if moonlight is the cause, the moon should matter less under a
    # full overcast (reanalysis cloud is a weak proxy for the sky at a point, so this can only blur)
    for lo, hi, name in ((0, 6, 'cloud under 6 tenths'), (9, 10.01, 'cloud 9 tenths or more')):
        s_ = [r for r in rows if lo <= r['cloud'] < hi]
        g = collections.defaultdict(set)
        for r in s_:
            g[r['group']].add(r['y'])
        s_ = [r for r in s_ if len(g[r['group']]) == 2]
        show(f'model 1 (added), {name}', s_, ['moonlit', 'rain'], 0)
    # added after the first run (not in the plan): the 14-15-day null mirrors the moon rather than erasing it, so a
    # null with the moon of a random 1-29 days away; and the calendar check below
    rng = random.Random(6)
    shifted = []
    for r in rows:
        d = dt.date.fromisoformat(r['night'])
        m = dt.datetime(d.year, d.month, d.day) + dt.timedelta(days=1 + rng.randint(1, 29), minutes=clock_offset_min(r['coast'], r['lon']))
        alt, lit = moon(r['lat'], r['lon'], m)
        shifted.append(dict(r, moonlit=int(lit > 0.5 and alt > 0)))
    show('null (added): moon of a random 1-29 days later', shifted, xs, 0)
    calendar(a.outcome)
    # the keepers' own letters
    lr = [r for r in rows if r['letters']]
    print(f'keepers\' weather letters, nights with any printed ({len(lr)}):')
    for L, what in (('O', 'overcast'), ('C', 'cloudy'), ('G', 'gloomy'), ('F', 'fog'), ('M', 'misty'), ('D', 'drizzle'), ('R', 'rain'),
                    ('B', 'blue sky')):
        for r in lr:
            r['L'] = int(L in r['letters'])
        n = sum(r['L'] for r in lr)
        if n >= 20:
            gs = collections.defaultdict(list)
            for r in lr:
                gs[r['group']].append(dict(r))
            keys, rng = list(gs), random.Random(9)
            bs = []
            for _ in range(1000):
                smp = [r for k in (rng.choice(keys) for _ in keys) for r in gs[k]]
                try:
                    bs.append(matched_means(smp, 'L'))
                except ZeroDivisionError:
                    pass
            n_sm = sum(1 for v in gs.values() if len({r['y'] for r in v}) == 2)
            print(f'   {L} {what:9} on {n:4} nights; strike minus other, same station-month ({n_sm} with both): {matched_means(lr, "L"):+.3f} '
                  f'(95% {np.percentile(bs, 2.5):+.3f} to {np.percentile(bs, 97.5):+.3f})  '
                  f'(strike {np.mean([r["L"] for r in lr if r["y"]]):.2f}, other {np.mean([r["L"] for r in lr if not r["y"]]):.2f})')


if __name__ == '__main__':
    main()
