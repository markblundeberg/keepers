"""Look test for movement I: the South Bishop lantern, 21-22 October 1887.

The light: "One rev. br. lt., 20 secs." (Findlay 1887): one beam, turning
once in 20 s; here its phase is set so it faces the camera at t = 4 s. The
night: S.E. 4, overcast, misty (the printed entry). Birds are lit only where
the beam or the lantern's glow falls on them (the painting's logic: a bird in
the dark is unseen). Toning: sepia aquatint, grain.

Run in the venv: .venv/bin/python -I film/test/lantern_test.py OUT_DIR [--w 960] [--seconds 8]
"""
import argparse, math, os, subprocess
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

FPS = 24
CYCLE = 20.0                    # seconds per turn (Findlay 1887)
FLASH_AT = 4.0                  # the beam faces the camera here


def sepia(L):
    """Luminance 0..1 to a warm ink-on-paper ramp: deep brown-black, umber, cream."""
    stops = np.array([[0.00, 10, 8, 7], [0.25, 38, 28, 20], [0.55, 120, 92, 62], [0.85, 222, 200, 160], [1.0, 250, 238, 210]])
    L = np.clip(L, 0, 1)
    out = np.empty(L.shape + (3,))
    for c in range(3):
        out[..., c] = np.interp(L, stops[:, 0], stops[:, c + 1])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--w', type=int, default=960)
    ap.add_argument('--seconds', type=float, default=8.0)
    a = ap.parse_args()
    W, H = a.w, a.w * 9 // 16
    s = W / 960                                         # scale factor for sizes
    os.makedirs(a.out, exist_ok=True)
    rng = np.random.default_rng(1887)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    LX, LY = 0.50 * W, 0.34 * H                          # the lamp
    # mist: two layers of soft noise drifting with the S.E. wind (from the right, slightly toward the camera)
    mist_a = gaussian_filter(rng.random((H // 4 + 8, W // 4 + 40)), 6 * s)
    mist_b = gaussian_filter(rng.random((H // 8 + 8, W // 8 + 40)), 3 * s)
    for m in (mist_a, mist_b):
        m -= m.min(); m /= m.max()
    paper = gaussian_filter(rng.random((H, W)), 0.7) * 0.5 + gaussian_filter(rng.random((H, W)), 3) * 0.5
    paper = (paper - paper.mean()) / paper.std()
    # birds: positions in a cylinder round the lantern (units: lamp-to-gallery ~ 1), each circling and fluttering
    N = 2200
    r0 = 0.7 + rng.gamma(1.6, 1.5, N)
    th0 = rng.uniform(0, 2 * math.pi, N)
    z0 = rng.normal(0, 1.0, N) * (0.3 + 0.25 * r0)
    om = rng.normal(0, 1, N) * 0.35 + np.sign(rng.normal(0, 1, N)) * 0.25     # angular speeds (rad/s), both ways
    flap = rng.uniform(7, 13, N)
    arrive = rng.uniform(-6, a.seconds * 1.2, N)                               # the flock thickens through the shot
    unit = 92 * s                                                              # pixels per unit at the lamp's depth
    nf = int(a.seconds * FPS)
    for f in range(nf):
        t = f / FPS
        phi = 2 * math.pi * (t - FLASH_AT) / CYCLE                             # 0 = toward the camera
        bx, bz = math.sin(phi), -math.cos(phi)                                 # beam direction: x right, z away from camera
        push = 1.0 + 0.035 * t / a.seconds                                    # a slow push in
        X = (xx - LX) / (unit * push)
        Y = (yy - LY) / (unit * push)
        # the beam seen from the side: a cone along +x or -x, its on-screen length shrinking as it turns toward us
        side = math.copysign(1, bx) if abs(bx) > 1e-6 else 1
        along = X * side
        reach = abs(bx)                                                         # foreshortening
        width = 0.40 + 0.22 * np.clip(along, 0, None)
        cone = np.where(along > 0, np.exp(-(Y / width) ** 2) * np.exp(-np.clip(along, 0, None) / (9 * reach + 0.3)), 0)
        cone *= (0.25 + 0.75 * reach) * (1 + 0.6 * max(0.0, -bz))             # brighter scatter when it points a little toward us
        # glare when it faces the camera
        rr = np.hypot(X, Y)
        facing = max(0.0, -bz) ** 24
        glare = facing * (np.exp(-(rr / 2.2) ** 2) + 0.45 * np.exp(-rr / 5.0))
        # mist modulates the visible beam
        ox = int((t * 6 * s) % 30)
        ma = np.kron(mist_a[:, ox:ox + W // 4 + 1], np.ones((4, 4)))[:H, :W]
        mb = np.kron(mist_b[:, ox // 2:ox // 2 + W // 8 + 1], np.ones((8, 8)))[:H, :W]
        mist = 0.55 + 0.45 * (0.6 * ma + 0.4 * mb)
        lamp_glow = 0.55 * np.exp(-(rr / 0.55) ** 2) + 0.12 * np.exp(-rr / 2.5)
        sky = 0.06 + 0.03 * (1 - yy / H)
        L = sky + (cone * 0.9 + glare * 1.2) * mist + lamp_glow
        # the tower: a dark silhouette below the lamp, the lantern glazing lit
        tw = np.abs(X) < (0.62 + 0.05 * np.clip(Y, 0, None))
        tower = tw & (Y > 0.75)
        gallery = (np.abs(X) < 1.05) & (Y > 0.62) & (Y < 0.78)
        glazing = (np.abs(X) < 0.45) & (Y > -0.45) & (Y < 0.62)
        dome = (X ** 2 / 0.5 ** 2 + (Y + 0.45) ** 2 / 0.35 ** 2 < 1) & (Y < -0.45)
        L = np.where(tower | gallery, 0.035 + 0.04 * np.clip(1 - Y / 8, 0, 1) * (0.5 + 0.5 * np.sign(-X)), L)
        L = np.where(dome, 0.05, L)
        bars = (np.abs(((X + 0.6 * Y + 0.45) / 0.22) % 1 - 0.5) < 0.07) | (np.abs(((Y + 0.45) / 0.36) % 1 - 0.5) < 0.05)
        rail = ((np.abs(Y - 0.52) < 0.025) | ((np.abs(((X) / 0.16) % 1 - 0.5) < 0.06) & (Y > 0.52) & (Y < 0.64))) & (np.abs(X) < 1.0)
        L = np.where(glazing, np.where(bars, 0.30, 0.92 + 0.3 * facing), L)
        L = np.where(rail & ~glazing, 0.03, L)
        lightmap = (cone * 0.9 + glare * 1.2) * mist + lamp_glow                 # what light falls where, on screen
        # birds
        live = t > arrive
        th = th0 + om * t
        r = r0 + 0.15 * np.sin(t * 0.7 + th0 * 3)
        bxp, bzp = r * np.cos(th), r * np.sin(th)
        byp = z0 + 0.12 * np.sin(t * 1.3 + th0)
        depth = 1 + bzp * 0.06
        sx = LX + bxp * unit * push / depth
        sy = LY + byp * unit * push / depth
        ang = np.arctan2(bxp, -bzp)                                            # bird's bearing from the lamp, 0 = toward camera
        dang = np.angle(np.exp(1j * (ang - phi)))
        lit = np.exp(-(dang / (0.10 + 0.05 / np.maximum(r, 0.5))) ** 2) * np.exp(-r / 10) * np.exp(-(byp / (0.4 + 0.18 * r)) ** 2)
        lit = np.maximum(lit, 0.5 * np.exp(-(r / 1.3) ** 2))                     # near the glazing the lamp lights them all round
        lit = np.maximum(lit, 0.08)                                              # faint ambient
        size = np.clip(3.2 * s / depth, 1.5, 8)
        wing = np.sin(t * flap * 2 * math.pi + th0)
        img = L.copy()
        for k in np.nonzero(live)[0]:
            x0, y0, sz = sx[k], sy[k], size[k]
            if not (8 < x0 < W - 9 and 8 < y0 < H - 9):
                continue
            ix, iy = int(x0), int(y0)
            bg, light = L[iy, ix], lightmap[iy, ix]
            if bg > 0.6:
                v, mixw = 0.08, 0.85                                           # against the lit glazing: a dark shape
            elif light > 0.05:
                v, mixw = min(1.0, 0.25 + 1.6 * light), min(0.9, 0.2 + 2.5 * light)   # lit by the beam: pale, as in the painting
            else:
                continue                                                       # in the dark: unseen
            dy = wing[k] * sz * 0.7
            for dx in np.linspace(-sz, sz, max(3, int(2 * sz) + 1)):            # a small 'v' or a flat stroke, by wingbeat
                px, py = int(round(x0 + dx)), int(round(y0 - abs(dx) / sz * dy))
                for qy in (py, py + (1 if sz > 3 else 0)):
                    img[qy, px] = img[qy, px] * (1 - mixw) + v * mixw
        # aquatint: grain that bites more in the mid-tones, then a soft lens (halation) and vignette
        grain = paper * 0.045 * (0.4 + np.sin(np.pi * np.clip(img, 0, 1)))
        img = img + grain + rng.normal(0, 0.012, img.shape)
        img = img + 0.25 * gaussian_filter(np.clip(img - 0.6, 0, None), 6 * s)
        vig = 1 - 0.35 * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
        img = img * vig
        Image.fromarray(sepia(img).astype(np.uint8)).save(os.path.join(a.out, f'f{f:04d}.png'))
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', os.path.join(a.out, 'f%04d.png'),
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', os.path.join(a.out, 'lantern_test.mp4')], check=True)
    print('wrote', os.path.join(a.out, 'lantern_test.mp4'), nf, 'frames')


if __name__ == '__main__':
    main()
