"""The keepers' winds beside the reanalysis: every distinct printed wind (a
station, a date, a time if printed, a bearing) with the 20CRv3 10 m wind at
the station then (bilinear in space, linear in time; the day's mean vector,
00-24 UT, where no time is printed) and the magnetic declination there and
then (gufm1).

Run: python3 -I tools/winds.py  ->  data/weather/winds.csv
"""
import bisect, collections, csv, datetime as dt, math, os, sys
import numpy as np
import netCDF4 as nc
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA, ROOT
from declination import declination

RE = os.path.join(ROOT, 'sources', 'reanalysis')
EPOCH = dt.datetime(1800, 1, 1)


class Field:
    """One variable's subsets, all years, as an array over (hours since 1800, lat, lon)."""

    def __init__(self, stem, var, years=range(1879, 1889)):
        ts, xs = [], []
        for y in years:
            p = os.path.join(RE, f'{stem}.{y}.nc')
            if not os.path.exists(p):
                continue
            d = nc.Dataset(p)
            ts.append(np.asarray(d.variables['time'][:], dtype=float))
            xs.append(np.asarray(d.variables[var][:], dtype=float))
            self.lat, self.lon = np.asarray(d.variables['lat'][:]), np.asarray(d.variables['lon'][:])
            d.close()
        self.t, self.x = np.concatenate(ts), np.concatenate(xs, axis=0)

    def at(self, lat, lon, hours):
        """Bilinear in space, linear in time; nan outside."""
        if not (self.t[0] <= hours <= self.t[-1]):
            return float('nan')
        i = min(int(np.searchsorted(self.t, hours, side='right')) - 1, len(self.t) - 2)
        ft = (hours - self.t[i]) / (self.t[i + 1] - self.t[i])
        fy = (lat - self.lat[0]) / (self.lat[1] - self.lat[0])
        fx = (lon - self.lon[0]) / (self.lon[1] - self.lon[0])
        y0, x0 = int(math.floor(fy)), int(math.floor(fx))
        if not (0 <= y0 < len(self.lat) - 1 and 0 <= x0 < len(self.lon) - 1):
            return float('nan')
        wy, wx = fy - y0, fx - x0
        def plane(k):
            g = self.x[k]
            return ((1 - wy) * (1 - wx) * g[y0, x0] + (1 - wy) * wx * g[y0, x0 + 1] + wy * (1 - wx) * g[y0 + 1, x0]
                    + wy * wx * g[y0 + 1, x0 + 1])
        return float((1 - ft) * plane(i) + ft * plane(i + 1))


def bearing_from(u, v):
    """Meteorological direction: where the wind blows from, degrees clockwise from true north."""
    return (math.degrees(math.atan2(-u, -v)) + 360) % 360


def hours(t):
    return (t - EPOCH).total_seconds() / 3600


def main():
    U, V = Field('uwnd.10m', 'uwnd'), Field('vwnd.10m', 'vwnd')
    pos = {r['id']: (float(r['lat']), float(r['lon'])) for r in csv.DictReader(open(os.path.join(DATA, 'stations', 'positions.csv')))
           if r['lat']}
    seen, rows = set(), []
    skipped = collections.Counter()
    for r in csv.DictReader(open(os.path.join(DATA, 'records.csv'))):
        if not r['wind_deg']:
            continue
        ids = r['station_ids'].split()
        if len(ids) != 1 or ids[0] not in pos:
            skipped['no single placed station'] += 1
            continue
        if not r['date'] or len(r['date']) != 10 or r['date_end']:      # a range is no single day
            skipped['no single day'] += 1
            continue
        sid, lat, lon = ids[0], *pos[ids[0]]
        day = dt.datetime.strptime(r['date'], '%Y-%m-%d')
        timed = r['time_kind'] == 'clock' and r['t_start_min'] != ''
        offset = 25 + 21 / 60 if 'IRISH' in r['coast'].upper() else (-lon * 4 if 'HELIGOLAND' in r['coast'].upper() else 0)
        key = (sid, r['date'], r['t_start_min'] if timed else '', r['wind_deg'])
        if key in seen:
            continue
        seen.add(key)
        if timed:
            t = day + dt.timedelta(minutes=float(r['t_start_min']) + offset)
            u, v = U.at(lat, lon, hours(t)), V.at(lat, lon, hours(t))
            how = 'at the printed time'
        else:
            hs = [hours(day) + h for h in range(0, 24, 3)]
            u = float(np.mean([U.at(lat, lon, h) for h in hs]))
            v = float(np.mean([V.at(lat, lon, h) for h in hs]))
            how = 'day mean (no time printed)'
        if math.isnan(u) or math.isnan(v):
            skipped['outside the reanalysis subset'] += 1
            continue
        rows.append({'station': sid, 'coast': r['coast'], 'date': r['date'], 'ut': t.isoformat(timespec='minutes') if timed else '',
                     'time_how': how, 'record_id': r['record_id'], 'wind_raw': r['wind_raw'], 'keeper_deg': float(r['wind_deg']),
                     'wind_how': r['wind_how'], 'force_bft': r['force_bft'], 'r_deg': round(bearing_from(u, v), 1),
                     'r_speed': round(math.hypot(u, v), 2), 'declination': round(declination(lat, lon, day.year + day.timetuple().tm_yday / 365.25), 2),
                     'lat': lat, 'lon': lon})
    os.makedirs(os.path.join(DATA, 'weather'), exist_ok=True)
    with open(os.path.join(DATA, 'weather', 'winds.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f'{len(rows)} distinct winds -> data/weather/winds.csv ({sum(r["ut"] != "" for r in rows)} at a printed time); '
          f'skipped records: {dict(skipped)}')


if __name__ == '__main__':
    main()
