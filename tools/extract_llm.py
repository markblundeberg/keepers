"""Extract bird observations from segments with an LLM, in batches.

Each batch of segments goes to `claude -p` in safe mode (no CLAUDE.md, no
customisations), with no tools, under a memory cap, asking for JSON that
matches SCHEMA. Raw replies are cached under cache/llm/ by a hash of the
prompt, so a rerun only asks again for what changed.

Every string the model returns (except `note`) must be an exact substring
of its segment; tools/validate.py checks that (T1, T2).

Run: python3 -I tools/extract_llm.py 1887 [--ver v2] [--limit 2] [--workers 6] [--batch 40]
  -> data/pilot/obs_llm_<year>_<ver>.jsonl and data/pilot/wx_llm_<year>_<ver>.jsonl
"""
import argparse, concurrent.futures as cf, hashlib, json, os, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA, ROOT

EFFORT = 'high'
PROMPTS = os.path.join(ROOT, 'tools', 'prompts')
CACHE = os.path.join(ROOT, 'cache', 'llm')
SECTION_NAMES = {'ENE': 'East Coast of England, diary', 'ENW': 'West Coast of England and Wales, and the Isle of Man, diary'}
BEHAVIOURS = {'v1': ['passing', 'round_lantern', 'struck', 'dead', 'caught', 'shot', 'settled', 'heard', 'seen', 'same_as']}
BEHAVIOURS['v2'] = BEHAVIOURS['v1'][:2] + ['round_station'] + BEHAVIOURS['v1'][2:]
BEHAVIOURS['v3'] = BEHAVIOURS['v2'][:4] + ['lost_over'] + BEHAVIOURS['v2'][4:]
S, N = {'type': 'string'}, {'type': ['string', 'null']}


def schema(ver):
    obs_props = {'quote': S, 'species': N, 'count': N, 'count_shared': {'type': 'boolean'},
                 'behaviour': {'type': 'string', 'enum': BEHAVIOURS[ver]}, 'at_light': {'type': 'boolean'},
                 'time': N, 'direction': N, 'other_dates': N, 'specimen': N, 'note': N}
    if ver != 'v1':
        obs_props['total'] = {'type': 'boolean'}
    return {'type': 'object', 'required': ['segments'], 'properties': {'segments': {'type': 'array', 'items': {
        'type': 'object', 'required': ['seg', 'wind', 'force', 'weather', 'obs'],
        'properties': {'seg': S, 'wind': N, 'force': N, 'weather': N, 'obs': {'type': 'array', 'items': {
            'type': 'object', 'required': list(obs_props), 'properties': obs_props}}}}}}}


def norm(s):
    return ' '.join(s.split())


def make_batches(segs, size):
    """Consecutive segments, cut only between dates (a big date stays whole)."""
    out, cur = [], []
    for r in segs:
        if cur and len(cur) >= size and (r['section'], r['date']) != (cur[-1]['section'], cur[-1]['date']):
            out.append(cur)
            cur = []
        cur.append(r)
    if cur:
        out.append(cur)
    return out


def build_prompt(batch, year, ver):
    tpl = open(os.path.join(PROMPTS, f'extract_diary_{ver}.md'), encoding='utf-8').read()
    lines = '\n'.join(f"[{r['seg_id']}] {norm(r['text'])}" for r in batch)
    sec = batch[0]['section']
    return tpl.format(year=year, section_name=SECTION_NAMES.get(sec, sec), segments=lines)


