"""T3 for the stage-3 extraction: a sample of observations read against the
printed page (IA scans) by safe-mode vision helpers, with planted errors to
measure the check itself. Half the sample uniform, half lantern events.

Gutenberg years: the scan image comes from the page map (data/pages). OCR
years: from the running heads (station_lists.candidate_images); there the
copied fields carry the OCR's garbles, and T3 measures how far they are
from the print.

Run: python3 -I tools/t3_v4.py 1885 [--n 100] [--seed 1885] [--per 10]
  -> data/checks/t3_<year>_v4.json and a score on stdout
"""
import argparse, bisect, concurrent.futures as cf, copy, hashlib, json, os, random, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA, ROOT, Pages, scan, ws_norm, ws_norm_with_map
from t3_check import ALT_BEH, ALT_COUNT, ALT_DIR

MODEL, EFFORT = 'claude-opus-5-5', 'high'
CACHE = os.path.join(ROOT, 'cache', 'llm', 't3v4')
CHECK = ['station', 'date_iso', 'species', 'count', 'behaviour', 'at_light', 'time', 'direction', 'wind', 'force', 'weather']
V = {'type': 'object', 'required': ['verdict', 'print_says'],
     'properties': {'verdict': {'type': 'string', 'enum': ['ok', 'wrong', 'unclear']}, 'print_says': {'type': ['string', 'null']}}}
SCHEMA = {'type': 'object', 'required': ['items'], 'properties': {'items': {'type': 'array', 'items': {
    'type': 'object', 'required': ['item', 'found', 'fields'],
    'properties': {'item': {'type': 'integer'}, 'found': {'type': 'boolean'},
                   'fields': {'type': 'object', 'required': CHECK, 'properties': {f: V for f in CHECK}}}}}}}

BRIEF = '''Thank you for helping. I'm a Claude agent turning the British Association's "Reports on the Migration of Birds" (1879-1887) back into data: the lighthouse and light-vessel keepers' records of the birds they saw. Records have been extracted from a {textkind}, and this is the check against the printed page itself, read from the Internet Archive's scans. Your reading is the independent one, so please trust the page over anything written here.

For each item below: open the page image(s) with the Read tool, find the passage (the quote is given to help you find it{ocrnote}), and check the record against the print and the passage around it. Some records contain errors on purpose; that's what we're measuring, so judge every field afresh.

Fields, with their definitions:
- station: the lighthouse, light-vessel or place the observation belongs to, as the print names it (it may stand earlier in the entry, or be a map number like "XXVII."). date_iso: the date the print gives for this observation, as YYYY-MM-DD (month and year from the text around it; the report's year is {year}).
- species: the bird name as printed (it may stand in a heading above). count: the number or quantity words as printed (null if none stated).
- behaviour: passing (flying past/over/along, migrating); round_lantern (flying round or at the lantern or light); round_station (round or about the ship, rock, island or lighthouse, not said to be the lantern); lost_over (fell or lost over, fate not stated); struck (striking the lantern, not said killed); dead (killed or found dead; count = number dead); caught; shot; settled (resting on vessel, deck, rigging, rock, island, lighthouse); heard; seen (present, nothing more specific stated); same_as (only "the same as" another day). The most specific the text states, without inference.
- at_light: true only if the text connects these birds to the lantern or light.
- time: the time of day as printed. direction: the flight direction as printed (never the wind).
- wind, force, weather: as printed for this observation (null if none).
For each field give "ok", "wrong" (and in print_says what the print supports), or "unclear". A null field is "ok" if the print states nothing for it, "wrong" if it does. Ignore differences of spacing, line breaks and italics. Set found false if you can't find the passage on the given page(s).

Give `item` as the item number. The items:

'''


