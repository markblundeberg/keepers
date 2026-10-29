"""Compare the LLM extractor with the deterministic rules, segment by segment,
on what both can read: wind direction, force and weather from the bracket;
clock times; flight directions; and whether a segment has deaths, strikes or
birds at the light. Disagreements are listed for reading; they tell which
method errs where.

Run: python3 -I tools/compare.py 1887 [--show 15]
"""
import argparse, collections, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA, ws_norm
from rules import (BRACKET, DEATH, LANTERN, STRUCK, clock_times, compass_key, flight_directions,
                   parse_bracket, weather)


def k(s):
    """Loose key for comparing printed strings: no case, spaces or final stops."""
    return re.sub(r'[\s.,;:]', '', (s or '').lower()) or None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('year', type=int)
    ap.add_argument('--ver', default='v2')
    ap.add_argument('--show', type=int, default=15)
    a = ap.parse_args()
    p = os.path.join(DATA, 'pilot')
    segs = [json.loads(l) for l in open(os.path.join(p, f'segments_{a.year}.jsonl'))]
    obs = [json.loads(l) for l in open(os.path.join(p, f'obs_llm_{a.year}_{a.ver}.jsonl'))]
    wx = {w['seg_id']: w for w in (json.loads(l) for l in open(os.path.join(p, f'wx_llm_{a.year}_{a.ver}.jsonl')))}
    by = collections.defaultdict(list)
    for o in obs:
        by[o['seg_id']].append(o)
    tally = collections.defaultdict(collections.Counter)
    diffs = collections.defaultdict(list)

    def note(field, agree, sid, msg):
        tally[field]['agree' if agree else 'differ'] += 1
        if not agree:
            diffs[field].append(f'{sid}: {msg}')

    for s in segs:
        sid = s['seg_id']
        if sid not in wx:
            continue
        t = ws_norm(s['text'])
        L = wx[sid]
        R = weather(t)
        # weather: does the LLM's choice match one of the rules' brackets?
        rd = [r['dir_raw'] for r in R if r['dir_raw']]
        rf = [r['force_raw'] for r in R if r['force_raw']]
        rw = [r['weather_raw'] for r in R if r['weather_raw']]
        for field, mine, theirs in (('wind', rd, L['wind']), ('force', rf, L['force']), ('weather', rw, L['weather'])):
            if not mine and not theirs:
                continue
            ok = bool(theirs) and any(k(theirs) == k(x) or (field == 'wind' and compass_key(theirs) and
                                                              compass_key(theirs) == compass_key(x)) for x in mine)
            note(field, ok, sid, f'rules {mine} | llm {theirs!r} | {t[-70:]!r}')
        # clock times outside weather brackets
        body = BRACKET.sub(lambda m: ' ' if parse_bracket(m.group(1)) else m.group(0), t)
        rt = collections.Counter(clock_times(body))
        lt = collections.Counter()
        seen_t = set()
        for o in by[sid]:
            if o['time'] and o['time'] not in seen_t:
                seen_t.add(o['time'])
                lt.update(clock_times(o['time']))
        if rt or lt:
            note('clock times', set(rt) == set(lt), sid, f'rules {sorted(rt)} | llm {sorted(lt)} | {t[:110]!r}')
        # flight directions (destination points)
        rdir = {d[1] for d in flight_directions(body)}
        ldir = {d[1] for o in by[sid] if o['direction'] for d in flight_directions(o['direction'])}
        if rdir or ldir:
            note('flight to', rdir == ldir, sid, f'rules {sorted(rdir)} | llm {sorted(ldir)} | {t[:110]!r}')
        # deaths, strikes, light
        for field, rx, pred in (('any dead', DEATH, lambda o: o['behaviour'] == 'dead'),
                                ('any struck', STRUCK, lambda o: o['behaviour'] == 'struck'),
                                ('any at light', LANTERN, lambda o: o['at_light'])):
            r_has = bool(rx.search(body))
            l_has = any(pred(o) for o in by[sid])
            if r_has or l_has:
                note(field, r_has == l_has, sid, f'rules {r_has} | llm {l_has} | {t[:120]!r}')

    for field, c in tally.items():
        tot = c['agree'] + c['differ']
        print(f"{field:14} {c['agree']:5}/{tot:<5} agree ({100 * c['agree'] / tot:.1f}%)")
    for field, d in diffs.items():
        print(f'\n## {field}: {len(d)} disagreements')
        for x in d[:a.show]:
            print('  ', x)


if __name__ == '__main__':
    main()
