"""Station lists: every list of lighthouses and light-vessels in the nine
reports (the master lists with map numbers, and the list at the head of each
coast's section), read row by row with exact quotes.

  find:    one helper per report finds the lists (line ranges, legends,
           printed counts)          -> data/stations/lists/<year>_found.json
  extract: two independent helpers per list read its rows
                                    -> data/stations/lists/<year>_<k>_run<r>.json
  check:   every quote exact, every field inside its row's quote, rows
           against the printed count and an independent line count, and the
           two readings compared.

Run: python3 -I tools/station_lists.py find 1879 1880 ...
     python3 -I tools/station_lists.py extract 1879 ... [--workers 6]
     python3 -I tools/station_lists.py check [years] [--break quote|drop]
"""
import argparse, concurrent.futures as cf, json, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA, MANIFEST, ROOT, scan_ia

OUT = os.path.join(DATA, 'stations', 'lists')
YEARS = list(range(1879, 1888))
NUM_WORDS = {w: i for i, w in enumerate(
    'zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen '
    'seventeen eighteen nineteen twenty'.split())}
for t, w in enumerate(['twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety'], start=2):
    NUM_WORDS[w] = 10 * t
    for u, uw in enumerate('one two three four five six seven eight nine'.split(), start=1):
        NUM_WORDS[f'{w}-{uw}'] = 10 * t + u


def source(year):
    """(path, kind): the Gutenberg text where there is one, else the IA OCR."""
    m = MANIFEST[str(year)]
    if 'gutenberg_txt' in m:
        return os.path.join(ROOT, m['gutenberg_txt']['path']), 'gutenberg'
    return os.path.join(ROOT, m['ia_ocr']['path']), 'ocr'


def lines_of(year):
    return open(source(year)[0], encoding='utf-8').read().split('\n')


def run_helper(brief, schema, tools, timeout=3600):
    cmd = ['systemd-run', '--user', '--scope', '-q', '-p', 'MemoryMax=3G', '-p', 'MemorySwapMax=0',
           'claude', '-p', '--safe-mode', '--model', 'claude-opus-5-5', '--effort', 'high', '--tools', tools,
           '--allowedTools', tools, '--no-session-persistence', '--output-format', 'json', '--json-schema', json.dumps(schema)]
    p = subprocess.run(cmd, input=brief, capture_output=True, text=True, timeout=timeout)
    res = json.loads(p.stdout)
    if res.get('is_error') or not res.get('structured_output'):
        raise RuntimeError(str(res)[:400])
    return res['structured_output'], res.get('total_cost_usd')


ABOUT = '''Thank you for helping. I'm a Claude agent rebuilding the records of the lighthouse keepers who reported bird migration to a British Association committee, 1879-1887. Each annual report lists the lighthouses and light-vessels the committee sent its schedules to, often with the keepers' names, a number on the committee's map, marks for the stations that sent returns, and sometimes each light's character. These lists will become the project's table of stations and its roll of keepers, so the exact printed words matter.'''

OCR_NOTE = ''' This text is the Internet Archive's OCR of the {year} report, not a clean transcription: it garbles small capitals and some letters ("L.H." can come out as "t.x." or "u.H."), and a table's columns may be run together or split. Quote it exactly as it is, garbles included.'''

N = {'type': ['string', 'null']}
FIND_SCHEMA = {'type': 'object', 'required': ['lists'], 'properties': {'lists': {'type': 'array', 'items': {
    'type': 'object',
    'required': ['section', 'kind', 'first_line', 'last_line', 'lead_quote', 'legend_quotes', 'printed_count_quote',
                 'rows_counted', 'columns'],
    'properties': {'section': {'type': 'string'}, 'kind': {'type': 'string', 'enum': ['master', 'section', 'other']},
                   'first_line': {'type': 'integer'}, 'last_line': {'type': 'integer'}, 'lead_quote': N,
                   'legend_quotes': {'type': 'array', 'items': {'type': 'string'}}, 'printed_count_quote': N,
                   'rows_counted': {'type': 'integer'}, 'columns': {'type': 'string'}}}}}}

