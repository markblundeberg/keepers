"""For list-of-lights pages whose longitude column straddles Greenwich, ask a
safe-mode helper to read, row by row, whether each printed longitude is
East or West (a change of column heading, or an E./W. by the figures).

Run: python3 -I tools/hemispheres.py findlay1887 52 59 61 73
  -> data/lights/<book>/hemispheres.json  {page: {row name: "E" | "W" | null}}
"""
import json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA
from transcribe_lights import page_image


def ask(book, page):
    rows = json.load(open(os.path.join(DATA, 'lights', book, f'p{page}_run1.json')))['rows']
    names = [r['name'] for r in rows if r['long']]
    path = page_image(book, page)
    brief = (f'This page of an 1880s list of lighthouses gives each light\'s longitude, but the page crosses the meridian of '
             f'Greenwich, so some longitudes are East and some West. Open the image with the Read tool: {path}\n\n'
             'Find how the print marks the change (a change in the column heading "Long. E."/"Long. W.", a sub-heading, or '
             'an E. or W. by the figures), and for each light below say whether its printed longitude is "E" or "W". '
             'Use null only if the print truly does not say. Lights, top to bottom:\n' + '\n'.join(f'- {n}' for n in names))
    schema = {'type': 'object', 'required': ['how_marked', 'rows'], 'properties': {
        'how_marked': {'type': 'string'},
        'rows': {'type': 'array', 'items': {'type': 'object', 'required': ['name', 'hemisphere'], 'properties': {
            'name': {'type': 'string'}, 'hemisphere': {'type': ['string', 'null'], 'enum': ['E', 'W', None]}}}}}}
    cmd = ['systemd-run', '--user', '--scope', '-q', '-p', 'MemoryMax=3G', '-p', 'MemorySwapMax=0',
           'claude', '-p', '--safe-mode', '--model', 'claude-opus-5-5', '--effort', 'high', '--tools', 'Read',
           '--allowedTools', 'Read', '--no-session-persistence', '--output-format', 'json', '--json-schema', json.dumps(schema)]
    res = json.loads(subprocess.run(cmd, input=brief, capture_output=True, text=True, timeout=1800).stdout)
    out = res['structured_output']
    return out['how_marked'], {r['name']: r['hemisphere'] for r in out['rows']}


if __name__ == '__main__':
    book, pages = sys.argv[1], [int(x) for x in sys.argv[2:]]
    path = os.path.join(DATA, 'lights', book, 'hemispheres.json')
    store = json.load(open(path)) if os.path.exists(path) else {}
    for p in pages:
        how, h = ask(book, p)
        store[str(p)] = h
        print(f'p{p}: {how[:120]} | E {sum(v == "E" for v in h.values())}, W {sum(v == "W" for v in h.values())}, '
              f'unknown {sum(v is None for v in h.values())}')
    json.dump(store, open(path, 'w'), indent=1, ensure_ascii=False)
