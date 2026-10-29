"""Drawable light patterns. Each distinct character text used in
data/stations/characters.csv (with its description, which often holds the
real pattern: "bright, bright, and red alternately", "visible 1 min., and
then eclipsed ½ min.") is read twice by independent helpers into the steps
of one full cycle: light or dark, colour, seconds, and whether the source
states the seconds. The readings are compared step by step; tools/characters.py
stays as a coarse cross-check (kind and period).

  ask:     -> data/stations/patterns/batch<k>_run<r>.json
  compare: the two runs, item by item
  build:   -> data/stations/patterns.json  {text key: lights}

Run: python3 -I tools/patterns.py ask | compare | build
"""
import concurrent.futures as cf, csv, hashlib, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA
from station_lists import run_helper

ST = os.path.join(DATA, 'stations')
OUT = os.path.join(ST, 'patterns')
BATCH = 65
KINDS = ['fixed', 'revolving', 'flashing', 'group_flashing', 'occulting', 'group_occulting', 'fixed_and_flashing', 'unknown']
STEP = {'type': 'object', 'required': ['light', 'colour', 'seconds', 'stated'], 'properties': {
    'light': {'type': 'boolean'}, 'colour': {'type': ['string', 'null'], 'enum': ['white', 'red', 'green', None]},
    'seconds': {'type': ['number', 'null']}, 'stated': {'type': 'boolean'}}}
LIGHT = {'type': 'object', 'required': ['role', 'kind', 'group', 'cycle_s', 'cycle_stated', 'steps', 'sector_colours', 'note'],
         'properties': {'role': {'type': 'string'}, 'kind': {'type': 'string', 'enum': KINDS}, 'group': {'type': ['integer', 'null']},
                        'cycle_s': {'type': ['number', 'null']}, 'cycle_stated': {'type': 'boolean'},
                        'steps': {'type': 'array', 'items': STEP},
                        'sector_colours': {'type': 'array', 'items': {'type': 'string'}}, 'note': {'type': ['string', 'null']}}}
SCHEMA = {'type': 'object', 'required': ['items'], 'properties': {'items': {'type': 'array', 'items': {
    'type': 'object', 'required': ['n', 'lights', 'unsure'],
    'properties': {'n': {'type': 'integer'}, 'lights': {'type': 'array', 'items': LIGHT}, 'unsure': {'type': ['string', 'null']}}}}}}

BRIEF = '''Thank you for helping. I'm a Claude agent making a chart of the lighthouses and light-vessels of Britain and Ireland in the 1880s, on which each light will flash as it did then. I need each light's pattern in a form a program can draw, read from the period sources.

The file {path} (JSON; open it with the Read tool) holds {k} items. Each is one station's entry in a period source (Findlay's list of lights, 1879 or 1887; E. Price Edwards's list, 1884; or the bird-migration reports' own words, 1879-80): a character line and often a description. The description frequently gives the real pattern ("shows two bright flashes and one red flash: a flash every 20 secs."; "Light visible 1 min., and then eclipsed ½ min."; "Two quick flashes, first bright, second red, followed by an eclipse of 22 secs."). Read both.

For each item, list the lights a ship would see from the station (a high and a low light are two; a lower fixed light is its own light; a harbour or pier light mentioned in the entry counts only if the character line counts it). For each light:
- role: "main", "upper", "lower", "high", "low", or as the source names it.
- kind: fixed; revolving (a beam sweeping round: light grows, then dark); flashing (short flashes, dark longer than light); group_flashing (two or more flashes close together, then a longer dark); occulting (light longer than dark, with eclipses; older sources say "intermittent" or "intermitting" for this); group_occulting; fixed_and_flashing; unknown.
- group: flashes (or eclipses) per group, else null.
- cycle_s: seconds for the whole pattern to repeat, colours included: a light flashing every 20 s as bright, bright, red repeats every 60 s; "visible 1 min., eclipsed ½ min." repeats every 90 s. Null if the source doesn't give it. cycle_stated: true if the source gives it or it follows by plain arithmetic from what it gives.
- steps: one full cycle in order, starting with the first light: each step is light (true) or dark (false), its colour for a light step (white for "bright", "br.", "brilliant", "white"; red; green; null if not stated), its seconds, and stated (true only if the source gives that duration or it follows by arithmetic, e.g. a 30 s interval with a 10 s flash leaves 20 s dark). Where the source doesn't give a duration, put null and stated false; don't guess. A fixed light is one light step with seconds null. A revolving or flashing light every N seconds is a light step and a dark step whose sum is N.
- sector_colours: colours the light shows only over certain bearings (a red sector over a shoal), else [].
- note: anything the steps can't hold (the pattern differs by direction; "visible for 10 and 30 secs. alternately at intervals of 10 secs."; a light shown only in winter).
In unsure, say what you couldn't settle from the text, else null. Put the item number in n.'''


def text_key(character, description):
    return hashlib.sha1(f'{character}\n{description}'.encode()).hexdigest()[:12]


def items():
    rows = list(csv.DictReader(open(os.path.join(ST, 'characters.csv'))))
    seen, out = set(), []
    for r in rows:
        k = text_key(r['character'], r['description'])
        if k in seen:
            continue
        seen.add(k)
        out.append({'n': len(out) + 1, 'key': k, 'source': r['source'], 'character': r['character'], 'description': r['description']})
    return out