FIND_BRIEF = ABOUT + '''

I need to find every such list in the {year} report. Its text is at {path} ({n} lines).{ocr} Use Grep and Read to search it; Read shows line numbers, and those are the numbers I need.

Please return every list of stations in it:
- master lists of all the stations, by coast, with map numbers (often near the front);
- the list at the head of each coast's section ("The East Coast stations included in this report are:--", "The stations from which co-operation was asked are the following");
- any other table that lists stations by name with something about each (returns by station, years of returns, values).
Not the passing mentions of stations inside the observations ("at the following stations:--Butt of Lewis, ...").

For each list: the section it sits in, as the report heads it; its kind (master, section, other); the line numbers of its first and last rows (1-based, as Read shows them); its heading or lead-in sentence, quoted exactly (null if none); every sentence that explains its marks (what *, **, †, italics or the columns mean), quoted exactly; the sentence giving the number of stations, if there is one ("Schedules were issued to thirty-four stations"), quoted exactly; how many station rows you count in it; and in a few words what its columns are.
Some lists are printed in two columns side by side, or interleave several coasts; give each such list once, with the lines it spans.'''

ROW = {'type': 'object',
       'required': ['line', 'fragments', 'number', 'marks', 'name', 'type', 'place', 'keepers', 'character', 'other', 'coast'],
       'properties': {'line': {'type': 'integer'}, 'fragments': {'type': 'array', 'items': {'type': 'string'}},
                      'number': N, 'marks': N, 'name': {'type': 'string'}, 'type': N, 'place': N,
                      'keepers': {'type': 'array', 'items': {'type': 'string'}}, 'character': N, 'other': N, 'coast': N}}
EXTRACT_SCHEMA = {'type': 'object', 'required': ['rows', 'notes'],
                  'properties': {'rows': {'type': 'array', 'items': ROW}, 'notes': {'type': 'string'}}}

EXTRACT_BRIEF = ABOUT + '''

Please read one list, row by row. It is in the {year} report, text at {path}, lines {a} to {b}{where}.{ocr}
{lead}{legend}{columns}
Open the file with the Read tool (offset {off}, limit {lim} shows a little either side). Then give one entry per station, in the order printed:
- line: the line number (as Read shows it) where the station's row starts.
- fragments: the row's text exactly as printed, one string per printed line the row occupies (a row that wraps onto a second line, or a station in the right-hand column of a two-column list, has its pieces on separate lines; give each piece as an exact copy of what is on that line, without the other column's text). Keep every character: marks, underscores (italics), dots, odd spellings.
- number: the station's number as printed ("30", "28_b_", "5*", "XIV"), or null.
- marks: any mark printed with the station (*, **, †, ‡, a brace), or "italic" if its name is printed in italics (underscores in this text), as printed; null if none.
- name: the station's name exactly as printed, without the number, marks or type ("Farn, Inner,", "Hoy Sound (Low)", "Island Ghlais").
- type: "L.H.", "L.V.", "Lt.-ship" or the like, exactly as printed, or null.
- place: a county, island or locality printed with the name ("Shetland", "Co. Cork", "Isle of Man"), exactly as printed, or null.
- keepers: each person named for the station, exactly as printed ("Annie Rose Smith", "J. B. Smith"; "Messrs Black and Beggs" stays as one entry), or [] if none. "_Nil._" is not a person: put it in other.
- character: the description of the light where the list gives one ("white, flash every 10 seconds"), exactly as printed, or null.
- other: anything else printed in the row (heights, values, counts of schedules or returns, years, "_Nil._", fog signals), exactly as printed, or null.
- coast: the coast or sub-heading the row sits under in the list ("Scotland--East Coast", "Orkney", "N. W. England"), or null.
A row like '"     (High) Orkney' that repeats the name above with ditto marks is its own station: give the fragment as printed and the name as printed ('"     (High)').
Copy, don't correct: if a name looks misspelled or a type looks wrong, keep it as printed and mention it in notes.
In notes, say anything a reader of the list should know (a row you weren't sure was a station, a column you couldn't interpret).'''


