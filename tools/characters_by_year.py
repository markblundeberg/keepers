"""Each station's light character for each year 1879-1887.

Witnesses: Findlay 1879 (the lights as compiled for that edition), Findlay
1887 (with a year column that gives a light's alteration years, "1841 /
1879"), and the reports' own station lists (1879, 1880). A character that
is the same in both editions holds throughout; one that differs changes in
the alteration year where Findlay 1887 gives one, and is uncertain between
the editions where it doesn't.

Run: python3 -I tools/characters_by_year.py census
"""
import argparse, csv, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA
from characters import parse
from match_findlay import agreed, by_id

ST = os.path.join(DATA, 'stations')


def signature(rows):
    """The parsed lights of a station's Findlay row(s), as a comparable tuple:
    kind, group, period, colours, alternating per light, sorted."""
    sig = []
    for r in rows:
        lights, _ = parse(r['character'], r['description'])
        for l in lights:
            sig.append((l['kind'], l['group'], l['period_s'], tuple(sorted(l['colours'])), l['alternating']))
    return tuple(sorted(sig, key=str))


def years(s):
    return [int(y) for y in re.findall(r'\b(1[6-8]\d\d)\b', s or '')]


def census():
    S = json.load(open(os.path.join(ST, 'stations.json')))
    M, R = agreed(), {ed: by_id(ed) for ed in ('findlay1879', 'findlay1887')}
    out = {'same': [], 'changed_dated': [], 'changed_undated': [], 'new': [], 'gone': [], 'neither': []}
    for s in S:
        m = M.get(s['id'], {})
        rows = {ed: [R[ed][x] for x in ([m[ed][0]] + m[ed][1]) if x] for ed in m if m[ed][0]}
        a, b = rows.get('findlay1879'), rows.get('findlay1887')
        if not a and not b:
            out['neither'].append(s['id'])
            continue
        if not a:
            out['new'].append((s['id'], years(b[0]['year'])))
            continue
        if not b:
            out['gone'].append(s['id'])
            continue
        sa, sb = signature(a), signature(b)
        if sa == sb:
            out['same'].append(s['id'])
            continue
        alts = [y for y in years(b[0]['year'])[1:] if 1879 <= y <= 1887]
        (out['changed_dated'] if alts else out['changed_undated']).append((s['id'], alts, a[0]['character'], b[0]['character']))
    for k, v in out.items():
        print(f'{k}: {len(v)}')
    for k in ('changed_dated', 'changed_undated'):
        print(f'--- {k}')
        for sid, alts, ca, cb in out[k]:
            print(f'  {sid}: {alts} | 1879 "{ca[:55]}" | 1887 "{cb[:55]}"')
    print('--- new (Findlay 1887 only):', out['new'])
    print('--- gone (Findlay 1879 only):', out['gone'])
    return out


# ---------- Edwards 1884: match stations to its rows ----------

from station_lists import run_helper
import concurrent.futures as cf

ED_SCHEMA = {'type': 'object', 'required': ['matches', 'notes'], 'properties': {
    'matches': {'type': 'array', 'items': {'type': 'object', 'required': ['id', 'row', 'confidence', 'note'], 'properties': {
        'id': {'type': 'string'}, 'row': {'type': ['string', 'null']},
        'confidence': {'type': 'string', 'enum': ['high', 'medium', 'low']}, 'note': {'type': ['string', 'null']}}}},
    'notes': {'type': 'string'}}}

ED_BRIEF = '''Thank you for helping. I'm a Claude agent rebuilding the records of the lighthouse keepers who reported bird migration to a British Association committee, 1879-1887. I need each of their stations matched to its entry in the appendix of E. Price Edwards's "Our Seamarks" (1884), a list of the principal lights of the British Isles corrected to March 1884, so the project knows each light's character in 1884.

Two tables (CSV; open each with the Read tool):
- {stations}: the stations, as the reports print them, with an id, a usual modern name, kind, every printed name, coasts, years, and their entries in Findlay's list of lights (1879 and 1887 editions: name and character).
- {edwards}: Edwards's entries: row id ("p183r4"), country, number, name, character and range as printed.

For each station, give the Edwards row that describes it, or null if Edwards has none (he lists principal lights only, so many minor lights and some light-vessels are missing; observers' stations are not lights). Watch for the usual traps: two places of one name (Start Point in Orkney and Devon), a lighthouse and the light-vessel off it, old and new names (Edwards may say "Haisborough" for the reports' "Hasbro'"). Say how sure you are and give a reason in note for anything not obvious. In notes, list anything I should check.'''


