"""Stage 3 extraction (prompt v4): the chunks of every report, in batches,
through Opus in safe mode with no tools and a JSON schema; every string
copied exactly from the chunk (or, flagged, from its context), the date also
read as an ISO date (checked against the copied words by tools/check_obs.py).
Replies cached under cache/llm/ by a hash of the prompt.

Run: python3 -I tools/extract.py 1887 [--only diary] [--workers 8] [--limit N]
  -> data/obs/<year>_v4.jsonl  (one line per chunk: {"chunk", "obs": [...]})
"""
import argparse, concurrent.futures as cf, hashlib, json, os, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA, ROOT

PROMPT = os.path.join(ROOT, 'tools', 'prompts', 'extract_v4.md')
CACHE = os.path.join(ROOT, 'cache', 'llm')
OUT = os.path.join(DATA, 'obs')
MODEL, EFFORT = 'claude-opus-5-5', 'high'
BATCH_CHARS = 6000
BEHAVIOURS = ['passing', 'round_lantern', 'round_station', 'lost_over', 'struck', 'dead', 'caught', 'shot', 'settled', 'heard', 'seen',
              'same_as']
S, N = {'type': 'string'}, {'type': ['string', 'null']}
OBS = {'quote': S, 'station': N, 'date': N, 'date_iso': N, 'wind': N, 'force': N, 'weather': N,
       'from_context': {'type': 'array', 'items': {'type': 'string', 'enum': ['species', 'station', 'date']}},
       'species': N, 'count': N, 'count_shared': {'type': 'boolean'}, 'total': {'type': 'boolean'},
       'behaviour': {'type': 'string', 'enum': BEHAVIOURS}, 'at_light': {'type': 'boolean'}, 'time': N, 'direction': N,
       'other_dates': N, 'specimen': N, 'note': N}
SCHEMA = {'type': 'object', 'required': ['chunks'], 'properties': {'chunks': {'type': 'array', 'items': {
    'type': 'object', 'required': ['chunk', 'obs'], 'properties': {
        'chunk': S, 'obs': {'type': 'array', 'items': {'type': 'object', 'required': list(OBS), 'properties': OBS}}}}}}}


def load_chunks(year):
    return [json.loads(l) for l in open(os.path.join(DATA, 'chunks', f'{year}.jsonl'))]


def batches(chunks):
    out, cur, n = [], [], 0
    for c in chunks:
        if cur and n + len(c['text']) > BATCH_CHARS:
            out.append(cur)
            cur, n = [], 0
        cur.append(c)
        n += len(c['text'])
    if cur:
        out.append(cur)
    return out


def render(c):
    head = f'[{c["id"]}] coast: {c["coast"]}; section: {c["title"] or "-"}; layout: {c["layout"]}; season: {c["season"]}'
    return f'{head}\nCONTEXT (do not extract from it):\n<<<{c["context"]}>>>\nCHUNK:\n<<<{c["text"]}>>>\n'


def call(year, batch, tag='v4'):
    prompt = open(PROMPT).read().format(year=year, next_year=year + 1, chunks='\n'.join(render(c) for c in batch))
    h = hashlib.sha256((MODEL + EFFORT + json.dumps(SCHEMA) + prompt).encode()).hexdigest()[:24]
    path = os.path.join(CACHE, f'{tag}_{h}.json')  # tag: a second reading keeps its own cache
    if os.path.exists(path):
        return json.load(open(path)), True
    cmd = ['systemd-run', '--user', '--scope', '-q', '-p', 'MemoryMax=3G', '-p', 'MemorySwapMax=0',
           'claude', '-p', '--safe-mode', '--model', MODEL, '--effort', EFFORT, '--tools', '',
           '--no-session-persistence', '--output-format', 'json', '--json-schema', json.dumps(SCHEMA)]
    t0 = time.time()
    for attempt in range(3):
        p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=3600)
        try:
            res = json.loads(p.stdout)
        except json.JSONDecodeError:
            res = {'is_error': True, 'raw': p.stdout[:500] + p.stderr[:500]}
        if not res.get('is_error') and res.get('structured_output'):
            break
        time.sleep(30 * (attempt + 1))
    else:
        raise RuntimeError(f'batch {batch[0]["id"]}..{batch[-1]["id"]}: {str(res)[:300]}')
    res['_wall_s'] = round(time.time() - t0)
    os.makedirs(CACHE, exist_ok=True)
    json.dump(res, open(path, 'w'))
    return res, False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('year', type=int)
    ap.add_argument('--only', help='layouts to run, comma-separated')
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--limit', type=int, help='first N batches only (a trial)')
    a = ap.parse_args()
    chunks = load_chunks(a.year)
    if a.only:
        chunks = [c for c in chunks if c['layout'] in a.only.split(',')]
    bs = batches(chunks)[:a.limit] if a.limit else batches(chunks)
    results, cost, t0 = {}, 0.0, time.time()
    with cf.ThreadPoolExecutor(a.workers) as ex:
        futs = {ex.submit(call, a.year, b): b for b in bs}
        for i, f in enumerate(cf.as_completed(futs), 1):
            b = futs[f]
            try:
                res, cached = f.result()
            except Exception as e:
                print(f'  FAILED {b[0]["id"]}: {e}', flush=True)
                continue
            got = {x['chunk']: x for x in res['structured_output']['chunks']}
            for c in b:
                results[c['id']] = got.get(c['id'], {'chunk': c['id'], 'obs': None})
            cost += res.get('total_cost_usd', 0) or 0
            if i % 10 == 0 or i == len(bs):
                print(f'  {i}/{len(bs)} batches; ${cost:.2f}; {round(time.time() - t0)} s', flush=True)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f'{a.year}_v4.jsonl')
    old = {}
    if os.path.exists(path):
        old = {json.loads(l)['chunk']: json.loads(l) for l in open(path)}
    old.update(results)
    with open(path, 'w') as f:
        for c in load_chunks(a.year):
            if c['id'] in old:
                f.write(json.dumps(old[c['id']], ensure_ascii=False) + '\n')
    missing = [c['id'] for c in chunks if c['id'] not in results or results[c['id']]['obs'] is None]
    print(f'{a.year}: {len(results)} chunks, {sum(len(r["obs"] or []) for r in results.values())} observations; '
          f'missing from replies: {missing[:10]}{"..." if len(missing) > 10 else ""}; ${cost:.2f}')


if __name__ == '__main__':
    main()
