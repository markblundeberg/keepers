"""A second, independent reading of the chunks where the first pass's errors
cluster (primary chunks that mention the light, the lantern, striking,
killing or catching): the same prompt, one chunk per call (the first pass
read about four per call), cached apart. Where the two readings differ is
where a third look is needed; where they agree, the first stands.

The test, before any adjudication: on a year's T3 sample, how many fields T3
found wrong does the second reading flag (by differing from the first), and
how many fields T3 confirmed does it flag too (work for an adjudicator)?

Run: python3 -I tools/second_reading.py run <year> [--workers 10]  ->  data/obs/<year>_v4b.jsonl
     python3 -I tools/second_reading.py eval <year>
"""
import argparse, collections, concurrent.futures as cf, difflib, hashlib, json, os, re, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA, ws_norm, ws_norm_with_map
from extract import BEHAVIOURS, CACHE, EFFORT, MODEL, call, load_chunks
from review import LANTERN, rules_text
from check_obs import IN_QUOTE, date_ok, inside
from review_eval import FIELDS, norm
import normalize, records


def todo(year):
    return [c for c in load_chunks(year) if c['observations'] == 'primary' and LANTERN.search(c['text'])]


def run(year, workers):
    cs = todo(year)
    out, cost = {}, 0.0
    with cf.ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(call, year, [c], 'v4b'): c for c in cs}
        for i, f in enumerate(cf.as_completed(futs), 1):
            c = futs[f]
            try:
                res, _ = f.result()
            except Exception as e:
                print('  FAILED', c['id'], e, flush=True)
                continue
            got = {x['chunk']: x for x in res['structured_output']['chunks']}
            out[c['id']] = {'chunk': c['id'], 'obs': got.get(c['id'], {}).get('obs')}
            cost += res.get('total_cost_usd', 0) or 0
            if i % 25 == 0:
                print(f'  {i}/{len(cs)}; ${cost:.2f}', flush=True)
    with open(os.path.join(DATA, 'obs', f'{year}_v4b.jsonl'), 'w') as fo:
        for c in cs:
            if c['id'] in out:
                fo.write(json.dumps(out[c['id']], ensure_ascii=False) + '\n')
    print(f'{year}: second reading of {len(out)}/{len(cs)} chunks, {sum(len(r["obs"] or []) for r in out.values())} observations; ${cost:.2f}')


def match(o, cands):
    """The second reading's observation for a first-reading one: same quote region, station, species."""
    return max(cands, key=lambda c: (difflib.SequenceMatcher(None, c['quote'], o['quote']).ratio()
                                     + 2 * (norm(c['station']) == norm(o['station'])) + (norm(c['species']) == norm(o['species']))
                                     + 0.5 * (c['behaviour'] == o['behaviour'])), default=None)


def same(f, a, b):
    """Do two readings of a field agree once wording that changes no value is set aside ("at 3 p.m." and "3 p.m.";
    "the Longstone" and "Longstone"; "Swallows" and "Swallow")?"""
    if f in ('behaviour', 'at_light', 'date_iso'):
        return a == b
    if not a or not b:
        return not a and not b
    if f == 'time':
        return normalize.time_of_day(a)[:3] == normalize.time_of_day(b)[:3] and normalize.time_of_day(a)[0] != 'unparsed' \
            or words(a) == words(b)
    if f == 'count':
        return normalize.count(a) == normalize.count(b) and normalize.count(a)[0] is not None or words(a) == words(b)
    if f == 'direction':
        return normalize.direction(a) == normalize.direction(b) and normalize.direction(a)[0] is not None or words(a) == words(b)
    if f == 'wind':
        return records.wind_deg(a)[0] is not None and records.wind_deg(a)[0] == records.wind_deg(b)[0] or words(a) == words(b)
    if f == 'force':
        return records.force_bft(a) is not None and records.force_bft(a) == records.force_bft(b) or words(a) == words(b)
    return words(a) == words(b)


def words(v):
    w = re.findall(r'[a-z0-9]+', str(v).lower().replace('æ', 'ae'))
    w = [x[:-1] if len(x) > 3 and x.endswith('s') else x for x in w if x not in ('the', 'at', 'a', 'of', 'about')]
    return w