def edwards_inputs():
    S = json.load(open(os.path.join(ST, 'stations.json')))
    M, R = agreed(), {ed: by_id(ed) for ed in ('findlay1879', 'findlay1887')}
    d = os.path.join(ST, 'edwards')
    os.makedirs(d, exist_ok=True)
    sp = os.path.join(d, 'stations.csv')
    with open(sp, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['id', 'name', 'kind', 'printed_names', 'regions', 'years', 'findlay1879', 'findlay1887'])
        for s in S:
            m = M.get(s['id'], {})
            fl = {ed: (f"{R[ed][m[ed][0]]['name']}: {R[ed][m[ed][0]]['character']}" if m.get(ed, (None,))[0] else '')
                  for ed in ('findlay1879', 'findlay1887')}
            w.writerow([s['id'], s['name'], s['kind'], ' ; '.join(s['printed']), ' '.join(s['regions']), ' '.join(s['seen']),
                        fl['findlay1879'], fl['findlay1887']])
    return sp, os.path.join(DATA, 'lights', 'edwards1884.csv')


def edwards_match(run):
    out = os.path.join(ST, 'edwards', f'match_run{run}.json')
    if os.path.exists(out):
        return json.load(open(out))
    sp, ep = edwards_inputs()
    d, cost = run_helper(ED_BRIEF.format(stations=sp, edwards=ep), ED_SCHEMA, 'Read')
    d['_meta'] = {'run': run, 'cost_usd': cost}
    json.dump(d, open(out, 'w'), indent=1, ensure_ascii=False)
    return d


def edwards_compare():
    E = {r['row_id']: r for r in csv.DictReader(open(os.path.join(DATA, 'lights', 'edwards1884.csv')))}
    A, B = ({m['id']: m for m in json.load(open(os.path.join(ST, 'edwards', f'match_run{r}.json')))['matches']} for r in (1, 2))
    ids = [s['id'] for s in json.load(open(os.path.join(ST, 'stations.json')))]
    dis = [i for i in ids if A.get(i, {}).get('row') != B.get(i, {}).get('row')]
    print(f'{len(ids)} stations; matched run1 {sum(bool(A.get(i, {}).get("row")) for i in ids)}, run2 '
          f'{sum(bool(B.get(i, {}).get("row")) for i in ids)}; differ {len(dis)}; Edwards rows used '
          f'{len({A[i]["row"] for i in ids if A.get(i, {}).get("row")})} of {len(E)}')
    for i in dis:
        show = lambda m: f'{m["row"]}:{E[m["row"]]["name"]}' if m.get('row') else 'None'
        print(f'  {i}: run1 {show(A.get(i, {}))} ({A.get(i, {}).get("confidence")}) | run2 {show(B.get(i, {}))} ({B.get(i, {}).get("confidence")})')


# ---------- judge: one timeline of characters per station ----------

SOURCES = ['findlay1879', 'edwards1884', 'findlay1887', 'report1879', 'report1880']
J_SCHEMA = {'type': 'object', 'required': ['stations', 'notes'], 'properties': {
    'stations': {'type': 'array', 'items': {'type': 'object',
        'required': ['id', 'changed', 'what_changed', 'change_year', 'earliest', 'latest', 'states', 'wording', 'confidence', 'note'],
        'properties': {
            'id': {'type': 'string'}, 'changed': {'type': 'boolean'}, 'what_changed': {'type': ['string', 'null']},
            'change_year': {'type': ['integer', 'null']}, 'earliest': {'type': ['integer', 'null']}, 'latest': {'type': ['integer', 'null']},
            'states': {'type': 'array', 'items': {'type': 'object', 'required': ['from', 'to', 'source'], 'properties': {
                'from': {'type': 'integer'}, 'to': {'type': 'integer'}, 'source': {'type': 'string', 'enum': SOURCES}}}},
            'wording': {'type': ['string', 'null']}, 'confidence': {'type': 'string', 'enum': ['high', 'medium', 'low']},
            'note': {'type': ['string', 'null']}}}},
    'notes': {'type': 'string'}}}

