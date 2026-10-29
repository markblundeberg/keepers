"""Check tools/characters.py against a blind reading: every distinct light
character used in data/stations/characters.csv is read by a helper (which
does not see the parser's output) into kind, flashes per group, period and
colours per light; the two are compared field by field.

Run: python3 -I tools/check_patterns.py ask | compare
"""
import csv, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA
from station_lists import run_helper

ST = os.path.join(DATA, 'stations')
OUT = os.path.join(ST, 'characters', 'pattern_check.json')
KINDS = ['fixed', 'revolving', 'flashing', 'group_flashing', 'occulting', 'intermittent', 'fixed_flashing', 'unknown']
SCHEMA = {'type': 'object', 'required': ['items'], 'properties': {'items': {'type': 'array', 'items': {
    'type': 'object', 'required': ['n', 'lights'], 'properties': {'n': {'type': 'integer'}, 'lights': {'type': 'array', 'items': {
        'type': 'object', 'required': ['kind', 'group', 'period_s', 'colours'],
        'properties': {'kind': {'type': 'string', 'enum': KINDS}, 'group': {'type': ['integer', 'null']},
                       'period_s': {'type': ['number', 'null']}, 'colours': {'type': 'array', 'items': {'type': 'string'}}}}}}}}}}
BRIEF = '''Thank you for helping. I'm a Claude agent making a chart of the lighthouses of Britain and Ireland in the 1880s, with each light flashing as it did then. The file {path} (JSON; open it with the Read tool) holds {n} descriptions of lights from period sources (Findlay's list of lights, 1879 and 1887; E. Price Edwards, 1884; the bird-migration reports of 1879-80), each a character line and sometimes a description.

For each item, list the lights it describes that a ship would see (a high and a low light are two; a pier light described inside a lighthouse's entry counts only if the character line counts it), and for each light give:
- kind: fixed, revolving (a beam that sweeps round: bright, then dark), flashing (short flashes, more dark than light), group_flashing (two or more flashes together, then a longer dark: "2-flash.", "3 flashes in quick succession"), occulting (mostly light, with short eclipses; older sources may call this "intermittent"), intermittent (only if you can't tell it from occulting), fixed_flashing, or unknown.
- group: flashes per group for group_flashing, else null.
- period_s: the time in seconds for the whole cycle to repeat ("½ min." is 30; "1 min." is 60; "every 10 seconds" is 10), or null if not given. A duration of darkness or of an eclipse is not the period.
- colours: the colours shown, as "white" (the sources write "bright", "br.", "brilliant" or "white"), "red", "green"; for a light that shows red in some directions and white in others ("bright or red"), give both. Use ["white?"] if no colour is stated.
Read the description where the character line leaves the kind or period out. Put the item number in n.'''


def ask():
    rows = list(csv.DictReader(open(os.path.join(ST, 'characters.csv'))))
    items = []
    for r in rows:
        k = (r['character'], r['description'])
        if k not in [(i['character'], i['description']) for i in items]:
            items.append({'n': len(items) + 1, 'character': r['character'], 'description': r['description']})
    path = os.path.join(ST, 'characters', 'pattern_check_items.json')
    json.dump(items, open(path, 'w'), indent=1, ensure_ascii=False)
    if not os.path.exists(OUT):
        d, cost = run_helper(BRIEF.format(path=path, n=len(items)), SCHEMA, 'Read')
        d['_meta'] = {'cost_usd': cost}
        json.dump(d, open(OUT, 'w'), indent=1, ensure_ascii=False)
    print(len(items), 'items read')


def compare():
    from characters import parse
    items = json.load(open(os.path.join(ST, 'characters', 'pattern_check_items.json')))
    H = {x['n']: x['lights'] for x in json.load(open(OUT))['items']}
    same = {'count': 0, 'kind': 0, 'group': 0, 'period': 0, 'colours': 0}
    n = 0
    norm_kind = lambda k: {'intermittent': 'occulting', 'revolving': 'flashing'}.get(k, k)
    bad = []
    for it in items:
        mine = parse(it['character'], it['description'])[0] if it['character'] else parse(it['description'])[0]
        theirs = H.get(it['n'], [])
        n += 1
        if len(mine) != len(theirs):
            bad.append((it['n'], 'count', len(mine), len(theirs), it['character'][:70]))
            continue
        same['count'] += 1
        ok = True
        for a, b in zip(sorted(mine, key=lambda l: str(l['kind'])), sorted(theirs, key=lambda l: str(l['kind']))):
            for f, va, vb in (('kind', norm_kind(a['kind']), norm_kind(b['kind'])), ('group', a['group'], b['group']),
                              ('period', a['period_s'], b['period_s']),
                              ('colours', sorted(set(a['colours']) - {'white?'}), sorted(set(b['colours']) - {'white?'}))):
                if va != vb:
                    ok = False
                    bad.append((it['n'], f, va, vb, it['character'][:70]))
        if ok:
            for f in ('kind', 'group', 'period', 'colours'):
                same[f] += 1
    print(f'{n} items; same number of lights {same["count"]}; items agreeing on every field {same["kind"]}')
    from collections import Counter
    print('disagreements by field:', Counter(b[1] for b in bad))
    for b in bad:
        print('  ', b)


if __name__ == '__main__':
    {'ask': ask, 'compare': compare}[sys.argv[1]]()
