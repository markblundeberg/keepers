"""T3: check a random sample of extracted observations against the printed
page, read from the Internet Archive scans by safe-mode helpers.

Known errors are planted in about one item in six of what the checkers see
(they aren't told which, or how many), so the check's sensitivity is measured
alongside the error rate. Unplanted fields the checkers call wrong are
candidates, to be adjudicated by looking at the scan.

Run: python3 -I tools/t3_check.py 1887 [--n 100] [--seed 1887] [--per 10] [--workers 5]
  -> data/pilot/t3_<year>.json (sample, plants, verdicts) and a summary on stdout
"""
import argparse, concurrent.futures as cf, copy, hashlib, json, os, random, re, subprocess, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA, MANIFEST, ROOT, Pages, ws_norm

MODEL, EFFORT = 'claude-opus-5-5', 'high'
SCANS = os.path.join(ROOT, 'cache', 'scans')
CACHE = os.path.join(ROOT, 'cache', 't3')
CHECK = ['species', 'count', 'behaviour', 'at_light', 'time', 'direction', 'wind', 'force', 'weather']
V = {'type': 'object', 'required': ['verdict', 'print_says'],
     'properties': {'verdict': {'type': 'string', 'enum': ['ok', 'wrong', 'unclear']}, 'print_says': {'type': ['string', 'null']}}}
SCHEMA = {'type': 'object', 'required': ['items'], 'properties': {'items': {'type': 'array', 'items': {
    'type': 'object', 'required': ['item', 'found', 'transcription_diffs', 'fields'],
    'properties': {'item': {'type': 'integer'}, 'found': {'type': 'boolean'},
                   'transcription_diffs': {'type': 'array', 'items': {'type': 'string'}},
                   'fields': {'type': 'object', 'required': CHECK, 'properties': {f: V for f in CHECK}}}}}}}

BRIEF = '''Thank you for helping. I'm a Claude agent turning the 1887 British Association "Report on the Migration of Birds" back into data: the lighthouse and light-vessel keepers' records of the birds they saw. A transcription and an extraction have been made from a Project Gutenberg text, and this is the check against the printed page itself, read from the Internet Archive's scans. Your reading is the independent one, so please trust the page over anything written here.

For each item below: open the page image(s) with the Read tool, find the entry (station and date are given; the diary runs by date, with station names in italics), and check the record against the print. Some records may contain errors; that's what we're measuring, so please judge every field afresh.

1. `transcription_diffs`: compare the quoted text with the print, letter by letter. List every difference (wrong letter, missing or extra punctuation, word), e.g. "print has 'W.S.W.,' where quote has 'W.S.W,'". Ignore line breaks, hyphenation at line ends, italics and small capitals. Empty list if identical.
2. `fields`: for each field, verdict "ok", "wrong" (and in `print_says` what the print supports), or "unclear". The fields follow these definitions:
   - species: the bird name as printed. count: the number or quantity words as printed (null if none stated).
   - behaviour: passing (flying past/over/along, migrating); round_lantern (flying round or at the lantern or light); round_station (flying round or about the ship, vessel, rock, island or lighthouse, not said to be the lantern); struck (striking the lantern, not said killed); dead (killed or found dead; count = number dead); caught; shot; settled (resting on vessel, deck, rigging, rock, island, lighthouse); heard; seen (present, nothing more specific stated); same_as (only says "the same as" another day). The most specific the text states, without inference.
   - at_light: true only if the text connects these birds to the lantern or light.
   - time: the time of day as printed. direction: the flight direction as printed (never the wind).
   - wind, force, weather: from the weather bracket of this station's entry, as printed (null if none).
   A null field is "ok" if the print states nothing for it, "wrong" if it does.
3. `found`: false if you can't find the entry on the given page(s); then mark fields "unclear".

Give `item` as the item number. Here are the items:

'''


