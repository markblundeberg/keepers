"""Sound for movement III (the shot 'pattern', 22 s): the nine years of strikes heard as they are drawn.

Each night with a strike makes one soft tick (a pen on paper: a short band of noise) at the moment its strokes appear
(shots.js: nights in date order across MARK_T0..MARK_T1 seconds), louder with the number of stations that struck;
so the migration seasons come as showers and the summers and winters as gaps. Under it, faint wind; then quiet for
the cards. Stereo, each tick placed left to right as its column (the moon's age).

Run: python3 -I film/sound/mix_iii.py [OUT.wav]
"""
import json, os, subprocess, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # our own dir; -I drops it
from mix_i import SR, FILM, fft_filter

DUR = 22.0
MARK_T0, MARK_T1 = 1.5, 9.5          # = shots.js


def main(out):
    rng = np.random.default_rng(1889)
    n = int(DUR * SR)
    t = np.arange(n) / SR
    cal = json.load(open(os.path.join(FILM, 'engine', 'assets', 'calendar.json')))['nights']
    ticks = np.zeros((2, n))
    m = int(0.004 * SR)
    k = np.arange(m)
    for i, r in enumerate(cal):
        c = len(r['struck'])
        if not c:
            continue
        at = MARK_T0 + (MARK_T1 - MARK_T0) * i / len(cal)
        g = 0.35 * np.sqrt(c)
        tick = fft_filter(np.pad(rng.normal(0, 1, m) * np.exp(-k / (0.0009 * SR)), (0, 1024)), 1800, 7000)[:m]
        tick *= g / max(1e-9, np.max(np.abs(tick)))
        p = float(np.clip(r['age'] / 29.53, 0, 1))              # the column's place, left to right
        th = (0.15 + 0.7 * p) * np.pi / 2
        s = int(at * SR) + int(rng.uniform(0, 0.007) * SR)
        if s + m < n:
            ticks[0, s:s + m] += np.cos(th) * tick
            ticks[1, s:s + m] += np.sin(th) * tick
    wind = np.stack([fft_filter(rng.normal(0, 1, n), 250, 2000, -3) for _ in range(2)])
    wind /= np.std(wind)
    wind *= 0.05 * np.interp(t, [0, 1.0, 10, 12, DUR - 1.5, DUR], [0.3, 1, 1, 0.6, 0.6, 0])
    mix = 0.5 * ticks + wind
    mix *= 0.7 / np.max(np.abs(mix))
    pcm = (np.clip(mix.T, -1, 1) * 32767).astype('<i2')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 's16le', '-ar', str(SR), '-ac', '2', '-i', '-', out], input=pcm.tobytes(), check=True)
    print('wrote', out, f'{DUR} s, stereo')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(FILM, 'out', 'movement_iii.wav'))
