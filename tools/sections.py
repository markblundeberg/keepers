"""The map of each report: every section and sub-section of observations,
its layout, season and line range, found by a helper per report (Read and
Grep) and checked against the survey's independent counts (notes/SURVEY.md).

Run: python3 -I tools/sections.py find [years]   ->  data/sections/<year>.json
     python3 -I tools/sections.py show [years]
"""
import concurrent.futures as cf, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA, ROOT
from station_lists import ABOUT, OCR_NOTE, lines_of, run_helper, source

OUT = os.path.join(DATA, 'sections')
LAYOUTS = ['diary', 'station', 'species', 'prose', 'table', 'station_list', 'front_matter', 'other']
N = {'type': ['string', 'null']}
SCHEMA = {'type': 'object', 'required': ['sections', 'notes'], 'properties': {'sections': {'type': 'array', 'items': {
    'type': 'object', 'required': ['coast', 'title', 'season', 'layout', 'first_line', 'last_line', 'head_examples', 'observations', 'note'],
    'properties': {'coast': {'type': 'string'}, 'title': N, 'season': {'type': 'string', 'enum': ['spring', 'autumn', 'both', 'none']},
                   'layout': {'type': 'string', 'enum': LAYOUTS}, 'first_line': {'type': 'integer'}, 'last_line': {'type': 'integer'},
                   'head_examples': {'type': 'array', 'items': {'type': 'string'}},
                   'observations': {'type': 'string', 'enum': ['primary', 'summary', 'none']}, 'note': N}}},
    'notes': {'type': 'string'}}}

BRIEF = ABOUT + '''

Now I need a map of the {year} report, so a program can cut its observations into pieces. Its text is at {path} ({n} lines).{ocr} Use Grep and Read to go through all of it; Read shows line numbers, and those are the numbers I need.

Please divide the whole report, from the first line to the last, into consecutive sections (no gaps, no overlaps), each with one layout:
- diary: entries by date ("October 21st.--_Coquet_ L.H., One Woodcock, ...");
- station: entries by station ("_North Maidens._--October 21st, striking, ..."; "_N. Unst._--John Nichol (principal) says: ...");
- species: entries by bird ("Gannet, _Sula bassana_.--At Spurn L.V., Oct. 1st to 16th, many to S. ..."), each species' notes naming stations and dates;
- prose: running text (introductions, general remarks, summaries of a season, letters);
- table: tabulated counts or returns;
- station_list: a list of the stations (these are already read);
- front_matter: title pages, contents, the committee's preamble; other: anything else (licence text at the end, adverts).
For each: the coast or part of the report it belongs to as the report heads it ("EAST COAST OF SCOTLAND", "IRISH COAST", "HELIGOLAND"); its own sub-heading if any ("AUTUMN MIGRATION, 1880. SEPARATE REPORT ON EACH SPECIES"); season (spring, autumn, both, none); layout; the first and last line; up to three exact quotes of how its entries begin (for a program to recognise them; copy them exactly, underscores and all); whether it holds observations: primary (the stations' own records, one place each), summary (records retold or summarised from elsewhere in the report, e.g. general remarks that repeat what the station or species entries give), none.
Split a coast where its layout or season changes. In note, say anything a program cutting it should know (entries that run on without a break, a heading that sits mid-line, a layout that changes for a few lines).'''


def find(year):
    path, kind = source(year)
    out = os.path.join(OUT, f'{year}.json')
    if os.path.exists(out):
        return json.load(open(out))
    brief = BRIEF.format(year=year, path=path, n=len(lines_of(year)), ocr=OCR_NOTE.format(year=year) if kind == 'ocr' else '')
    d, cost = run_helper(brief, SCHEMA, 'Read,Grep')
    d['_meta'] = {'year': year, 'source': os.path.relpath(path, ROOT), 'cost_usd': cost}
    os.makedirs(OUT, exist_ok=True)
    json.dump(d, open(out, 'w'), indent=1, ensure_ascii=False)
    return d


def show(year):
    d = json.load(open(os.path.join(OUT, f'{year}.json')))
    n = len(lines_of(year))
    secs = d['sections']
    gaps = [(a['last_line'], b['first_line']) for a, b in zip(secs, secs[1:]) if b['first_line'] != a['last_line'] + 1]
    print(f'== {year}: {len(secs)} sections; covers {secs[0]["first_line"]}-{secs[-1]["last_line"]} of {n}; gaps/overlaps {gaps[:8]}')
    for s in secs:
        if s['layout'] in ('front_matter', 'other', 'station_list'):
            continue
        print(f'  {s["first_line"]:>5}-{s["last_line"]:<5} {s["layout"]:8} {s["season"]:6} {s["observations"]:7} {s["coast"][:28]:28} '
              f'{(s["title"] or "")[:40]!r} | {(s["head_examples"] or [""])[0][:60]!r}')


if __name__ == '__main__':
    step, years = sys.argv[1], [int(y) for y in sys.argv[2:]] or list(range(1879, 1888))
    if step == 'find':
        with cf.ThreadPoolExecutor(9) as ex:
            for y, d in zip(years, ex.map(find, years)):
                print(y, len(d['sections']), 'sections', flush=True)
    for y in years:
        show(y)
