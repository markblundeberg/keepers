"""L1 (notes/TESTS.md): do fixed lights kill more birds per watched night
than eclipsing ones?

- unit: a station-year with primary records; outcome: strike nights
  (strike_wide, the amended K1 outcome; the registered `strike` beside it);
  exposure: nights with any record (data/weather/nights.csv);
- light kind that year (data/stations/characters.csv): fixed if every light
  of the station is steady, eclipsing if none is (revolving, flashing,
  group flashing, occulting, intermittent), mixed if both; a year the
  witnesses can't split (two rows) counts only if both states are of one
  kind;
- Poisson regression, log exposure as offset, kind (fixed vs eclipsing;
  mixed reported apart), station type, coast x year effects; standard
  errors clustered by station; a negative binomial beside it;
- within stations: lights whose kind changed between years of known state,
  strike rate per watched night before and after, and a sign test;
- broken: each station's kinds shuffled among the stations of its coast
  (200 draws); the effect must vanish.

Run in the venv: .venv/bin/python -I tools/light_test.py [--outcome strike_wide]
"""
import argparse, collections, csv, json, math, os, random, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA

ECLIPSING = {'revolving', 'flashing', 'group_flashing', 'occulting', 'intermittent'}


def kinds():
    states = collections.defaultdict(set)
    for r in csv.DictReader(open(os.path.join(DATA, 'stations', 'characters.csv'))):
        ks = {x['kind'] for x in json.loads(r['pattern'])} if r['pattern'] else set()
        if not ks:
            continue
        states[(r['id'], int(r['year']))].add('fixed' if ks == {'fixed'} else 'eclipsing' if ks <= ECLIPSING else 'mixed')
    return {k: next(iter(v)) for k, v in states.items() if len(v) == 1}


def heights():
    """Height of the light above high water (ft), from the Findlay row each station's character came from."""
    F = {}
    for b in ('findlay1879', 'findlay1887'):
        for r in csv.DictReader(open(os.path.join(DATA, 'lights', f'{b}.csv'))):
            F[(b, r['row_id'])] = r['height_ft']
    h = {}
    for r in csv.DictReader(open(os.path.join(DATA, 'stations', 'characters.csv'))):
        v = F.get((r['source'], r['ref']), '')
        m = __import__('re').match(r'\d+', v or '')
        if m and r['id'] not in h:
            h[r['id']] = float(m.group())
    return h


def station_years(outcome):
    sy = collections.defaultdict(lambda: {'n': 0, 'y': 0})
    meta = {}
    for r in csv.DictReader(open(os.path.join(DATA, 'weather', 'nights.csv'))):
        k = (r['station'], int(r['night'][:4]))
        sy[k]['n'] += 1
        sy[k]['y'] += int(r[outcome])
        meta[r['station']] = (r['kind'], r['coast'])
    kd = kinds()
    rows = []
    for (s, y), v in sy.items():
        if (s, y) in kd and s in meta:
            rows.append({'station': s, 'year': y, 'kind': kd[(s, y)], 'type': meta[s][0], 'coast': meta[s][1], 'n': v['n'], 'y': v['y']})
    return rows


