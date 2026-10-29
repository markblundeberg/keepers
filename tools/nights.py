"""Station-nights for K1 and L1 (notes/TESTS.md): every night a station has a
primary record, named by its evening date, with whether anything struck or
died at the light, the moon and twilight there (skyfield), and the
reanalysis cloud, humidity, rain and pressure at local midnight (20CRv3).

A record's night: a clock time before noon belongs to the night begun the
evening before ("Oct. 13th, 2 a.m." is the night of the 12th); a time from
noon on, or none, to the night of its own date (`night_how` says which).

Run in the venv: .venv/bin/python -I tools/nights.py  ->  data/weather/nights.csv
"""
import collections, csv, datetime as dt, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA
from sky import clock_offset_min, moon, night as twilight
from winds import EPOCH, Field

STRIKE = {'struck', 'dead', 'caught', 'round_lantern'}
STRIKE_WIDE = {'struck', 'dead', 'round_lantern'}     # the amended outcome (TESTS.md K1): at_light follows wording


def main():
    pos = {r['id']: (float(r['lat']), float(r['lon']), r['kind']) for r in csv.DictReader(open(os.path.join(DATA, 'stations', 'positions.csv')))
           if r['lat']}
    nights = collections.defaultdict(lambda: {'records': 0, 'strike': 0, 'strike_records': 0, 'strike_wide': 0, 'letters': set(), 'how': set(), 'coast': ''})
    for r in csv.DictReader(open(os.path.join(DATA, 'records.csv'))):
        ids = r['station_ids'].split()
        if r['source_kind'] != 'primary' or len(ids) != 1 or ids[0] not in pos or len(r['date']) != 10 or r['date_end']:
            continue                                    # a date range ("Oct. 10th to Jan. 3rd") is no one night
        d = dt.date.fromisoformat(r['date'])
        if not 1878 <= d.year <= 1888:                  # a past year quoted ("in 1831"), outside the survey and the reanalysis
            continue
        if r['time_kind'] == 'clock' and r['t_start_min'] != '' and float(r['t_start_min']) < 720:
            d, how = d - dt.timedelta(days=1), 'morning time: night before'
        else:
            how = 'own date'
        n = nights[(ids[0], d)]
        n['records'] += 1
        n['coast'] = r['coast']
        n['how'].add(how)
        n['letters'] |= set(r['weather_codes'] or '')
        if r['behaviour'] in STRIKE_WIDE or (r['behaviour'] == 'caught' and r['at_light'] == 'True'):
            n['strike_wide'] = 1
        if r['behaviour'] in STRIKE and r['at_light'] == 'True':
            n['strike'] = 1
            n['strike_records'] += 1
    fields = {k: Field(*v) for k, v in {'tcdc': ('tcdc.eatm', 'tcdc'), 'lcdc': ('tcdc.lowcld', 'tcdc'), 'rhum': ('rhum.2m', 'rhum'),
                                         'prmsl': ('prmsl', 'prmsl'), 'apcp': ('apcp', 'apcp'), 'uwnd': ('uwnd.10m', 'uwnd'),
                                         'vwnd': ('vwnd.10m', 'vwnd')}.items()}
    rows = []
    for (sid, d), n in sorted(nights.items()):
        lat, lon, kind = pos[sid]
        off = clock_offset_min(n['coast'], lon)
        midnight = dt.datetime(d.year, d.month, d.day) + dt.timedelta(days=1, minutes=off)     # local midnight, in UT
        alt, lit = moon(lat, lon, midnight.replace(tzinfo=dt.timezone.utc))
        tw = twilight(lat, lon, d)
        h = (midnight - EPOCH).total_seconds() / 3600
        w = {k: f.at(lat, lon, h) for k, f in fields.items()}
        rows.append({'station': sid, 'kind': kind, 'coast': n['coast'], 'night': d.isoformat(), 'records': n['records'], 'strike': n['strike'], 'strike_wide': n['strike_wide'],
                     'strike_records': n['strike_records'], 'night_how': '; '.join(sorted(n['how'])), 'letters': ''.join(sorted(n['letters'])),
                     'moon_lit': round(lit, 3), 'moon_alt_midnight': round(alt, 1), 'moonlit': int(lit > 0.5 and alt > 0),
                     'sunset': tw['sunset'] and tw['sunset'].isoformat(timespec='minutes'), 'dusk': tw['dusk'] and tw['dusk'].isoformat(timespec='minutes'),
                     'dawn': tw['dawn'] and tw['dawn'].isoformat(timespec='minutes'),
                     'sunrise': tw['sunrise'] and tw['sunrise'].isoformat(timespec='minutes'),
                     **{k: (round(v, 2) if not math.isnan(v) else '') for k, v in w.items()}, 'lat': lat, 'lon': lon})
    os.makedirs(os.path.join(DATA, 'weather'), exist_ok=True)
    with open(os.path.join(DATA, 'weather', 'nights.csv'), 'w', newline='') as f:
        wr = csv.DictWriter(f, list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)
    print(f'{len(rows)} station-nights -> data/weather/nights.csv; strike nights {sum(r["strike"] for r in rows)}; '
          f'with reanalysis cloud {sum(r["tcdc"] != "" for r in rows)}')


if __name__ == '__main__':
    main()