def fetch(year, idx):
    os.makedirs(os.path.join(SCANS, str(year)), exist_ok=True)
    path = os.path.join(SCANS, str(year), f'n{idx}.jpg')
    if not os.path.exists(path):
        url = MANIFEST[str(year)]['page_image_pattern'].format(index=idx)
        req = urllib.request.Request(url, headers={'User-Agent': 'keepers-project/0.1 (research; via Mark Lundeberg)'})
        data = urllib.request.urlopen(req, timeout=120).read()
        open(path, 'wb').write(data)
        time.sleep(1.0)
    return path


ALT_COUNT = {'one': 'two', 'two': 'three', 'three': 'four', 'four': 'five', 'five': 'six', 'six': 'seven',
             'a': 'two', 'several': 'a few', 'a few': 'several', 'many': 'a few', 'large flocks': 'small flocks'}
ALT_BEH = {'passing': 'seen', 'seen': 'passing', 'dead': 'caught', 'caught': 'dead', 'round_lantern': 'passing',
           'struck': 'dead', 'settled': 'passing', 'shot': 'seen', 'heard': 'seen', 'same_as': 'seen',
           'round_station': 'round_lantern', 'lost_over': 'dead'}
ALT_DIR = {'N': 'S', 'S': 'N', 'E': 'W', 'W': 'E'}


def plant(rec, rng):
    """Alter one field plausibly; returns (field, old, new) or None."""
    opts = []
    if rec['count'] and (rec['count'].lower() in ALT_COUNT or re.fullmatch(r'\d+', rec['count'])):
        opts.append('count')
    opts.append('behaviour')
    if rec['time'] and re.search(r'\d', rec['time']):
        opts.append('time')
    if rec['direction'] and re.search(r'[NSEW]', rec['direction']):
        opts.append('direction')
    if rec['wind'] and re.search(r'[NSEW]', rec['wind']):
        opts.append('wind')
    f = rng.choice(opts)
    old = rec[f]
    if f == 'count':
        new = ALT_COUNT.get(old.lower()) or str(int(old) * 2 if int(old) > 1 else 3)
    elif f == 'behaviour':
        new = ALT_BEH[old]
    elif f == 'time':
        new = re.sub(r'\d+', lambda m: str(int(m.group(0)) % 12 + 1), old, count=1)
    else:
        new = re.sub(r'[NSEW]', lambda m: ALT_DIR[m.group(0)], old, count=1)
    rec[f] = new
    return f, old, new


