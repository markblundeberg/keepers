"""Sound for movement I (shots cold..count, 0-53 s): the sea, a force-4 wind, the lens clockwork, and the
South Bishop keeper's three lines (film/voice/takes/, Mark's casting). All ambience is synthesised here;
nothing is a recording. Strike taps are added from the birds kit's strike times when they exist
(film/sound/strikes_i.json: a list of film seconds), else left out.

Run: python3 -I film/sound/mix_i.py [OUT.wav]
"""
import json, os, subprocess, sys
import numpy as np

SR = 48000
DUR = 55.7
HERE = os.path.dirname(os.path.abspath(__file__))
FILM = os.path.dirname(HERE)
# shot starts (film/engine/shots.js, cut 3): open 0, nightdead 9, cold 11.2, approach 18.2, glazing 28.2, dawn 34.2, gallery 43.2, page 47.7
LINES = [('sb1_chris_1.mp3', 19.2), ('sb2_chris_1.mp3', 35.7), ('sb3_chris_1.mp3', 50.9)]   # = shots.js VOICE (shot start + at)


def load(path):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-f', 'f32le', '-ac', '1', '-ar', str(SR), '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).astype(np.float64)


def fft_filter(x, lo, hi, tilt=0.0):
    """Band-pass by FFT with soft edges; tilt in dB/octave (negative darkens)."""
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    g = 1 / (1 + (lo / np.maximum(f, 1)) ** 4) / (1 + (f / hi) ** 4)
    g *= (np.maximum(f, 20) / 1000) ** (tilt / 6.02)
    return np.fft.irfft(X * g, len(x))