def ask(prompt, tag, ver, model):
    SCHEMA = schema(ver)
    key = hashlib.sha256((model + EFFORT + json.dumps(SCHEMA) + prompt).encode()).hexdigest()[:20]
    path = os.path.join(CACHE, f'{key}.json')
    if os.path.exists(path):
        return json.load(open(path)), True
    cmd = ['systemd-run', '--user', '--scope', '-q', '-p', 'MemoryMax=3G', '-p', 'MemorySwapMax=0',
           'claude', '-p', '--safe-mode', '--model', model, '--effort', EFFORT, '--tools', '',
           '--no-session-persistence', '--output-format', 'json', '--json-schema', json.dumps(SCHEMA)]
    t0 = time.time()
    p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=3600)
    if p.returncode != 0:
        raise RuntimeError(f'{tag}: exit {p.returncode}: {p.stderr[-500:]} {p.stdout[-500:]}')
    res = json.loads(p.stdout)
    if res.get('is_error') or not res.get('structured_output'):
        raise RuntimeError(f'{tag}: no structured output: {str(res)[:500]}')
    res['_wall_s'] = round(time.time() - t0, 1)
    res['_prompt'] = prompt
    os.makedirs(CACHE, exist_ok=True)
    json.dump(res, open(path, 'w'))
    return res, False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('year', type=int)
    ap.add_argument('--limit', type=int, default=0, help='only the first N batches')
    ap.add_argument('--workers', type=int, default=6)
    ap.add_argument('--batch', type=int, default=40)
    ap.add_argument('--ver', default='v2')
    ap.add_argument('--model', default='claude-opus-5-5')
    a = ap.parse_args()
    # outputs are tagged by prompt version, plus the model when it isn't Opus: v2, v2-sonnet
    tag = a.ver if 'opus' in a.model else f"{a.ver}-{a.model.split('-')[1]}"
    segs = [json.loads(l) for l in open(os.path.join(DATA, 'pilot', f'segments_{a.year}.jsonl'))]
    batches = make_batches(segs, a.batch)
    if a.limit:
        batches = batches[:a.limit]
    print(f'{len(segs)} segments in {len(batches)} batches; asking {a.model} ({EFFORT}), prompt {a.ver}, tag {tag}', flush=True)
    results = {}
    with cf.ThreadPoolExecutor(a.workers) as ex:
        futs = {ex.submit(ask, build_prompt(b, a.year, a.ver), f'batch {i}', a.ver, a.model): i for i, b in enumerate(batches)}
        for f in cf.as_completed(futs):
            i = futs[f]
            try:
                res, cached = f.result()
            except Exception as e:
                print(f'batch {i} FAILED: {e}', flush=True)
                continue
            results[i] = res
            got = {s['seg'] for s in res['structured_output']['segments']}
            want = {r['seg_id'] for r in batches[i]}
            print(f'batch {i}: {len(want)} segs, {sum(len(s["obs"]) for s in res["structured_output"]["segments"])} obs, '
                  f'missing {sorted(want - got)[:5]}, extra {sorted(got - want)[:5]}, '
                  f'{"cached" if cached else str(res.get("_wall_s")) + " s"}, ${res.get("total_cost_usd", 0):.3f}', flush=True)
    seg_by_id = {r['seg_id']: r for r in segs}
    n_obs = 0
    with open(os.path.join(DATA, 'pilot', f'obs_llm_{a.year}_{tag}.jsonl'), 'w') as fo, \
         open(os.path.join(DATA, 'pilot', f'wx_llm_{a.year}_{tag}.jsonl'), 'w') as fw:
        for i in sorted(results):
            for s in results[i]['structured_output']['segments']:
                if s['seg'] not in seg_by_id:
                    continue
                fw.write(json.dumps({'seg_id': s['seg'], 'wind': s['wind'], 'force': s['force'],
                                     'weather': s['weather'], 'n_obs': len(s['obs'])}, ensure_ascii=False) + '\n')
                for k, o in enumerate(s['obs']):
                    fo.write(json.dumps({'obs_id': f"{s['seg']}.{k + 1}", 'seg_id': s['seg'], **o}, ensure_ascii=False) + '\n')
                    n_obs += 1
    cost = sum(r.get('total_cost_usd', 0) for r in results.values())
    print(f'wrote {n_obs} observations from {len(results)}/{len(batches)} batches; total ${cost:.2f}')


if __name__ == '__main__':
    main()