def pair(A, B):
    """One-to-one pairs of two readings' observations of a chunk, best first; the rest are each reading's alone."""
    score = lambda a, b: (difflib.SequenceMatcher(None, a['quote'], b['quote']).ratio() + 2 * (words(a['station']) == words(b['station']))
                          + 1.5 * (words(a['species']) == words(b['species'])) + 0.5 * (a['behaviour'] == b['behaviour'])
                          + 0.5 * (a['date_iso'] == b['date_iso']))
    cand = sorted(((score(a, b), i, j) for i, a in enumerate(A) for j, b in enumerate(B)), reverse=True)
    used_a, used_b, pairs = set(), set(), []
    for sc, i, j in cand:
        if sc < 2.0 or i in used_a or j in used_b:      # not the same station and species, nor a near-identical quote
            continue
        used_a.add(i)
        used_b.add(j)
        pairs.append((i, j))
    return sorted(pairs), [i for i in range(len(A)) if i not in used_a], [j for j in range(len(B)) if j not in used_b]


DISPUTE_FIELDS = ['station', 'date_iso', 'species', 'count', 'behaviour', 'at_light', 'time', 'direction', 'wind', 'force', 'weather']


def disputes(year):
    first = {json.loads(l)['chunk']: json.loads(l) for l in open(os.path.join(DATA, 'obs', f'{year}_v4.jsonl'))}
    second = {json.loads(l)['chunk']: json.loads(l) for l in open(os.path.join(DATA, 'obs', f'{year}_v4b.jsonl'))}
    out = {}
    for c, b in second.items():
        A, B = first[c]['obs'] or [], b['obs'] or []
        pairs, only_a, only_b = pair(A, B)
        fields = [(i, j, f) for i, j in pairs for f in DISPUTE_FIELDS if not same(f, A[i].get(f), B[j].get(f))]
        out[c] = {'pairs': pairs, 'fields': fields, 'only_a': only_a, 'only_b': only_b}
    return first, second, out


def diff(year):
    first, second, d = disputes(year)
    nf = collections.Counter(f for x in d.values() for _, _, f in x['fields'])
    print(f'{year}: {len(d)} chunks read twice; pairs {sum(len(x["pairs"]) for x in d.values())}; '
          f'first reading alone {sum(len(x["only_a"]) for x in d.values())}, second alone {sum(len(x["only_b"]) for x in d.values())}; '
          f'disputed fields {sum(nf.values())} {dict(nf.most_common())}; chunks with any dispute '
          f'{sum(1 for x in d.values() if x["fields"] or x["only_a"] or x["only_b"])}')
    return d


ADJ_SCHEMA = {'type': 'object', 'required': ['fields', 'lone'], 'properties': {
    'fields': {'type': 'array', 'items': {'type': 'object', 'required': ['id', 'choice', 'value', 'why'], 'properties': {
        'id': {'type': 'string'}, 'choice': {'type': 'string', 'enum': ['1', '2', 'neither']}, 'value': {'type': ['string', 'null']},
        'why': {'type': 'string'}}}},
    'lone': {'type': 'array', 'items': {'type': 'object', 'required': ['id', 'keep', 'why'], 'properties': {
        'id': {'type': 'string'}, 'keep': {'type': 'boolean'}, 'why': {'type': 'string'}}}}}}

ADJ_BRIEF = '''Thank you for helping. I'm a Claude agent turning a Victorian bird-migration report ({year}) back into data: lighthouse and light-vessel keepers' records of birds, printed by a British Association committee. Two readers extracted observations from the CHUNK below independently, following the same rules (at the end). Where they agree, their reading stands. Below are the places where they differ. Please decide each from the text alone.

CONTEXT (what comes before the chunk; observations come only from the chunk, but a heading here may govern it):
<<<{context}>>>
CHUNK [{chunk}] (coast: {coast}; section: {title}; layout: {layout}):
<<<{text}>>>

FIELDS THE READERS DISAGREE ON. Each names the observation (as the two readers have it) and the two values:
{fields}

OBSERVATIONS ONLY ONE READER EXTRACTED:
{lone}

For each field: choice "1" or "2" for the reading the text supports, or "neither" with the right value (copied exactly from the chunk, or null when the text gives nothing for it; for at_light "true" or "false"; for behaviour one of the rule's words; for date_iso an ISO date). Both may be acceptable: then pick the one that follows the rules more closely. For each lone observation: keep it if it is a real observation by the rules that the other reader missed (the other reader may have folded it into another observation; then drop it only if that other observation already carries its kind and its numbers), else drop it. In `why`, a few words from the text.

THE EXTRACTION RULES:
{rules}'''


