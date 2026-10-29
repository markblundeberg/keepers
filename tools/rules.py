"""Deterministic readings of a diary segment, independent of the LLM extractor
so the two can be compared: the weather bracket (wind direction, force,
Beaufort letters), clock times, flight directions, and words for deaths,
strikes and the lantern.

The report's own key (1887, West Coast of England preface): "the force of
the wind ranges from 0 to 12"; weather letters "B. blue sky; C. detached
clouds; D. drizzling rain; F. fog; G. dark, gloomy; H. hail; L. lightning;
M. misty; O. overcast; P. passing showers; Q. squally; R. rain; S. snow;
T. thunder; U. ugly, threatening; V. visibility, unusual transparency;
W. dew."
"""
import re

# 32 compass points, clockwise from N; 'b' = 'by'
POINTS = ['n', 'nbe', 'nne', 'nebn', 'ne', 'nebe', 'ene', 'ebn',
          'e', 'ebs', 'ese', 'sebe', 'se', 'sebs', 'sse', 'sbe',
          's', 'sbw', 'ssw', 'swbs', 'sw', 'swbw', 'wsw', 'wbs',
          'w', 'wbn', 'wnw', 'nwbw', 'nw', 'nwbn', 'nnw', 'nbw']
DEG = {p: i * 11.25 for i, p in enumerate(POINTS)}

# a compass direction as printed: "N.", "S.E.", "N.N.E.", "S. by E.", "E.N.E", "W.S.W,"
COMPASS = r'(?:[NSEW]\.?\s?){1,3}(?:by\s[NSEW]\.?(?:\s?[NSEW]\.?)?)?'
COMPASS_RE = re.compile(r'(?<![A-Za-z])(' + COMPASS + r')(?![a-z])')

FORCE_WORDS = [  # longest first; Beaufort's descriptions, and the bare words keepers used
    ('hurricane', 12), ('storm', 11), ('whole gale', 10), ('strong gale', 9), ('fresh gale', 8),
    ('moderate gale', 7), ('heavy gale', 9), ('gale', 8), ('strong breeze', 6), ('fresh breeze', 5),
    ('moderate breeze', 4), ('gentle breeze', 3), ('light breeze', 2), ('light air', 1),
    ('light airs', 1), ('very light', 1), ('calm', 0), ('strong', 6), ('fresh', 5),
    ('stiff', 6), ('moderate', 4), ('gentle', 3), ('light', 2), ('high', 7), ('heavy', 8)]
WEATHER_LETTERS = set('BCDFGHLMOPQRSTUVW')


def compass_key(s):
    k = re.sub(r'[\s.]', '', s.lower()).replace('by', 'b')
    return k if k in DEG else None


WEATHER_WORDS = re.compile(r'\b(?:fog|foggy|mist|misty|haze|hazy|rain|rainy|showers?|snow|sleet|hail|'
                           r'clear|fine|gloomy|dull|cloudy|clouds|overcast|thick|dense|heavy|drizzle|'
                           r'frost|frosty|hard|cold|squally|stormy|bright|sunny|threatening|thunder|lightning|dark|'
                           r'very|and|to|with)\b', re.I)
# words allowed in the wind part besides directions and forces
WIND_FILLER = re.compile(r'\b(?:wind|winds|breeze|airs?|and|to|by|very|variable|veering|backing|'
                         r'shifting|from|at|night|of|the|or)\b', re.I)


