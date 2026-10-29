"""Parse a light's printed character (Findlay's abbreviations) into a pattern
the chart can draw: per light, its kind, colours, flashes per group and
period. Durations within a period (how long a flash or an eclipse lasts)
come from the description when it gives them ("eclipsed 3 secs. ev. ½
min."); otherwise the chart uses a stated rendering assumption.

kind: fixed | revolving | flashing | group_flashing | occulting |
      intermittent | unknown
"""
import re

COLOURS = [(r'\bbright\b|\bbr\b\.?|\bwhite\b', 'white'), (r'\bred\b', 'red'), (r'\bgreen\b', 'green')]
KINDS = [(r'\b(\d)-flash', 'group_flashing'), (r'\bfix(?:ed|\.)? ?& ?flash', 'fixed_flashing'), (r'\bocc(?:ult(?:ing)?|\.)', 'occulting'),
         (r'\binterm(?:ittent|it)?\.?', 'intermittent'), (r'\bflash(?:ing)?\.?', 'flashing'),
         (r'\brev(?:ol(?:ving)?)?\.?', 'revolving'), (r'\bfix(?:ed)?\.?', 'fixed')]
COUNT = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5}


def period_s(s):
    """'½ min.' -> 30, '1 min.' -> 60, '20 secs.' -> 20, '10 s.' -> 10, '½ m.' -> 30, '1½ min.' -> 90,
    '7-1/2 seconds' -> 7.5 (the Gutenberg transcriptions write fractions so)."""
    s = re.sub(r'(\d+)-1/2\b', lambda m: m.group(1) + '½', s)
    # a duration of darkness is not the period: "36 seconds darkness", "eclipsed 3 secs.", "obscured 36 secs."
    s = re.sub(r'\d+(?:\.\d+)?\s*(?:sec(?:ond)?s?\.?|s\.)\s*(?:of\s+)?dark(?:ness)?\b', ' ', s)
    s = re.sub(r'(?:eclipsed?|obscured|dark)\s+(?:for\s+)?\d+(?:\.\d+)?\s*(?:sec(?:ond)?s?\.?|s\b\.?)', ' ', s)
    s = re.sub(r'(?<![\d-])1/2\b', '½', s)
    if re.search(r'every (?:half[ -])minute|half-minute', s):
        return 30.0
    if re.search(r'every minute|\bin (?:a|each|ev(?:ery|\.)) ?min(?:ute)?\b', s):
        return 60.0                     # "36 seconds in a minute dark": the period is the minute
    # the first unit with a number before it ("interm." ends in an m too)
    m = next((m for m in re.finditer(r'(\d+)?\s*([½¼¾])?\s*(min(?:ute)?s?|m|sec(?:ond)?s?|s)\b\.?', s)
              if m.group(1) or m.group(2)), None)
    if not m:
        return None
    v = float(m.group(1) or 0) + {'½': .5, '¼': .25, '¾': .75, None: 0}[m.group(2)]
    return v * 60 if m.group(3).startswith('m') else v


def parse_one(s):
    """One light's character -> dict."""
    t = s.lower()
    kind, group = 'unknown', None
    for rx, k in KINDS:
        m = re.search(rx, t)
        if m:
            kind = k
            if k == 'group_flashing':
                group = int(m.group(1))
            break
    # the reports' own words for a group: "three quick flashes", "two flashes in quick succession"
    g = re.search(r'\b(two|three|four|\d)\s+(?:quick\s+)?flashes\b', t)
    if g and kind in ('flashing', 'revolving', 'unknown'):
        kind, group = 'group_flashing', COUNT.get(g.group(1)) or int(g.group(1))
    assumed = False
    if kind == 'unknown' and re.search(r'\b(?:light|lights|lt|lts)\b', t):
        kind, assumed = 'fixed', True      # no kind word ("One red light"): taken as fixed, flagged
    cols = [c for rx, c in COLOURS if re.search(rx, t)]
    alternating = bool(re.search(r'\balternat|\b(?:red|br\.?|bright) ?& ?(?:red|br\.?|bright)\b', t))
    sectored = bool(re.search(r'\b(?:br\.?|bright|red|white) or (?:br\.?|bright|red|white)\b', t))
    return {'kind': kind, 'group': group, 'colours': cols or ['white?'], 'alternating': alternating,
            'sectored': sectored, 'period_s': period_s(t), 'kind_assumed': assumed}


def parse(character, description=''):
    """A printed character -> (lights, how): a list of light dicts, and how
    the split was made ('single', 'counted', 'numbered', 'upper-lower')."""
    s = ' '.join((character or '').split())
    if not s:
        return [], 'empty'
    numbered = re.split(r'\b\d\.\s+', s)
    if len(numbered) > 2:                                    # "1. One occulting ... 2. One fixed ..."
        return [l for part in numbered[1:] for l in parse(part, description)[0]], 'numbered'
    if re.search(r'\bupper\b.*\blower\b', s, re.I):          # "Upper rev. lt. 1 min., lower fixed light"
        up, low = re.split(r'\blower\b', s, maxsplit=1, flags=re.I)
        u, l = parse_one(up), parse_one(low)
        if u['kind'] == 'unknown' and l['kind'] != 'unknown':
            u = dict(u, kind=l['kind'], kind_assumed=True)   # "Upper br., lower red, fixed lights": one kind word for both
        return [u, l], 'upper-lower'
    m = re.match(r'(one|two|three|four|five)\b', s, re.I)
    n = COUNT[m.group(1).lower()] if m else 1
    one = parse_one(s)
    if one['period_s'] is None and one['kind'] not in ('fixed',) and description:
        one['period_s'] = period_s(' '.join(re.findall(r'ev(?:ery|\.)\s*[^;,.]*', description.lower()))) or None
    # grouped flashes described in prose ("Lt. shows 3 flashes in quick succession"): the 1879
    # character column has no word for it, so the description is the record
    g = re.search(r'\b(\d|two|three|four)\s+flashes\s+in\s+(?:quick\s+)?succession', (description or '').lower())
    if g and one['kind'] in ('revolving', 'flashing', 'unknown'):
        one['kind'], one['group'] = 'group_flashing', COUNT.get(g.group(1), None) or int(g.group(1))
        one['from_description'] = True
    # eclipse or flash durations from the description, where printed
    ecl = re.search(r'eclipsed?\s+(\d+(?:\.\d+)?)\s*s', description or '', re.I)
    if ecl:
        one['eclipse_s'] = float(ecl.group(1))
    if n > 1 and one['alternating'] is False and len(one['colours']) > 1 and re.search(r',\s*(?:bright|br\.?) and red|red and (?:bright|br)', s, re.I):
        # "Two fixed lts., bright and red": one of each
        return [dict(one, colours=[c]) for c in one['colours'][:n]], 'counted'
    return [dict(one) for _ in range(n)], ('counted' if n > 1 else 'single')
