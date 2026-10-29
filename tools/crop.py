"""Crop the part of a scan where a segment or observation is printed, for
reading by eye. The vertical position is estimated from where the segment
sits in its page's text (the scans' text block is linear in lines, near
enough), with a generous margin.

Run: python3 -I tools/crop.py 1887 1887-ENW-0287 [--out DIR] [--band 0.35]
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ is ours; -I drops it
from kp import DATA, ROOT, Pages, scan
from PIL import Image

TOP, BOTTOM = 0.08, 0.94      # text block as fractions of the page height (1887 scans)


def crop(year, ident, out_dir, band=0.35, width=900):
    segs = {s['seg_id']: s for s in (json.loads(l) for l in open(os.path.join(DATA, 'pilot', f'segments_{year}.jsonl')))}
    seg = segs[ident.rsplit('.', 1)[0] if ident.count('.') else ident]
    pages = Pages(year)
    i = pages.offsets.index(pages.at(seg['start'])['txt_offset'])
    m0 = pages.markers[i]
    nxt = pages.markers[i + 1]['txt_offset'] if i + 1 < len(pages.markers) else seg['end'] + 2000
    frac = (seg['start'] - m0['txt_offset']) / max(1, nxt - m0['txt_offset'])
    paths = []
    img = Image.open(scan(year, m0['image_index']))
    w, h = img.size
    y = TOP + frac * (BOTTOM - TOP)
    a, b = max(0.0, y - band * 0.35), min(1.0, y + band * 0.65)
    c = img.crop((0, int(a * h), w, int(b * h)))
    c = c.resize((width, int(width * c.size[1] / w)))
    os.makedirs(out_dir, exist_ok=True)
    p = os.path.join(out_dir, f'{ident}.jpg')
    c.save(p, quality=82)
    paths.append(p)
    if seg['end'] > nxt:          # runs onto the next page: add its top
        img2 = Image.open(scan(year, pages.markers[i + 1]['image_index']))
        c2 = img2.crop((0, 0, img2.size[0], int(0.35 * img2.size[1])))
        c2 = c2.resize((width, int(width * c2.size[1] / img2.size[0])))
        p2 = os.path.join(out_dir, f'{ident}_next.jpg')
        c2.save(p2, quality=82)
        paths.append(p2)
    return paths


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('year', type=int)
    ap.add_argument('ident')
    ap.add_argument('--out', default=os.path.join(ROOT, 'cache', 'crops'))
    ap.add_argument('--band', type=float, default=0.35)
    a = ap.parse_args()
    print('\n'.join(crop(a.year, a.ident, a.out, a.band)))