def show(o):
    return json.dumps({k: o.get(k) for k in ('quote', 'station', 'date', 'species', 'count', 'behaviour', 'at_light', 'time', 'direction',
                                             'wind', 'force', 'weather')}, ensure_ascii=False)


def adj_call(year, c, prompt):
    h = hashlib.sha256((MODEL + EFFORT + json.dumps(ADJ_SCHEMA) + prompt).encode()).hexdigest()[:24]
    path = os.path.join(CACHE, f'adj_{h}.json')
    if os.path.exists(path):
        return json.load(open(path))
    cmd = ['systemd-run', '--user', '--scope', '-q', '-p', 'MemoryMax=3G', '-p', 'MemorySwapMax=0',
           'claude', '-p', '--safe-mode', '--model', MODEL, '--effort', EFFORT, '--tools', '',
           '--no-session-persistence', '--output-format', 'json', '--json-schema', json.dumps(ADJ_SCHEMA)]
    for attempt in range(3):
        p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=3600)
        try:
            res = json.loads(p.stdout)
        except json.JSONDecodeError:
            res = {'is_error': True}
        if not res.get('is_error') and res.get('structured_output'):
            break
        time.sleep(30 * (attempt + 1))
    else:
        raise RuntimeError(f'{c["id"]}: adjudication failed')
    json.dump(res, open(path, 'w'))
    return res


def adjudicate(year, workers):
    """Each chunk with a dispute to a third reader, which decides only the disputes; the merged observations are
    built from its decisions, so a field both readings agree on cannot change."""
    first, second, d = disputes(year)
    chunks = {c['id']: c for c in load_chunks(year)}
    rules = rules_text()
    jobs = {}
    for cid, x in d.items():
        if not (x['fields'] or x['only_a'] or x['only_b']):
            continue
        A, B = first[cid]['obs'], second[cid]['obs']
        fl = '\n'.join(f'[f{n}] {f}: reading 1 {json.dumps(A[i].get(f), ensure_ascii=False)}; reading 2 '
                       f'{json.dumps(B[j].get(f), ensure_ascii=False)}\n   observation (reading 1): {show(A[i])}\n   observation (reading 2): {show(B[j])}'
                       for n, (i, j, f) in enumerate(x['fields']))
        lo = '\n'.join([f'[a{i}] (reading 1 only) {show(A[i])}' for i in x['only_a']] + [f'[b{j}] (reading 2 only) {show(B[j])}' for j in x['only_b']])
        c = chunks[cid]
        jobs[cid] = ADJ_BRIEF.format(year=year, context=c['context'], chunk=cid, coast=c['coast'], title=c['title'] or '-', layout=c['layout'],
                                     text=c['text'], fields=fl or '(none)', lone=lo or '(none)', rules=rules)
    out, cost = {}, 0.0
    with cf.ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(adj_call, year, chunks[cid], p): cid for cid, p in jobs.items()}
        for f in cf.as_completed(futs):
            cid = futs[f]
            try:
                res = f.result()
            except Exception as e:
                print('  FAILED', cid, e, flush=True)
                continue
            out[cid] = res['structured_output']
            cost += res.get('total_cost_usd', 0) or 0
    merged, log = merge(year, first, second, d, out, chunks)
    with open(os.path.join(DATA, 'obs', f'{year}_v4m.jsonl'), 'w') as fo:
        for cid in first:
            fo.write(json.dumps({'chunk': cid, 'obs': merged.get(cid, first[cid]['obs']), 'merged': cid in merged}, ensure_ascii=False) + '\n')
    json.dump(log, open(os.path.join(DATA, 'obs', f'{year}_v4m_decisions.json'), 'w'), indent=1, ensure_ascii=False)
    n = collections.Counter(x['kind'] for x in log)
    print(f'{year}: adjudicated {len(out)}/{len(jobs)} chunks; ${cost:.2f}; decisions {dict(n)}')


