"""What T3's flags mean: each field the scan checker called wrong (planted
errors aside) is classed by two independent helpers, from the chunk, the
record, the checker's reading of the print and the extraction rules:

  extraction  the record is wrong by the rules (the error rate counts these);
  checker     the record is right; the checker misread or misjudged;
  ocr_copy    the record copies the OCR text faithfully, as the rules ask,
              and the OCR garbles the print;
  gutenberg   the record copies the Gutenberg text faithfully and Gutenberg
              differs from the print (an erratum);
  judgement   the rules allow either reading.

Disagreements between the two are decided by hand in
data/checks/t3review/decided.json. Rates come with Wilson 95% intervals.

Run: python3 -I tools/t3_review.py ask <years> | compare <years> | rates
"""
import collections, concurrent.futures as cf, json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA
from extract import load_chunks
from review import rules_text
from station_lists import run_helper

OUT = os.path.join(DATA, 'checks', 't3review')
KINDS = ['extraction', 'checker', 'ocr_copy', 'gutenberg', 'judgement']
SCHEMA = {'type': 'object', 'required': ['flags'], 'properties': {'flags': {'type': 'array', 'items': {
    'type': 'object', 'required': ['id', 'kind', 'right_value', 'why'], 'properties': {
        'id': {'type': 'string'}, 'kind': {'type': 'string', 'enum': KINDS}, 'right_value': {'type': ['string', 'null']},
        'why': {'type': 'string'}}}}}}

BRIEF = '''Thank you for helping. I'm a Claude agent turning the British Association's reports on bird migration at lighthouses ({year} report) back into data. Observations were extracted from {textkind} by fixed rules (below). A second reader then checked a sample against the printed page, on the scans, and called some fields wrong. I need to know what each of those flags means.

The file {path} (JSON; open it with the Read tool) lists the flags. Each has: id; the chunk of text the observation came from, with the context before it; the observation as extracted (every field); the flagged field and its extracted value; and what the checker says the print supports.

For each flag, decide which it is:
- extraction: the extracted value is wrong by the rules, given the text (a time, count or behaviour the text states for these birds left out or misread; the wrong bird; a wrong date). Give the right value.
- checker: the extracted value is right by the rules; the checker misread the print or misapplied the rules.
- ocr_copy: {ocrnote}
- gutenberg: the value copies the transcribed text exactly, and the transcription itself differs from the print (the checker read the print): the record is right as a copy; the text has a slip.
- judgement: the rules allow either reading (wording of a species or station, how far a time or a count reaches, a vague count).
Judge by the rules below, not by what would be nicest. Copying exactly is required: a value that tidies the text is not right by the rules. In `why`, a few words, quoting the text.

THE EXTRACTION RULES:
{rules}'''


def flags(year):
    t3 = json.load(open(os.path.join(DATA, 'checks', f't3_{year}_v4.json')))
    planted = {(p['item'], p['field']) for p in t3['plants']}
    chunks = {c['id']: c for c in load_chunks(year)}
    first = {json.loads(l)['chunk']: json.loads(l) for l in open(os.path.join(DATA, 'obs', f'{year}_v4.jsonl'))}
    out = []
    for it in t3['items']:
        v = t3['verdicts'].get(str(it['item']))
        if not v:
            continue
        for f, x in v['fields'].items():
            if x['verdict'] != 'wrong' or (it['item'], f) in planted:
                continue
            o = first[it['chunk']]['obs'][it['k']]
            c = chunks[it['chunk']]
            out.append({'id': f'{it["item"]}:{f}', 'item': it['item'], 'field': f, 'extracted': o.get(f), 'checker_says': x['print_says'],
                        'observation': {k: o.get(k) for k in ('quote', 'station', 'date', 'date_iso', 'species', 'count', 'behaviour',
                                                              'at_light', 'time', 'direction', 'wind', 'force', 'weather')},
                        'chunk': c['text'], 'context': c['context'][-700:], 'reading': c['reading']})
    return t3, out


