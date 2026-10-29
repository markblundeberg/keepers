"""The transcription checks of CHECKS.md on the pilot data: T1, T2, T4, T5.

T1  every segment is the exact source text at its offsets; every quote is an
    exact substring of its segment and of the source file (only whitespace
    may differ: the text's line breaks become spaces)
T2  every copied field lies inside its own quote; a segment's weather fields
    lie inside the segment
T4  completeness: bird-like words in a segment that no quote covers
T5  dates: non-decreasing through each section, and in the month of the
    heading above them

--break NAME damages a copy of the data as CHECKS.md says, and that check
must then fail. Exit status 1 if any check fails.

Run: python3 -I tools/validate.py 1887 [--break t1|t2|t4|t5]
"""
import argparse, collections, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA, MONTH_NUM, read_source, ws_norm, ws_norm_with_map
from rules import weather

FIELDS = ['species', 'count', 'time', 'direction', 'other_dates', 'specimen']
WX = ['wind', 'force', 'weather']
# capitalised words that are not birds, for T4
NOT_BIRDS = set('''A I M P L H V N S E W One Two Three Four Five Six Seven Eight Nine Ten Also The This These
Several Many Large Great Number Numbers Same See Wind Light Very About Some Few Flock Flocks Hundreds Thousands
No None Nothing Saw Seen Heard Killed Caught Shot Dead On At In Of To From With And Or But Not Night Day Morning
Evening Noon Midnight Do Did Was Were Had Have Has Is It Its They He We Mr Messrs Rev Dr Esq Island Isle Rock
Shore Sea Coast Head Point Bay River Harbour Breakwater Lighthouse Lantern Station Vessel Ship Deck Gallery
Essex Norfolk Suffolk Lincolnshire Yorkshire Durham Kent Wales England Scotland Ireland Man Guernsey Breydon
Denes Carlisle Silloth Cockermouth Covenham Grainsby Park Hall Keswick Beaufort Scale Field Naturalist Zoologist
January February March April May June July August September October November December First Last Second
Afterwards Again All Altogether Between During Each Every Most Probably Previous Remained Small Young Old Male
Female Males Females Adult Adults Immature Pair Pairs Wings Wing Leg Legs Sent Received Bird Birds'''.split())
BIRDISH = re.compile(r'\b(larks?|thrush(?:es)?|starlings?|blackbirds?|finch(?:es)?|sparrows?|swallows?|'
                     r'martins?|wagtails?|wrens?|crows?|gulls?|ducks?|geese|plovers?|snipe|woodcock|'
                     r'linnets?|redwings?|fieldfares?|goldcrests?|robins?|birds?|flycatchers?)\b')


def locate(quote, seg):
    """Source offsets (a, b) of the first occurrence of quote in seg, or None."""
    n, idx = ws_norm_with_map(seg['text'])
    q = ws_norm(quote)
    k = n.find(q) if q else -1
    if k < 0:
        return None
    return seg['start'] + idx[k], seg['start'] + idx[k + len(q) - 1] + 1


def load(year, ver='v2'):
    p = os.path.join(DATA, 'pilot')
    segs = [json.loads(l) for l in open(os.path.join(p, f'segments_{year}.jsonl'))]
    obs = [json.loads(l) for l in open(os.path.join(p, f'obs_llm_{year}_{ver}.jsonl'))]
    wx = [json.loads(l) for l in open(os.path.join(p, f'wx_llm_{year}_{ver}.jsonl'))]
    return segs, obs, wx


