"""Ask a safe-mode helper point questions about what the print shows, one
crop per question, options in random order and unlabelled as to source.
Generalises T6's resolve step to any reading (symbols, letters, numbers).

Input: a JSON list of {"seg_id", "near", "question", "options": [...]}.
Run: python3 -I tools/scan_questions.py 1887 questions.json  ->  questions_answered.json
"""
import json, os, random, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import ROOT
from crop import crop


def ask(year, qs, seed=0):
    rng = random.Random(seed)
    lines = []
    for k, q in enumerate(qs, 1):
        paths = crop(year, q['seg_id'], os.path.join(ROOT, 'cache', 'crops', 'questions'), band=q.get('band', 0.3))
        opts = list(q['options'])
        rng.shuffle(opts)
        q['shown'] = opts
        lines.append(f"Item {k}: image(s) {', '.join(paths)}. Near the words {q['near']!r}: {q['question']} "
                     f"Options: {' / '.join(repr(o) for o in opts)}, or 'other', or 'unclear'.")
    brief = ('I am checking a transcription of an 1887 bird-migration report against the printed page. For each '
             'item, open the cropped scan(s) with the Read tool, find the words given, and answer from the print '
             'alone. Trust the page over every option. If the entry runs onto a second image, it is the top of the '
             'next page.\n\n' + '\n'.join(lines))
    schema = {'type': 'object', 'required': ['items'], 'properties': {'items': {'type': 'array', 'items': {
        'type': 'object', 'required': ['item', 'answer', 'printed'],
        'properties': {'item': {'type': 'integer'}, 'answer': {'type': 'string'}, 'printed': {'type': 'string'}}}}}}
    cmd = ['systemd-run', '--user', '--scope', '-q', '-p', 'MemoryMax=3G', '-p', 'MemorySwapMax=0',
           'claude', '-p', '--safe-mode', '--model', 'claude-opus-5-5', '--effort', 'high', '--tools', 'Read',
           '--allowedTools', 'Read', '--no-session-persistence', '--output-format', 'json', '--json-schema', json.dumps(schema)]
    p = subprocess.run(cmd, input=brief, capture_output=True, text=True, timeout=3600)
    res = json.loads(p.stdout)
    ans = {v['item']: v for v in res['structured_output']['items']}
    for k, q in enumerate(qs, 1):
        q['answer'] = ans.get(k, {}).get('answer')
        q['printed'] = ans.get(k, {}).get('printed')
    return qs, res.get('total_cost_usd')


if __name__ == '__main__':
    year, path = int(sys.argv[1]), sys.argv[2]
    qs, cost = ask(year, json.load(open(path)))
    out = path.replace('.json', '_answered.json')
    json.dump(qs, open(out, 'w'), indent=1, ensure_ascii=False)
    for q in qs:
        print(f"  {q['seg_id']}: {q.get('gutenberg', '')!r} -> {q['answer']!r} ({q['printed']!r})")
    print(f'cost ${cost:.2f} -> {out}')
