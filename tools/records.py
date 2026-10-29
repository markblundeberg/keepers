"""Build data/records.csv: one row per observation, every copied field as
extracted (the record's own words) beside its normalised value, joined to
the station table (data/stations/aliases.csv) and the species crosswalk
(data/species.csv). Numbers come only from fixed rules (tools/normalize.py,
tools/rules.py), never from a model; the model's one reading, the ISO date,
is kept only where it agrees with the copied date words (tools/check_obs.py).
Observations are the two readings merged where the chunk was read twice
(tools/second_reading.py; `adjudicated` names the fields a third reader
decided between them), else the first reading.

Run: python3 -I tools/records.py  ->  data/records.csv
"""
import bisect, collections, csv, glob, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA, MANIFEST, Pages, obs_paths, ocr_leaf, ws_norm, ws_norm_with_map
import normalize
from rules import COMPASS_RE, DEG, FORCE_WORDS, WEATHER_LETTERS, compass_key
from check_obs import IN_CHUNK, IN_QUOTE, date_ok, inside, inside_name
from species import key as species_key

COLS = ['record_id', 'report_year', 'coast', 'section_title', 'layout', 'season', 'source_kind', 'reading', 'chunk', 'page', 'scan', 'offset',
        'quote', 'station_raw', 'station_ids', 'place', 'station_how', 'date_raw', 'date', 'date_end', 'date_ok', 'from_context',
        'time_raw', 'time_kind', 't_start_min', 't_end_min', 'time_label', 'species_raw', 'species_level', 'species_sci',
        'species_en', 'count_raw', 'count_lo', 'count_hi', 'count_category', 'count_shared', 'total', 'behaviour', 'at_light',
        'direction_raw', 'from_deg', 'to_deg', 'wind_raw', 'wind_deg', 'wind_how', 'force_raw', 'force_bft', 'weather_raw', 'weather_codes',
        'other_dates', 'specimen', 'note', 'unverified_fields', 'carried', 'errata', 'adjudicated']


QUADRANT = {'north': 0, 'northerly': 0, 'east': 90, 'easterly': 90, 'south': 180, 'southerly': 180, 'west': 270, 'westerly': 270,
            'north-east': 45, 'north-easterly': 45, 'northeasterly': 45, 'south-east': 135, 'south-easterly': 135,
            'southeasterly': 135, 'south-west': 225, 'south-westerly': 225, 'southwesterly': 225, 'north-west': 315,
            'north-westerly': 315, 'northwesterly': 315}


def ocr_compass(raw):
    """In OCR text, small-capital S often comes out as § or 8, and E as H: read compass tokens so, and only those."""
    def fix(m):
        t = m.group(0)
        return t.replace('\u00a7', 'S').replace('8', 'S').replace('H', 'E') if re.fullmatch(r'(?:[NSEW8\u00a7H]\.\s?){1,3}', t) else t
    return re.sub(r'(?<![A-Za-z0-9])(?:[NSEW8\u00a7H]\.\s?){1,3}', fix, raw)


def circ_mean(degs):
    import math
    x = sum(math.cos(math.radians(d)) for d in degs)
    y = sum(math.sin(math.radians(d)) for d in degs)
    return round(math.degrees(math.atan2(y, x)) % 360, 2) if abs(x) + abs(y) > 1e-6 else None


def wind_deg(raw, ocr=False):
    """(bearing, how) for a printed wind. how: 'point' ("S.E.", "N. by E."; also inside "mod. N. by E. breeze");
    'two points' ("E. to S.E.", "S.E. and S.": their circular mean); 'shifting' ("S.E., shifting to N.E.": the
    first); 'quadrant' ("westerly": the quadrant's middle); with '+ocr' where § or 8 was read as S, H as E."""
    if not raw:
        return None, ''
    tag = ''
    text = raw
    if ocr:
        fixed = ocr_compass(raw)
        if fixed != raw:
            text, tag = fixed, '+ocr'
    k = compass_key(text.strip())
    if k:
        return DEG.get(k), 'point' + tag
    pts = [compass_key(m.group(1)) for m in COMPASS_RE.finditer(text)]
    pts = [p for p in pts if p]
    if len(pts) == 1:
        return DEG.get(pts[0]), 'point' + tag
    if len(pts) >= 2:
        if re.search(r'shift|veer|back|chang|later|afterwards|becoming', text, re.I):
            return DEG.get(pts[0]), 'shifting' + tag
        if len(pts) == 2:
            return circ_mean([DEG[p] for p in pts]), 'two points' + tag
        return None, 'unread (three or more points)'
    w = re.findall(r"[a-z]+(?:-[a-z]+)?", text.lower())
    qs = [QUADRANT[x] for x in w if x in QUADRANT]
    if len(qs) == 1:
        return qs[0], 'quadrant' + tag
    return None, 'unread'