def damage(name, segs, obs, wx):
    """The deliberate breaks of CHECKS.md, applied to copies."""
    if name == 't1':      # alter one character in one quote
        o = next(o for o in obs if len(o['quote']) > 20)
        q = o['quote']
        o['quote'] = q[:10] + ('x' if q[10] != 'x' else 'y') + q[11:]
        return f"altered quote of {o['obs_id']}"
    if name == 't2':      # swap two segments' winds
        a = next(w for w in wx if w['wind'])
        b = next(w for w in wx if w['wind'] and w['wind'] != a['wind'] and w['seg_id'][:8] == a['seg_id'][:8])
        a['wind'], b['wind'] = b['wind'], a['wind']
        return f"swapped winds of {a['seg_id']} and {b['seg_id']}"
    if name == 't4':      # delete one segment's records
        sid = collections.Counter(o['seg_id'] for o in obs).most_common(1)[0][0]
        obs[:] = [o for o in obs if o['seg_id'] != sid]
        return f'deleted the records of {sid}'
    if name == 't5':      # shift one date block a month
        key = (segs[200]['section'], segs[200]['date'])
        for s in segs:
            if (s['section'], s['date']) == key:
                y, m, d = s['date'].split('-')
                s['date'] = f'{y}-{int(m) % 12 + 1:02d}-{d}'
        return f'shifted {key} a month'
    raise SystemExit(f'unknown break {name}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('year', type=int)
    ap.add_argument('--ver', default='v2')
    ap.add_argument('--break', dest='brk')
    ap.add_argument('--show', type=int, default=8)
    a = ap.parse_args()
    src = read_source(a.year)
    segs, obs, wx = load(a.year, a.ver)
    if a.brk:
        print('BREAK:', damage(a.brk, segs, obs, wx))
    seg = {s['seg_id']: s for s in segs}
    fails = collections.defaultdict(list)
    n = collections.Counter()

    # T1
    for s in segs:
        n['T1 segments'] += 1
        if src[s['start']:s['end']] != s['text']:
            fails['T1'].append(f"{s['seg_id']}: segment text differs from source at its offsets")
    for o in obs:
        n['T1 quotes'] += 1
        s = seg.get(o['seg_id'])
        loc = locate(o['quote'], s) if s else None
        if not loc:
            fails['T1'].append(f"{o['obs_id']}: quote not in segment: {o['quote']!r}")
        elif ws_norm(src[loc[0]:loc[1]]) != ws_norm(o['quote']):
            fails['T1'].append(f"{o['obs_id']}: quote differs from source at {loc}")

    # T2
    for o in obs:
        q = ws_norm(o['quote'])
        for f in FIELDS:
            if o.get(f) is not None:
                n['T2 fields'] += 1
                if ws_norm(o[f]) not in q:
                    fails['T2'].append(f"{o['obs_id']}: {f} {o[f]!r} not in quote {o['quote']!r}")
    for w in wx:
        t = ws_norm(seg[w['seg_id']]['text'])
        for f in WX:
            if w.get(f) is not None:
                n['T2 weather fields'] += 1
                if ws_norm(w[f]) not in t:
                    fails['T2'].append(f"{w['seg_id']}: {f} {w[f]!r} not in segment")

    # T4: uncovered bird-like words; segments the extractor never returned
    by_seg = collections.defaultdict(list)
    for o in obs:
        by_seg[o['seg_id']].append(o)
    returned = {w['seg_id'] for w in wx}
    uncovered = collections.Counter()
    # flags already read and judged harmless (commentary, people, places): {seg_id: {"words": [...], "reason": ...}}
    rp = os.path.join(DATA, 'pilot', 'checks', f't4_reviewed_{a.year}.json')
    reviewed = json.load(open(rp)) if os.path.exists(rp) else {}
    n_reviewed = 0
    for s in segs:
        n['T4 segments'] += 1
        if s['seg_id'] not in returned:
            fails['T4'].append(f"{s['seg_id']}: not returned by the extractor")
            continue
        t = ws_norm(s['text'])
        cov = [False] * len(t)
        head = ws_norm(s['head'] or '')
        for i in range(len(head)):
            cov[i] = True
        for w in weather(t):
            for i in range(*w['span']):
                cov[i] = True
        for o in by_seg[s['seg_id']]:
            q = ws_norm(o['quote'])
            for m in re.finditer(re.escape(q), t) if q else ():
                for i in range(m.start(), m.end()):
                    cov[i] = True
        gaps = ''.join(c if not cv else ' ' for c, cv in zip(t, cov))
        words = [w for w in re.findall(r"\b[A-Z][a-z]+(?:[- ][A-Z][a-z]+)*", gaps)
                 if not all(x in NOT_BIRDS for x in re.split(r'[- ]', w))]
        words += BIRDISH.findall(gaps)
        if words and set(words) <= set(reviewed.get(s['seg_id'], {}).get('words', [])):
            n_reviewed += 1
        elif words:
            uncovered.update(words)
            fails['T4'].append(f"{s['seg_id']}: uncovered {words} in {s['text'][:60]!r}")

    # T5
    last = {}
    heads = [(m.start(), MONTH_NUM[m.group(1).capitalize()]) for m in
             re.finditer(r'^\s*(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\.?\s*$',
                         src, re.M)]
    for s in segs:
        if not s['date']:
            continue
        n['T5 dated segments'] += 1
        if s['section'] in last and s['date'] < last[s['section']]:
            fails['T5'].append(f"{s['seg_id']}: date {s['date']} before the previous {last[s['section']]}")
        last[s['section']] = s['date']
        hm = [m for p, m in heads if p < s['start']]
        if hm and hm[-1] != int(s['date'][5:7]):
            fails['T5'].append(f"{s['seg_id']}: date {s['date']} under the heading for month {hm[-1]}")

    n['T4 flags already reviewed'] = n_reviewed
    print('checked:', dict(n))
    ok = True
    for t in ('T1', 'T2', 'T4', 'T5'):
        f = fails.get(t, [])
        print(f'{t}: {"PASS" if not f else "FAIL"} ({len(f)} problems)')
        for x in f[:a.show]:
            print('   ', x)
        ok &= not f
    if uncovered:
        print('T4 uncovered words, most common:', uncovered.most_common(30))
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