def ask(b, run):
    out = os.path.join(OUT, f'batch{b}_run{run}.json')
    if os.path.exists(out):
        return json.load(open(out))
    its = items()[b * BATCH:(b + 1) * BATCH]
    path = os.path.join(OUT, f'batch{b}_items.json')
    json.dump([{k: i[k] for k in ('n', 'source', 'character', 'description')} for i in its], open(path, 'w'), indent=1, ensure_ascii=False)
    d, cost = run_helper(BRIEF.format(path=path, k=len(its)), SCHEMA, 'Read')
    d['_meta'] = {'batch': b, 'run': run, 'keys': {i['n']: i['key'] for i in its}, 'cost_usd': cost}
    json.dump(d, open(out, 'w'), indent=1, ensure_ascii=False)
    return d


def readings():
    """{item n: (run1 lights, run2 lights)} over all batches."""
    out = {}
    nb = (len(items()) + BATCH - 1) // BATCH
    for b in range(nb):
        A, B = (json.load(open(os.path.join(OUT, f'batch{b}_run{r}.json'))) for r in (1, 2))
        ma, mb = {x['n']: x for x in A['items']}, {x['n']: x for x in B['items']}
        for n in A['_meta']['keys']:
            n = int(n)
            out[n] = (ma.get(n), mb.get(n))
    return out


def first_colour(character):
    """The colour named first in a character line ("One fixed bright, or red light" -> white)."""
    import re
    m = re.search(r'\b(bright|br\.|brilliant|white|red|green)\b', (character or '').lower())
    return None if not m else ('white' if m.group(1) in ('bright', 'br.', 'brilliant', 'white') else m.group(1))


def normalise(l, character):
    """Formatting choices that don't change the light: group 1 is no group;
    a colour cycle may be read from any start (rotate to a canonical start);
    a sectored light's main colour is the one its character line names first."""
    l = json.loads(json.dumps(l))
    if l['kind'] not in ('group_flashing', 'group_occulting') and l['group'] == 1:
        l['group'] = None
    lights = [i for i, s in enumerate(l['steps']) if s['light']]
    if len(lights) > 1:
        seq = [l['steps'][i]['colour'] for i in lights]
        best_r = min(range(len(seq)), key=lambda r: [str(c) for c in seq[r:] + seq[:r]])
        if best_r:
            start = lights[best_r]
            l['steps'] = l['steps'][start:] + l['steps'][:start]
    if l['sector_colours'] and len({s['colour'] for s in l['steps'] if s['light']}) == 1:
        fc = first_colour(character)          # a sectored light of one colour per flash: its main colour
        if fc:
            for s_ in l['steps']:
                if s_['light']:
                    s_['colour'] = fc
    return l


def summary(l):
    """What must agree: kind, group, cycle, the colours of the light steps in
    order, and every stated duration."""
    return (l['kind'], l['group'], l['cycle_s'], tuple(s['colour'] for s in l['steps'] if s['light']),
            tuple((s['light'], s['seconds']) for s in l['steps'] if s['stated']))


def compare(verbose=True):
    its = {i['n']: i for i in items()}
    R = readings()
    agree, dis = 0, []
    for n, (a, b) in sorted(R.items()):
        if not a or not b:
            dis.append((n, 'missing'))
            continue
        ch = its[n]['character']
        sa, sb = [summary(normalise(l, ch)) for l in a['lights']], [summary(normalise(l, ch)) for l in b['lights']]
        if sa == sb:
            agree += 1
        else:
            dis.append((n, sa, sb))
    print(f'{len(R)} items; the two readings agree on every light, kind, group, cycle, colour sequence and stated duration: {agree}')
    if verbose:
        for d in dis:
            n = d[0]
            print(f'  {n} [{its[n]["character"][:50]}]')
            if len(d) == 3:
                print(f'     run1 {d[1]}\n     run2 {d[2]}')
    return dis


def build():
    """data/stations/patterns.json: {text key: {"lights": [...], "decided": how}} from the
    agreed (normalised) readings, the reviewed choices, and nothing else."""
    its = {i['n']: i for i in items()}
    rev = json.load(open(os.path.join(OUT, 'reviewed.json')))
    R = readings()
    out, open_ = {}, []
    for n, (a, b) in sorted(R.items()):
        ch = its[n]['character']
        la, lb = [normalise(l, ch) for l in a['lights']], [normalise(l, ch) for l in b['lights']]
        if [summary(l) for l in la] == [summary(l) for l in lb]:
            out[its[n]['key']] = {'lights': la, 'decided': 'runs agree'}
        elif str(n) in rev:
            take = rev[str(n)]['take']
            out[its[n]['key']] = {'lights': la if take == 'run1' else lb, 'decided': f'{take}: {rev[str(n)]["why"]}'}
        else:
            open_.append(n)
    json.dump(out, open(os.path.join(ST, 'patterns.json'), 'w'), indent=1, ensure_ascii=False)
    print(f'{len(out)} patterns -> data/stations/patterns.json; undecided: {open_}')


if __name__ == '__main__':
    step = sys.argv[1]
    if step == 'ask':
        nb = (len(items()) + BATCH - 1) // BATCH
        jobs = [(b, r) for b in range(nb) for r in (1, 2)]
        with cf.ThreadPoolExecutor(8) as ex:
            for j, d in zip(jobs, ex.map(lambda j: ask(*j), jobs)):
                print(j, len(d['items']), 'items', flush=True)
    elif step == 'compare':
        compare()
    elif step == 'build':
        build()