ABBREV = {'mod.': 'moderate', 'mod': 'moderate', 'str.': 'strong', 'lt.': 'light', 'mod': 'moderate'}


def force_bft(raw, wind_raw=None):
    """Beaufort force from the printed force ("3", "4 to 5", "fresh breeze", "mod. gale"), or, where the force was
    left in the wind's words ("strong E.S.E. breeze", "fresh N. breeze"), from those."""
    for text in (raw, wind_raw if not raw else None):
        if not text:
            continue
        bare = ' '.join(text.lower().strip(' .,;').split())
        m = re.fullmatch(r'(\d{1,2})(?:\s*(?:to|-|,)\s*(\d{1,2}))?', bare)
        if m:
            v = [int(x) for x in m.groups() if x]
            return max(v) if max(v) <= 12 else None
        s = COMPASS_RE.sub(' ', text)                       # "fresh N. breeze" -> "fresh   breeze" (compass points are capitals)
        s = ' '.join(ABBREV.get(w, w) for w in s.lower().split())
        for w, b in FORCE_WORDS:
            if re.search(r'\b' + re.escape(w) + r'\b', s):
                return b
    return None


def weather_codes(raw):
    if not raw:
        return None
    # Beaufort letters, in either case (case marks intensity: "c. V.", "B.c.mM."); a token is one letter or a doubled
    # one, so words ("fog", "cold") stay out
    toks = [t for t in re.split(r'[\s.,]+', raw) if t]
    if not toks or any(len(t) > 2 or (len(t) == 2 and t[0].upper() != t[1].upper()) for t in toks):
        return None
    letters = set(''.join(toks).upper())
    return ''.join(sorted(letters)) if letters <= WEATHER_LETTERS else None


def page_maps():
    out = {}
    for y in range(1879, 1888):
        p = os.path.join(DATA, 'pages', f'{y}.json')
        out[y] = Pages(y) if os.path.exists(p) else None
    return out


def ocr_page(year, offset, cache={}):
    """Printed page of an OCR offset, from the last running head before it (an estimate)."""
    if year not in cache:
        from station_lists import lines_of, running_heads
        lines = lines_of(year)
        off = [0]
        for l in lines:
            off.append(off[-1] + len(l) + 1)
        cache[year] = ([off[ln - 1] for ln, _ in running_heads(lines)], [p for _, p in running_heads(lines)])
    offs, pages = cache[year]
    i = bisect.bisect_right(offs, offset) - 1
    return f'~{pages[i]}' if i >= 0 else None


def load_errata():
    """data/errata.csv as {year: [((start, end), wrong token, printed token, row)]}: where the Gutenberg text differs from
    the print (read on the scan). An erratum is placed by its Gutenberg offset, or by its words found once in the
    text (a pilot row: its station-day segment); its tokens are the words that differ. Quotes stay as Gutenberg has them; values are read from the print."""
    import difflib
    out, unplaced = collections.defaultdict(list), []
    pilot = {json.loads(l)['seg_id']: json.loads(l) for l in open(os.path.join(DATA, 'pilot', 'segments_1887.jsonl'))}
    for i, e in enumerate(csv.DictReader(open(os.path.join(DATA, 'errata.csv')))):
        y = int(e['year'])
        src = open(os.path.join(os.path.dirname(DATA), MANIFEST[str(y)]['gutenberg_txt']['path']), encoding='utf-8').read()
        g, p = e['gutenberg_reads'].split(), e['print_reads'].split()
        pairs = [(g[k].strip('(),;_'), p[c + k - a].strip('(),;_'))
                 for tag, a, b, c, d in difflib.SequenceMatcher(None, g, p, autojunk=False).get_opcodes()
                 if tag == 'replace' and b - a == d - c for k in range(a, b)]
        seg = pilot.get(e['seg_id'])
        if e['seg_id'].startswith('gutenberg offset '):
            lo = int(e['seg_id'].split()[-1])
            rng = (lo, lo + len(e['gutenberg_reads']) + 2)
        elif seg:                                       # the pilot's station-day segment
            rng = (seg['start'], seg['end'])
        else:
            t, m = ws_norm_with_map(src)
            hits = [x.start() for x in re.finditer(re.escape(ws_norm(e['gutenberg_reads'])), t)]
            if len(hits) != 1:
                unplaced.append(e['gutenberg_reads'])
                continue
            rng = (m[hits[0]], m[hits[0] + len(ws_norm(e['gutenberg_reads'])) - 1] + 1)
        out[y] += [(rng, w, r, i + 2 if not e['changes_a_value'].startswith('no') else None) for w, r in pairs]
    return out, unplaced


