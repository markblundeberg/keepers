"""Sound for movement II (the shot 'elsewhere', 26 s): the five keepers' lines at once over a quiet sea and wind.
Stereo: each voice is panned by its station's longitude (west left, east right), so the overlap stays separable
and the chart's geography is heard. Timings = film/engine/shots.js VOICE (shot-local 'at'); keep the two in step.
The ambience is mix_i.py's, synthesised; it thins as the view rises away from the sea.

Run: python3 -I film/sound/mix_ii.py [OUT.wav]
"""
import os, subprocess, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # our own dir; -I drops it
from mix_i import SR, FILM, fft_filter, load

DUR = 26.0
# id, take, at (s into the shot), station longitude
LINES = [('tk1', 'tk1_flynn_1.mp3', 4.5, -6.21), ('cg1', 'cg1_keanan_1.mp3', 6.6, -6.67), ('ed1', 'ed1_tom_1.mp3', 9.0, -4.26),
         ('cr1', 'cr1_adam_1.mp3', 10.4, -4.84), ('md1', 'md1_mark_1.mp3', 12.6, -5.73)]
LON_C, LON_HALF, PAN_MAX = -5.46, 1.21, 0.75


def main(out):
    rng = np.random.default_rng(1888)
    n = int(DUR * SR)
    t = np.arange(n) / SR
    rise = np.clip((t - 1.0) / 12, 0, 1)
    rise = rise * rise * (3 - 2 * rise)                                  # = shots.js zoomK
    sea = fft_filter(rng.normal(0, 1, n), 40, 900, -3)
    swell = 0.55 + 0.45 * np.sin(2 * np.pi * t / 10.3 + 2.0) ** 2
    sea *= swell / np.std(sea)
    wind = [fft_filter(rng.normal(0, 1, n), 250, 2200, -2) for _ in range(2)]   # the wind a little different in each ear
    wind = [w / np.std(w) for w in wind]
    amb_l = 0.22 * sea * (1 - 0.75 * rise) + 0.10 * wind[0] * (1 - 0.3 * rise)
    amb_r = 0.22 * sea * (1 - 0.75 * rise) + 0.10 * wind[1] * (1 - 0.3 * rise)
    fade = np.interp(t, [0, 0.8, DUR - 2.0, DUR], [0.4, 1, 1, 0])
    amb = np.stack([amb_l, amb_r]) * fade
    vo = np.zeros((2, n))
    for _, f, at, lon in LINES:
        v = load(os.path.join(FILM, 'voice', 'takes', f))
        v = v / np.sqrt(np.mean(v[np.abs(v) > 0.02] ** 2))               # each reader at the same speaking level
        pan = float(np.clip((lon - LON_C) / LON_HALF, -1, 1)) * PAN_MAX
        th = (pan + 1) * np.pi / 4                                         # constant-power pan
        s = int(at * SR)
        m = min(len(v), n - s)
        vo[0, s:s + m] += np.cos(th) * v[:m]
        vo[1, s:s + m] += np.sin(th) * v[:m]
    vo *= 0.8 / max(1e-9, np.max(np.abs(vo)))
    w = int(0.3 * SR)
    act = (np.abs(vo).max(0) > 0.02).astype(float)
    c = np.concatenate([[0.0], np.cumsum(act)])
    duck = (c[np.clip(np.arange(n) + w // 2, 0, n)] - c[np.clip(np.arange(n) - w // 2, 0, n)]) / w
    d = np.clip(duck * 3, 0, 1)
    mix = 1.25 * vo + amb * (1 - 0.6 * d)
    mix *= 0.89 / np.max(np.abs(mix))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    pcm = (np.clip(mix.T, -1, 1) * 32767).astype('<i2')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 's16le', '-ar', str(SR), '-ac', '2', '-i', '-', out], input=pcm.tobytes(), check=True)
    print('wrote', out, f'{DUR} s, stereo')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(FILM, 'out', 'movement_ii.wav'))
