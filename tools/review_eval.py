"""Did the review help? On a year's T3 sample (first pass, read against the
print): for each sampled observation, find its reviewed version, then count
the fields T3 found wrong that the review changed toward the print, and the
fields T3 found right that the review changed (possible new errors, to read).

Run: python3 -I tools/review_eval.py 1879 [v4r | v4m]   (the review pass; the two readings merged)
"""
import difflib, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA

FIELDS = ['station', 'date_iso', 'species', 'count', 'behaviour', 'at_light', 'time', 'direction', 'wind', 'force', 'weather']
norm = lambda v: re.sub(r'[\s.,;:"\'()]+', ' ', str(v).lower()).strip()


def main(year, kind='v4r'):
    t3 = json.load(open(os.path.join(DATA, 'checks', f't3_{year}_v4.json')))
    rev = {json.loads(l)['chunk']: json.loads(l) for l in open(os.path.join(DATA, 'obs', f'{year}_{kind}.jsonl'))}
    flag = {'v4r': 'reviewed', 'v4m': 'merged'}[kind]
    first = {json.loads(l)['chunk']: json.loads(l) for l in open(os.path.join(DATA, 'obs', f'{year}_v4.jsonl'))}
    planted = {(p['item'], p['field']) for p in t3['plants']}
    classes = None
    if os.path.exists(os.path.join(DATA, 'checks', 't3review', f'{year}_run2.json')):
        from t3_review import compare
        classes = compare(year, show=False)[1]
    fixed = still = broke = kept_ok = 0
    notes = []
    for it in t3['items']:
        v = t3['verdicts'].get(str(it['item'])) or t3['verdicts'].get(it['item'])
        r = rev.get(it['chunk'])
        if not v or not r or not r.get(flag):
            continue
        o = first[it['chunk']]['obs'][it['k']]
        cands = r['obs']
        same = [c for c in cands if c.get('first_index') == it['k']]   # the merge says which observation it is
        if kind == 'v4m':
            if not same:
                notes.append(('dropped by the merge', it['item']))
                continue
            cands = same
        # siblings share a quote (one observation per station of a sentence): match quote and station first
        best = max(cands, key=lambda c: (difflib.SequenceMatcher(None, c['quote'], o['quote']).ratio()
                                         + 2 * (norm(c['station']) == norm(o['station'])) + (c['species'] == o['species'])
                                         + 0.5 * (c['behaviour'] == o['behaviour'])), default=None)
        if not best:
            continue
        for f in FIELDS:
            if (it['item'], f) in planted:
                continue
            vd = v['fields'][f]['verdict']
            if vd == 'wrong' and classes is not None and classes.get(f'{it["item"]}:{f}') != 'extraction':
                continue                                # a flag that isn't an extraction error (tools/t3_review.py)
            old, new = o.get(f), best.get(f)
            if vd == 'wrong':
                ps = v['fields'][f]['print_says']
                if norm(new) != norm(old) and (ps is None or norm(new) in norm(ps) or norm(ps) in norm(new) or
                                               (f == 'at_light' and str(new).lower() in norm(ps)) or (f == 'behaviour' and new in norm(ps))):
                    fixed += 1
                else:
                    still += 1
                    notes.append(('still', it['item'], f, old, new, (ps or '')[:60]))
            elif vd == 'ok':
                if norm(new) != norm(old):
                    broke += 1
                    notes.append(('changed a confirmed field', it['item'], f, old, new))
                else:
                    kept_ok += 1
    print(f'{year}: of the fields T3 found wrong, the review fixed {fixed}, left {still}; of the fields T3 confirmed, '
          f'the review kept {kept_ok} and changed {broke}')
    for n in notes:
        print('  ', n)
    added = sum(max(0, len(rev[c]['obs']) - len(first[c]['obs'])) for c in rev if rev[c].get(flag))
    print(f'observations added by the review (net): {added}')


if __name__ == '__main__':
    main(int(sys.argv[1]), *sys.argv[2:3])