def parse_bracket(inner):
    """Read a bracket's contents as wind and weather: direction, force, then
    weather after ';' (letters or words). Returns None if anything else is
    left over, e.g. "(Guernsey)", "(4 A.M.)", "(ten killed)", "(7th)"."""
    s = inner.strip().rstrip('.').strip()
    if (not s or '_' in s or re.search(r'\d\s?[AP]\.\s?M|\d(?:st|nd|rd|th|d)\b|killed|struck|striking|\bsee\b|q\.\s?v', s, re.I)
            or re.fullmatch(r'[AP]\.M', s)):
        return None
    wind_part, semi, wx_part = s.partition(';')
    out = {'wind_raw': None, 'dir_raw': None, 'wind_deg': None, 'force_raw': None, 'force_bft': None,
           'weather_raw': wx_part.strip() or None, 'weather_codes': None, 'leftover': None}
    if not semi:
        # weather without a ';': a trailing run of single capitals, not all compass
        # letters, "(S., O. M.)"; or trailing weather words, "(Calm, misty)", "(Thick fog.)"
        m = re.search(r'((?:\b[A-Z]\b\.?\s?)+)$', s)
        if m and set(re.findall(r'[A-Z]', m.group(1))) - set('NSEW'):
            out['weather_raw'] = m.group(1).strip()
            wind_part = s[:m.start()]
        else:
            parts = [x.strip() for x in s.split(',')]
            k = len(parts)
            while k > 0 and WEATHER_WORDS.sub('', parts[k - 1]).strip(' ,.') == '' and WEATHER_WORDS.search(parts[k - 1]):
                k -= 1
            if k < len(parts):
                out['weather_raw'] = ', '.join(parts[k:])
                wind_part = ', '.join(parts[:k])
    if semi:
        # "(S.W.; fresh.)", "(N.; 8.)": a force printed after the ';' is still the force
        wx = wx_part.strip()
        fw = [w for w, _ in FORCE_WORDS if re.fullmatch(r'(?:very\s+)?' + w, wx, re.I)]
        if re.fullmatch(r'\d{1,2}', wx) or fw:
            wind_part, out['weather_raw'] = wind_part + ', ' + wx, None
    w = re.sub(r'^\s*wind\s+', '', wind_part, flags=re.I).strip(' ,')
    out['wind_raw'] = w or None
    rest = w
    num = re.search(r'(?<![\d.])(\d{1,2})(?![\d.]?\d)', rest)
    if num and 0 <= int(num.group(1)) <= 12:
        out['force_raw'], out['force_bft'] = num.group(1), int(num.group(1))
        rest = rest[:num.start()] + ' ' + rest[num.end():]
    for word, bft in FORCE_WORDS:
        m = re.search(r'\b' + word + r'\b', rest, re.I)
        if m:
            if out['force_raw'] is None:
                out['force_raw'], out['force_bft'] = m.group(0), bft
            rest = rest[:m.start()] + ' ' + rest[m.end():]
            break
    dirs = [d for d in COMPASS_RE.findall(rest) if compass_key(d)]
    if dirs:
        ms = [m for m in COMPASS_RE.finditer(rest) if compass_key(m.group(1))]
        out['dir_raw'] = ' '.join(rest[ms[0].start():ms[-1].end()].split())     # just the compass span
        degs = [DEG[compass_key(d)] for d in dirs]
        between = COMPASS_RE.sub(' ', rest)
        if len(degs) == 1:
            out['wind_deg'] = degs[0]
        elif len(degs) == 2 and re.search(r'\b(?:and|to)\b', between):
            a, b = degs     # "N. and N.E.": the mean direction; flagged by having two
            d = ((b - a + 180) % 360) - 180
            out['wind_deg'] = (a + d / 2) % 360
    elif re.search(r'\bvariable\b', rest, re.I):
        out['dir_raw'] = 'variable'
    left = WIND_FILLER.sub(' ', COMPASS_RE.sub(' ', rest))
    left = re.sub(r'[\s,.:]+', ' ', left).strip()
    if left:
        out['leftover'] = left
        if not (out['dir_raw'] or out['force_raw']):
            return None
    codes = re.findall(r'(?<![A-Za-z])([A-Z])(?![a-z])', out['weather_raw'] or '')
    if codes and all(c in WEATHER_LETTERS for c in codes):
        out['weather_codes'] = ''.join(codes)
    if not any([out['dir_raw'], out['force_raw'], out['weather_raw']]):
        return None
    return out


BRACKET = re.compile(r'\(([^()]{1,80})\)')


def weather(text):
    """All brackets in a segment that read as weather, with their spans. A
    bare "(E. to W.)" that the sentence runs on after is a flight direction
    ("a few Larks (E. to W.) at daylight"), not the wind."""
    found = []
    for m in BRACKET.finditer(text):
        p = parse_bracket(' '.join(m.group(1).split()))
        after = text[m.end():m.end() + 3].lstrip()
        if (p and not p['force_raw'] and not p['weather_raw'] and re.search(r'\bto\b', m.group(1))
                and after[:1] and (after[0].islower() or after[0] == ',')):
            continue
        if p:
            p['span'] = (m.start(), m.end())
            found.append(p)
    return found


CLOCK = re.compile(r'(?<![\d.])(\d{1,2})(?:[.:](\d{2}))?\s?(A\.\s?M\.?|P\.\s?M\.?|a\.\s?m\.?|p\.\s?m\.?|am\b|pm\b)')
WORD_TIMES = re.compile(r'\b(midnight|noon|mid-day|midday|daybreak|daylight|dawn|sunrise|sunset|dusk|'
                        r'all night|during (?:the )?night|at night|night|all day|during (?:the )?day|'
                        r'morning|forenoon|afternoon|evening)\b', re.I)


def clock_times(text):
    """Clock times in minutes after midnight (12 A.M. counted as midnight)."""
    out = []
    for h, m, ap in CLOCK.findall(text):
        h, m = int(h), int(m or 0)
        pm = ap.lower().startswith('p')
        if h == 12:
            h = 12 if pm else 0
        elif pm:
            h += 12
        if h < 24 and m < 60:
            out.append(h * 60 + m)
    return out


FLIGHT_FT = re.compile(r'(?<![A-Za-z])(' + COMPASS + r')\s?to\s(?:the\s)?(' + COMPASS + r')(?![a-z])')
FLIGHT_T = re.compile(r'\b(?:to|towards|going|flying|passing|travelling|crossing)\s(?:to\s)?(?:the\s)?(' + COMPASS + r')(?![a-z])')


def flight_directions(text):
    """(from, to) compass keys for flight directions outside weather brackets;
    "going S. to N." is one direction, S. to N."""
    t = text
    for w in reversed(weather(text)):
        a, b = w['span']
        t = t[:a] + ' ' * (b - a) + t[b:]
    out = []
    for m in FLIGHT_FT.finditer(t):
        if compass_key(m.group(1)) and compass_key(m.group(2)):
            out.append((compass_key(m.group(1)), compass_key(m.group(2))))
            t = t[:m.start()] + ' ' * (m.end() - m.start()) + t[m.end():]
    for m in FLIGHT_T.finditer(t):
        if compass_key(m.group(1)):
            out.append((None, compass_key(m.group(1))))
    return out


DEATH = re.compile(r'\b(killed|dead|died|picked up dead)\b', re.I)
STRUCK = re.compile(r'\b(struck|striking|strike|strikes|hit|dashed)\b', re.I)
LANTERN = re.compile(r'\b(lantern|lanterns|light|lamp|glass|rays)\b', re.I)