def ask(prompt, key):
    path = os.path.join(CACHE, f'{key}.json')
    if os.path.exists(path):
        return json.load(open(path))
    cmd = ['systemd-run', '--user', '--scope', '-q', '-p', 'MemoryMax=3G', '-p', 'MemorySwapMax=0',
           'claude', '-p', '--safe-mode', '--model', MODEL, '--effort', EFFORT, '--tools', 'Read',
           '--allowedTools', 'Read', '--no-session-persistence', '--output-format', 'json',
           '--json-schema', json.dumps(SCHEMA)]
    p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=3600, cwd=SCANS)
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
    ap.add_argument('--ver', default='v2')
    ap.add_argument('--n', type=int, default=100)
    ap.add_argument('--seed', type=int, default=1887)
    ap.add_argument('--per', type=int, default=10)
    ap.add_argument('--workers', type=int, default=5)
    ap.add_argument('--stratify', action='store_true', help='half the sample from lantern events')
    a = ap.parse_args()
    p = os.path.join(DATA, 'pilot')
    segs = {s['seg_id']: s for s in (json.loads(l) for l in open(os.path.join(p, f'segments_{a.year}.jsonl')))}
    obs = [json.loads(l) for l in open(os.path.join(p, f'obs_llm_{a.year}_{a.ver}.jsonl'))]
    wx = {w['seg_id']: w for w in (json.loads(l) for l in open(os.path.join(p, f'wx_llm_{a.year}_{a.ver}.jsonl')))}
    pages = Pages(a.year)
    rng = random.Random(a.seed)
    if a.stratify:      # half uniform, half from the lantern events (reported separately)
        LANTERN = ('dead', 'struck', 'round_lantern', 'round_station', 'caught')
        lan = [o for o in obs if o['at_light'] or o['behaviour'] in LANTERN]
        first = rng.sample(obs, a.n // 2)
        ids = {o['obs_id'] for o in first}
        sample = first + rng.sample([o for o in lan if o['obs_id'] not in ids], a.n - a.n // 2)
    else:
        sample = rng.sample(obs, a.n)
    stratum = {o['obs_id']: ('uniform' if not a.stratify or k < a.n // 2 else 'lantern') for k, o in enumerate(sample)}
    items, plants = [], []
    for i, o in enumerate(sample, 1):
        s = segs[o['seg_id']]
        m0, m1 = pages.at(s['start']), pages.at(s['end'] - 1)
        idxs = sorted({m0['image_index'], m1['image_index']})
        rec = {f: o.get(f) for f in CHECK if f in o}
        rec.update({f: wx[o['seg_id']][f] for f in ('wind', 'force', 'weather')})
        truth = copy.deepcopy(rec)
        pl = plant(rec, rng) if rng.random() < 1 / 6 else None
        if pl:
            plants.append({'item': i, 'field': pl[0], 'extracted': pl[1], 'planted': pl[2]})
        items.append({'item': i, 'obs_id': o['obs_id'], 'stratum': stratum[o['obs_id']], 'station': ' '.join(s['head'].split()) if s['head'] else None,
                      'date': s['date'], 'pages': [m0['page']] + ([m1['page']] if m1['page'] != m0['page'] else []),
                      'images': [fetch(a.year, k) for k in idxs], 'quote': ws_norm(o['quote']),
                      'shown': rec, 'extracted': truth})
    print(f'{len(items)} items, {len(plants)} planted errors, {len({x for it in items for x in it["images"]})} page images', flush=True)
    batches = [items[k:k + a.per] for k in range(0, len(items), a.per)]

    def prompt_for(b):
        lines = []
        for it in b:
            lines.append(f"Item {it['item']}: page image(s) {', '.join(it['images'])} (printed page {', '.join(it['pages'])}); "
                         f"station {it['station']}; date {it['date']}.\n  quote: {it['quote']!r}\n  record: "
                         + json.dumps(it['shown'], ensure_ascii=False))
        return BRIEF + '\n\n'.join(lines)

    results = {}
    with cf.ThreadPoolExecutor(a.workers) as ex:
        futs = {ex.submit(ask, prompt_for(b), hashlib.sha256((MODEL + prompt_for(b)).encode()).hexdigest()[:20]): k
                for k, b in enumerate(batches)}
        for f in cf.as_completed(futs):
            k = futs[f]
            try:
                res = f.result()
            except Exception as e:
                print(f'batch {k} FAILED: {e}', flush=True)
                continue
            for v in res['structured_output']['items']:
                results[v['item']] = v
            print(f'batch {k} done, ${res.get("total_cost_usd", 0):.2f}', flush=True)
    out = {'year': a.year, 'n': a.n, 'seed': a.seed, 'model': MODEL, 'items': items, 'plants': plants,
           'verdicts': results}
    json.dump(out, open(os.path.join(p, f't3_{a.year}_{a.ver}.json'), 'w'), indent=1, ensure_ascii=False)

    # score
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
                flagged.append((it['item'], it['obs_id'], f, it['extracted'][f], v['fields'][f]['print_says']))
    for st in sorted({it['stratum'] for it in items}):
        its = [it for it in items if it['stratum'] == st and it['item'] in results]
        fl = [x for x in flagged if any(it['item'] == x[0] for it in its)]
        print(f'  stratum {st}: {len(its)} items, {len(fl)} flags on unplanted fields')
    print(f'unplanted fields checked: {checked}; flagged wrong: {len(flagged)}; unclear: {unclear}; '
          f'not found: {sum(1 for v in results.values() if not v["found"])}')
    for x in flagged:
        print('   flag', x)
    td = [(it['item'], it['obs_id'], d) for it in items if it['item'] in results for d in results[it['item']]['transcription_diffs']]
    print(f'transcription differences reported: {len(td)} in {len({x[0] for x in td})} of {len(results)} quotes')
    for x in td:
        print('   diff', x)


if __name__ == '__main__':
    main()