J_BRIEF = """Thank you for helping. I'm a Claude agent rebuilding the records of the lighthouse keepers who reported bird migration to a British Association committee, 1879-1887. The project will draw each light flashing as it did on the night of each observation, so I need each light's character for each year 1879-1887, with the source for it.

The file {path} (JSON; open it with the Read tool) gives, for {n} stations, every witness I have:
- findlay1879 and findlay1887: the station's entries in Findlay's "Description and List of the Lighthouses of the World", 1879 and 1887 editions: name, character, description (which often gives the flashes or eclipses in words), and the year column. In the 1887 edition a second year there is the year of the light's latest alteration ("1841 / 1879": built 1841, altered 1879). An edition reflects the lights as its compiler knew them, a little before its date.
- edwards1884: the station's entry in the appendix of E. Price Edwards's "Our Seamarks", corrected to March 1884.
- report1879, report1880: the reports' own words for the light, from their station lists, where they give them.

For each station, decide:
- changed: did the light itself change between the 1879 and 1887 editions (its kind, number of flashes, period, colours, or the number of lights shown), as opposed to only the wording? The words changed in these years: Findlay 1879 says "intermittent" or "revolving" where 1887 may say "occulting" or "flashing" for the same light, writes "bright" or leaves it out, and puts flashes in the description rather than the character. A sector of red added or a light-vessel moved a little is a change only if it changes what a watcher at the station would see of its own light; say so in what_changed either way.
- if it changed: what changed; change_year where a source dates it (Findlay 1887's alteration year; a description that says when); else earliest and latest, the window the witnesses allow (Edwards's March 1884 state, the reports' 1879 and 1880 words).
- states: which source's text best describes the light in each span of years 1879-1887, as from-to spans covering the years the light existed (a light first lit in 1884 starts in 1884). For an unchanged light pick the clearest text (often findlay1887). For a changed light, the old text up to the change and the new from it; if the change fell in a year you can't split, let both spans include that year (the overlap marks the uncertainty), and likewise across an undated window.
- wording: the differences that are only wording, briefly.
- confidence, and a note where something needs a reason. In notes, list anything I should check. If the witnesses contradict each other (a report says one period, Findlay another), say so in the note rather than choosing silently.
Stations with no witness at all are not in the file."""


def judge_inputs(group):
    S = json.load(open(os.path.join(ST, 'stations.json')))
    M, R = agreed(), {ed: by_id(ed) for ed in ('findlay1879', 'findlay1887')}
    E = {r['row_id']: r for r in csv.DictReader(open(os.path.join(DATA, 'lights', 'edwards1884.csv')))}
    em = {m['id']: m['row'] for m in json.load(open(os.path.join(ST, 'edwards', 'match_run1.json')))['matches']}
    rows = list(csv.DictReader(open(os.path.join(ST, 'list_rows.csv'))))
    from match_findlay import country_of
    from stations import key
    nm = {int(r['idx']): r for r in csv.DictReader(open(os.path.join(ST, 'names.csv')))}
    clean = lambda x: ' '.join(re.sub(r'[_*†‡{}]', ' ', x or '').split()).strip(' .,;:').lower()
    key2sid = {(nm[i]['region'], clean(nm[i]['name']), clean(nm[i]['type'])): s['id'] for s in S for i in s['members']}
    rep = {}
    for r in rows:
        if r['year'] in ('1879', '1880') and r['character']:
            sid = key2sid.get(key(r))
            if sid:
                rep.setdefault(sid, {})[f'report{r["year"]}'] = r['character']
    out = []
    for s in S:
        if (country_of(s) or 'ENGLAND') != group:
            continue
        w = {}
        for ed in ('findlay1879', 'findlay1887'):
            m = M.get(s['id'], {}).get(ed)
            if m and m[0]:
                w[ed] = [{k: R[ed][x][k] for k in ('row_id', 'name', 'character', 'description', 'year')} for x in [m[0]] + m[1]]
        if em.get(s['id']):
            e = E[em[s['id']]]
            w['edwards1884'] = {k: e[k] for k in ('row_id', 'name', 'character')}
        w.update(rep.get(s['id'], {}))
        if w:
            out.append({'id': s['id'], 'name': s['name'], 'kind': s['kind'], 'years_in_reports': s['seen'], **w})
    path = os.path.join(ST, 'characters', f'witnesses_{group}.json')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(out, open(path, 'w'), indent=1, ensure_ascii=False)
    return path, len(out)


def judge(group, run):
    out = os.path.join(ST, 'characters', f'judge_{group}_run{run}.json')
    if os.path.exists(out):
        return json.load(open(out))
    path, n = judge_inputs(group)
    d, cost = run_helper(J_BRIEF.format(path=path, n=n), J_SCHEMA, 'Read')
    d['_meta'] = {'group': group, 'run': run, 'cost_usd': cost}
    json.dump(d, open(out, 'w'), indent=1, ensure_ascii=False)
    return d


def judge_compare():
    tot = agree_changed = agree_all = 0
    for g in ('ENGLAND', 'SCOTLAND', 'IRELAND'):
        A, B = ({x['id']: x for x in json.load(open(os.path.join(ST, 'characters', f'judge_{g}_run{r}.json')))['stations']} for r in (1, 2))
        W = {x['id']: x for x in json.load(open(os.path.join(ST, 'characters', f'witnesses_{g}.json')))}
        for i in W:
            a, b = A.get(i), B.get(i)
            tot += 1
            if not a or not b:
                print(f'  {g} {i}: missing in a run')
                continue
            same_changed = a['changed'] == b['changed']
            agree_changed += same_changed
            spans = lambda x: [(s['from'], s['to'], s['source']) for s in x['states']]
            same_all = same_changed and spans(a) == spans(b) and (a['change_year'], a['earliest'], a['latest']) == (b['change_year'], b['earliest'], b['latest'])
            agree_all += same_all
            if not same_all:
                print(f'  {g} {i}: changed {a["changed"]}/{b["changed"]}; year {a["change_year"]}/{b["change_year"]}; window '
                      f'{a["earliest"]}-{a["latest"]} / {b["earliest"]}-{b["latest"]}; spans {spans(a)} / {spans(b)}')
    print(f'{tot} stations; agree on changed {agree_changed}; agree on everything {agree_all}')


