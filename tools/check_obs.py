"""Checks on the stage-3 extraction (data/obs/<year>_v4.jsonl):

  T1  every quote is in its chunk (whitespace aside);
  T2  every copied field lies inside its quote; species, station and date
      inside the chunk, or inside the context when flagged from_context;
  TD  the ISO date agrees with the copied date words (day; month where the
      words name one; year where printed);
  T4  (soft) chunks with bird-like words but no observations.

Run: python3 -I tools/check_obs.py [years] [--break t1|t2|td]
"""
import argparse, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA, obs_path

MONTHS = {m: i + 1 for i, m in enumerate(['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'])}
IN_QUOTE = ['count', 'time', 'direction']
IN_CHUNK = ['wind', 'force', 'weather', 'other_dates', 'specimen']   # may stand outside the quote: the bracket closing the entry, a range shared by several birds, where a specimen went
WS = lambda s: ' '.join((s or '').split())


def dehyph(s):
    return re.sub(r'(\w)- (\w)', r'\1\2', s)


def inside(v, text):
    v, text = WS(v), WS(text)
    return v in text or dehyph(v) in dehyph(text)


def inside_name(v, text):
    """A name (species, station, date) is a copy if its words are, whatever their case and italics: headings are
    in small capitals ("SKY LARK"), and the stop inside "_Numenius arquata._" is the sentence's."""
    plain = lambda s: re.sub(r'[_*]', '', WS(s)).lower().rstrip('.')
    return inside(v, text) or plain(v) in dehyph(plain(text)) or dehyph(plain(v)) in dehyph(plain(text))


def date_ok(words, iso, ocr=False):
    """See _date_ok. In OCR text the commonest garble is 3 read as 8 ("Noy. 8rd", "28rd", "1888" in the 1883
    report): there the words also count as agreeing if they do once every 8 is read as 3."""
    if ocr and words:       # and 1 read as I or l ("Ist", "I1th"), Nov. as "Noy.": mended first, so a garble can't hide a wrong day
        words = re.sub(r'\b[Il](?=st\b)|(?<=\d)[Il]|[Il](?=\d)', '1', re.sub(r'\bNoy\b', 'Nov', words))
    if _date_ok(words, iso):
        return True
    if not (ocr and words and '8' in words):
        return False
    import itertools
    toks = [m for m in re.finditer(r'\d+', words) if '8' in m.group(0)][:4]
    for flips in itertools.product((False, True), repeat=len(toks)):      # each number with 8 as printed, or as 3
        w, shift = words, 0
        for m, f in zip(toks, flips):
            if f:
                a, b = m.start() + shift, m.end() + shift
                w = w[:a] + m.group(0).replace('8', '3') + w[b:]
        if _date_ok(w, iso):
            return True
    return False


def _date_ok(words, iso):
    """The ISO date against the copied words. True when they agree: each day
    number the ISO date gives (start, and end of a range) is printed in the
    words or the words give no day; a month named in the words is the month
    of one end; a year printed is the year of one end. Words with no ISO
    reading (the day couldn't be placed, "During the summer") are not a
    disagreement: the date is simply unknown. ISO with no words is."""
    if not iso:
        return True
    if not words:
        return False
    ends = [e.split('-') for e in iso.split('/')]
    w = words.lower()
    days = {int(x) for x in re.findall(r'\b(\d{1,2})(?:st|nd|rd|th|d)?\b', w) if 1 <= int(x) <= 31}
    if days and not any(len(e) == 3 and int(e[2]) in days for e in ends):
        return False
    months = {MONTHS[m] for m in re.findall(r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b', w)}
    if months and not any(len(e) >= 2 and int(e[1]) in months for e in ends):
        return False
    years = set(re.findall(r'\b(18[789]\d)\b', w))
    if years and not any(e[0] in years for e in ends):
        return False
    return True


def check(year, brk=None, show=8):
    chunks = {json.loads(l)['id']: json.loads(l) for l in open(os.path.join(DATA, 'chunks', f'{year}.jsonl'))}
    path = obs_path(year)
    rows = [json.loads(l) for l in open(path)]
    probs = {'t1': [], 't2': [], 'td': [], 't4': []}
    n_obs = n_fields = 0
    for r in rows:
        c = chunks[r['chunk']]
        obs = r['obs'] or []
        if brk and obs:
            o = obs[0]
            if brk == 't1':
                o['quote'] = o['quote'] + ' x'
            elif brk == 't2':
                o['count'] = 'seventeen hundred'
            elif brk == 'td' and o['date_iso']:
                y, m = o['date_iso'][:4], o['date_iso'][5:7]
                o['date_iso'] = f'{y}-{m}-28' if not o['date_iso'].endswith('28') else f'{y}-{m}-27'
            brk = None
        if not obs and re.search(r'\b(L\.\s?[HV]\.|killed|struck|lantern|flock|passing)\b', c['text']):
            probs['t4'].append((r['chunk'], c['text'][:80]))
        for o in obs:
            n_obs += 1
            if not inside(o['quote'], c['text']):
                probs['t1'].append((r['chunk'], o['quote'][:80]))
            for f in IN_QUOTE:
                if o[f]:
                    n_fields += 1
                    if not inside(o[f], o['quote']):
                        probs['t2'].append((r['chunk'], f, o[f], o['quote'][:60]))
            for f in IN_CHUNK:
                if o[f]:
                    n_fields += 1
                    if not inside(o[f], c['text']):
                        probs['t2'].append((r['chunk'], f, o[f], 'chunk'))
            for f in ('species', 'station', 'date'):
                if o[f]:
                    n_fields += 1
                    where = c['context'] if f in o['from_context'] else c['text']
                    if not inside_name(o[f], where) and not inside_name(o[f], c['text']):
                        probs['t2'].append((r['chunk'], f, o[f], 'context' if f in o['from_context'] else 'chunk'))
            if not date_ok(o['date'], o['date_iso'], ocr=c['reading'] == 'ocr'):
                probs['td'].append((r['chunk'], o['date'], o['date_iso']))
    print(f'{year}: {len(rows)} chunks, {n_obs} observations, {n_fields} copied fields; T1 {len(probs["t1"])}, T2 {len(probs["t2"])}, '
          f'dates {len(probs["td"])}, chunks with bird words but no observations {len(probs["t4"])}')
    for k in ('t1', 't2', 'td', 't4'):
        for p in probs[k][:show]:
            print(f'   {k}: {p}')
    return probs


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('years', nargs='*', type=int)
    ap.add_argument('--break', dest='brk', choices=['t1', 't2', 'td'])
    ap.add_argument('--show', type=int, default=8)
    a = ap.parse_args()
    for y in a.years or [y for y in range(1879, 1888) if os.path.exists(os.path.join(DATA, 'obs', f'{y}_v4.jsonl'))]:
        check(y, a.brk, a.show)
