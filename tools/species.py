"""The species crosswalk: every bird name the extraction copied, as printed
("Titlarks", "Golden-crested Wren", "Grey Crows", "Solan Goose",
"_Turdus viscivorus_", the OCR's "Turpus Viscivorus"), mapped to a modern
species by two independent helpers, keyed by scientific name (IOC), with
groups ("small birds", "Thrushes") and unknowns kept as such.

Run: python3 -I tools/species.py collect | ask | compare | build
  -> data/species/names.json, data/species/map_run<r>_b<k>.json, data/species.csv
"""
import collections, concurrent.futures as cf, csv, glob, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA, obs_paths
from station_lists import run_helper

OUT = os.path.join(DATA, 'species')
BATCH = 350


def key(name):
    return ' '.join(re.sub(r'[_*"“”]', ' ', name or '').split()).strip(' .,;:').lower()


def collect():
    names = collections.Counter()
    example = {}
    for path in obs_paths():
        for l in open(path):
            r = json.loads(l)
            for o in r['obs'] or []:
                if o['species']:
                    k = key(o['species'])
                    names[k] += 1
                    example.setdefault(k, (o['species'], o['quote'][:100]))
    # Numbers are kept from an earlier collect (the helpers' answers are filed by them); names new since then
    # start at the next whole batch, so they make batches of their own.
    np_ = os.path.join(OUT, 'names.json')
    old = {i['name']: i['n'] for i in json.load(open(np_))} if os.path.exists(np_) else {}
    nxt = -(-(max(old.values()) + 1) // BATCH) * BATCH if old else 0
    items = []
    for k, c in sorted(names.items()):
        if k not in old:
            old[k], nxt = nxt, nxt + 1
        items.append({'n': old[k], 'name': k, 'printed': example[k][0], 'observations': c, 'example': example[k][1]})
    items.sort(key=lambda i: i['n'])
    os.makedirs(OUT, exist_ok=True)
    json.dump(items, open(os.path.join(OUT, 'names.json'), 'w'), indent=1, ensure_ascii=False)
    print(f'{len(items)} distinct names, {sum(names.values())} observations')
    return items


SCHEMA = {'type': 'object', 'required': ['items', 'notes'], 'properties': {'items': {'type': 'array', 'items': {
    'type': 'object', 'required': ['n', 'level', 'scientific', 'english', 'note'], 'properties': {
        'n': {'type': 'integer'}, 'level': {'type': 'string', 'enum': ['species', 'genus', 'family', 'group', 'not_a_bird', 'unknown']},
        'scientific': {'type': ['string', 'null']}, 'english': {'type': ['string', 'null']}, 'note': {'type': ['string', 'null']}}}},
    'notes': {'type': 'string'}}}

BRIEF = '''Thank you for helping. I'm a Claude agent turning the British Association's reports on bird migration at British and Irish lighthouses (1879-1887) back into data. The keepers and the committee wrote Victorian bird names; I need each one mapped to a modern species.

The file {path} (JSON; open it with the Read tool) lists {k} names as printed (lowercased for matching; "printed" shows one original), with how many observations use each and an example.

For each name give:
- level: species (one modern species); genus or family (only that far: "Gulls", "Divers", "Hawks"); group (a loose group: "small birds", "Waders", "Sea-fowl", "birds"); not_a_bird (a bat, a moth, an insect); unknown (can't tell, or a garble you can't read).
- scientific: the modern scientific name (IOC World Bird List) for a species, the genus or family name for those levels, else null.
- english: the modern English name (IOC; British usage where it differs: "Northern Wheatear" is "Wheatear" in Britain, so give "Northern Wheatear") for a species; for a genus or family a plain English label ("gulls"); for a group the printed sense ("small birds").
Victorian names to watch: Titlark = Meadow Pipit; Golden-crested Wren = Goldcrest; Fire-crested Wren = Firecrest; Solan Goose = Northern Gannet; Grey or Hooded Crow = Hooded Crow; Black Crow: a black corvid that the same reports keep apart from Rooks, yet seen in migrating flocks of hundreds over the North Sea, where Rooks are likely; give genus Corvus unless the text settles it; "Crows" alone: genus Corvus (Hooded, Carrion or Rook); Hedge Sparrow = Dunnock; Missel or Mistletoe Thrush = Mistle Thrush; Song Thrush or "Thrush" alone = Song Thrush (say so in note); Ring Ouzel; Mealy Redpoll; Shore Lark = Horned Lark; Snow Bunting; Twite; Green Plover or Peewit = Northern Lapwing; Grey Plover; Stone Curlew; Brent Goose; Tystie = Black Guillemot; Gilliemot, Willock; Scart = cormorant or shag (genus if unclear); Kittiwake; Sea-swallow or Tern (genus unless named); Short-eared Owl; Hobby; Merlin; Sparrow-hawk; Hen-harrier; "Red-backed Shrike"; "Pied Flycatcher". Latin names of the time (Turdus iliacus = Redwing; Sylvia rufa = Common Chiffchaff; Ruticilla phoenicurus = Common Redstart; Saxicola oenanthe = Northern Wheatear; Anthus pratensis = Meadow Pipit) map to their modern species; OCR garbles of them too ("Turpus Viscivorus" = Turdus viscivorus = Mistle Thrush) where you are sure.
A plural or a sex or age word doesn't change the species ("hen Blackbird", "young Larks"). "Lark" alone in these reports usually means Eurasian Skylark: give it with a note. Say in note anything uncertain. In notes, list what I should check.'''


def ask(run, b):
    out = os.path.join(OUT, f'map_run{run}_b{b}.json')
    if os.path.exists(out):
        return json.load(open(out))
    items = [i for i in json.load(open(os.path.join(OUT, 'names.json'))) if i['n'] // BATCH == b]
    path = os.path.join(OUT, f'batch{b}.json')
    json.dump(items, open(path, 'w'), indent=1, ensure_ascii=False)
    d, cost = run_helper(BRIEF.format(path=path, k=len(items)), SCHEMA, 'Read')
    d['_meta'] = {'run': run, 'batch': b, 'cost_usd': cost}
    json.dump(d, open(out, 'w'), indent=1, ensure_ascii=False)
    return d


def batch_numbers():
    return sorted({i['n'] // BATCH for i in json.load(open(os.path.join(OUT, 'names.json')))})


def runs():
    out = [{}, {}]
    for r in (1, 2):
        for b in batch_numbers():
            p = os.path.join(OUT, f'map_run{r}_b{b}.json')
            if os.path.exists(p):
                for x in json.load(open(p))['items']:
                    out[r - 1][x['n']] = x
    return out


def sig(x):
    return (x['level'], (x['scientific'] or '').lower().strip()) if x else None


def compare():
    items = {i['n']: i for i in json.load(open(os.path.join(OUT, 'names.json')))}
    A, B = runs()
    dis = [n for n in items if sig(A.get(n)) != sig(B.get(n))]
    tot = sum(i['observations'] for i in items.values())
    print(f'{len(items)} names ({tot} observations); runs differ on {len(dis)} names '
          f'({sum(items[n]["observations"] for n in dis)} observations)')
    for n in sorted(dis, key=lambda n: -items[n]['observations'])[:60]:
        print(f"  {n} {items[n]['name']!r} x{items[n]['observations']}: {sig(A.get(n))} | {sig(B.get(n))}")


RANK = {'species': 1, 'genus': 2, 'family': 3, 'group': 4}


def build():
    items = {i['n']: i for i in json.load(open(os.path.join(OUT, 'names.json')))}
    A, B = runs()
    rp = os.path.join(OUT, 'reviewed.json')
    rev = json.load(open(rp)) if os.path.exists(rp) else {}
    rows = []
    for n, i in items.items():
        if str(n) in rev:
            x, how = rev[str(n)], 'reviewed'
        elif sig(A.get(n)) == sig(B.get(n)):
            x, how = A[n], 'helpers agree'
        elif A.get(n) and B.get(n) and A[n]['level'] in RANK and B[n]['level'] in RANK and A[n]['level'] != B[n]['level']:
            x = max(A[n], B[n], key=lambda y: RANK[y['level']])      # "Hawks": family or group; claim no more than both allow
            how = 'helpers differ in level: the coarser'
        else:
            x, how = {'level': 'unresolved', 'scientific': None, 'english': None}, 'helpers differ'
        rows.append({'name': i['name'], 'observations': i['observations'], 'level': x['level'], 'scientific': x.get('scientific') or '',
                     'english': x.get('english') or '', 'how': how, 'note': (A.get(n) or {}).get('note') or ''})
    # one name per species: a synonym the helpers both used for some names, and the commonest English name
    syn = {'charadrius morinellus': 'Eudromias morinellus'}
    for r in rows:
        r['scientific'] = syn.get(r['scientific'].lower(), r['scientific'])
    en = collections.defaultdict(collections.Counter)
    for r in rows:
        if r['level'] == 'species':
            en[r['scientific']][r['english']] += r['observations']
    for r in rows:
        if r['level'] == 'species':
            r['english'] = en[r['scientific']].most_common(1)[0][0]
    with open(os.path.join(DATA, 'species.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f'{len(rows)} names -> data/species.csv; by level {dict(collections.Counter(r["level"] for r in rows))}; '
          f'species: {len({r["scientific"] for r in rows if r["level"] == "species"})}')


if __name__ == '__main__':
    step = sys.argv[1]
    if step == 'collect':
        collect()
    elif step == 'ask':
        jobs = [(r, b) for r in (1, 2) for b in batch_numbers()]
        with cf.ThreadPoolExecutor(8) as ex:
            for j, d in zip(jobs, ex.map(lambda j: ask(*j), jobs)):
                print(j, len(d['items']), 'names', flush=True)
    elif step == 'compare':
        compare()
    elif step == 'build':
        build()
