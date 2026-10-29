"""Sound for the title, roll and credits (the shot 'roll', 38.5 s): the sea and the wind back, faint, as from the rock,
and the lens clockwork ticking slowly under the title; all fading out under the credits. Synthesised, as mix_i.py.

Run: python3 -I film/sound/mix_roll.py [OUT.wav]
"""
import os, subprocess, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # our own dir; -I drops it
from mix_i import SR, FILM, fft_filter

DUR = 38.5                    # = shots.js TITLE_DUR + 24 + CREDITS_DUR


def main(out):
    rng = np.random.default_rng(1890)
    n = int(DUR * SR)
    t = np.arange(n) / SR
    sea = fft_filter(rng.normal(0, 1, n), 40, 900, -3)
    sea *= (0.55 + 0.45 * np.sin(2 * np.pi * t / 10.3 + 0.4) ** 2) / np.std(sea)
    wind = np.stack([fft_filter(rng.normal(0, 1, n), 250, 2200, -2) for _ in range(2)])
    wind /= np.std(wind)
    tick = np.zeros(n)
    k = np.arange(int(0.012 * SR))
    click = np.sin(2 * np.pi * 2900 * k / SR) * np.exp(-k / (0.0025 * SR)) + 0.5 * np.sin(2 * np.pi * 1700 * k / SR) * np.exp(-k / (0.004 * SR))
    for i, tt in enumerate(np.arange(0.3, 6.0, 0.5)):
        s = int(tt * SR)
        tick[s:s + len(click)] += click * (1.0 if i % 2 == 0 else 0.7) * max(0, 1 - tt / 6)
    env = np.interp(t, [0, 1.5, DUR - 6, DUR], [0.2, 1, 0.7, 0])
    mix = np.stack([0.20 * sea + 0.09 * wind[0], 0.20 * sea + 0.09 * wind[1]]) * env + 0.04 * tick
    mix *= 0.45 / np.max(np.abs(mix))           # quieter than the movements: a coda
    pcm = (np.clip(mix.T, -1, 1) * 32767).astype('<i2')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 's16le', '-ar', str(SR), '-ac', '2', '-i', '-', out], input=pcm.tobytes(), check=True)
    print('wrote', out, f'{DUR} s, stereo')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(FILM, 'out', 'roll.wav'))
