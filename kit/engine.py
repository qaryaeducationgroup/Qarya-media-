"""Textured riso/halftone motion-graphics engine for Qarya explainer reels."""
import math, numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from config import FONTS

W, H, FPS = 1080, 1920, 30
FD = FONTS
BG0 = (11, 16, 29)
BG1 = (22, 31, 52)
CREAM = (240, 228, 204)
GOLD = (212, 172, 88)
GOLDHI = (248, 204, 100)
ROSE = (222, 112, 94)
TEAL = (78, 146, 156)
SKY = (118, 158, 212)
NAVYTXT = (16, 22, 38)

_f = {}


def font(name, size, var=None):
    k = (name, size, var)
    if k not in _f:
        f = ImageFont.truetype(FD + name, size)
        if var:
            f.set_variation_by_name(var)
        _f[k] = f
    return _f[k]


MONO = lambda s: font('SpaceMono-Regular.ttf', s)
MONOB = lambda s: font('SpaceMono-Bold.ttf', s)
SANS = lambda s: font('Poppins-Medium.ttf', s)
SANSB = lambda s: font('Poppins-SemiBold.ttf', s)
SERIF_I = lambda s: font('DMSerifDisplay-Italic.ttf', s)
SERIF = lambda s: font('DMSerifDisplay-Regular.ttf', s)
WORDMARK = lambda s: font('PlayfairDisplay[wght].ttf', s, 'Bold')


