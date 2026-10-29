"""K2 (notes/TESTS.md): does a station's record change more with a change of
keeper than with a change of light?

- pairs of consecutive station-years (t-1, t), both with primary records and
  a keeper named in data/keepers.csv;
- keeper changed: no surname in common ("Messrs Pritchard, Owen, and
  Hughes" gives three); light changed: the kind (tools/light_test.py)
  differs between two years of known state;
- outcomes: |change in log records| and |change in strike nights per
  watched night| (strike_wide);
- least squares with coast x year effects, clustered by station; keeper
  flags shuffled within coast-year (500 draws); planted: records tripled in
  each year after a keeper change.

Run in the venv: .venv/bin/python -I tools/keeper_test.py [--plant]
"""
import argparse, collections, csv, math, os, random, re, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA
from light_test import kinds

TITLES = re.compile(r"\b(mr|mrs|messrs|capt|captain|jun|sen|junr|senr)\b\.?", re.I)


def surnames(printed):
    s = TITLES.sub(' ', printed or '')
    out = set()
    for part in re.split(r',|\band\b|&|;', s):
        w = [x for x in re.findall(r"[A-Za-z'’]+", part) if len(x) > 1]
        if w:
            out.add(w[-1].lower().replace('’', "'"))
    return out


def pairs(outcome='strike_wide', plant=False):
    names = collections.defaultdict(set)
    for r in csv.DictReader(open(os.path.join(DATA, 'keepers.csv'))):
        names[(r['station_id'], int(r['year']))] |= surnames(r['keeper_printed'])
    recs = collections.Counter()
    coast = {}
    for r in csv.DictReader(open(os.path.join(DATA, 'records.csv'))):
        ids = r['station_ids'].split()
        if r['source_kind'] == 'primary' and len(ids) == 1:
            recs[(ids[0], int(r['report_year']))] += 1
            coast[ids[0]] = r['coast'].split(',')[0].split(':')[0]
    sn = collections.defaultdict(lambda: [0, 0])
    for r in csv.DictReader(open(os.path.join(DATA, 'weather', 'nights.csv'))):
        k = sn[(r['station'], int(r['night'][:4]))]
        k[0] += int(r[outcome])
        k[1] += 1
    kd = kinds()
    out = []
    for (s, y), n in recs.items():
        p = (s, y - 1)
        if p not in recs or not names.get((s, y)) or not names.get(p):
            continue
        kc = int(not (names[(s, y)] & names[p]))
        lc = None
        if (s, y) in kd and p in kd:
            lc = int(kd[(s, y)] != kd[p])
        a, b = recs[p], n
        if plant and kc:
            b *= 3
        row = {'station': s, 'year': y, 'cy': f'{coast[s]}|{y}', 'keeper': kc, 'light': lc, 'd_rec': abs(math.log(b) - math.log(a))}
        if sn[(s, y)][1] >= 5 and sn[p][1] >= 5:
            row['d_strike'] = abs(sn[(s, y)][0] / sn[(s, y)][1] - sn[p][0] / sn[p][1])
        out.append(row)
    return out


def fit(rows, y, xs):
    import pandas as pd
    import statsmodels.formula.api as smf
    d = pd.DataFrame([r for r in rows if r.get(y) is not None and all(r.get(x) is not None for x in xs)])
    res = smf.ols(f'{y} ~ ' + ' + '.join(xs) + ' + C(cy)', data=d).fit(cov_type='cluster', cov_kwds={'groups': pd.factorize(d['station'])[0]})
    return {x: (res.params[x], res.bse[x]) for x in xs}, len(d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--plant', action='store_true')
    ap.add_argument('--draws', type=int, default=500)
    a = ap.parse_args()
    rows = pairs(plant=a.plant)
    print(f'{len(rows)} consecutive station-year pairs with keepers named; keeper changed in {sum(r["keeper"] for r in rows)}; '
          f'light of known kind both years in {sum(r["light"] is not None for r in rows)}, changed in {sum(r["light"] or 0 for r in rows)}')
    for y, what in (('d_rec', '|change in log records|'), ('d_strike', '|change in strike nights per watched night|')):
        s = [r for r in rows if r.get(y) is not None]
        for k in (0, 1):
            v = [r[y] for r in s if r['keeper'] == k]
            print(f'   {what}: keeper {"changed" if k else "same":7} mean {np.mean(v):.3f} ({len(v)} pairs)')
        est, n = fit(rows, y, ['keeper'])
        b, se = est['keeper']
        print(f'   {y}, coast x year effects ({n} pairs): keeper changed {b:+.3f} (95% {b - 1.96 * se:+.3f} to {b + 1.96 * se:+.3f})')
        est, n = fit(rows, y, ['keeper', 'light'])
        print(f'   {y}, with light changed ({n} pairs with both known): keeper {est["keeper"][0]:+.3f} (se {est["keeper"][1]:.3f}), '
              f'light {est["light"][0]:+.3f} (se {est["light"][1]:.3f})')
        if a.draws:
            rng = random.Random(8)
            cells = collections.defaultdict(list)
            for i, r in enumerate(rows):
                cells[r['cy']].append(i)
            null = []
            for _ in range(a.draws):
                flags = [r['keeper'] for r in rows]
                for idx in cells.values():
                    f = [flags[i] for i in idx]
                    rng.shuffle(f)
                    for i, v in zip(idx, f):
                        flags[i] = v
                null.append(fit([dict(r, keeper=f) for r, f in zip(rows, flags)], y, ['keeper'])[0]['keeper'][0])
            print(f'      keeper flags shuffled within coast-year ({a.draws}): 95% of draws {np.percentile(null, 2.5):+.3f} to '
                  f'{np.percentile(null, 97.5):+.3f}; share as large as the real {np.mean(np.array(null) >= b):.3f}')


if __name__ == '__main__':
    main()
