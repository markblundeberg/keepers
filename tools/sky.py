"""Sun and moon at the stations: sunset, dusk, dawn and sunrise round each
night, and the moon's altitude and lit fraction at any moment, from the JPL
DE440s ephemeris through skyfield (built-in Delta T; no downloads but the
kernel). Run in the project venv: .venv/bin/python -I tools/sky.py check

The keepers' clocks: Great Britain's legal time was Greenwich Mean Time
(Statutes (Definition of Time) Act, 2 August 1880; railway time long
before), Ireland's Dublin Mean Time (GMT - 25 min 21 s, same Act);
Heligoland kept its own local time. `clock_offset_min` gives the offset to
add to a printed clock time to reach UT.

Check: the full moons of the two total lunar eclipses in the period's
neighbourhood whose dates are known independently (4 Oct 1884, the dark
eclipse after Krakatoa; 28 Jan 1888) fall on skyfield's full-moon dates,
and sunrise at Greenwich on the equinox is near 6 a.m.
"""
import datetime as dt, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import ROOT
from skyfield import almanac
from skyfield.api import load, wgs84

TS = load.timescale(builtin=True)
EPH = load(os.path.join(ROOT, 'sources', 'ephemeris', 'de440s.bsp'))
SUN, MOON, EARTH = EPH['sun'], EPH['moon'], EPH['earth']
UTC = dt.timezone.utc


def clock_offset_min(coast, lon):
    """Minutes to add to a printed time to reach UT."""
    c = (coast or '').lower()
    if 'ireland' in c or 'irish' in c:
        return 25 + 21 / 60
    if 'heligoland' in c:
        return -lon * 4                                 # local mean time
    return 0.0


def night(lat, lon, date):
    """Sunset, civil dusk, civil dawn and sunrise round the night that begins on `date` (UT datetimes)."""
    top = wgs84.latlon(lat, lon)
    t0 = TS.from_datetime(dt.datetime(date.year, date.month, date.day, 12, tzinfo=UTC))
    t1 = TS.from_datetime(dt.datetime(date.year, date.month, date.day, 12, tzinfo=UTC) + dt.timedelta(days=1))
    f = almanac.dark_twilight_day(EPH, top)
    times, states = almanac.find_discrete(t0, t1, f)
    out = {'sunset': None, 'dusk': None, 'dawn': None, 'sunrise': None}
    prev = int(f(t0))
    for t, s in zip(times, states):
        s = int(s)
        if prev == 4 and s < 4:
            out['sunset'] = t.utc_datetime()
        elif prev == 3 and s < 3:
            out['dusk'] = t.utc_datetime()
        elif prev < 3 and s == 3:
            out['dawn'] = t.utc_datetime()
        elif prev < 4 and s == 4:
            out['sunrise'] = t.utc_datetime()
        prev = s
    return out


def moon(lat, lon, when):
    """(altitude in degrees, lit fraction 0-1) of the moon at a UT datetime."""
    t = TS.from_datetime(when.replace(tzinfo=UTC) if when.tzinfo is None else when)
    obs = EARTH + wgs84.latlon(lat, lon)
    alt = obs.at(t).observe(MOON).apparent().altaz()[0].degrees
    lit = almanac.fraction_illuminated(EPH, 'moon', t)
    return float(alt), float(lit)


def full_moons(y0, y1):
    t, y = almanac.find_discrete(TS.utc(y0, 1, 1), TS.utc(y1 + 1, 1, 1), almanac.moon_phases(EPH))
    return [ti.utc_datetime() for ti, yi in zip(t, y) if yi == 2]


def check():
    fm = full_moons(1879, 1888)
    ok = True
    for known in (dt.date(1884, 10, 4), dt.date(1888, 1, 28)):          # dates only: the hours I don't know independently
        near = min(fm, key=lambda x: abs(x.date() - known))
        print(f'eclipse of {known}: skyfield full moon {near:%Y-%m-%d %H:%M} UT')
        ok &= near.date() == known
    n = night(51.48, 0.0, dt.date(1880, 3, 19))
    print('Greenwich, night of 19 Mar 1880:', {k: f'{v:%d %H:%M}' for k, v in n.items()})
    ok &= 5.5 < n['sunrise'].hour + n['sunrise'].minute / 60 < 6.5
    print(f'{len(fm)} full moons 1879-1888;', 'CHECK OK' if ok else 'CHECK FAILED')
    return ok


if __name__ == '__main__':
    check()