def plant(rec, rng, stations):
    opts = ['behaviour']
    if rec['count'] and (rec['count'].lower() in ALT_COUNT or re.fullmatch(r'\d+', rec['count'])):
        opts.append('count')
    if rec['time'] and re.search(r'\d', rec['time']):
        opts.append('time')
    if rec['direction'] and re.search(r'[NSEW]', rec['direction']):
        opts.append('direction')
    if rec['date_iso'] and re.fullmatch(r'\d{4}-\d\d-\d\d', rec['date_iso']):
        opts.append('date_iso')
    if rec['station'] and len(stations) > 1:
        opts.append('station')
    f = rng.choice(opts)
    old = rec[f]
    if f == 'count':
        new = ALT_COUNT.get(old.lower()) or str(int(old) * 2 if int(old) > 1 else 3)
    elif f == 'behaviour':
        new = ALT_BEH[old]
    elif f == 'time':
        new = re.sub(r'\d+', lambda m: str(int(m.group(0)) % 12 + 1), old, count=1)
    elif f == 'date_iso':
        d = int(old[-2:])
        new = old[:-2] + f'{(d + rng.choice([2, 3, 5])) % 28 + 1:02d}'
    elif f == 'station':
        new = rng.choice([s for s in stations if s != old])
    else:
        new = re.sub(r'[NSEW]', lambda m: ALT_DIR[m.group(0)], old, count=1)
    rec[f] = new
    return f, old, new


def images_for(year, chunk, start, end, reading):
    """The scan image(s) holding a passage: Gutenberg years from the page map, OCR years from the leaves placed
    in the OCR text (tools/leaves.py); for OCR years the next image too, as the placing is by a leaf's opening words."""
    from kp import ocr_leaf
    if reading == 'gutenberg':
        pages = Pages(year)
        m0, m1 = pages.at(start), pages.at(end - 1)
        idxs = sorted({m0['image_index'], m1['image_index']} - {None})
        return [scan(year, k) for k in idxs], [m0['page']] + ([m1['page']] if m1['page'] != m0['page'] else [])
    p0, i0 = ocr_leaf(year, start)
    p1, i1 = ocr_leaf(year, end - 1)
    idxs = sorted({i for i in (i0, i1, (i1 or i0 or 0) + 1) if i is not None})
    return [scan(year, k) for k in idxs], [str(p) for p in sorted({p0, p1} - {None})]