def widen(text, qa, qb, v, cap=600):
    """The stretch of the chunk from the first reading's quote to the value it now carries (through the second
    reading's quote, which holds it), as printed; None if over cap characters or not found."""
    t, m = ws_norm_with_map(text)
    a = t.find(ws_norm(qa))
    if a < 0:
        return None
    spans = [(a, a + len(ws_norm(qa)))]
    b = t.find(ws_norm(qb))
    if b >= 0 and ws_norm(v) in ws_norm(qb):
        spans.append((b, b + len(ws_norm(qb))))
    else:
        hits = [k.start() for k in re.finditer(re.escape(ws_norm(v)), t)]
        if not hits:
            return None
        h = min(hits, key=lambda k: abs(k - a))
        spans.append((h, h + len(ws_norm(v))))
    lo, hi = min(x for x, _ in spans), max(y for _, y in spans)
    if hi - lo > cap:
        return None
    return text[m[lo]:m[hi - 1] + 1]


# The fields the merge takes from the third reader: where the first reading's errors fall (T3), all one way. The
# others (species, station, date, wind, force, weather, direction) differ between readings mostly in wording, and
# taking them broke the one-species-per-observation rule (1880: "Thrushes, Blackbirds, and Ring Ouzels").
ADOPT = {'behaviour', 'at_light', 'time', 'count'}


def merge(year, first, second, d, decisions, chunks):
    merged, log = {}, []
    for cid, dec in decisions.items():
        A, B, x, c = first[cid]['obs'], second[cid]['obs'], d[cid], chunks[cid]
        new = {i: dict(o, first_index=i) for i, o in enumerate(A)}       # first_index: which first-reading observation it is
        by_id = {y['id'].strip('[]'): y for y in dec['fields']}
        for n, (i, j, f) in enumerate(x['fields']):
            y = by_id.get(f'f{n}')
            if f not in ADOPT:
                log.append({'chunk': cid, 'kind': 'field: not adopted (first kept)', 'field': f, 'first': A[i].get(f),
                            'second': B[j].get(f), 'decided': y['choice'] if y else None})
                continue
            if not y:
                log.append({'chunk': cid, 'kind': 'field: no decision (first kept)', 'field': f})
                continue
            if y['choice'] == '2':
                v = B[j].get(f)
            elif y['choice'] == 'neither':
                v = y['value']
                if f == 'at_light':
                    v = str(v).lower() == 'true'
                elif f in ('quote', 'station', 'species', 'count', 'time', 'direction', 'wind', 'force', 'weather') and v and \
                        not inside(v, c['text']) and not inside(v, c['context']):
                    log.append({'chunk': cid, 'kind': 'field: "neither" value not in the text (first kept)', 'field': f, 'value': v})
                    continue
                elif f == 'behaviour' and v not in BEHAVIOURS:
                    log.append({'chunk': cid, 'kind': 'field: "neither" behaviour unknown (first kept)', 'field': f, 'value': v})
                    continue
            else:
                v = A[i].get(f)
            if f == 'date_iso' and y['choice'] == '2':      # the date's words travel with its reading
                new[i]['date'] = B[j]['date']
                new[i]['from_context'] = sorted(set(x for x in A[i]['from_context'] if x != 'date') |
                                                ({'date'} & set(B[j]['from_context'])))
            elif f == 'date_iso' and y['choice'] == 'neither' and not date_ok(A[i]['date'], v, ocr=c['reading'] == 'ocr'):
                log.append({'chunk': cid, 'kind': 'field: "neither" date disagrees with the words (first kept)', 'field': f, 'value': v})
                continue
            if v != A[i].get(f):
                new[i][f] = v
                new[i].setdefault('adjudicated', []).append(f)
                if f in IN_QUOTE and v and not inside(v, new[i]['quote']):
                    q = widen(c['text'], new[i]['quote'], B[j]['quote'], v)
                    if q:
                        new[i]['quote'] = q
                    else:
                        new[i][f] = A[i].get(f)
                        new[i]['adjudicated'].remove(f)
                        log.append({'chunk': cid, 'kind': 'field: chosen value too far from the quote (first kept)', 'field': f, 'value': v})
                        continue
            log.append({'chunk': cid, 'kind': f'field: {y["choice"]}', 'field': f, 'first': A[i].get(f), 'second': B[j].get(f), 'chosen': v,
                        'why': y['why']})
        lone = {y['id'].strip('[]'): y for y in dec['lone']}
        keep_b = []
        for i in x['only_a']:
            y = lone.get(f'a{i}')
            if y and not y['keep']:
                del new[i]
            log.append({'chunk': cid, 'kind': 'lone first: ' + ('kept' if not y or y['keep'] else 'dropped'), 'quote': A[i]['quote'],
                        'why': y['why'] if y else None})
        for j in x['only_b']:
            y = lone.get(f'b{j}')
            if y and y['keep']:
                keep_b.append(dict(B[j], adjudicated=['added from the second reading']))
            log.append({'chunk': cid, 'kind': 'lone second: ' + ('kept' if y and y['keep'] else 'dropped'), 'quote': B[j]['quote'],
                        'why': y['why'] if y else None})
        t = ws_norm(c['text'])
        pos = lambda o: (t.find(ws_norm(o['quote'])) if t.find(ws_norm(o['quote'])) >= 0 else 10 ** 6)
        obs = [new[i] for i in sorted(new)]
        span = lambda o: (pos(o), pos(o) + len(ws_norm(o['quote'])))
        for o in keep_b:                                # in text order, after the first reading's observations at that place
            # the third reader kept some that repeat a first-reading observation in other words (1881: a third of a
            # sample): one with the same bird whose quote overlaps this one's is the same observation
            a0, a1 = span(o)
            dup = next((x for x in obs if words(x['species']) == words(o['species']) and a0 < span(x)[1] and span(x)[0] < a1), None)
            if dup is not None and a0 < 10 ** 6:
                log.append({'chunk': cid, 'kind': 'lone second: kept, but repeats a first-reading observation (dropped)',
                            'quote': o['quote'], 'repeats': dup['quote']})
                continue
            k = next((n for n, a in enumerate(obs) if pos(a) > pos(o)), len(obs))
            obs.insert(k, o)
        merged[cid] = obs
    return merged, log


