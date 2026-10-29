"""Magnetic declination at a place and time, from gufm1 (Jackson, Jonkers &
Walker 2000, Phil. Trans. R. Soc. A 358, 957-990; built from ships' logs and
observatories, 1590-1990): Gauss coefficients to degree 14 in cubic B-splines
of time, file sources/geomag/gufm1.txt (geomag.colorado.edu). If the keepers
read their winds off a magnetic compass, their bearings run clockwise of the
true ones by the westerly declination.

Run: python3 -I tools/declination.py check
"""
import math, os, sys
import numpy as np
from scipy.interpolate import BSpline
from scipy.special import lpmv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import ROOT

PATH = os.path.join(ROOT, 'sources', 'geomag', 'gufm1.txt')


def load():
    nums = []
    for line in open(PATH).readlines()[1:]:                    # line 1 is the title
        nums += [float(x) for x in line.split()]
    lmax, nspl = int(nums[0]), int(nums[1])
    knots = np.array(nums[2:2 + nspl + 4])
    nc = lmax * (lmax + 2)
    coef = np.array(nums[2 + nspl + 4:]).reshape(nspl, nc)
    assert coef.shape == (nspl, nc), coef.shape
    return lmax, knots, coef


LMAX, KNOTS, COEF = load()


def gauss(year):
    """The Gauss coefficients at a decimal year: g10, g11, h11, g20, g21, h21, g22, h22, ..."""
    return BSpline(KNOTS, COEF, 3, extrapolate=False)(year)


def schmidt(n, m, x):
    p = lpmv(m, n, x) * (-1) ** m                              # drop the Condon-Shortley phase
    return p if m == 0 else p * math.sqrt(2 * math.factorial(n - m) / math.factorial(n + m))


def declination(lat, lon, year):
    """Degrees east of true north (negative = west); geocentric latitude taken as geodetic (under 0.2 deg here)."""
    g = gauss(year)
    th, ph = math.radians(90 - lat), math.radians(lon)
    eps = 1e-6
    X = Y = 0.0
    k = 0
    for n in range(1, LMAX + 1):
        for m in range(0, n + 1):
            gnm = g[k]
            k += 1
            hnm = 0.0
            if m > 0:
                hnm = g[k]
                k += 1
            dP = (schmidt(n, m, math.cos(th + eps)) - schmidt(n, m, math.cos(th - eps))) / (2 * eps)
            P = schmidt(n, m, math.cos(th))
            X += (gnm * math.cos(m * ph) + hnm * math.sin(m * ph)) * dP
            Y += m * (gnm * math.sin(m * ph) - hnm * math.cos(m * ph)) * P / math.sin(th)
    return math.degrees(math.atan2(Y, X))


def check():
    london = (51.5, -0.1)
    rows = [(1990, -5.5, -3.5), (1900, -17.5, -15.5), (1880, -20.0, -17.5)]   # what I recall, as ranges
    ok = True
    for y, lo, hi in rows:
        d = declination(*london, y)
        good = lo <= d <= hi
        ok &= good
        print(f'London {y}: {d:6.2f} deg (expected {lo}..{hi}) {"ok" if good else "OFF"}')
    for name, lat, lon in (('Sumburgh Head', 59.85, -1.27), ('Fastnet', 51.39, -9.60), ('Heligoland', 54.18, 7.88), ('Eddystone', 50.18, -4.27)):
        print(f'{name} 1883: {declination(lat, lon, 1883.5):6.2f} deg')
    print('CHECK OK' if ok else 'CHECK FAILED')
    return ok


if __name__ == '__main__':
    check()