def ask(prompt, key):
    path = os.path.join(CACHE, f'{key}.json')
    if os.path.exists(path):
        return json.load(open(path))
    cmd = ['systemd-run', '--user', '--scope', '-q', '-p', 'MemoryMax=3G', '-p', 'MemorySwapMax=0',
           'claude', '-p', '--safe-mode', '--model', MODEL, '--effort', EFFORT, '--tools', 'Read', '--allowedTools', 'Read',
           '--no-session-persistence', '--output-format', 'json', '--json-schema', json.dumps(SCHEMA)]
    p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=3600)
    res = json.loads(p.stdout)
    if res.get('is_error') or not res.get('structured_output'):
        raise RuntimeError(str(res)[:400])
    res['_prompt'] = prompt
    os.makedirs(CACHE, exist_ok=True)
    json.dump(res, open(path, 'w'))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('year', type=int)
    ap.add_argument('--n', type=int, default=100)
    ap.add_argument('--seed', type=int)
    ap.add_argument('--per', type=int, default=10)
    ap.add_argument('--workers', type=int, default=5)
    ap.add_argument('--layout', help='only chunks of these layouts')
    ap.add_argument('--obs', default='v4', help="which extraction: v4 (first pass) or v4r (reviewed)")
    a = ap.parse_args()
    seed = a.seed if a.seed is not None else a.year
    chunks = {json.loads(l)['id']: json.loads(l) for l in open(os.path.join(DATA, 'chunks', f'{a.year}.jsonl'))}
    obs = []
    for l in open(os.path.join(DATA, 'obs', f'{a.year}_{a.obs}.jsonl')):
        r = json.loads(l)
        c = chunks[r['chunk']]
        if c['observations'] != 'primary' or (a.layout and c['layout'] not in a.layout.split(',')):
            continue
        for k, o in enumerate(r['obs'] or []):
            obs.append((r['chunk'], k, o))
    rng = random.Random(seed)
    LANTERN = ('dead', 'struck', 'round_lantern', 'round_station', 'caught', 'lost_over')
    first = rng.sample(obs, a.n // 2)
    taken = {(c, k) for c, k, _ in first}
    lan = [x for x in obs if (x[2]['at_light'] or x[2]['behaviour'] in LANTERN) and (x[0], x[1]) not in taken]
    sample = [(x, 'uniform') for x in first] + [(x, 'lantern') for x in rng.sample(lan, min(len(lan), a.n - a.n // 2))]
    items, plants = [], []
    for i, ((cid, k, o), stratum) in enumerate(sample, 1):
        c = chunks[cid]
        t, m = ws_norm_with_map(c['text'])
        j = t.find(ws_norm(o['quote']))
        start = c['start'] + (m[j] if j >= 0 else 0)
        end = c['start'] + (m[min(len(m) - 1, j + len(ws_norm(o['quote'])) - 1)] + 1 if j >= 0 else len(c['text']))
        imgs, pages = images_for(a.year, c, start, end, c['reading'])
        rec = {f: o.get(f) for f in CHECK}
        truth = copy.deepcopy(rec)
        stations = sorted({x['station'] for x in json.loads(json.dumps([oo for cc, kk, oo in obs if cc == cid])) if x['station']})
        pl = plant(rec, rng, stations) if rng.random() < 1 / 6 else None
        if pl:
            plants.append({'item': i, 'field': pl[0], 'extracted': pl[1], 'planted': pl[2]})
        items.append({'item': i, 'chunk': cid, 'k': k, 'stratum': stratum, 'layout': c['layout'], 'images': imgs, 'pages': pages,
                      'quote': ws_norm(o['quote']), 'shown': rec, 'extracted': truth})
    print(f'{len(items)} items, {len(plants)} planted, {len({x for it in items for x in it["images"]})} images', flush=True)
    textkind = 'Project Gutenberg transcription' if items and chunks[items[0]['chunk']]['reading'] == 'gutenberg' else \
        "the Internet Archive's OCR of the report, which garbles some letters and figures"
    ocrnote = '' if 'Gutenberg' in textkind else '; it is OCR text, so expect garbled letters in it, and judge the fields by what the print says'
    brief = BRIEF.format(textkind=textkind, ocrnote=ocrnote, year=a.year)
    batches = [items[k:k + a.per] for k in range(0, len(items), a.per)]

    def prompt_for(b):
        return brief + '\n\n'.join(f"Item {it['item']}: page image(s) {', '.join(it['images'])}"
                                   + (f" (printed page {', '.join(it['pages'])})" if it['pages'] else '')
                                   + f".\n  quote: {it['quote']!r}\n  record: " + json.dumps(it['shown'], ensure_ascii=False) for it in b)

    results = {}
    with cf.ThreadPoolExecutor(a.workers) as ex:
        futs = {ex.submit(ask, prompt_for(b), hashlib.sha256((MODEL + prompt_for(b)).encode()).hexdigest()[:20]): k
                for k, b in enumerate(batches)}
        for f in cf.as_completed(futs):
            try:
                for v in f.result()['structured_output']['items']:
                    results[v['item']] = v
            except Exception as e:
                print('batch FAILED', e, flush=True)
    os.makedirs(os.path.join(DATA, 'checks'), exist_ok=True)
    json.dump({'year': a.year, 'n': a.n, 'seed': seed, 'items': items, 'plants': plants, 'verdicts': results},
              open(os.path.join(DATA, 'checks', f't3_{a.year}_{a.obs}.json'), 'w'), indent=1, ensure_ascii=False)
    planted = {(x['item'], x['field']) for x in plants}
    caught = sum(1 for (i, f) in planted if results.get(i, {}).get('fields', {}).get(f, {}).get('verdict') == 'wrong')
    print(f'planted errors caught: {caught}/{len(planted)}')
    flagged, checked, unclear = [], 0, 0
    for it in items:
        v = results.get(it['item'])
        if not v:
            continue
        for f in CHECK:
            if (it['item'], f) in planted:
                continue
            checked += 1
            vd = v['fields'][f]['verdict']
            unclear += vd == 'unclear'
            if vd == 'wrong':
                flagged.append((it['item'], it['stratum'], it['chunk'], f, it['extracted'][f], v['fields'][f]['print_says']))
    print(f'unplanted fields checked: {checked}; flagged wrong: {len(flagged)}; unclear: {unclear}; '
          f'not found: {sum(1 for v in results.values() if not v["found"])}')
    for x in flagged:
        print('   flag', x)


if __name__ == '__main__':
    main()
