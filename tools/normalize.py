"""Turn the printed fields the extractor copied into numbers, by fixed rules:
times into minutes after the entry date's midnight, counts into ranges and
categories, flight directions into compass bearings. Nothing here reads the
source; it only interprets strings, so every value can be traced to its
words.

Times are the station's local clock. Events after midnight that run on from
an evening ("10 P.M. till 4 A.M.") get minutes past 1440 (the next day).
"""
import re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from rules import COMPASS, DEG, compass_key

NUM = {'a': 1, 'an': 1, 'one': 1, 'single': 1, 'two': 2, 'pair': 2, 'couple': 2, 'three': 3, 'four': 4, 'five': 5,
       'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12, 'dozen': 12,
       'thirteen': 13, 'fourteen': 14, 'fifteen': 15, 'sixteen': 16, 'seventeen': 17, 'eighteen': 18,
       'nineteen': 19, 'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50, 'sixty': 60, 'seventy': 70,
       'eighty': 80, 'ninety': 90, 'hundred': 100, 'score': 20}
# vague quantities: (category, lo, hi); None where nothing honest can be said
VAGUE = [(r'\bthousands\b|\bimmense\b|\bvast\b|\benormous\b|\bcountless\b|\bmyriads\b', 'thousands', 1000, None),
         (r'\bhundreds\b', 'hundreds', 100, None),
         (r'\bscores\b', 'scores', 40, None),
         (r'\bgreat (?:many|numbers?|flocks?|quantities)\b|\blarge (?:numbers?|flocks?|quantities)\b|\bvery many\b|\bgreat rush\b', 'great numbers', 50, None),
         (r'\bdozens\b|\bseveral dozen\b', 'dozens', 24, None),
         (r'\bmany\b|\bnumbers?\b|\bflocks\b|\bplenty\b|\bplentiful\b|\bnumerous\b|\bcommon\b|\babundant\b', 'many', 10, None),
         (r'\bflock\b|\bparty\b|\bcompany\b|\bsmall flocks?\b', 'flock', 5, None),
         (r'\bseveral\b|\bsome\b', 'several', 3, 9),
         (r'\ba few\b|\bfew\b|\bodd\b', 'few', 2, 5),
         (r'\bsingle\b|\bsolitary\b|\ban? \b', 'one', 1, 1)]


def word_number(s):
    """'twenty-four' -> 24, 'one hundred' -> 100, '156' -> 156; None if not a number."""
    s = s.lower().strip()
    if re.fullmatch(r'\d+', s):
        return int(s)
    total, cur = 0, 0
    for w in re.split(r'[\s-]+', s):
        if w in ('and',):
            continue
        if w not in NUM:
            return None
        v = NUM[w]
        if v == 100:
            cur = max(cur, 1) * 100
        else:
            cur += v
    return total + cur if cur else None


def count(raw):
    """(lo, hi, category) for a printed count; hi None means open-ended."""
    if not raw:
        return None, None, None
    s = raw.lower().strip(' .,;:')
    if s in ('a', 'an', 'single'):
        return 1, 1, 'number'
    m = re.search(r'(\d+|[a-z-]+)\s*(?:to|-|or)\s*(\d+|[a-z-]+)', s)
    if m:
        a, b = word_number(m.group(1)), word_number(m.group(2))
        if a and b and a < b:
            return a, b, 'range'
    m = re.search(r'\b(\d+|(?:(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|'
                  r'fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|'
                  r'ninety|hundred|dozen|score|pair|couple|single)[\s-]*)+)\b', s)
    if m:
        n = word_number(m.group(1).strip(' -'))
        if n:
            about = re.search(r'\b(about|nearly|over|upwards of|some|at least|quite)\b', s)
            if re.search(r'\bflocks?\b', s) and not re.search(r'\bin (?:a )?flocks?\b', s):
                return n, None, 'flocks'        # "two flocks": that many flocks, birds unknown
            return n, n if not about else None, 'number'
    for rx, cat, lo, hi in VAGUE:
        if re.search(rx, s + ' '):
            return lo, hi, cat
    return None, None, 'unparsed'


CLOCK = re.compile(r'(?<![\d.])(\d{1,2})(?:[.:](\d{1,2})(?!\d))?\s?(A\.\s?M\.?|P\.\s?M\.?|a\.\s?m\.?|p\.\s?m\.?|am\b|pm\b)?')
PERIODS = [  # (pattern, label, start, end) in minutes; None = resolve with sun times later
    (r'\ball night\b|\bthroughout the night\b|\bduring (?:the )?night\b|\bat night\b|\bnight\b', 'night', None, None),
    (r'\bmidnight\b', 'clock', 1440, 1440),
    (r'\bnoon\b|\bmid-?day\b', 'clock', 720, 720),
    (r'\bdaybreak\b|\bdawn\b|\bdaylight\b|\bsunrise\b|\bfogbreak\b', 'dawn', None, None),
    (r'\bsunset\b|\bdusk\b|\bnightfall\b|\bdark\b', 'dusk', None, None),
    (r'\bearly morn(?:ing)?\b', 'early morning', 240, 480),
    (r'\bforenoon\b|\bmorning\b|\bmorn\b', 'morning', 360, 720),
    (r'\bafternoon\b', 'afternoon', 720, 1080),
    (r'\bevening\b', 'evening', 1080, 1320),
    (r'\ball day\b|\bduring (?:the )?day\b|\bday\b', 'day', None, None)]


