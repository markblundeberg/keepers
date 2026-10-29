"""Data for the film's roll: every station on the lists with its keepers and their years, in the reports' order.

Names: data/keepers.csv (the printed lists, 1879-1887) and data/keepers_1887_scotland.csv (1887's Scottish keepers,
printed only in the "Diary from the Stations" paragraphs, read from the text). A keeper's years are written as
ranges ("1880-1884, 1886"). The lists print one man's name differently from year to year ("William Anderson", "Wm.
Anderson"; "M'Culloch", "MacCulloch"): forms at one station with the same surname (M', Mc and Mac as one) and the
same first initial are taken as one keeper, shown in the fullest form printed. Beside four stations, the
committee's own line about their returns (1887 report).

Run: python3 -I tools/film_roll.py film/engine/assets/roll.json
"""
import collections, csv, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA

LINES = {   # the committee on the returns, 1887 ("Diary from the Stations", data/chunks/1887.jsonl)
    'Sumburgh Head': 'A very short single schedule. Birds very scarce.',
    'Rhinns of Islay': 'send nine carefully filled sheets, and write nearly each time at length.',
    'Ailsa Craig': 'Our first returns sent from the “Old Rock” are very full in interest',
    'Kyleakin': 'send three well-filled schedules.',
}
ALIAS = {'Lochindaul: Islay': 'Loch Indaal', 'Dhuheartach': 'Dubh Artach', 'North Ronaldshay': 'North Ronaldsay', 'Lamlash': 'Holy Isle (Lamlash)'}


def ranges(ys):
    ys = sorted(ys)
    out, a = [], ys[0]
    for p, q in zip(ys, ys[1:] + [None]):
        if q != p + 1:
            out.append(str(a) if a == p else f'{a}–{p}')
            a = q
    return ', '.join(out)


def person_key(name):
    t = name.replace('.', '. ').split()
    if len(t) > 2 and t[0].rstrip('.').lower() == 'mr':      # "Mr John West" and "John West"
        t = t[1:]
    if not t:
        return name
    sur = re.sub(r"^m[^a-z]", 'mc', t[-1].lower())       # M' (any apostrophe the print used) as Mc
    sur = re.sub(r'^mac', 'mc', re.sub(r'[^a-z]', '', sur))   # M'Kenna, McKenna, MacKenna as one
    return (sur, t[0][0].lower() if len(t) > 1 else '')


def merged(people):
    groups = collections.OrderedDict()
    for n, ys in people.items():
        g = groups.setdefault(person_key(n), [n, set()])
        bare = lambda x: re.sub(r'^Mr\.? ', '', x)
        if len(bare(n)) > len(bare(g[0])) or (len(bare(n)) == len(bare(g[0])) and len(n) < len(g[0])):
            g[0] = n
        g[1] |= ys
    return [tuple(g) for g in groups.values()]


def main(out):
    order, people = [], collections.OrderedDict()
    def add(station, name, year):
        if station not in order:
            order.append(station)
        people.setdefault(station, collections.OrderedDict()).setdefault(name, set()).add(year)
    for r in csv.DictReader(open(os.path.join(DATA, 'keepers.csv'))):
        add(r['station'], r['keeper_printed'].strip(), int(r['year']))
    known = {s.lower(): s for s in order}
    unmatched = []
    for r in csv.DictReader(open(os.path.join(DATA, 'keepers_1887_scotland.csv'))):
        st = r['station']
        hit = known.get(st.lower()) or known.get(ALIAS.get(st, st).lower()) or next((s for s in order if s.lower().startswith(ALIAS.get(st, st).lower())), None)
        if not hit:
            unmatched.append(st)
            hit = st
        add(hit, r['keeper_printed'].strip() or 'unsigned', int(r['year']))
    roll = [{'station': s, 'keepers': [f'{n}, {ranges(ys)}' for n, ys in merged(people[s])], 'line': LINES.get(s)} for s in order]
    json.dump({'source': 'tools/film_roll.py', 'stations': roll}, open(out, 'w'), ensure_ascii=False, indent=0)
    print(f'{out}: {len(roll)} stations, {sum(len(r["keepers"]) for r in roll)} keeper entries; '
          f'1887 Scottish stations not on the earlier lists: {unmatched or "none"}; committee lines placed: '
          f'{[s for s in LINES if s in people]}')


if __name__ == '__main__':
    main(sys.argv[1])