def fit(rows, family='poisson', extra=''):
    import pandas as pd
    import statsmodels.api as sm
    import statsmodels.formula.api as smf
    d = pd.DataFrame(rows)
    d = d[d['kind'] != 'mixed'].copy()
    d['fixed'] = (d['kind'] == 'fixed').astype(int)
    d['vessel'] = (d['type'] == 'light-vessel').astype(int)
    d['cy'] = d['coast'] + '|' + d['year'].astype(str)
    fam = sm.families.Poisson() if family == 'poisson' else sm.families.NegativeBinomial(alpha=1.0)
    if extra:
        d = d[d['height'] > 0].copy()
        d['log_height'] = np.log(d['height'])
    m = smf.glm('y ~ fixed + vessel + C(cy)' + extra, data=d, family=fam, offset=np.log(d['n']))
    res = m.fit(cov_type='cluster', cov_kwds={'groups': pd.factorize(d['station'])[0]})
    return res.params['fixed'], res.bse['fixed'], res.params['vessel'], res.bse['vessel'], len(d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--outcome', default='strike_wide')
    ap.add_argument('--draws', type=int, default=200)
    a = ap.parse_args()
    rows = station_years(a.outcome)
    print(f'outcome {a.outcome}: {len(rows)} station-years of known kind')
    for kind in ('fixed', 'eclipsing', 'mixed'):
        for t in ('lighthouse', 'light-vessel'):
            s = [r for r in rows if r['kind'] == kind and r['type'] == t]
            if s:
                n, y = sum(r['n'] for r in s), sum(r['y'] for r in s)
                print(f'   {kind:9} {t:12} {len(s):4} station-years ({len({r["station"] for r in s})} stations): {y} strike nights in {n} watched, {y / n:.1%}')
    for fam in ('poisson', 'negbin'):
        b, se, bv, sev, n = fit(rows, fam)
        print(f'{fam}, coast x year effects, clustered by station ({n} station-years): fixed vs eclipsing rate ratio {math.exp(b):.2f} '
              f'(95% {math.exp(b - 1.96 * se):.2f}-{math.exp(b + 1.96 * se):.2f}); light-vessel vs tower {math.exp(bv):.2f} '
              f'({math.exp(bv - 1.96 * sev):.2f}-{math.exp(bv + 1.96 * sev):.2f})')
    # added after the first run (not in the plan): the eclipsing lights of the 1880s were often the great headland and
    # rock lights; tower height (Findlay) as a first control for that
    hs = heights()
    hrows = [dict(r, height=hs.get(r['station'], 0)) for r in rows]
    for kind in ('fixed', 'eclipsing'):
        v = [r['height'] for r in hrows if r['kind'] == kind and r['height'] > 0]
        print(f'   {kind}: median height {np.median(v):.0f} ft ({len(v)} station-years with a height)')
    b, se, bv, sev, n = fit(hrows, 'negbin', ' + log_height')
    print(f'negbin (added), + log height ({n} station-years): fixed vs eclipsing {math.exp(b):.2f} ({math.exp(b - 1.96 * se):.2f}-{math.exp(b + 1.96 * se):.2f})')
    # within stations: kind changed between years of known state
    by = collections.defaultdict(list)
    for r in rows:
        by[r['station']].append(r)
    pairs = []
    for s, rs in by.items():
        ks = {r['kind'] for r in rs if r['kind'] != 'mixed'}
        if ks == {'fixed', 'eclipsing'}:
            rate = {k: (sum(r['y'] for r in rs if r['kind'] == k), sum(r['n'] for r in rs if r['kind'] == k)) for k in ks}
            pairs.append((s, rate))
    print(f'within stations whose light went between fixed and eclipsing (years of known state): {len(pairs)}')
    up = 0
    for s, rate in pairs:
        f, e = rate['fixed'][0] / rate['fixed'][1], rate['eclipsing'][0] / rate['eclipsing'][1]
        up += f > e
        print(f'   {s:28} fixed {rate["fixed"][0]}/{rate["fixed"][1]} = {f:.1%}   eclipsing {rate["eclipsing"][0]}/{rate["eclipsing"][1]} = {e:.1%}')
    if pairs:
        from scipy.stats import binomtest
        ties = sum(1 for s, r in pairs if r['fixed'][0] / r['fixed'][1] == r['eclipsing'][0] / r['eclipsing'][1])
        print(f'   fixed higher at {up} of {len(pairs) - ties} (ties {ties}); sign test p = {binomtest(up, len(pairs) - ties).pvalue:.2f}')
    # broken: shuffle each station's kinds among the stations of its coast
    rng = random.Random(3)
    real = fit(rows)[0]
    null = []
    coasts = collections.defaultdict(list)
    for s, rs in by.items():
        coasts[rs[0]['coast']].append(s)
    for _ in range(a.draws):
        perm = {}
        for c, ss in coasts.items():
            sh = ss[:]
            rng.shuffle(sh)
            perm.update(zip(ss, sh))
        kd = {(r['station'], r['year']): r['kind'] for r in rows}
        sh_rows = []
        for r in rows:
            k = kd.get((perm[r['station']], r['year']))
            if k:
                sh_rows.append(dict(r, kind=k))
        null.append(fit(sh_rows)[0])
    null = np.array(null)
    print(f'shuffled kinds within coast ({a.draws} draws): rate ratio median {math.exp(np.median(null)):.2f}, '
          f'95% of draws {math.exp(np.percentile(null, 2.5)):.2f}-{math.exp(np.percentile(null, 97.5)):.2f}; '
          f'real {math.exp(real):.2f}, share of draws as far from 1: {np.mean(np.abs(null) >= abs(real)):.2f}')


if __name__ == '__main__':
    main()