def find(year):
    path, kind = source(year)
    out = os.path.join(OUT, f'{year}_found.json')
    if os.path.exists(out):
        return json.load(open(out))
    brief = FIND_BRIEF.format(year=year, path=path, n=len(lines_of(year)), ocr=OCR_NOTE.format(year=year) if kind == 'ocr' else '')
    d, cost = run_helper(brief, FIND_SCHEMA, 'Read,Grep')
    d['_meta'] = {'year': year, 'source': os.path.relpath(path, ROOT), 'cost_usd': cost}
    os.makedirs(OUT, exist_ok=True)
    json.dump(d, open(out, 'w'), indent=1, ensure_ascii=False)
    return d


def extract(year, k, lst, run):
    path, kind = source(year)
    out = os.path.join(OUT, f'{year}_{k}_run{run}.json')
    if os.path.exists(out):
        return json.load(open(out))
    a, b = lst['first_line'], lst['last_line']
    brief = EXTRACT_BRIEF.format(
        year=year, path=path, a=a, b=b, off=max(1, a - 8), lim=b - a + 20,
        where=f' (section: {lst["section"]})', ocr=OCR_NOTE.format(year=year) if kind == 'ocr' else '',
        lead=f'Its lead-in: "{lst["lead_quote"]}"\n' if lst.get('lead_quote') else '',
        legend=''.join(f'What its marks mean: "{q}"\n' for q in lst.get('legend_quotes') or []),
        columns=f'Its columns, as another reader described them: {lst["columns"]}\n' if lst.get('columns') else '')
    d, cost = run_helper(brief, EXTRACT_SCHEMA, 'Read')
    d['_meta'] = {'year': year, 'list': k, 'run': run, 'source': os.path.relpath(path, ROOT), 'first_line': a,
                  'last_line': b, 'section': lst['section'], 'kind': lst['kind'], 'cost_usd': cost}
    json.dump(d, open(out, 'w'), indent=1, ensure_ascii=False)
    return d


# ---------- the OCR years: read the lists off the page scans ----------

HEAD1 = re.compile(r'^\s*([A-Z][A-Za-z ,.&\'-]{8,60}?)[.,]?\s+(\d{1,3})\s*$')   # "EAST COAST OF SCOTLAND. 11"
HEAD2 = re.compile(r'^\s*(\d{1,3})\s+([A-Z][A-Z ,.&\'-]{8,60})\s*$')            # "12 REPORT ON THE MIGRATION ..."


def running_heads(lines):
    """(line, printed page) for the OCR's running heads."""
    out = []
    for i, l in enumerate(lines):
        if not re.search(r'COAST|REPORT|MIGRATION|REMARKS', l.upper()):
            continue
        m1, m2 = HEAD1.match(l), HEAD2.match(l)
        if m1 or m2:
            out.append((i + 1, int(m1.group(2) if m1 else m2.group(1))))
    return out