def _clock(h, m, ap, hint=None):
    h, m = int(h), int(m or 0)
    ap = (ap or hint or '').lower()[:1]
    if not ap or h > 12 or m > 59:
        return None
    if h == 12:
        h = 12 if ap == 'p' else 0      # as printed; but see the 'ambiguous 12' label
    elif ap == 'p':
        h += 12
    return h * 60 + m


def time_of_day(raw):
    """(kind, start, end, label). kind 'clock': minutes after the entry date's
    midnight, a range ending before it starts running past 1440. kind
    'period': a label to resolve against the sun ('night', 'dawn', 'dusk',
    'day'). 'unparsed' otherwise. Labels flag 'ambiguous 12' (Victorian
    "12 P.M." often meant midnight) and a named part of day."""
    if not raw:
        return None, None, None, None
    s = raw.strip()
    toks = []       # (position, start, end, label, follows 'till/to')
    cl = list(CLOCK.finditer(s))
    marks = [m.group(3) for m in cl]
    for i, m in enumerate(cl):
        hint = next((x for x in marks[i:] if x), None)     # "between 1 and 3 A.M.": borrow the next mark
        t = _clock(m.group(1), m.group(2), m.group(3), hint)
        if t is not None:
            lab = 'ambiguous 12' if int(m.group(1)) == 12 else None
            toks.append((m.start(), t, t, lab, False))
    blank = s
    for rx, label, a, b in PERIODS:
        for m in re.finditer(rx, blank, re.I):
            till = bool(re.search(r'\b(?:till|until|to)\s*$', s[:m.start()]))
            toks.append((m.start(), a, b, None if label == 'clock' else label, till))
            blank = blank[:m.start()] + ' ' * (m.end() - m.start()) + blank[m.end():]
    toks.sort()
    num = [t for t in toks if t[1] is not None]
    labels = [t[3] for t in toks if t[3]]
    if num:
        first, last = num[0], num[-1]
        start = first[1]
        end = last[1] if last[4] and last is not first else last[2]
        if first is not last and start == 1440 and end < 720:      # "midnight to 4 A.M."
            start = 0
        if end < start:
            end += 1440
        after = [t for t in toks if t[0] > last[0] and t[1] is None and t[4]]
        if after:                                   # "11 P.M. to daylight": ends at dawn, resolved later
            return 'clock', start, None, 'until ' + after[0][3]
        if end - start > 12 * 60:
            labels.insert(0, 'long range')
        return 'clock', start, end, (labels[0] if labels else None)
    if labels:
        return 'period', None, None, labels[0]
    return 'unparsed', None, None, None


FLIGHT_FROM_TO = re.compile(r'(?<![A-Za-z])(' + COMPASS + r')\s?(?:to|towards)\s(?:the\s)?(' + COMPASS + r')(?![a-z])')
FLIGHT_TO = re.compile(r'\b(?:to|towards|going|flying|passing|travelling|moving|for)\s(?:to\s)?(?:the\s)?(' + COMPASS + r')(?![a-z])'
                       r'|^\s*(' + COMPASS + r')\s*$')
FLIGHT_FROM = re.compile(r'\bfrom\s(?:the\s)?(' + COMPASS + r')(?![a-z])')
WORDY = {'northerly': 0, 'north': 0, 'northward': 0, 'northwards': 0, 'easterly': 90, 'east': 90, 'eastward': 90,
         'eastwards': 90, 'southerly': 180, 'south': 180, 'southward': 180, 'southwards': 180, 'westerly': 270,
         'west': 270, 'westward': 270, 'westwards': 270}


def direction(raw):
    """(from_deg, to_deg) of a printed flight direction; None where not stated."""
    if not raw:
        return None, None
    s = raw.strip()
    m = FLIGHT_FROM_TO.search(s)
    if m and compass_key(m.group(1)) and compass_key(m.group(2)):
        return DEG[compass_key(m.group(1))], DEG[compass_key(m.group(2))]
    f = FLIGHT_FROM.search(s)
    t = FLIGHT_TO.search(s)
    fd = DEG.get(compass_key(f.group(1))) if f and compass_key(f.group(1)) else None
    td = None
    if t:
        g = t.group(1) or t.group(2)
        td = DEG.get(compass_key(g)) if compass_key(g) else None
    if td is None:
        w = re.search(r'\b(' + '|'.join(WORDY) + r')\b', s.lower())
        if w:
            td = WORDY[w.group(1)]
    return fd, td


def deaths(seg_obs):
    """Birds dead in one segment, as (lo, hi, n_records), by a fixed rule:
    a count shared by several kinds ("many killed") counts once; a printed
    total that the segment breaks down counts instead of the parts when it is
    larger (print totals and parts don't always agree: "Forty-four birds
    killed, viz." over parts summing to 41). hi is None when open-ended."""
    dead = [o for o in seg_obs if o['behaviour'] == 'dead']
    if not dead:
        return 0, 0, 0
    totals = [o for o in dead if o.get('total')]
    parts = [o for o in dead if not o.get('total')]
    lo = hi = 0
    seen_shared = set()
    for o in parts:
        if o.get('count_shared'):
            k = (o['count'] or '').strip().lower()
            if k in seen_shared:
                continue
            seen_shared.add(k)
        a, b, _ = count(o['count']) if o['count'] else (1, None, None)   # a plural with no count: at least one
        lo += a or 0
        hi = None if (hi is None or b is None) else hi + b
    for o in totals:
        a, b, _ = count(o['count']) if o['count'] else (None, None, None)
        if a and a > lo:
            lo, hi = a, b
    return lo, hi, len(dead)
