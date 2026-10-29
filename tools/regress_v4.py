"""Regression test for prompt v4: its reading of the 1887 English diaries
against the pilot's v2 reading (validated by T3: 1 error in 884 fields).
Each v4 observation is placed in the v2 diary segment that holds its quote;
per segment the (species, behaviour) multisets are compared, and for paired
observations count, time, direction and at_light; the station and date v4
copies are checked against the segment's own; the weather against v2's.

Run: python3 -I tools/regress_v4.py
"""
import bisect, collections, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA, ws_norm, ws_norm_with_map
import normalize

norm = lambda s: ' '.join((s or '').lower().replace('_', '').split()).strip(' .,;:')


def main():
    segs = [json.loads(l) for l in open(os.path.join(DATA, 'pilot', 'segments_1887.jsonl'))]
    v2 = collections.defaultdict(list)
    for l in open(os.path.join(DATA, 'pilot', 'obs_llm_1887_v2.jsonl')):
        o = json.loads(l)
        v2[o['seg_id']].append(o)
    wx2 = {}
    for l in open(os.path.join(DATA, 'pilot', 'wx_llm_1887_v2.jsonl')):
        w = json.loads(l)
        wx2[w['seg_id']] = w
    starts = [s['start'] for s in segs]
    chunks = {json.loads(l)['id']: json.loads(l) for l in open(os.path.join(DATA, 'chunks', '1887.jsonl'))}
    v4 = collections.defaultdict(list)
    unplaced = 0
    for l in open(os.path.join(DATA, 'obs', '1887_v4.jsonl')):
        r = json.loads(l)
        c = chunks[r['chunk']]
        if c['layout'] != 'diary':
            continue
        t, m = ws_norm_with_map(c['text'])
        for o in r['obs'] or []:
            q = ws_norm(o['quote'])
            cands = []
            i = t.find(q)
            while i >= 0:                      # every occurrence: a short quote ("Fieldfare") can recur in a chunk
                off = c['start'] + m[i]
                k = bisect.bisect_right(starts, off) - 1
                if k >= 0 and segs[k]['start'] <= off < segs[k]['end']:
                    cands.append(k)
                i = t.find(q, i + 1)
            if not cands:
                unplaced += 1
                continue
            named = [k for k in cands if o['station'] and norm(segs[k]['station_name']) in norm(o['station'])]
            v4[segs[(named or cands)[0]]['seg_id']].append(o)
    same_set = n = 0
    fields = collections.Counter()
    agree = collections.Counter()
    st_ok = st_n = dt_ok = dt_n = wx_ok = wx_n = 0
    examples = []
    for s in segs:
        a, b = v2.get(s['seg_id'], []), v4.get(s['seg_id'], [])
        if not a and not b:
            continue
        n += 1
        ka = collections.Counter((norm(o['species']), o['behaviour']) for o in a)
        kb = collections.Counter((norm(o['species']), o['behaviour']) for o in b)
        if ka == kb:
            same_set += 1
        elif len(examples) < 12:
            examples.append((s['seg_id'], dict(ka - kb), dict(kb - ka)))
        pool = list(b)
        for o in a:
            for j, p in enumerate(pool):
                if (norm(p['species']), p['behaviour']) == (norm(o['species']), o['behaviour']):
                    for f in ('count', 'time', 'direction', 'at_light'):
                        fields[f] += 1
                        agree[f] += (norm(str(o[f])) == norm(str(p[f])))
                    fields['count (normalised)'] += 1
                    agree['count (normalised)'] += normalize.count(o['count'])[:2] == normalize.count(p['count'])[:2]
                    fields['time (normalised)'] += 1
                    ta, tb = normalize.time_of_day(o['time']), normalize.time_of_day(p['time'])
                    agree['time (normalised)'] += (ta[:3] if ta else None) == (tb[:3] if tb else None)
                    pool.pop(j)
                    break
        for p in b:
            if p['station']:
                st_n += 1
                st_ok += norm(s['station_name']) in norm(p['station'])
            if p['date_iso']:
                dt_n += 1
                dt_ok += p['date_iso'].split('/')[0] == s['date']
        w = wx2.get(s['seg_id'])
        if w and b:
            for f in ('wind', 'force', 'weather'):
                vals = {norm(p[f]) for p in b if p[f]}
                if w.get(f):
                    wx_n += 1
                    wx_ok += norm(w[f]) in vals
    print(f'segments with observations in either: {n}; identical (species, behaviour) multisets: {same_set} ({same_set / n:.1%}); '
          f'v4 quotes not placed in a segment: {unplaced}')
    print('paired fields agree:', {f: f'{agree[f]}/{fields[f]} ({agree[f] / fields[f]:.1%})' for f in fields})
    print(f'station words name the segment\'s station: {st_ok}/{st_n}; date_iso = segment date: {dt_ok}/{dt_n}; '
          f'v2 weather fields found in v4: {wx_ok}/{wx_n}')
    print('totals: v2', sum(len(v) for v in v2.values()), 'v4', sum(len(v) for v in v4.values()))
    for e in examples:
        print('  ', e)


if __name__ == '__main__':
    main()
