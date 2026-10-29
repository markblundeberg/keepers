"""Split a diary-layout section into station-day segments.

Diary layout (1887 English coasts): one paragraph per date, opening
"October 21st.--", then station entries, each opening with the station's
name in italics: "_Coquet_ L.H., One Woodcock, 10.30 A.M., shot."

A segment is one station's entry on one date: its exact text, offsets into
the source, and the printed page. Text before the first station on a date
becomes a segment with no station.

Run: python3 -I tools/segment_diary.py 1887  ->  data/pilot/segments_1887.jsonl
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA, MONTH_NUM, MONTHS, Pages, read_source

# (code, diary heading, the heading that ends the section)
SECTIONS = {1887: [('ENE', 'Diary of Migratory Movements on East Coast of England, 1887.', 'WEST COAST OF SCOTLAND.'),
                   ('ENW', 'Diary of the Migratory Movements as Observed at the various Stations.', 'IRISH COAST.')]}

DATE_HEAD = re.compile(r'(?P<fn>\[\d+\])?_?(?P<month>' + '|'.join(MONTHS) + r') (?P<day>\d{1,2}(?:st|nd|rd|th|d)?|-+)\.?_?\s*-_?-')
MONTH_LINE = re.compile(r'[A-Z]{3,}\.?')
# a station head: footnote mark, italic (or =bold=) name, which may wrap a
# line, qualifier "(_E._)", type, place "(Guernsey)". Seen in 1887: "East
# _Goodwin_ L.V.", "_Chickens Rock_, L.H.", "=Outer Dowsing= L.V."
HEAD = re.compile(r'(?P<fn>\[\d+\]\s*)?(?P<pre>(?:East|West|North|South|Inner|Outer)\s+)?(?P<open>[_=])'
                  r'(?P<name>[A-Z][^_=]{0,40}?)[_=]'
                  r'(?P<qual>\s*\((?:_[^_\n]{1,12}_|[A-Za-z. ]{1,12})\))?'
                  r'(?P<type>,?\s*L\.\s?[HV]\.)?'
                  r'(?P<place>\s*\((?:[A-Z][a-z]+ ?)+\))?')
NOOPEN = re.compile(HEAD.pattern.replace('(?P<open>[_=])', '(?P<open>)', 1))
LATIN = re.compile(r'[A-Z][a-z\u00e6\u0153\u00eb]+\s+[a-z\u00e6\u0153\u00eb]+\??')
# what may precede a station head (besides the date header)
OPENER = set('.)"\'!?;:')


def paragraphs(text, start, end):
    """(offset, paragraph) for each blank-line-separated paragraph in text[start:end]."""
    for m in re.finditer(r'(?:(?!\n[ \t]*\n).)+', text[start:end], re.S):
        p = m.group(0)
        if p.strip():
            lead = len(p) - len(p.lstrip())
            yield start + m.start() + lead, p.strip()


def station_heads(par, body_start, plain_names=(), open_missing=False):
    """Station heads in a date paragraph: italic names at the start of the
    entries, i.e. right after the date header, after a sentence end, or
    after a comma if the head names L.H./L.V. Names known from italic heads
    elsewhere are also accepted in plain type (plain_names)."""
    heads = []
    cands = list(HEAD.finditer(par, body_start))
    if open_missing:    # ".-_-Holyhead Breakwater_ L.H.": the opening underscore slipped into the dash
        m0 = NOOPEN.match(par, body_start)
        if m0:
            cands.insert(0, m0)
    if plain_names:
        alt = '|'.join(re.escape(n).replace('\\ ', '\\s+') for n in sorted(plain_names, key=len, reverse=True))
        plain = re.compile(r'(?P<fn>\[\d+\]\s*)?(?P<pre>)(?P<open>)(?P<name>' + alt + r')(?![a-z])'
                           r'(?P<qual>\s*\((?:_[^_\n]{1,12}_|[A-Za-z. ]{1,12})\))?'
                           r'(?P<type>,?\s*L\.\s?[HV]\.)?(?P<place>\s*\((?:[A-Z][a-z]+ ?)+\))?(?=,)')
        taken = [(m.start(), m.end()) for m in cands]
        cands += [m for m in plain.finditer(par, body_start)
                  if not any(a <= m.start() < b for a, b in taken)]
        cands.sort(key=lambda m: m.start())
    for m in cands:
        name = ' '.join(m['name'].split())
        if LATIN.fullmatch(name) and not m['type']:
            continue
        before = par[body_start:m.start()].rstrip()
        prev = before[-1:] if before else ''
        if m.start() == body_start or prev in OPENER or before.endswith(',"') or (prev == ',' and m['type']):
            if heads and m.start() < heads[-1].end():
                continue
            heads.append(m)
    return heads


def segment(year, plain_names=()):
    t = read_source(year)
    pages = Pages(year)
    segs, notes = [], []
    for code, diary_head, end_head in SECTIONS[year]:
        a = t.index(diary_head)
        b = t.index('\n' + end_head, a)
        n = 0
        for off, par in paragraphs(t, a + len(diary_head), b):
            dm = DATE_HEAD.match(par)
            if not dm:
                if not (MONTH_LINE.fullmatch(par) or par.startswith('[Footnote')):
                    notes.append(f'{code} non-diary paragraph at {off}: {par[:70]!r}')
                continue
            month = MONTH_NUM[dm['month']]
            dd = re.match(r'\d+', dm['day'])
            date = f'{year}-{month:02d}-{int(dd.group(0)):02d}' if dd else None
            open_missing = dm.group(0).endswith('-_-')
            if open_missing:
                notes.append(f'{code} date-header slip at {off}: {dm.group(0)!r}')
            heads = station_heads(par, dm.end(), plain_names, open_missing)
            # stretches: [date body start, first head) is a no-station segment if non-empty
            cuts = [h.start() for h in heads] + [len(par)]
            pre = par[dm.end():cuts[0]].strip()
            spans = []
            if pre:
                spans.append((dm.end(), cuts[0], None))
            for h, c in zip(heads, cuts[1:]):
                spans.append((h.start(), c, h))
            for s, e, h in spans:
                seg_text = par[s:e].rstrip()
                n += 1
                start = off + s
                rec = {'seg_id': f'{year}-{code}-{n:04d}', 'year': year, 'section': code,
                       'date': date, 'date_raw': dm.group(0), 'start': start,
                       'end': start + len(seg_text), 'text': seg_text,
                       'station_name': ' '.join(h['name'].split()) if h else None,
                       'station_qual': re.sub(r'[_()\s]', '', h['qual']) if h and h['qual'] else None,
                       'station_type': re.sub(r'[\s,]', '', h['type']) if h and h['type'] else None,
                       'station_place': h['place'].strip(' ()') if h and h['place'] else None,
                       'head': h.group(0).strip() if h else None,
                       'page': pages.page(start), 'image_index': pages.at(start)['image_index']}
                assert t[rec['start']:rec['end']] == seg_text
                segs.append(rec)
    return t, segs, notes


if __name__ == '__main__':
    year = int(sys.argv[1])
    t, segs, notes = segment(year)
    # names seen in italic heads with L.H./L.V., or at least twice, may also appear in plain type
    from collections import Counter
    seen = Counter(r['station_name'] for r in segs if r['station_name'])
    names = {r['station_name'] for r in segs if r['station_name'] and (r['station_type'] or seen[r['station_name']] >= 2)}
    t, segs, notes = segment(year, names)
    os.makedirs(os.path.join(DATA, 'pilot'), exist_ok=True)
    with open(os.path.join(DATA, 'pilot', f'segments_{year}.jsonl'), 'w') as f:
        for r in segs:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    for n in notes:
        print(n)
    from collections import Counter
    c = Counter((r['section']) for r in segs)
    print(f'{len(segs)} segments', dict(c), 'no-station:', sum(1 for r in segs if not r['station_name']),
          'dates:', len({(r["section"], r["date"]) for r in segs}))
