"""Two extraction runs on the same segments, compared: how often they agree,
field by field. Where the prompt didn't change a rule, disagreement is the
extractor's own wobble, a floor under its error rate that one run can't show.

Observations are matched within a segment by species and behaviour (in
order), then their copied fields compared.

Run: python3 -I tools/consistency.py 1887 v1 v2 [--show 10]
"""
import argparse, collections, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA, ws_norm
from normalize import count, deaths, direction, time_of_day

FIELDS = ['count', 'time', 'direction', 'at_light', 'count_shared', 'other_dates', 'specimen']


def load(year, ver):
    by = collections.defaultdict(list)
    for l in open(os.path.join(DATA, 'pilot', f'obs_llm_{year}_{ver}.jsonl')):
        o = json.loads(l)
        by[o['seg_id']].append(o)
    wx = {w['seg_id']: w for w in (json.loads(l) for l in open(os.path.join(DATA, 'pilot', f'wx_llm_{year}_{ver}.jsonl')))}
    return by, wx


def key(o):
    return (ws_norm(o['species'] or '').lower(), o['behaviour'])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('year', type=int)
    ap.add_argument('a')
    ap.add_argument('b')
    ap.add_argument('--show', type=int, default=10)
    a = ap.parse_args()
    A, wa = load(a.year, a.a)
    B, wb = load(a.year, a.b)
    segs = sorted(set(wa) & set(wb))
    same_set = 0
    pairs, only_a, only_b = [], [], []
    for s in segs:
        ka = collections.Counter(key(o) for o in A[s])
        kb = collections.Counter(key(o) for o in B[s])
        same_set += ka == kb
        pool = collections.defaultdict(list)
        for o in B[s]:
            pool[key(o)].append(o)
        for o in A[s]:
            if pool[key(o)]:
                pairs.append((o, pool[key(o)].pop(0)))
            else:
                only_a.append(o)
        only_b += [o for v in pool.values() for o in v]
    print(f'{len(segs)} segments in both; identical (species, behaviour) sets in {same_set} '
          f'({100 * same_set / len(segs):.1f}%); {len(pairs)} matched observations, '
          f'{len(only_a)} only in {a.a}, {len(only_b)} only in {a.b}')
    beh_a = collections.Counter(o['behaviour'] for o in only_a)
    beh_b = collections.Counter(o['behaviour'] for o in only_b)
    print(f'  unmatched by behaviour: {a.a} {dict(beh_a)}; {a.b} {dict(beh_b)}')
    for f in FIELDS:
        d = [(x, y) for x, y in pairs if (ws_norm(str(x.get(f))) if x.get(f) is not None else None) !=
             (ws_norm(str(y.get(f))) if y.get(f) is not None else None)]
        print(f'  {f:13} agree {len(pairs) - len(d)}/{len(pairs)} ({100 * (len(pairs) - len(d)) / len(pairs):.1f}%)')
        for x, y in d[:a.show]:
            print(f'     {x["obs_id"]}: {x.get(f)!r} | {y.get(f)!r}   [{ws_norm(x["quote"])[:70]}]')
    # the same, on the numbers the data will carry
    for f, fn in (('time (minutes)', lambda o: time_of_day(o['time'])[:3]), ('count (range)', lambda o: count(o['count'])[:2]),
                  ('direction (deg)', lambda o: direction(o['direction']))):
        d = [(x, y) for x, y in pairs if fn(x) != fn(y)]
        print(f'  {f:16} agree {len(pairs) - len(d)}/{len(pairs)} ({100 * (len(pairs) - len(d)) / len(pairs):.1f}%)')
    dd = [s for s in segs if (deaths(A[s])[2] or deaths(B[s])[2]) and deaths(A[s])[:2] != deaths(B[s])[:2]]
    nd = sum(1 for s in segs if deaths(A[s])[2] or deaths(B[s])[2])
    print(f'  death tally    agree {nd - len(dd)}/{nd} segments with deaths; birds dead (floor) {a.a} '
          f'{sum(deaths(A[s])[0] for s in segs)}, {a.b} {sum(deaths(B[s])[0] for s in segs)}')
    for s in dd[:a.show]:
        print(f'     {s}: {deaths(A[s])} | {deaths(B[s])}')
    for f in ('wind', 'force', 'weather'):
        n = sum(1 for s in segs if ws_norm(wa[s][f] or '') == ws_norm(wb[s][f] or ''))
        print(f'  segment {f:8} agree {n}/{len(segs)} ({100 * n / len(segs):.1f}%)')


if __name__ == '__main__':
    main()
