"""Riso-style illustrations from Microsoft Fluent emoji (MIT licence).

icon('Bellhop bell', 360)              -> RGBA sprite in the Qarya ink palette
icon('Ice', 300, style='mono', ink=CREAM) -> one-ink silhouette
python3 icons.py search cold           -> list matching emoji names
python3 icons.py sheet out.jpg Ice Key -> preview sheet
"""
import os, sys, json, glob, subprocess, hashlib
import numpy as np
import cv2
from PIL import Image
from config import EMOJI, ICON_CACHE
from engine import CREAM, GOLD, GOLDHI, ROSE, TEAL, SKY

MAUVE = (196, 120, 160)
GREY = (150, 150, 160)
DARK = (40, 48, 70)


def _index():
    idx = {}
    for d in glob.glob(os.path.join(EMOJI, '*')):
        name = os.path.basename(d)
        idx[name.lower()] = d
    return idx


_IDX = None


def find(name):
    global _IDX
    if _IDX is None:
        _IDX = _index()
    d = _IDX.get(name.lower())
    if d is None:
        raise KeyError(f'No Fluent emoji called {name!r}. Try: python3 kit/icons.py search <word>')
    for pat in ('Flat/*.svg', 'Default/Flat/*.svg'):
        g = sorted(glob.glob(os.path.join(d, pat)))
        if g:
            return g[0]
    raise KeyError(f'{name!r} has no Flat SVG')


def search(word):
    word = word.lower()
    hits = []
    for d in sorted(glob.glob(os.path.join(EMOJI, '*'))):
        name = os.path.basename(d)
        kw = []
        try:
            m = json.load(open(os.path.join(d, 'metadata.json')))
            kw = [k.lower() for k in m.get('keywords', [])] + [m.get('group', '').lower()]
        except Exception:
            pass
        if word in name.lower() or any(word in k for k in kw):
            try:
                find(name)
                hits.append(name)
            except KeyError:
                pass
    return hits


def _raster(svg, size):
    os.makedirs(ICON_CACHE, exist_ok=True)
    out = os.path.join(ICON_CACHE, hashlib.md5(f'{svg}{size}'.encode()).hexdigest() + '.png')
    if not os.path.exists(out):
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-width', str(size), '-height', str(size), '-keep_ar', '1',
                        '-i', svg, '-frames:v', '1', out], check=True)
    return np.asarray(Image.open(out).convert('RGBA'), np.float32)


def _hsv(f):
    r, g, b = f[..., 0] / 255., f[..., 1] / 255., f[..., 2] / 255.
    mx = np.max(f[..., :3], -1) / 255.
    mn = np.min(f[..., :3], -1) / 255.
    d = mx - mn + 1e-6
    h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60
    s = np.where(mx > 0, (mx - mn) / (mx + 1e-6), 0)
    return h, s, mx


_paper = {}


def _paper_tex(n):
    if n not in _paper:
        rng = np.random.default_rng(3)
        z = rng.standard_normal((max(2, n // 3), max(2, n // 3))).astype(np.float32)
        z = np.asarray(Image.fromarray(((z * 40) + 128).clip(0, 255).astype(np.uint8)).resize((n, n), Image.BICUBIC), np.float32) / 255 - 0.5
        _paper[n] = z
    return _paper[n]


_memo = {}


def icon(name, size=320, style='ink', ink=CREAM, under=GOLD, offset=(7, 6), edges=True):
    """Return an RGBA sprite (size + padding) of the named Fluent emoji in riso style.

    style='ink'  : colours mapped to the Qarya palette, halftone shading, gold misregistration
    style='mono' : single flat ink (ink=...), still with gold misregistration
    """
    key = (name, size, style, ink, under, offset, edges)
    if key in _memo:
        return _memo[key]
    f = _raster(find(name), size * 2)
    f = np.asarray(Image.fromarray(f.astype(np.uint8), 'RGBA').resize((size, size), Image.LANCZOS), np.float32)
    a = f[..., 3] / 255.
    h, s, v = _hsv(f)
    out = np.zeros(f.shape[:2] + (3,), np.float32)
    if style == 'mono':
        out[:] = ink
        out *= (0.86 + 0.2 * v)[..., None]
    else:
        def setc(m, c, shade=True):
            k = (0.72 + 0.38 * v) if shade else 1.0
            for i in range(3):
                out[..., i] = np.where(m, c[i] * k, out[..., i])
        grey = s < 0.18
        setc(grey & (v > 0.62), CREAM)
        setc(grey & (v <= 0.62) & (v > 0.32), GREY)
        setc(grey & (v <= 0.32), DARK, False)
        col = ~grey
        setc(col & ((h < 38) | (h >= 330)), ROSE)
        setc(col & (h >= 38) & (h < 70), GOLDHI)
        setc(col & (h >= 70) & (h < 170), TEAL)
        setc(col & (h >= 170) & (h < 265), SKY)
        setc(col & (h >= 265) & (h < 330), MAUVE)
        tone = np.clip((0.75 - v) * 1.4, 0, 1) * a
        yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
        c = max(5, size // 46)
        u, w = (xx + yy) * 0.7071, (yy - xx) * 0.7071
        d = np.sqrt((np.mod(u, c) - c / 2) ** 2 + (np.mod(w, c) - c / 2) ** 2)
        dots = np.clip(c * 0.5 * np.sqrt(tone) * 1.2 - d + 0.5, 0, 1)
        out *= (1 - 0.35 * dots)[..., None]
    if edges:
        lum = (0.3 * f[..., 0] + 0.59 * f[..., 1] + 0.11 * f[..., 2]) / 255.
        gx = cv2.Sobel(lum, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(lum, cv2.CV_32F, 0, 1, ksize=3)
        g = np.sqrt(gx * gx + gy * gy)
        k = max(3, size // 45)
        inner = cv2.erode((a > 0.5).astype(np.uint8), np.ones((k, k), np.uint8)).astype(np.float32)
        e = np.clip((g - 0.12) * 4, 0, 1) * inner
        e = cv2.GaussianBlur(cv2.dilate(e, np.ones((2, 2), np.uint8)), (0, 0), 0.8)
        out *= (1 - (0.55 if style == 'ink' else 0.35) * e)[..., None]
    out *= (1 + 0.10 * _paper_tex(size))[..., None]
    body = Image.fromarray(np.dstack([out.clip(0, 255), a * 255]).astype(np.uint8), 'RGBA')
    pad = max(12, size // 12)
    im = Image.new('RGBA', (size + pad * 2, size + pad * 2), (0, 0, 0, 0))
    if under is not None:
        und = Image.new('RGBA', (size, size), under + (255,))
        und.putalpha(Image.fromarray((a * 255 * 0.5).astype(np.uint8)))
        ox, oy = int(offset[0] * size / 300), int(offset[1] * size / 300)
        im.alpha_composite(und, (pad + ox, pad + oy))
    im.alpha_composite(body, (pad, pad))
    _memo[key] = im
    return im


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'search':
        for n in search(' '.join(sys.argv[2:])):
            print(n)
    elif cmd == 'sheet':
        names = sys.argv[3:]
        sheet = Image.new('RGBA', (340 * min(5, len(names)), 360 * ((len(names) + 4) // 5)), (18, 26, 44, 255))
        for k, n in enumerate(names):
            im = icon(n, 280)
            sheet.alpha_composite(im, ((k % 5) * 340 + 10, (k // 5) * 360 + 10))
        sheet.convert('RGB').save(sys.argv[2], quality=90)