def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def ease(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def eout(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def eback(x, s=1.6):
    x = clamp(x) - 1
    return x * x * ((s + 1) * x + s) + 1


# ------------------------------------------------------------------ masks & inks
SS = 3


def mask(fn, w=W, h=H):
    """Anti-aliased mask: fn(draw, k) draws in white with coords scaled by k."""
    im = Image.new('L', (w * SS, h * SS), 0)
    fn(ImageDraw.Draw(im), SS)
    return np.asarray(im.resize((w, h), Image.LANCZOS), np.float32) / 255.0


_grid = None


def _uv(angle=45):
    global _grid
    if _grid is None:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        _grid = (xx, yy)
    xx, yy = _grid
    a = math.radians(angle)
    return xx * math.cos(a) + yy * math.sin(a), -xx * math.sin(a) + yy * math.cos(a)


_uvc = {}


def halftone(tone, cell=9, angle=45):
    """tone: (H,W) 0..1 -> dot coverage alpha."""
    key = (cell, angle)
    if key not in _uvc:
        u, v = _uv(angle)
        cu = np.mod(u, cell) - cell / 2
        cv = np.mod(v, cell) - cell / 2
        _uvc[key] = np.sqrt(cu * cu + cv * cv)
    d = _uvc[key]
    r = cell * 0.5 * np.sqrt(np.clip(tone, 0, 1)) * 1.28
    return np.clip(r - d + 0.5, 0, 1)


_paper = None


def paper_noise():
    global _paper
    if _paper is None:
        rng = np.random.default_rng(5)
        n = rng.standard_normal((H // 4, W // 4)).astype(np.float32)
        n = np.asarray(Image.fromarray(((n * 40) + 128).clip(0, 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)
                       .filter(ImageFilter.GaussianBlur(3)), np.float32) / 255.0 - 0.5
        f = rng.standard_normal((H, W)).astype(np.float32) * 0.5
        _paper = n * 0.9 + f * 0.25
    return _paper


def layer(alpha, color, texture=0.10):
    """RGBA PIL layer from alpha (H,W) + flat colour with paper texture variation."""
    a = np.clip(alpha, 0, 1)
    tex = 1 + texture * paper_noise()
    rgb = np.empty((H, W, 3), np.float32)
    for c in range(3):
        rgb[..., c] = color[c] * tex
    out = np.dstack([np.clip(rgb, 0, 255), a * 255]).astype(np.uint8)
    return Image.fromarray(out, 'RGBA')


def over(*layers):
    base = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    for l in layers:
        if l is not None:
            base.alpha_composite(l)
    return base


def shift(img, dx, dy):
    out = Image.new('RGBA', img.size, (0, 0, 0, 0))
    out.paste(img, (dx, dy))
    return out


def riso(alpha, color, under=GOLD, off=(4, 3), under_a=0.55, texture=0.10):
    """Ink layer with a misregistered second ink underneath (risograph feel)."""
    u = layer(alpha * under_a, under, texture)
    return over(shift(u, *off), layer(alpha, color, texture))


def radial(cx, cy, rx, ry=None):
    ry = ry or rx
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    return np.clip(1 - np.sqrt(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2), 0, 1)


def vgrad(y0, y1):
    yy = np.mgrid[0:H, 0:W][0].astype(np.float32)
    return np.clip((yy - y0) / (y1 - y0), 0, 1)


def glow_sprite(r, color, strength=1.0):
    s = int(r * 2)
    yy, xx = np.mgrid[0:s, 0:s].astype(np.float32)
    d = np.sqrt((xx - r) ** 2 + (yy - r) ** 2) / r
    a = np.clip(1 - d, 0, 1) ** 2.2 * 255 * strength
    arr = np.zeros((s, s, 4), np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = color
    arr[..., 3] = a.clip(0, 255).astype(np.uint8)
    return Image.fromarray(arr, 'RGBA')


def put(canvas, sprite, cx, cy, alpha=1.0, scale=1.0, rot=0.0):
    if alpha <= 0.01 or scale <= 0.01:
        return
    im = sprite
    if abs(scale - 1) > 0.003:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BICUBIC)
    if abs(rot) > 0.05:
        im = im.rotate(rot, resample=Image.BICUBIC, expand=True)
    if alpha < 0.999:
        im = im.copy()
        im.putalpha(im.getchannel('A').point(lambda v: int(v * alpha)))
    x, y = int(round(cx - im.width / 2)), int(round(cy - im.height / 2))
    sx0, sy0 = max(0, -x), max(0, -y)
    sx1, sy1 = min(im.width, W - x), min(im.height, H - y)
    if sx1 <= sx0 or sy1 <= sy0:
        return
    if (sx0, sy0, sx1, sy1) != (0, 0, im.width, im.height):
        im = im.crop((sx0, sy0, sx1, sy1))
    canvas.alpha_composite(im, (x + sx0, y + sy0))


def text_sprite(txt, fnt, color, tracking=0):
    if tracking:
        widths = [fnt.getlength(ch) for ch in txt]
        w = int(sum(widths) + tracking * (len(txt) - 1)) + 8
    else:
        w = int(fnt.getlength(txt)) + 8
    asc, desc = fnt.getmetrics()
    im = Image.new('RGBA', (w, asc + desc + 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if tracking:
        x = 4
        for ch, cw in zip(txt, widths):
            d.text((x, 4 + asc), ch, font=fnt, fill=color, anchor='ls')
            x += cw + tracking
    else:
        d.text((4, 4 + asc), txt, font=fnt, fill=color, anchor='ls')
    return im


def polyline(draw, pts, color, width, k=1):
    draw.line([(x * k, y * k) for x, y in pts], fill=color, width=int(width * k), joint='curve')


def catmull(points, n=12, closed=False):
    P = list(points)
    if closed:
        P = [P[-1]] + P + [P[0], P[1]]
    else:
        P = [P[0]] + P + [P[-1]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = map(np.array, (P[i - 1], P[i], P[i + 1], P[i + 2]))
        for t in np.linspace(0, 1, n, endpoint=False):
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)))
    out.append(tuple(P[-2]))
    return out


# ------------------------------------------------------------------ animated primitives
class Wisp:
    """A drifting scent ribbon."""

    def __init__(self, origin, direction, length, amp, freq, speed, phase, width, color, alpha=0.8):
        self.o = np.array(origin, float)
        d = np.array(direction, float)
        self.d = d / np.linalg.norm(d)
        self.p = np.array([-self.d[1], self.d[0]])
        self.L, self.A, self.f, self.v, self.ph, self.w, self.c, self.a = length, amp, freq, speed, phase, width, color, alpha

    def points(self, t, grow=1.0, n=60):
        s = np.linspace(0, 1, n) * grow
        off = self.A * np.sin(2 * np.pi * (s * self.f - t * self.v) + self.ph) * (0.25 + s)
        return [tuple(self.o + self.d * si * self.L + self.p * oi) for si, oi in zip(s, off)], s

    def draw(self, img, t, grow=1.0, alpha=1.0):
        pts, s = self.points(t, grow)
        d = ImageDraw.Draw(img)
        n = len(pts)
        for i in range(n - 1):
            fade = math.sin(math.pi * (i / (n - 1))) ** 0.8
            a = int(255 * self.a * alpha * fade)
            if a <= 2:
                continue
            d.line([pts[i], pts[i + 1]], fill=self.c + (a,), width=max(1, int(self.w * (0.6 + 0.6 * fade))))


class Particles:
    def __init__(self, n, box, seed, color=CREAM, size=(2, 5), drift=(0, -12), alpha=0.6):
        rng = np.random.default_rng(seed)
        x0, y0, x1, y1 = box
        self.p = np.column_stack([rng.uniform(x0, x1, n), rng.uniform(y0, y1, n)])
        self.v = np.column_stack([rng.normal(drift[0], 6, n), rng.normal(drift[1], 5, n)])
        self.s = rng.uniform(*size, n)
        self.ph = rng.uniform(0, 6.28, n)
        self.box, self.c, self.a = box, color, alpha
        self.sprites = {}

    def draw(self, img, t, alpha=1.0):
        x0, y0, x1, y1 = self.box
        for (px, py), (vx, vy), s, ph in zip(self.p, self.v, self.s, self.ph):
            x = x0 + (px - x0 + vx * t) % (x1 - x0)
            y = y0 + (py - y0 + vy * t) % (y1 - y0)
            a = self.a * alpha * (0.5 + 0.5 * math.sin(t * 1.7 + ph))
            k = int(round(s))
            if k not in self.sprites:
                self.sprites[k] = glow_sprite(k * 2.2, self.c)
            put(img, self.sprites[k], x, y, a)


def draw_path_partial(img, pts, frac, color, width, alpha=1.0, dash=None):
    if frac <= 0:
        return
    n = max(2, int(len(pts) * clamp(frac)))
    d = ImageDraw.Draw(img)
    seg = pts[:n]
    if dash:
        on, off = dash
        acc = 0
        for i in range(len(seg) - 1):
            a, b = np.array(seg[i]), np.array(seg[i + 1])
            l = np.linalg.norm(b - a)
            if (acc % (on + off)) < on:
                d.line([tuple(a), tuple(b)], fill=color + (int(255 * alpha),), width=width)
            acc += l
    else:
        d.line(seg, fill=color + (int(255 * alpha),), width=width, joint='curve')
    return seg[-1]


_fadecache = {}


def smoke(img, w, top=None, bot=None, soft=9):
    """Composite a wisp layer as soft smoke: wide blurred body + faint core, optional vertical fade-in from `top` to `bot`."""
    if top is not None:
        k = (top, bot)
        if k not in _fadecache:
            _fadecache[k] = Image.fromarray((vgrad(top, bot) * 255).astype(np.uint8), 'L')
        from PIL import ImageChops
        w.putalpha(ImageChops.multiply(w.getchannel('A'), _fadecache[k]))
    img.alpha_composite(w.filter(ImageFilter.GaussianBlur(soft)))
    core = w.filter(ImageFilter.GaussianBlur(1.6))
    core.putalpha(core.getchannel('A').point(lambda v: int(v * 0.55)))
    img.alpha_composite(core)
