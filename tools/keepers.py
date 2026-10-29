"""The roll: every person the station lists name for a station, by year, as
printed, with the source row -> data/keepers.csv.

The Scottish lists of 1885-87 name no reporters ("The names of the Reporters
are given under 'Diary from the Stations'"): those names come from the
diaries in stage 3.

Run: python3 -I tools/keepers.py
"""
import csv, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA
from stations import key

ST = os.path.join(DATA, 'stations')


def main():
    S = json.load(open(os.path.join(ST, 'stations.json')))
    nm = {int(r['idx']): r for r in csv.DictReader(open(os.path.join(ST, 'names.csv')))}
    clean = lambda x: ' '.join(re.sub(r'[_*†‡{}]', ' ', x or '').split()).strip(' .,;:').lower()
    key2sid = {(nm[i]['region'], clean(nm[i]['name']), clean(nm[i]['type'])): s['id'] for s in S for i in s['members']}
    name_of = {s['id']: s['name'] for s in S}
    out, unresolved, prev = [], [], None
    for r in csv.DictReader(open(os.path.join(ST, 'list_rows.csv'))):
        if r['keepers'].strip() in ('"', '\u201d', '\u201c', 'do.', 'Do.') and prev is not None:
            r = dict(r, keepers=prev['keepers'], ditto=True)      # a ditto mark under the keeper above (Skerryvore, 1879)
        prev = r if r['keepers'] else prev
        if not r['keepers']:
            continue
        sid = key2sid.get(key(r))
        if not sid:
            unresolved.append((r['year'], r['name']))
        for k in r['keepers'].split(' | '):
            k = k.strip()
            if not k:
                continue
            out.append({'year': r['year'], 'station_id': sid, 'station': name_of.get(sid), 'station_printed': r['name'].strip(' ,.'),
                        'keeper_printed': re.sub(r'[\s.,;:†‡§¶*]+$', '', k) + ('.' if k.rstrip().endswith('.') and
                                                                                      re.search(r'\b[A-Z]\.$', k.rstrip()) else ''),
                        'list': f"{r['year']}:{r['list']}:{r['row']}", 'page': r['page'], 'line': r['line'], 'image': r['image'],
                        'reading': r['reading'], 'readings_agree': r['readings_agree'], 'ditto': bool(r.get('ditto'))})
    with open(os.path.join(DATA, 'keepers.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, list(out[0]))
        w.writeheader()
        w.writerows(out)
    people = {(o['station_id'], o['keeper_printed']) for o in out}
    print(f'{len(out)} keeper-years; {len(people)} distinct (station, name as printed); stations with a named keeper: '
          f'{len({o["station_id"] for o in out})}; rows unresolved to a station: {unresolved}')
    from collections import Counter
    print('by year:', dict(sorted(Counter(o['year'] for o in out).items())))


if __name__ == '__main__':
    main()