def ask_one(year, run):
    path = os.path.join(OUT, f'{year}_run{run}.json')
    if os.path.exists(path):
        return json.load(open(path))
    t3, fl = flags(year)
    os.makedirs(OUT, exist_ok=True)
    ip = os.path.join(OUT, f'{year}_flags.json')
    json.dump(fl, open(ip, 'w'), indent=1, ensure_ascii=False)
    ocr = fl and fl[0]['reading'] == 'ocr'
    brief = BRIEF.format(year=year, path=ip, rules=rules_text(),
                         textkind="the Internet Archive's OCR of the report (the only text of this year; the rules require copying it exactly, garbles and all)" if ocr else
                         "Project Gutenberg's transcription of the report",
                         ocrnote="the value copies the OCR text exactly and differs from the print only by the OCR's garbling (\"t.v.\" for L.V., \"§.W.\" for S.W., \"8\" for 3): right by the rules." if ocr else
                         "(not used for this year: the text is a transcription, not OCR).")
    d, cost = run_helper(brief, SCHEMA, 'Read')
    d['_meta'] = {'year': year, 'run': run, 'cost_usd': cost, 'n_flags': len(fl)}
    json.dump(d, open(path, 'w'), indent=1, ensure_ascii=False)
    return d


def compare(year, show=True):
    _, fl = flags(year)
    A, B = ({x['id']: x for x in json.load(open(os.path.join(OUT, f'{year}_run{r}.json')))['flags']} for r in (1, 2))
    dp = os.path.join(OUT, 'decided.json')
    dec = json.load(open(dp)) if os.path.exists(dp) else {}
    final, open_ = {}, []
    for f in fl:
        a, b = A.get(f['id'], {}).get('kind'), B.get(f['id'], {}).get('kind')
        k = f'{year}:{f["id"]}'
        if k in dec:
            final[f['id']] = dec[k]['kind']
        elif a == b and a:
            final[f['id']] = a
        else:
            open_.append((f, A.get(f['id']), B.get(f['id'])))
    if show:
        print(f'{year}: {len(fl)} flags; runs agree on {len(fl) - len(open_) - sum(1 for f in fl if f"{year}:{f["id"]}" in dec)}, '
              f'decided by hand {sum(1 for f in fl if f"{year}:{f["id"]}" in dec)}, open {len(open_)}; '
              f'{dict(collections.Counter(final.values()))}')
        for f, a, b in open_:
            print(f'  OPEN {year}:{f["id"]} {f["extracted"]!r} | checker: {f["checker_says"]!r}\n'
                  f'     run1 {a and a["kind"]}: {a and a["why"][:150]}\n     run2 {b and b["kind"]}: {b and b["why"][:150]}')
    return fl, final, open_


def wilson(k, n, z=1.96):
    if n == 0:
        return (0, 0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0, c - h), min(1, c + h)


def rates():
    print('| year | fields checked | flags | extraction errors | rate (95%) | checker | OCR copy | Gutenberg | judgement | open |')
    print('|---|---|---|---|---|---|---|---|---|---|')
    for y in range(1879, 1888):
        if not os.path.exists(os.path.join(OUT, f'{y}_run2.json')):
            continue
        t3, _ = flags(y)
        planted = {(p['item'], p['field']) for p in t3['plants']}
        n = sum(1 for k, v in t3['verdicts'].items() for f in v['fields'] if (int(k), f) not in planted)
        fl, final, open_ = compare(y, show=False)
        c = collections.Counter(final.values())
        lo, hi = wilson(c['extraction'], n)
        print(f'| {y} | {n} | {len(fl)} | {c["extraction"]} | {c["extraction"] / n:.1%} ({lo:.1%}-{hi:.1%}) | {c["checker"]} | {c["ocr_copy"]} | '
              f'{c["gutenberg"]} | {c["judgement"]} | {len(open_)} |')


if __name__ == '__main__':
    step, years = sys.argv[1], [int(y) for y in sys.argv[2:]]
    if step == 'ask':
        jobs = [(y, r) for y in years for r in (1, 2)]
        with cf.ThreadPoolExecutor(6) as ex:
            for j, d in zip(jobs, ex.map(lambda j: ask_one(*j), jobs)):
                print(j, len(d['flags']), 'flags classed', flush=True)
    elif step == 'compare':
        for y in years:
            compare(y)
    elif step == 'rates':
        rates()
