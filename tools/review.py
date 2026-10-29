"""A targeted review of the extraction where it matters most: every primary
chunk that mentions the light, the lantern, striking, killing or catching is
re-read by a helper beside the observations already extracted from it, and
only what the text contradicts is corrected. T3 found the first pass's errors
to cluster there, and all one way: a time stated elsewhere in the sentence
left out; at_light false where the text ties the birds to the light;
'seen' where the text says killed, struck or settled; a companion species
taken for the section's own.

Run: python3 -I tools/review.py <year> [--workers 8]
  -> data/obs/<year>_v4r.jsonl (reviewed chunks replaced, the rest as extracted)
"""
import argparse, concurrent.futures as cf, hashlib, json, os, re, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA, ROOT
from extract import BEHAVIOURS, CACHE, EFFORT, MODEL, OBS

LANTERN = re.compile(r'\b(lights?|lantern|lamp|glass|gallery|rays?|struck|strik\w*|killed|dead|caught|captured|taken)\b', re.I)
REVIEW_OBS = dict(OBS, change={'type': ['string', 'null']})
SCHEMA = {'type': 'object', 'required': ['obs'], 'properties': {
    'obs': {'type': 'array', 'items': {'type': 'object', 'required': list(REVIEW_OBS), 'properties': REVIEW_OBS}}}}

BRIEF = '''You are checking an extraction from a Victorian bird-migration report ({year}): lighthouse and light-vessel keepers' records of birds, printed by a British Association committee. Below is one CHUNK of the report (with the CONTEXT just before it), and the observations a first reader extracted from the chunk. The extraction rules are at the end.

Please re-read the chunk and return the corrected list of observations. Change only what the text contradicts or leaves out; keep everything else exactly as given. A second reading of the print found the first reader's mistakes to fall mostly here:
- time: a time stated elsewhere in the same sentence or clause and governing this observation ("from 1 to 4 a.m.; six Starlings ... killed" gives the killed birds that time) was left null.
- at_light: false although the text ties these birds to the light or lantern ("in the vicinity of light", "at the lantern", "against the glass", "in the rays").
- behaviour: 'seen' or 'passing' although the text says they were killed or found dead (dead), struck (struck), caught or taken (caught), alighted or rested (settled), or flew round the light (round_lantern) or the ship or rock (round_station).
- count: a number the text gives for these birds ("five killed") left null.
- species: the species of the heading the chunk sits under replaced by a companion species named only in passing ("seen amongst Flycatchers").
- a bird kind or a behaviour the text states but no observation gives (add it).
Each observation in your answer: every field as in the extraction rules, plus `change`: null if you kept the observation exactly, else a few words on what you changed and why ("time from 'from 1 to 4 a.m.'"; "added: five killed"). Keep the order; put added observations where they belong.

CONTEXT (do not extract from it):
<<<{context}>>>
CHUNK [{chunk}] (coast: {coast}; section: {title}; layout: {layout}):
<<<{text}>>>
EXTRACTED OBSERVATIONS:
{obs}

THE EXTRACTION RULES (as the first reader had them):
{rules}'''


def rules_text():
    p = open(os.path.join(ROOT, 'tools', 'prompts', 'extract_v4.md')).read()
    a = p.index('THE MOST IMPORTANT RULE')
    b = p.index('The chunks:')
    return p[a:b].replace('{{', '{').replace('}}', '}').replace('{year}', 'the report year').replace('{next_year}', 'the next year')


def call(year, c, obs, rules):
    prompt = BRIEF.format(year=year, context=c['context'], chunk=c['id'], coast=c['coast'], title=c['title'] or '-', layout=c['layout'],
                          text=c['text'], obs=json.dumps(obs, ensure_ascii=False, indent=0), rules=rules)
    h = hashlib.sha256((MODEL + EFFORT + json.dumps(SCHEMA) + prompt).encode()).hexdigest()[:24]
    path = os.path.join(CACHE, f'review_{h}.json')
    if os.path.exists(path):
        return json.load(open(path))
    cmd = ['systemd-run', '--user', '--scope', '-q', '-p', 'MemoryMax=3G', '-p', 'MemorySwapMax=0',
           'claude', '-p', '--safe-mode', '--model', MODEL, '--effort', EFFORT, '--tools', '',
           '--no-session-persistence', '--output-format', 'json', '--json-schema', json.dumps(SCHEMA)]
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
        raise RuntimeError(f'{c["id"]}: review failed')
    json.dump(res, open(path, 'w'))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('year', type=int)
    ap.add_argument('--workers', type=int, default=8)
    a = ap.parse_args()
    chunks = {json.loads(l)['id']: json.loads(l) for l in open(os.path.join(DATA, 'chunks', f'{a.year}.jsonl'))}
    rows = [json.loads(l) for l in open(os.path.join(DATA, 'obs', f'{a.year}_v4.jsonl'))]
    rules = rules_text()
    todo = [r for r in rows if r['obs'] and chunks[r['chunk']]['observations'] == 'primary' and LANTERN.search(chunks[r['chunk']]['text'])]
    out = {r['chunk']: r for r in rows}
    changed = added = removed = 0
    with cf.ThreadPoolExecutor(a.workers) as ex:
        futs = {ex.submit(call, a.year, chunks[r['chunk']], r['obs'], rules): r for r in todo}
        for f in cf.as_completed(futs):
            r = futs[f]
            try:
                new = f.result()['structured_output']['obs']
            except Exception as e:
                print('  FAILED', r['chunk'], e, flush=True)
                continue
            changed += sum(1 for o in new if o.get('change'))
            added += max(0, len(new) - len(r['obs']))
            removed += max(0, len(r['obs']) - len(new))
            out[r['chunk']] = {'chunk': r['chunk'], 'obs': new, 'reviewed': True}
    with open(os.path.join(DATA, 'obs', f'{a.year}_v4r.jsonl'), 'w') as fo:
        for r in rows:
            fo.write(json.dumps(out[r['chunk']], ensure_ascii=False) + '\n')
    print(f'{a.year}: reviewed {len(todo)} of {len(rows)} chunks; observations marked changed {changed}; net added {added}, '
          f'net removed {removed}')


if __name__ == '__main__':
    main()