def evaluate(year):
    t3 = json.load(open(os.path.join(DATA, 'checks', f't3_{year}_v4.json')))
    first = {json.loads(l)['chunk']: json.loads(l) for l in open(os.path.join(DATA, 'obs', f'{year}_v4.jsonl'))}
    second = {json.loads(l)['chunk']: json.loads(l) for l in open(os.path.join(DATA, 'obs', f'{year}_v4b.jsonl'))}
    planted = {(p['item'], p['field']) for p in t3['plants']}
    n = collections.Counter()
    by_field = collections.defaultdict(collections.Counter)
    notes = []
    for it in t3['items']:
        v = t3['verdicts'].get(str(it['item'])) or t3['verdicts'].get(it['item'])
        b = second.get(it['chunk'])
        if not v or not b or not b['obs']:
            continue
        n['items'] += 1
        o = first[it['chunk']]['obs'][it['k']]
        m = match(o, b['obs'])
        for f in FIELDS:
            if (it['item'], f) in planted:
                continue
            vd = v['fields'][f]['verdict']
            differs = norm(o.get(f)) != norm(m.get(f))
            if vd == 'wrong':
                ps = v['fields'][f]['print_says']
                key = 'wrong: flagged' if differs else 'wrong: same in both'
                n[key] += 1
                by_field[f][key] += 1
                notes.append((key, it['item'], f, o.get(f), m.get(f), (ps or '')[:60]))
            elif vd == 'ok':
                key = 'ok: flagged' if differs else 'ok: same in both'
                n[key] += 1
                by_field[f][key] += 1
                if differs:
                    notes.append((key, it['item'], f, o.get(f), m.get(f)))
    print(f'{year}: {n["items"]} T3 items in chunks read twice')
    print(f'  fields T3 found wrong: flagged by the second reading {n["wrong: flagged"]}, same in both {n["wrong: same in both"]}')
    print(f'  fields T3 confirmed:   flagged {n["ok: flagged"]}, same in both {n["ok: same in both"]}')
    for f in FIELDS:
        if by_field[f]:
            print(f'    {f:9} {dict(by_field[f])}')
    for x in sorted(notes, key=str):
        print('  ', x)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('step', choices=['run', 'eval', 'diff', 'adjudicate'])
    ap.add_argument('year', type=int)
    ap.add_argument('--workers', type=int, default=10)
    a = ap.parse_args()
    {'run': lambda: run(a.year, a.workers), 'eval': lambda: evaluate(a.year), 'diff': lambda: diff(a.year), 'adjudicate': lambda: adjudicate(a.year, a.workers)}[a.step]()