def build():
    """data/stations/characters.csv: one row per station, year and state
    (two rows in a year the witnesses can't split), with the source text and
    its parsed pattern."""
    rev = json.load(open(os.path.join(ST, 'characters', 'reviewed.json')))
    out = []
    for g in ('ENGLAND', 'SCOTLAND', 'IRELAND'):
        runs_ = [{x['id']: x for x in json.load(open(os.path.join(ST, 'characters', f'judge_{g}_run{r}.json')))['stations']} for r in (1, 2)]
        W = {x['id']: x for x in json.load(open(os.path.join(ST, 'characters', f'witnesses_{g}.json')))}
        for sid, w in W.items():
            take = rev.get(sid, {}).get('take', 'run1')
            j = dict(runs_[int(take[-1]) - 1][sid])
            if 'states' in rev.get(sid, {}):
                j['states'] = rev[sid]['states']
            for y in range(1879, 1888):
                st = [s_ for s_ in j['states'] if s_['from'] <= y <= s_['to']]
                for s_ in st:
                    src = s_['source']
                    if src.startswith('findlay'):
                        rows_ = w.get(src, [])
                        text = ' | '.join(r['character'] for r in rows_)
                        desc = ' | '.join(r['description'] for r in rows_)
                        ref = ' '.join(r['row_id'] for r in rows_)
                        # a light whose character is printed in the description column (Oyster Island) is read from there
                        lights = [l for r in rows_ for l in (parse(r['character'], r['description'])[0] if r['character']
                                                             else parse(r['description'])[0])]
                    elif src == 'edwards1884':
                        text, desc, ref = w['edwards1884']['character'], '', w['edwards1884']['row_id']
                        lights = parse(text)[0]
                    else:
                        text, desc, ref = w.get(src, ''), '', src
                        lights = parse(text)[0]
                    from patterns import text_key
                    out.append({'id': sid, 'year': y, 'states_this_year': len(st), 'source': src, 'ref': ref, 'character': text,
                                'pattern_key': text_key(text, desc[:300]),
                                'description': desc[:300],
                                'pattern': json.dumps([{k: l.get(k) for k in ('kind', 'group', 'period_s', 'colours', 'alternating',
                                                                               'sectored', 'eclipse_s', 'kind_assumed')} for l in lights]),
                                'changed': j['changed'], 'what_changed': j['what_changed'] or '', 'confidence': j['confidence'],
                                'decided': f'{take} (reviewed.json)' if sid in rev else 'run1'})
    cols = ['id', 'year', 'states_this_year', 'source', 'ref', 'character', 'pattern_key', 'description', 'pattern', 'changed', 'what_changed',
            'confidence', 'decided']
    with open(os.path.join(ST, 'characters.csv'), 'w', newline='') as f:
        wr = csv.DictWriter(f, cols)
        wr.writeheader()
        wr.writerows(out)
    from collections import Counter
    ids = {r['id'] for r in out}
    unknown = sorted({r['id'] for r in out if any(l['kind'] == 'unknown' for l in json.loads(r['pattern'])) or r['pattern'] == '[]'})
    print(f'{len(out)} rows for {len(ids)} stations; years with two states: {sum(r["states_this_year"] > 1 for r in out) // 2}; '
          f'changed lights: {len({r["id"] for r in out if r["changed"]})}; sources: {dict(Counter(r["source"] for r in out))}')
    print(f'patterns the parser could not read (kind unknown or empty): {len(unknown)}: {unknown}')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('step', choices=['census', 'edwards', 'edwards-compare', 'judge', 'judge-compare', 'build'])
    a = ap.parse_args()
    if a.step == 'census':
        census()
    elif a.step == 'edwards':
        with cf.ThreadPoolExecutor(2) as ex:
            for r, d in zip((1, 2), ex.map(edwards_match, (1, 2))):
                print(f'run {r}: {len(d["matches"])} matches')
    elif a.step == 'judge':
        jobs = [(g, r) for g in ('ENGLAND', 'SCOTLAND', 'IRELAND') for r in (1, 2)]
        with cf.ThreadPoolExecutor(6) as ex:
            for j, d in zip(jobs, ex.map(lambda j: judge(*j), jobs)):
                print(j, len(d['stations']), 'stations')
    elif a.step == 'judge-compare':
        judge_compare()
    elif a.step == 'build':
        build()
    else:
        edwards_compare()
