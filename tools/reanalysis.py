"""The weather the keepers had, as the 20th Century Reanalysis v3 has it
(NOAA/CIRES/DOE; Slivinski et al. 2019): 3-hourly fields on a 1-degree grid,
built from surface pressure observations alone, so independent of the
keepers' own winds and weather. Fetched over OPeNDAP from NOAA PSL's THREDDS
server, cut to a box round the British Isles and Heligoland (48-62 N,
12 W-10 E), one file per variable and year.

The subsets are not committed (a few hundred MB); sources/reanalysis/MANIFEST.json
records where each came from, the slice, its size and sha256, so this script
rebuilds them.

Run: python3 -I tools/reanalysis.py fetch [vars] [--years 1879-1888] | manifest
"""
import argparse, datetime, hashlib, json, os, sys, time
import numpy as np
import netCDF4 as nc
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import ROOT

BASE = 'https://psl.noaa.gov/thredds/dodsC/Datasets/20thC_ReanV3'
VARS = {  # short name: (directory, file stem, variable)
    'uwnd': ('10mSI', 'uwnd.10m', 'uwnd'), 'vwnd': ('10mSI', 'vwnd.10m', 'vwnd'),
    'prmsl': ('miscSI', 'prmsl', 'prmsl'), 'tcdc': ('miscSI', 'tcdc.eatm', 'tcdc'),
    'lcdc': ('cldLyrSI', 'tcdc.lowcld', 'tcdc'), 'air': ('2mSI', 'air.2m', 'air'),
    'rhum': ('2mSI', 'rhum.2m', 'rhum'), 'apcp': ('accumsSI', 'apcp', 'apcp')}
OUT = os.path.join(ROOT, 'sources', 'reanalysis')
BOX = dict(south=48, north=62, west=-12, east=10)


def fetch_one(short, year):
    d_, stem, var = VARS[short]
    path = os.path.join(OUT, f'{stem}.{year}.nc')
    if os.path.exists(path):
        return path, None
    if os.path.exists(path + '.part') and time.time() - os.path.getmtime(path + '.part') < 3600:
        return path, None                               # another fetcher is writing it
    url = f'{BASE}/{d_}/{stem}.{year}.nc'
    for attempt in range(4):
        try:
            d = nc.Dataset(url)
            lat, lon = d.variables['lat'][:], d.variables['lon'][:]
            la = np.where((lat >= BOX['south']) & (lat <= BOX['north']))[0]
            west = np.where(lon >= 360 + BOX['west'])[0]          # 348..359
            east = np.where(lon <= BOX['east'])[0]                 # 0..10
            t = d.variables['time']
            nt = t.shape[0]
            parts = []
            for a in range(0, nt, 744):                            # a month or so per request
                b = min(nt, a + 744)
                v = d.variables[var]
                w = v[a:b, la[0]:la[-1] + 1, west[0]:west[-1] + 1]
                e = v[a:b, la[0]:la[-1] + 1, east[0]:east[-1] + 1]
                parts.append(np.concatenate([w, e], axis=2))
            data = np.ma.concatenate(parts, axis=0)
            lats = lat[la[0]:la[-1] + 1]
            lons = np.concatenate([lon[west[0]:west[-1] + 1] - 360, lon[east[0]:east[-1] + 1]])
            tv, tunits = t[:], t.units
            units = getattr(d.variables[var], 'units', '')
            long_name = getattr(d.variables[var], 'long_name', '')
            d.close()
            break
        except Exception as e:
            print(f'  {short} {year}: {e}; retrying', flush=True)
            time.sleep(30 * (attempt + 1))
    else:
        raise RuntimeError(f'{short} {year}: failed')
    os.makedirs(OUT, exist_ok=True)
    tmp = path + '.part'
    o = nc.Dataset(tmp, 'w', format='NETCDF4_CLASSIC')
    o.createDimension('time', len(tv))
    o.createDimension('lat', len(lats))
    o.createDimension('lon', len(lons))
    o.createVariable('time', 'f8', ('time',))[:] = tv
    o.variables['time'].units = tunits
    o.createVariable('lat', 'f4', ('lat',))[:] = lats
    o.createVariable('lon', 'f4', ('lon',))[:] = lons
    x = o.createVariable(var, 'f4', ('time', 'lat', 'lon'), zlib=True, complevel=4)
    x[:] = data
    x.units, x.long_name = units, long_name
    o.source = f'{url} (OPeNDAP), lat {lats[0]}..{lats[-1]}, lon {lons[0]}..{lons[-1]}; NOAA/CIRES/DOE 20CRv3 (Slivinski et al. 2019)'
    o.close()
    os.replace(tmp, path)
    entry = {'url': url, 'slice': f'lat {float(lats[0])}..{float(lats[-1])}, lon {float(lons[0])}..{float(lons[-1])}, all times',
             'path': os.path.relpath(path, ROOT), 'bytes': os.path.getsize(path),
             'sha256': hashlib.sha256(open(path, 'rb').read()).hexdigest(), 'retrieved': datetime.date.today().isoformat()}
    return path, entry


def fetch(shorts, years):
    mp = os.path.join(OUT, 'MANIFEST.json')
    for y in years:
        for s in shorts:
            path, entry = fetch_one(s, y)
            if entry:
                man = json.load(open(mp)) if os.path.exists(mp) else {}      # re-read: other fetchers write it too
                man[os.path.basename(path)] = entry
                json.dump(man, open(mp, 'w'), indent=1, sort_keys=True)
                print(f'{s} {y}: {entry["bytes"] // 1024} kB', flush=True)


def manifest():
    """Entries for subset files the manifest lacks (fetchers running at once can overwrite each other's)."""
    mp = os.path.join(OUT, 'MANIFEST.json')
    man = json.load(open(mp)) if os.path.exists(mp) else {}
    for f in sorted(os.listdir(OUT)):
        if f.endswith('.nc') and f not in man:
            stem, year = f[:-3].rsplit('.', 1)
            short = next(k for k, v in VARS.items() if v[1] == stem)
            p = os.path.join(OUT, f)
            d = nc.Dataset(p)
            lats, lons = d.variables['lat'][:], d.variables['lon'][:]
            d.close()
            man[f] = {'url': f'{BASE}/{VARS[short][0]}/{f}', 'slice': f'lat {float(lats[0])}..{float(lats[-1])}, lon {float(lons[0])}..{float(lons[-1])}, all times',
                      'path': os.path.relpath(p, ROOT), 'bytes': os.path.getsize(p), 'sha256': hashlib.sha256(open(p, 'rb').read()).hexdigest(),
                      'retrieved': datetime.date.fromtimestamp(os.path.getmtime(p)).isoformat()}
            print('added', f)
    json.dump(man, open(mp, 'w'), indent=1, sort_keys=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('step', choices=['fetch', 'manifest'])
    ap.add_argument('vars', nargs='*')
    ap.add_argument('--years', default='1879-1888')
    a = ap.parse_args()
    y0, y1 = map(int, a.years.split('-'))
    fetch(a.vars or list(VARS), range(y0, y1 + 1)) if a.step == 'fetch' else manifest()