def apply_errata(o, c, span, errata):
    """Fields of one observation with the print's tokens put back, and the errata rows used."""
    used = set()
    for (lo, hi), wrong, right, row in errata:
        if not (lo < c['end'] and c['start'] < hi):
            continue
        tok = re.compile(r'(?<![\w.])' + re.escape(wrong) + r'(?![\w])')
        # the record's quote overlaps the erratum's words (or its station-day entry), or the slip is the chunk's only such word
        if not (span[0] < hi and lo < span[1] or len(tok.findall(c['text'])) == 1):
            continue
        for f in ('species', 'count', 'time', 'direction', 'wind', 'force', 'weather', 'specimen', 'date'):
            if o[f] and tok.search(o[f]):
                o[f] = tok.sub(right, o[f])
                if row:                                 # rows that change no value (a stop, a hyphen) aren't listed
                    used.add(row)
    return o, used


def main():
    errata, unplaced = load_errata()
    aliases = {}
    ap = os.path.join(DATA, 'stations', 'aliases.csv')
    if os.path.exists(ap):
        for r in csv.DictReader(open(ap)):
            aliases[(r['words'], r['coast'], int(r['year']))] = r
    species = {}
    sp = os.path.join(DATA, 'species.csv')
    if os.path.exists(sp):
        species = {r['name']: r for r in csv.DictReader(open(sp))}
    pages = page_maps()
    rows, n_bad_date = [], 0
    # A section's station, date or species heading can stand further back than a chunk's context (the
    # Heligoland almanac names its island only in the running head; a "November 9th." heading a page
    # earlier). Within a section, a field left null is filled from the last record that had it, and the
    # record says so in `carried`, only where a heading governs what follows: the date in diaries, the
    # station in diaries, station letters and tables, the species in species accounts. (An undated remark
    # in a letter or a species account is undated, not "the date above".) Heligoland's section is Heligoland's.
    carry = {}
    for path in obs_paths():
        year = int(os.path.basename(path)[:4])
        chunks = {json.loads(l)['id']: json.loads(l) for l in open(os.path.join(DATA, 'chunks', f'{year}.jsonl'))}
        for l in open(path):
            r = json.loads(l)
            c = chunks[r['chunk']]
            t, m = ws_norm_with_map(c['text'])
            sec = (year, c['section'])
            last = carry.setdefault(sec, {})
            for k, o in enumerate(r['obs'] or []):
                o = dict(o)
                carried = []
                if not o['station'] and c['coast'].upper().startswith('HELIGOLAND'):
                    o['station'], carried = 'Heligoland', ['station']
                for f, layouts in (('station', ('diary', 'station', 'table')), ('date', ('diary',)), ('species', ('species',))):
                    if not o[f] and c['layout'] in layouts and f in last:
                        o[f] = last[f]
                        if f == 'date':
                            o['date_iso'] = last['date_iso']
                        carried.append(f)
                for f in ('station', 'date', 'species'):
                    if o[f]:
                        last[f] = o[f]
                        if f == 'date':
                            last['date_iso'] = o['date_iso']
                j = t.find(ws_norm(o['quote']))
                off = c['start'] + (m[j] if j >= 0 else 0)
                end = c['start'] + (m[min(len(m) - 1, j + len(ws_norm(o['quote'])) - 1)] + 1 if j >= 0 else 0)
                # v: the values as printed, where the Gutenberg text has a slip (data/errata.csv); o stays the copy
                v, used = apply_errata(dict(o), c, (off, end), errata.get(year, [])) if c['reading'] == 'gutenberg' else (o, set())
                if c['reading'] == 'gutenberg':
                    page, img = pages[year].page(off), pages[year].at(off)['image_index'] if pages[year].at(off) else None
                else:
                    page, img = ocr_leaf(year, off)
                scan_url = MANIFEST[str(year)]['page_image_pattern'].format(index=img) if img is not None else ''
                al = aliases.get(((o['station'] or '').strip(), c['coast'], year)) if o['station'] else None
                sp_ = species.get(species_key(v['species'])) if v['species'] else None
                ok = date_ok(o['date'], o['date_iso'], ocr=c['reading'] == 'ocr')
                n_bad_date += not ok
                d0, _, d1 = (o['date_iso'] or '').partition('/')
                lo, hi, cat = normalize.count(v['count'])
                tk = normalize.time_of_day(v['time']) if v['time'] else None
                fd, td = normalize.direction(v['direction'])
                wd = wind_deg(v['wind'], ocr=c['reading'] == 'ocr')
                unver = [f for f in IN_QUOTE if o[f] and not inside(o[f], o['quote'])] + \
                        [f for f in IN_CHUNK if o[f] and not inside(o[f], c['text'])] + \
                        [f for f in ('species', 'station', 'date') if o[f] and f not in carried and not inside_name(o[f], c['text']) and
                         not (f in o['from_context'] and inside_name(o[f], c['context']))]
                if not inside(o['quote'], c['text']):
                    unver.append('quote')
                rows.append({
                    'unverified_fields': ' '.join(unver), 'carried': ' '.join(carried),
                    'record_id': f'{r["chunk"]}.{k}', 'report_year': year, 'coast': c['coast'], 'section_title': c['title'] or '',
                    'layout': c['layout'], 'season': c['season'], 'source_kind': c['observations'], 'reading': c['reading'],
                    'chunk': r['chunk'], 'page': page, 'scan': scan_url, 'offset': off, 'quote': o['quote'],
                    'station_raw': o['station'], 'station_ids': al['ids'] if al else '', 'place': al['place'] if al else '',
                    'station_how': al['how'] if al else ('' if not o['station'] else 'unresolved'),
                    'date_raw': o['date'], 'date': d0 if ok else '', 'date_end': d1 if ok else '', 'date_ok': ok,
                    'from_context': ' '.join(o['from_context']),
                    'time_raw': o['time'], 'time_kind': tk[0] if tk else '', 't_start_min': tk[1] if tk else '',
                    't_end_min': tk[2] if tk else '', 'time_label': tk[3] if tk else '',
                    'species_raw': o['species'], 'species_level': sp_['level'] if sp_ else '', 'species_sci': sp_['scientific'] if sp_ else '',
                    'species_en': sp_['english'] if sp_ else '',
                    'count_raw': o['count'], 'count_lo': lo, 'count_hi': hi, 'count_category': cat, 'count_shared': o['count_shared'],
                    'total': o['total'], 'behaviour': o['behaviour'], 'at_light': o['at_light'],
                    'direction_raw': o['direction'], 'from_deg': fd, 'to_deg': td,
                    'wind_raw': o['wind'], 'wind_deg': wd[0], 'wind_how': wd[1], 'force_raw': o['force'], 'force_bft': force_bft(v['force'], v['wind']),
                    'weather_raw': o['weather'], 'weather_codes': weather_codes(v['weather']),
                    'other_dates': o['other_dates'], 'specimen': o['specimen'], 'note': o['note'],
                    'errata': ' '.join(f'row{x}' for x in sorted(used)), 'adjudicated': '; '.join(o.get('adjudicated', []))})
    with open(os.path.join(DATA, 'records.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, COLS)
        w.writeheader()
        w.writerows(rows)
    by = collections.Counter(r['report_year'] for r in rows)
    print(f'{len(rows)} records -> data/records.csv; by year {dict(sorted(by.items()))}; dates disagreeing with their words '
          f'(left blank): {n_bad_date}; station resolved {sum(bool(r["station_ids"] or r["place"]) for r in rows)}; '
          f'species resolved {sum(r["species_level"] not in ("", "unresolved") for r in rows)}; '
          f'records with a field that is not a copy of the text: {sum(bool(r["unverified_fields"]) for r in rows)}; '
          f'with a field carried from earlier in its section: {sum(bool(r["carried"]) for r in rows)}; '
          f'with a value read from the print where Gutenberg slips (data/errata.csv): {sum(bool(r["errata"]) for r in rows)} '
          f'(errata not placed in the text: {unplaced})')


if __name__ == '__main__':
    main()