def main(out):
    rng = np.random.default_rng(1887)
    n = int(DUR * SR)
    t = np.arange(n) / SR
    dawn = np.clip((t - 34.2) / 3, 0, 1)                        # the dawn shots are calmer
    # the sea: low surf with swells about 10 s apart, and a slow wash on the rock below
    sea = fft_filter(rng.normal(0, 1, n), 40, 900, -3)
    swell = 0.55 + 0.45 * np.sin(2 * np.pi * t / 10.3 + 1.1) ** 2 * (0.7 + 0.3 * np.sin(2 * np.pi * t / 37))
    sea *= swell / np.std(sea)
    # the wind, S.E. force 4 (a moderate breeze): a band of noise, gusting slowly
    wind = fft_filter(rng.normal(0, 1, n), 250, 2200, -2)
    gust = 0.5 + 0.5 * np.clip(np.convolve(rng.normal(0, 1, n // 4800 + 3), np.ones(3) / 3, 'same'), -1, 1)
    gust = np.interp(t, np.linspace(0, DUR, len(gust)), gust)
    wind *= (0.35 + 0.65 * gust) / np.std(wind)
    # the clockwork that turns the lens: a soft escapement tick about twice a second, heard only near the lantern
    tick = np.zeros(n)
    near = np.interp(t, [0, 11.0, 11.4, 28.0, 28.4, 34.0, 34.4, DUR], [1, 1, 0, 0, 1, 1, 0.15, 0.15])   # near the lantern: open, nightdead, glazing
    k = np.arange(int(0.012 * SR))
    click = np.sin(2 * np.pi * 2900 * k / SR) * np.exp(-k / (0.0025 * SR)) + 0.5 * np.sin(2 * np.pi * 1700 * k / SR) * np.exp(-k / (0.004 * SR))
    for i, tt in enumerate(np.arange(0.2, DUR, 0.5)):
        s = int(tt * SR) + int(rng.normal(0, 0.004) * SR)
        if 0 <= s < n - len(click):
            tick[s:s + len(click)] += click * (1.0 if i % 2 == 0 else 0.7) * near[s]
    # strikes, from the birds kit's own events (film/sound/dump_strikes.mjs): a bird against glass is a dry knock, a
    # flutter against it a light tap, a body landing on the gallery a soft thud; loudness from the kit's hardness and
    # falling with distance (inaudible from the sea, as it would be)
    taps = np.zeros(n)
    sj = os.path.join(HERE, 'strikes_i.json')
    if os.path.exists(sj):
        # a bird hitting glass at speed is two sounds: the body's dull thud and the pane's ring
        kinds = {'dead': (900, 3200, 0.006, 1.0), 'glance': (900, 3200, 0.004, 0.6), 'flutter-tap': (1500, 4500, 0.002, 0.25),
                 'land-gallery': (120, 900, 0.010, 0.35), 'land-rock': (120, 700, 0.010, 0.2)}
        thud = {'dead': 1.0, 'glance': 0.55}
        for e in json.load(open(sj)):
            if e['kind'] not in kinds:
                continue
            lo, hi, tau, g = kinds[e['kind']]
            gain = g * e['hard'] * min(1.0, 5.0 / max(e['dist'], 1.0)) ** 1.2
            if gain < 0.004:
                continue
            m = int(8 * tau * SR)
            kk = np.arange(m)
            body = rng.normal(0, 1, m) * np.exp(-kk / (tau * SR))
            body = fft_filter(np.pad(body, (0, 2048)), lo, hi)[:m]
            body /= max(1e-9, np.max(np.abs(body)))
            if e['kind'] in thud:                                      # the body: a low, short thump under the knock
                mt = int(0.06 * SR)
                kt = np.arange(mt)
                th = rng.normal(0, 1, mt) * np.exp(-kt / (0.012 * SR))
                th = fft_filter(np.pad(th, (0, 4096)), 90, 520)[:mt]
                th /= max(1e-9, np.max(np.abs(th)))
                body = np.pad(body, (0, max(0, mt - m)))[:max(m, mt)] + 1.3 * thud[e['kind']] * np.pad(th, (0, max(0, m - mt)))[:max(m, mt)]
                m = len(body)
            st = int(e['t'] * SR)
            if 0 <= st < n - m:
                taps[st:st + m] += body * gain
    amb = (0.22 * sea * (1 - 0.4 * dawn) + 0.10 * wind * (1 - 0.5 * dawn) + 0.05 * tick)
    amb *= np.interp(t, [0, 0.8, DUR - 1.5, DUR], [0.3, 1, 1, 0.6])        # up out of black with the picture
    # the voice
    vo = np.zeros(n)
    for f, at in LINES:
        v = load(os.path.join(FILM, 'voice', 'takes', f))
        v = v / np.sqrt(np.mean(v[np.abs(v) > 0.02] ** 2))               # each line at the same speaking level (as mix_ii)
        s = int(at * SR)
        vo[s:s + len(v)] += v[:max(0, n - s)]
    vo *= 0.9 / max(1e-9, np.max(np.abs(vo)))
    w = int(0.3 * SR)
    c = np.concatenate([[0.0], np.cumsum((np.abs(vo) > 0.02).astype(float))])
    duck = (c[np.clip(np.arange(n) + w // 2, 0, n)] - c[np.clip(np.arange(n) - w // 2, 0, n)]) / w   # running mean over 0.3 s
    d = np.clip(duck * 3, 0, 1)
    tapg = np.interp(t, [0, 11.0, 11.6, DUR], [1.0, 1.0, 0.4, 0.4])          # the cold open is the strikes (Mark, cut 2 notes)
    mix = 1.25 * vo + amb * (1 - 0.72 * d) + tapg * taps * (1 - 0.35 * d)   # Mark: voice clearer (cut 1 at 0:13)
    mix *= 0.89 / np.max(np.abs(mix))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    pcm = (np.clip(mix, -1, 1) * 32767).astype('<i2')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 's16le', '-ar', str(SR), '-ac', '1', '-i', '-', out], input=pcm.tobytes(), check=True)
    print('wrote', out, f'{DUR} s; strikes: {"yes" if os.path.exists(sj) else "none yet"}')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(FILM, 'out', 'movement_i.wav'))