def candidate_images(year, a, b):
    """Scan images likely to hold OCR lines a..b: the printed pages between the
    running heads either side, padded by one, mapped to IA leaves through the
    page_numbers file (image index = leaf - 1)."""
    lines = lines_of(year)
    heads = running_heads(lines)
    before = [p for ln, p in heads if ln <= a][-2:]
    after = [p for ln, p in heads if ln >= b][:2]
    lo = before[-1] if before and (not after or 0 <= after[0] - before[-1] <= 8) else (after[0] - 2 if after else 1)
    hi = after[0] if after and after[0] >= lo else lo + 2
    m = MANIFEST[str(year)]
    pn = json.load(open(os.path.join(ROOT, m['ia_page_numbers']['path'])))['pages']
    leaf_of = {p['pageNumber']: p['leafNum'] for p in pn if p['pageNumber']}
    offs = sorted(p['leafNum'] - int(p['pageNumber']) for p in pn if p['pageNumber'].isdigit()
                  and abs(int(p['pageNumber']) - lo) < 15)
    off = offs[len(offs) // 2] if offs else 0
    leaves = [leaf_of.get(str(pg), pg + off) for pg in range(max(1, lo - 1), hi + 1)]
    return [scan_ia(m['ia_id'], leaf - 1, str(year)) for leaf in leaves]


SCAN_ROW = {'type': 'object',
            'required': ['image', 'printed', 'number', 'marks', 'name', 'type', 'place', 'keepers', 'character', 'other', 'coast', 'unsure'],
            'properties': {'image': {'type': 'string'}, 'printed': {'type': 'string'}, 'number': N, 'marks': N,
                           'name': {'type': 'string'}, 'type': N, 'place': N, 'keepers': {'type': 'array', 'items': {'type': 'string'}},
                           'character': N, 'other': N, 'coast': N, 'unsure': N}}
SCAN_SCHEMA = {'type': 'object', 'required': ['rows', 'notes'],
               'properties': {'rows': {'type': 'array', 'items': SCAN_ROW}, 'notes': {'type': 'string'}}}

SCAN_BRIEF = ABOUT + '''

Please read one list from the page scans of the {year} report. It is the station list in the section "{section}"{lead}. It is printed on one or more of these page images; open each with the Read tool and find it:
{images}
The Internet Archive's OCR of the same pages is in {ocr}, lines {a} to {b}. The OCR garbles letters ("L.H." can come out as "t.x."), and it splits a table's columns into separate blocks, so a station's name and its keeper's name may be far apart there. Use it only to find your way; read every word from the images.
{legend}{columns}
Then give one entry per station, in the order printed:
- image: the file name of the image it is on.
- printed: the whole row as printed, read from the image, as one line (numbers, marks, name, type, place, keepers, every column), keeping abbreviations, punctuation and spelling. Write italics as _underscores_.
- number: the station's number as printed ("30", "28b", "5*"), or null.
- marks: any mark printed with the station (*, **, \u2020, \u2021, a brace), or "italic" if its name is in italics; null if none.
- name: the station's name exactly as printed, without the number, marks or type.
- type: "L.H.", "L.V." or the like, exactly as printed, or null.
- place: a county, island or locality printed with the name, exactly as printed, or null.
- keepers: each person named for the station, exactly as printed ("Messrs Black and Beggs" stays one entry), or [] if none. "Nil." is not a person: put it in other.
- character: the description of the light where the list gives one, exactly as printed, or null.
- other: anything else printed in the row (heights, values, counts, years, "Nil."), as printed, or null.
- coast: the coast or sub-heading the row sits under ("Orkney", "N. W. England"), or null.
- unsure: if any letter or word in this row was hard to read, say which (and put [?] in its place in the fields); else null.
Copy, don't correct: a misspelt name stays as printed (mention it in notes). In notes, say anything a reader of the list should know.'''


def scan_read(year, k, lst, run):
    out = os.path.join(OUT, f'{year}_{k}_scan{run}.json')
    if os.path.exists(out):
        return json.load(open(out))
    imgs = candidate_images(year, lst['first_line'], lst['last_line'])
    brief = SCAN_BRIEF.format(
        year=year, section=lst['section'], images='\n'.join(imgs), ocr=source(year)[0], a=lst['first_line'], b=lst['last_line'],
        lead=f' (its lead-in, in the OCR: "{lst["lead_quote"]}")' if lst.get('lead_quote') else '',
        legend=''.join(f'What its marks mean (OCR): "{q}"\n' for q in lst.get('legend_quotes') or []),
        columns=f'Its columns, as another reader described them: {lst["columns"]}\n' if lst.get('columns') else '')
    d, cost = run_helper(brief, SCAN_SCHEMA, 'Read')
    d['_meta'] = {'year': year, 'list': k, 'run': run, 'images': [os.path.relpath(i, ROOT) for i in imgs],
                  'ocr_first_line': lst['first_line'], 'ocr_last_line': lst['last_line'], 'section': lst['section'],
                  'kind': lst['kind'], 'cost_usd': cost}
    json.dump(d, open(out, 'w'), indent=1, ensure_ascii=False)
    return d


# ---------- checks ----------

def ws(s):
    return ' '.join((s or '').split())


def fmt(s):
    """For comparing two readings: spacing, final punctuation, curly or
    straight apostrophes and trailing footnote marks are formatting."""
    s = ws(s).replace('\u2018', "'").replace('\u2019', "'").replace('\u201c', '"').replace('\u201d', '"')
    return re.sub(r'[\s.,;:*\u2020\u2021\u00a7\u00b6]+$', '', s).strip(' .,;:')


def dehyph(s):
    return re.sub(r'(\w)- (\w)', r'\1\2', s)


QUOTED = ('number', 'name', 'type', 'place', 'character')   # must lie inside the row; 'other' is the helper's annotation


def inside(v, text):
    """v occurs in text, up to spacing, a hyphen at a line break, italics
    underscores and the braces that join rows in the print."""
    clean = lambda x: ws(re.sub(r'[_{}]', ' ', x))
    v, text = clean(v), clean(text)
    squash = lambda x: re.sub(r'[\s.]', '', x)
    return v in text or dehyph(v) in dehyph(text) or squash(v) in squash(text)


def check_rows(year, lines, d):
    """For one reading of a text list: each fragment is exact text on its line
    or the few after it; each quoted field lies inside the row's fragments.
    Returns a list of problems (row index, what)."""
    probs = []
    for i, r in enumerate(d['rows']):
        L = r['line']
        window = [ws(lines[j]) for j in range(max(0, L - 2), min(len(lines), L + 8))]
        for frag in r['fragments']:
            if not ws(frag) or not any(ws(frag) in w for w in window):
                probs.append((i, f'fragment not on lines {L}..{L + 7}: {frag!r}'))
        joined = ' '.join(r['fragments'])
        probs += [(i, f'{f} not inside the row: {r[f]!r}') for f in QUOTED if r[f] and not inside(r[f], joined)]
        probs += [(i, f'keeper not inside the row: {k!r}') for k in r['keepers'] if not inside(k, joined)]
    return probs


def check_scan_rows(year, lines, d, a, b):
    """For one reading of a list off the scans: each quoted field lies inside
    the row as read; and the name (and each keeper) is found, allowing for OCR
    garbles, in the OCR of the list's lines (a soft check: similarity >= 0.75
    with some span of the OCR text)."""
    import difflib
    ocr = ws(' '.join(lines[max(0, a - 6):b + 6]))
    def found(v):
        v = ws(v).replace('[?]', '')
        if len(v) < 3:
            return True
        n = len(v)
        best = max((difflib.SequenceMatcher(None, v.lower(), ocr[j:j + n].lower()).ratio()
                    for j in range(0, max(1, len(ocr) - n + 1))), default=0)
        return best >= 0.75
    probs = []
    for i, r in enumerate(d['rows']):
        probs += [(i, f'{f} not inside the row: {r[f]!r}') for f in QUOTED if r[f] and not inside(r[f], r['printed'])]
        probs += [(i, f'keeper not inside the row: {k!r}') for k in r['keepers'] if not inside(k, r['printed'])]
        for v in [r['name']] + r['keepers']:
            if not found(v):
                probs.append((i, f'not found in the OCR: {v!r}'))
    return probs


def printed_counts(q):
    """Every number in a sentence ('thirty-four ... and two ... thirty-six altogether') -> [34, 2, 36]."""
    if not q:
        return []
    out = []
    for w in re.findall(r'[a-z]+(?:-[a-z]+)?|\d{1,3}', q.lower()):
        if w.isdigit():
            out.append(int(w))
        elif w in NUM_WORDS:
            out.append(NUM_WORDS[w])
    return out


NUMBERED = re.compile(r'(?:^|\s)\*?\s*(\d{1,3})(?:[*]|_b_|b)?\.\s*(?:\*|\*\*|†)?\s*(?:L\.[HV]\.\s+)?[A-Z_"]')


def numbered_rows(lines, a, b):
    """Independent count for numbered lists: the station numbers printed on lines a..b."""
    nums = []
    for j in range(a - 1, b):
        nums += [int(m.group(1)) for m in NUMBERED.finditer(lines[j])]
    return nums


def align(A, B):
    """Pair the rows of two readings by (number, name) in order."""
    import difflib
    key = lambda r: (re.sub(r'[\s.]', '', r['number'] or '').lower(), fmt(r['name']).lower())
    sm = difflib.SequenceMatcher(None, [key(r) for r in A], [key(r) for r in B], autojunk=False)
    pairs, only = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal' or (tag == 'replace' and i2 - i1 == j2 - j1):
            pairs += list(zip(A[i1:i2], B[j1:j2]))
        else:
            only += [('run1', r.get('line') or r.get('image'), r['name']) for r in A[i1:i2]] + \
                    [('run2', r.get('line') or r.get('image'), r['name']) for r in B[j1:j2]]
    return pairs, only


FIELDS = ['number', 'marks', 'name', 'type', 'place', 'keepers', 'character', 'other']
KEY_FIELDS = ['number', 'name', 'type', 'keepers', 'character']     # what the gazetteer and the roll use


def keeper_names(ks):
    """For comparing readings: 'A & B' and 'A and B' are two names either way;
    spacing after an initial's full stop is formatting."""
    out = []
    for k in ks:
        for part in re.split(r'\s*(?:&|,|\band\b)\s*', re.sub(r'^Messrs\.?\s+', '', fmt(k))):
            if part.strip(' .,'):
                out.append(re.sub(r'\.\s*', '.', fmt(part)).lower())
    return out


def same(f, ra, rb):
    if f == 'keepers':
        return keeper_names(ra[f]) == keeper_names(rb[f])
    if f == 'number':
        return re.sub(r'[\s._]', '', ra[f] or '').lower() == re.sub(r'[\s._]', '', rb[f] or '').lower()
    if f == 'type':
        return re.sub(r'[\s.,]', '', ra[f] or '') == re.sub(r'[\s.,]', '', rb[f] or '')
    return fmt(ra[f]) == fmt(rb[f])


def readings(year, k):
    """The two readings of list k: ('text', A, B), ('scan', A, B) or None."""
    for kind, tag in (('text', 'run'), ('scan', 'scan')):
        ps = [os.path.join(OUT, f'{year}_{k}_{tag}{r}.json') for r in (1, 2)]
        if all(os.path.exists(p) for p in ps):
            return (kind, *(json.load(open(p)) for p in ps))
    return None


def reviewed():
    p = os.path.join(OUT, 'reviewed.json')
    return json.load(open(p)) if os.path.exists(p) else {}


def check(years, brk=None, verbose=True):
    totals = {'rows': 0, 'fields': 0, 'agree': 0, 'key_fields': 0, 'key_agree': 0, 'flagged': 0}
    rev = reviewed()
    for year in years:
        fpath = os.path.join(OUT, f'{year}_found.json')
        if not os.path.exists(fpath):
            continue
        lines = lines_of(year)
        for k, lst in enumerate(json.load(open(fpath))['lists']):
            got = readings(year, k)
            if not got:
                continue
            kind, A, B = got
            if brk == 'quote':
                r0 = A['rows'][0]
                if kind == 'text':
                    r0['fragments'][0] = r0['fragments'][0].replace('a', 'o', 1) + 'x'
                else:
                    r0['name'] = r0['name'] + 'x'
            if brk == 'drop':
                del A['rows'][len(A['rows']) // 2]
            a, b = lst['first_line'], lst['last_line']
            if kind == 'text':
                pa, pb = check_rows(year, lines, A), check_rows(year, lines, B)
            else:
                pa, pb = check_scan_rows(year, lines, A, a, b), check_scan_rows(year, lines, B, a, b)
            pairs, only = align(A['rows'], B['rows'])
            diffs = [(ra.get('line') or ra.get('image'), ra['name'], f, ra[f], rb[f])
                     for ra, rb in pairs for f in FIELDS if not same(f, ra, rb)]
            totals['fields'] += len(pairs) * len(FIELDS)
            totals['agree'] += len(pairs) * len(FIELDS) - len(diffs)
            totals['key_fields'] += len(pairs) * len(KEY_FIELDS)
            totals['key_agree'] += len(pairs) * len(KEY_FIELDS) - sum(d[2] in KEY_FIELDS for d in diffs)
            want = printed_counts(lst.get('printed_count_quote'))
            nums = numbered_rows(lines, a, b) if kind == 'text' else []
            n = len(A['rows'])
            count_ok = not want or n in want or f'{year}_{k}' in rev
            flag = bool(pa or pb or only or not count_ok)
            totals['flagged'] += flag
            totals['rows'] += n
            if verbose or flag:
                print(f'{year} list {k} [{kind}, {lst["kind"]}] {lst["section"][:36]!r} lines {a}-{b}: rows {n}/{len(B["rows"])}, '
                      f'finder {lst["rows_counted"]}' + (f', printed {want}' if want else '') +
                      (f', numbers on the lines {len(nums)}' if nums else '') +
                      (f' [reviewed: {rev[f"{year}_{k}"][:70]}]' if f'{year}_{k}' in rev else '') +
                      f'; quote problems {len(pa)}/{len(pb)}; unpaired {len(only)}; field diffs {len(diffs)} '
                      f'(key fields {sum(d[2] in KEY_FIELDS for d in diffs)})')
                for p in (pa + pb)[:8]:
                    print('    quote:', p)
                for o in only[:6]:
                    print('    unpaired:', o)
                for x in [d for d in diffs if d[2] in KEY_FIELDS][:8]:
                    print('    diff:', x)
    print(f'TOTAL rows {totals["rows"]}; fields agree {totals["agree"]}/{totals["fields"]}; key fields agree '
          f'{totals["key_agree"]}/{totals["key_fields"]}; lists with a flag {totals["flagged"]}')
    return totals


# ---------- merge ----------

ROW_COLS = ['year', 'section', 'list_kind', 'list', 'row', 'reading', 'line', 'image', 'page', 'quote', 'number', 'marks',
            'name', 'type', 'place', 'keepers', 'character', 'other', 'coast', 'readings_agree', 'differs', 'unsure']


def pick(f, ra, rb, inside_text):
    """Merged value of a field: agreed, else the reading whose value is inside the row, else run 1's."""
    if rb is None or same(f, ra, rb):
        return ra[f]
    for r in (ra, rb):
        v = r[f]
        if f == 'keepers' and all(inside(x, inside_text(r)) for x in v):
            return v
        if f != 'keepers' and v and inside(v, inside_text(r)):
            return v
    return ra[f]


def merge(years):
    """All lists' rows, both readings merged, -> data/stations/list_rows.csv."""
    import csv
    from kp import Pages
    out_rows = []
    for year in years:
        fpath = os.path.join(OUT, f'{year}_found.json')
        if not os.path.exists(fpath):
            continue
        lines = lines_of(year)
        line_off = [0]
        for l in lines:
            line_off.append(line_off[-1] + len(l) + 1)
        pages = Pages(year) if os.path.exists(os.path.join(DATA, 'pages', f'{year}.json')) else None
        for k, lst in enumerate(json.load(open(fpath))['lists']):
            got = readings(year, k)
            if not got:
                continue
            kind, A, B = got
            pairs, only = align(A['rows'], B['rows'])
            partner = {id(ra): rb for ra, rb in pairs}
            text = (lambda r: ' '.join(r['fragments'])) if kind == 'text' else (lambda r: r['printed'])
            for j, ra in enumerate(A['rows']):
                rb = partner.get(id(ra))
                m = {f: pick(f, ra, rb, text) for f in FIELDS + ['coast']}
                differs = [f for f in FIELDS if rb is not None and not same(f, ra, rb)]
                page = None
                if kind == 'text' and pages:
                    page = pages.page(line_off[ra['line'] - 1])
                out_rows.append({
                    'year': year, 'section': lst['section'], 'list_kind': lst['kind'], 'list': k, 'row': j, 'reading': kind,
                    'line': ra.get('line'), 'image': ra.get('image'), 'page': page,
                    'quote': ' / '.join(ra['fragments']) if kind == 'text' else ra['printed'],
                    **{f: (' | '.join(m[f]) if f == 'keepers' else m[f]) for f in FIELDS + ['coast']},
                    'readings_agree': rb is not None and not differs, 'differs': ' '.join(differs) if rb is not None else 'unpaired',
                    'unsure': ra.get('unsure')})
    os.makedirs(os.path.join(DATA, 'stations'), exist_ok=True)
    path = os.path.join(DATA, 'stations', 'list_rows.csv')
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, ROW_COLS)
        w.writeheader()
        w.writerows(out_rows)
    print(f'{len(out_rows)} rows -> {os.path.relpath(path, ROOT)}; readings disagree on {sum(not r["readings_agree"] for r in out_rows)}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('step', choices=['find', 'extract', 'scan', 'check', 'merge'])
    ap.add_argument('years', nargs='*', type=int)
    ap.add_argument('--workers', type=int, default=6)
    ap.add_argument('--break', dest='brk', choices=['quote', 'drop'])
    ap.add_argument('--lists', help='only these list indices, e.g. 0,2 (with one year)')
    ap.add_argument('--kinds', default='master,section', help='list kinds to extract')
    ap.add_argument('--quiet', action='store_true', help='check: print flagged lists only')
    a = ap.parse_args()
    years = a.years or YEARS
    if a.step == 'find':
        with cf.ThreadPoolExecutor(a.workers) as ex:
            for y, d in zip(years, ex.map(find, years)):
                print(y, [(l['section'][:30], l['kind'], l['first_line'], l['last_line'], l['rows_counted']) for l in d['lists']])
    elif a.step == 'extract':
        only = {int(x) for x in a.lists.split(',')} if a.lists else None
        jobs = [(y, k, l, r) for y in years for k, l in enumerate(json.load(open(os.path.join(OUT, f'{y}_found.json')))['lists'])
                if (only is None or k in only) and l['kind'] in a.kinds.split(',') for r in (1, 2)]
        with cf.ThreadPoolExecutor(a.workers) as ex:
            futs = {ex.submit(extract, *j): j for j in jobs}
            for f in cf.as_completed(futs):
                y, k, l, r = futs[f]
                try:
                    print(y, k, r, len(f.result()['rows']), 'rows', flush=True)
                except Exception as e:
                    print(y, k, r, 'FAILED', e, flush=True)
    elif a.step == 'scan':
        only = {int(x) for x in a.lists.split(',')} if a.lists else None
        jobs = [(y, k, l, r) for y in years for k, l in enumerate(json.load(open(os.path.join(OUT, f'{y}_found.json')))['lists'])
                if (only is None or k in only) and l['kind'] in a.kinds.split(',') for r in (1, 2)]
        with cf.ThreadPoolExecutor(a.workers) as ex:
            futs = {ex.submit(scan_read, *j): j for j in jobs}
            for f in cf.as_completed(futs):
                y, k, l, r = futs[f]
                try:
                    print(y, k, r, len(f.result()['rows']), 'rows', flush=True)
                except Exception as e:
                    print(y, k, r, 'FAILED', e, flush=True)
    elif a.step == 'merge':
        merge(years)
    else:
        check(years, a.brk, verbose=not a.quiet)


if __name__ == '__main__':
    main()
