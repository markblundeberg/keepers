"""T6: the Gutenberg transcription against a second witness, the Internet
Archive's OCR of the same scans, number by number.

Two independent readings of the print (volunteer proofreaders; a machine)
rarely make the same slip, so where their numbers disagree one of them is
wrong, and the scan decides. Each segment is located in the OCR by word
shingles that occur once there, then the two word sequences are aligned and
every number (times, counts, forces, dates) is compared.

Run: python3 -I tools/witness.py 1887  ->  data/pilot/witness_1887.json and a summary
"""
import collections, difflib, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA, ROOT as ROOT_DIR, read_source

TOK = re.compile(r'[A-Za-zÀ-ɏ]+|\d+(?:\.\d+)?')


def toks(s):
    return [(m.group(0).lower(), m.start()) for m in TOK.finditer(s)]


def main(year):
    ocr = read_source(year, 'ia_ocr')
    ot = toks(ocr)
    ow = [w for w, _ in ot]
    shingle = collections.defaultdict(list)
    for i in range(len(ow) - 2):
        shingle[(ow[i], ow[i + 1], ow[i + 2])].append(i)
    segs = [json.loads(l) for l in open(os.path.join(DATA, 'pilot', f'segments_{year}.jsonl'))]
    src = read_source(year)
    # align whole date paragraphs (more anchors than one short entry), then
    # credit each difference to the segment its tokens fall in
    paras = collections.OrderedDict()
    for s in segs:
        paras.setdefault((s['section'], s['date_raw'], s['start'] // 1 if False else None), []).append(s)
    blocks = []
    for s in segs:
        if blocks and blocks[-1][-1]['section'] == s['section'] and blocks[-1][-1]['date_raw'] == s['date_raw'] \
                and src[blocks[-1][-1]['end']:s['start']].strip() == '':
            blocks[-1].append(s)
        else:
            blocks.append([s])
    out, n_num, n_same, n_unaligned = [], 0, 0, 0
    for blk in blocks:
        start, end = blk[0]['start'], blk[-1]['end']
        text = src[start:end]
        st = toks(text)
        sw = [w for w, _ in st]
        seg_of = [next(x['seg_id'] for x in blk if x['start'] <= start + p < x['end'] + 1) for _, p in st]
        votes = []
        for i in range(len(sw) - 2):
            hits = shingle.get((sw[i], sw[i + 1], sw[i + 2]), [])
            if len(hits) == 1:
                votes.append(hits[0] - i)
        nums = [w for w in sw if w[0].isdigit()]
        base = sorted(votes)[len(votes) // 2] if votes else None
        if base is None or sum(1 for v in votes if abs(v - base) <= 3) < 2:      # one anchor isn't enough
            n_unaligned += len(nums)
            if nums:
                out.append({'seg_id': blk[0]['seg_id'], 'kind': 'unaligned', 'gutenberg': nums})
            continue
        a, b = max(0, base - 15), min(len(ow), base + len(sw) + 15)
        sm = difflib.SequenceMatcher(None, sw, ow[a:b], autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            g = [w for w in sw[i1:i2] if w[0].isdigit()]
            o = [w for w in ow[a + j1:a + j2] if w[0].isdigit()]
            if tag == 'equal':
                n_num += len(g)
                n_same += len(g)
            elif g:
                # a Gutenberg number the OCR reads differently (OCR-only digits are
                # mostly letters misread, "8" for S, "0" for O, so they're not compared)
                n_num += len(g)
                if g == o:
                    n_same += len(g)
                    continue
                if not o and not (tag == 'delete' and i1 > 0 and i2 < len(sw)):
                    continue
                ctx_g = text[st[max(0, i1 - 4)][1]: st[min(len(st) - 1, i2 + 3)][1] + 8]
                ctx_o = ocr[ot[a + max(0, j1 - 4)][1]: ot[min(len(ot) - 1, a + j2 + 3)][1] + 8]
                out.append({'seg_id': seg_of[i1], 'kind': tag, 'gutenberg': g, 'ocr': o,
                            'gutenberg_context': ' '.join(ctx_g.split()), 'ocr_context': ' '.join(ctx_o.split())})
    json.dump({'year': year, 'numbers_compared': n_num, 'numbers_agree': n_same, 'unaligned_numbers': n_unaligned,
               'disagreements': out}, open(os.path.join(DATA, 'pilot', f'witness_{year}.json'), 'w'), indent=1,
              ensure_ascii=False)
    kinds = collections.Counter(d['kind'] for d in out)
    print(f'{year}: {n_num} Gutenberg numbers in aligned segments, {n_same} agree with the OCR; '
          f'{n_unaligned} in segments not located; disagreements by kind {dict(kinds)}')
    return out


def resolve(year, workers=1):
    """Settle same-shaped number disagreements on the scan: a safe-mode helper
    reads a crop and says which reading is printed. The two readings are
    shown in random order, without saying which witness gave which."""
    import hashlib, random, subprocess
    from crop import crop
    d = json.load(open(os.path.join(DATA, 'pilot', f'witness_{year}.json')))
    shape = lambda x: re.sub(r'\d', '9', x)
    cands = [x for x in d['disagreements'] if x['kind'] == 'replace' and len(x['gutenberg']) == 1 == len(x['ocr'])
             and shape(x['gutenberg'][0]).count('.') == shape(x['ocr'][0]).count('.')]
    rng = random.Random(year)
    items, lines = [], []
    for k, x in enumerate(cands, 1):
        path = crop(year, x['seg_id'], os.path.join(ROOT_DIR, 'cache', 'crops', 'witness'), band=0.3)[0]
        pair = [x['gutenberg'][0], x['ocr'][0]]
        rng.shuffle(pair)
        items.append({'item': k, 'seg_id': x['seg_id'], 'shown': pair, **x})
        lines.append(f"Item {k}: image {path}. Near the words {x['gutenberg_context']!r}, is the number printed "
                     f"{pair[0]!r} or {pair[1]!r} (or something else)?")
    brief = ('I am checking a transcription of an 1887 bird-migration report against the printed page. Each item '
             'below gives a cropped scan and two candidate readings of one number. Please open each image with the '
             'Read tool, find the words given, and say exactly what is printed. Trust the page over either '
             'candidate; "other" if neither is right, "unclear" if the print is unreadable.\n\n' + '\n'.join(lines))
    schema = {'type': 'object', 'required': ['items'], 'properties': {'items': {'type': 'array', 'items': {
        'type': 'object', 'required': ['item', 'printed', 'verdict'],
        'properties': {'item': {'type': 'integer'}, 'printed': {'type': 'string'},
                       'verdict': {'type': 'string', 'enum': ['first', 'second', 'other', 'unclear']}}}}}}
    cmd = ['systemd-run', '--user', '--scope', '-q', '-p', 'MemoryMax=3G', '-p', 'MemorySwapMax=0',
           'claude', '-p', '--safe-mode', '--model', 'claude-opus-5-5', '--effort', 'high', '--tools', 'Read',
           '--allowedTools', 'Read', '--no-session-persistence', '--output-format', 'json', '--json-schema', json.dumps(schema)]
    p = subprocess.run(cmd, input=brief, capture_output=True, text=True, timeout=3600)
    res = json.loads(p.stdout)
    verdicts = {v['item']: v for v in res['structured_output']['items']}
    for it in items:
        v = verdicts.get(it['item'], {})
        it['printed'] = v.get('printed')
        it['verdict'] = v.get('verdict')
        it['winner'] = (it['shown'][0] if v.get('verdict') == 'first' else it['shown'][1] if v.get('verdict') == 'second' else None)
        it['source_right'] = ('gutenberg' if it['winner'] == it['gutenberg'][0] else 'ocr' if it['winner'] == it['ocr'][0] else None)
    json.dump({'year': year, 'cost_usd': res.get('total_cost_usd'), 'items': items},
              open(os.path.join(DATA, 'pilot', f'witness_{year}_resolved.json'), 'w'), indent=1, ensure_ascii=False)
    for it in items:
        print(f"  {it['seg_id']}: Gutenberg {it['gutenberg'][0]!r}, OCR {it['ocr'][0]!r} -> printed {it['printed']!r} "
              f"({it['source_right'] or it['verdict']})")
    print(f"cost ${res.get('total_cost_usd', 0):.2f}")


if __name__ == '__main__':
    if '--resolve' in sys.argv:
        resolve(int(sys.argv[1]))
        sys.exit()
    for d in main(int(sys.argv[1]))[:int(sys.argv[2]) if len(sys.argv) > 2 else 40]:
        if d['kind'] != 'unaligned':
            print(f"  {d['seg_id']} G{d['gutenberg']} O{d['ocr']} | G: {d['gutenberg_context'][:70]!r} | O: {d['ocr_context'][:70]!r}")
