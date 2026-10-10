"""Scene + element library for spec-driven explainer reels.

A scene is a list of elements on the 1080x1920 canvas. Every element takes an `at` (when it appears)
and optional `out` (when it leaves). Time references (see Ctx.at):
    1.2        seconds after the scene starts
    "L1"       start of the scene's 2nd narration line (0-based); "L1.end" = end of that line
    "water"    when the narrator says "water" in this scene; "water#2" = 2nd time
    "@end"     scene end ("@start" = scene start)
  any of these can take an offset: "water+0.3", "L2-0.2"
Layout guide (px): label at y 452 (top), art zone y 560-1330, captions centred at y 1420, keep x 90-990.
"""
import math, re
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from engine import *
import icons as IC
from config import LOGO_DARK

COLORS = {'cream': CREAM, 'gold': GOLD, 'goldhi': GOLDHI, 'rose': ROSE, 'teal': TEAL, 'sky': SKY,
          'navy': NAVYTXT, 'mauve': (196, 120, 160), 'grey': (150, 150, 160), 'dim': (120, 128, 150)}
FONTS = {'serif': SERIF, 'serif_i': SERIF_I, 'sans': SANS, 'sansb': SANSB, 'mono': MONO, 'monob': MONOB,
         'bold': lambda s: font('Poppins-Bold.ttf', s)}


def col(c, default=CREAM):
    if c is None:
        return default
    if isinstance(c, str):
        return COLORS[c]
    return tuple(c)


def norm(w):
    return re.sub(r'[^a-z0-9]', '', w.lower())


_ONES = 'zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split()
_TENS = 'zero ten twenty thirty forty fifty sixty seventy eighty ninety'.split()


def numwords(n):
    """Spoken words for an integer as the narrator would say it (years read in pairs)."""
    if n < 20:
        return [_ONES[n]]
    if n < 100:
        return [_TENS[n // 10]] + ([_ONES[n % 10]] if n % 10 else [])
    if 1100 <= n <= 1999 or 2010 <= n <= 2099:
        return numwords(n // 100) + (numwords(n % 100) if n % 100 >= 10 else ['oh'] + numwords(n % 100) if n % 100 else ['hundred'])
    if n < 1000:
        return [_ONES[n // 100], 'hundred'] + (numwords(n % 100) if n % 100 else [])
    if n < 1000000:
        return numwords(n // 1000) + ['thousand'] + (numwords(n % 1000) if n % 1000 else [])
    return [str(n)]


def expand_words(ws):
    """Split ASR digit tokens ('60', '1993', '22') into number words sharing the token's time span."""
    out = []
    for w in ws:
        core = re.sub(r'[^0-9]', '', w['w'])
        if core and core == re.sub(r'[^0-9a-z]', '', w['w'].lower()) and len(core) <= 6:
            parts = numwords(int(core))
            d = (w['e'] - w['s']) / len(parts)
            out += [{'w': p, 's': w['s'] + k * d, 'e': w['s'] + (k + 1) * d} for k, p in enumerate(parts)]
        else:
            out.append(w)
    return out


# ------------------------------------------------------------------ timing context
class Ctx:
    def __init__(self, tl, si):
        self.si = si
        self.t0, self.t1 = tl['scenes'][si]['t0'], tl['scenes'][si]['t1']
        self.lines = [ln for ln in tl['lines'] if ln['scene'] == si]
        self.words = expand_words([w for ln in self.lines for w in ln.get('words', [])])

    def at(self, ref, default=None):
        if ref is None:
            return self.t0 if default is None else default
        if isinstance(ref, (int, float)):
            return self.t0 + ref
        ref = str(ref).strip()
        m = re.match(r'^(.*?)([+-]\d+(?:\.\d+)?)$', ref)
        off = 0.0
        if m and m.group(1):
            ref, off = m.group(1), float(m.group(2))
        if ref == '@end':
            return self.t1 + off
        if ref == '@start':
            return self.t0 + off
        m = re.match(r'^L(\d+)(\.end)?$', ref)
        if m:
            ln = self.lines[int(m.group(1))]
            return (ln['e'] if m.group(2) else ln['s']) + off
        word, nth = (ref.split('#') + ['1'])[:2]
        nth = int(nth) - 1
        key = norm(word)
        hits = [w for w in self.words if norm(w['w']) == key]
        if len(hits) <= nth:
            hits = [w for w in self.words if len(key) >= 3 and (norm(w['w']).startswith(key) or key.startswith(norm(w['w'])) and len(norm(w['w'])) >= 3)]
        if len(hits) > nth:
            return hits[nth]['s'] + off
        # fallback: estimate from the script text position
        seen = 0
        for ln in self.lines:
            toks = re.split(r'[\s\-]+', ln['tts'])
            for k, tok in enumerate(toks):
                if norm(tok) == key or (len(key) >= 4 and norm(tok).startswith(key)):
                    if seen == nth:
                        est = ln['s'] + (ln['e'] - ln['s']) * k / max(1, len(toks))
                        print(f'  [timing] "{word}" not heard in scene {self.si}; estimated {est:.2f}s')
                        return est + off
                    seen += 1
        raise ValueError(f'scene {self.si}: cannot find word "{word}" in narration: ' + ' | '.join(l['tts'] for l in self.lines))


# ------------------------------------------------------------------ helpers
def rich_text(txt, size, fnt='serif', color=CREAM, hl=GOLDHI, max_w=920, lh=1.15, align='center', tracking=0, upper=False):
    """Multi-line text with *highlighted* words. Shrinks to fit max_w."""
    if upper:
        txt = txt.upper()
    ff = FONTS[fnt]
    while True:
        f = ff(size)
        rows = []
        for line in txt.split('\n'):
            parts = line.split('*')
            segs = [(p, k % 2 == 1) for k, p in enumerate(parts) if p]
            wdt = sum(f.getlength(p) + tracking * len(p) for p, _ in segs)
            rows.append((segs, wdt))
        mw = max(w for _, w in rows) if rows else 0
        if mw <= max_w or size <= 18:
            break
        size = int(size * 0.94)
    asc, desc = f.getmetrics()
    lhp = int(size * lh)
    im = Image.new('RGBA', (int(mw) + 24, lhp * (len(rows) - 1) + asc + desc + 24), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    y = 12 + asc
    for segs, wdt in rows:
        x = 12 + ((mw - wdt) / 2 if align == 'center' else (mw - wdt) if align == 'right' else 0)
        for p, h in segs:
            c = hl if h else color
            if tracking:
                for ch in p:
                    d.text((x, y), ch, font=f, fill=c, anchor='ls')
                    x += f.getlength(ch) + tracking
            else:
                d.text((x, y), p, font=f, fill=c, anchor='ls')
                x += f.getlength(p)
        y += lhp
    return im


def faded(im, a):
    if a >= 0.999:
        return im
    im = im.copy()
    im.putalpha(im.getchannel('A').point(lambda v: int(v * a)))
    return im


# ------------------------------------------------------------------ elements
class El:
    fade_in, fade_out = 0.35, 0.35

    def __init__(self, p, ctx):
        self.p, self.ctx = p, ctx
        self.t_in = ctx.at(p.get('at'), ctx.t0)
        self.t_out = ctx.at(p['out']) if 'out' in p else None

    def life(self, T):
        """(t since in, alpha in, alpha out)"""
        t = T - self.t_in
        ai = eout(t / self.fade_in) if t >= 0 else 0.0
        ao = 1.0
        if self.t_out is not None:
            ao = 1 - eout((T - self.t_out) / self.fade_out)
        return t, ai, ao

    def draw(self, img, T):
        pass


class Icon(El):
    def __init__(self, p, ctx):
        super().__init__(p, ctx)
        self.sprite = IC.icon(p['name'], int(p.get('size', 320)), p.get('style', 'ink'), col(p.get('ink'), CREAM))
        g = p.get('glow', True)
        self.glow = glow_sprite(int(p.get('size', 320) * 0.78), col(g if isinstance(g, str) else 'gold'), 0.20) if g else None
        self.ph = (hash(p['name']) % 100) / 15.0

    def draw(self, img, T):
        t, ai, ao = self.life(T)
        if ai <= 0 or ao <= 0:
            return
        p = self.p
        anim = p.get('anim', 'pop')
        x, y = p['x'], p['y']
        s = 1.0
        if anim == 'pop':
            s = 0.35 + 0.65 * eback(t / 0.55)
        elif anim == 'rise':
            y += 60 * (1 - eout(t / 0.6))
        elif anim == 'drop':
            y -= 140 * (1 - eback(t / 0.7, 1.2))
        if self.t_out is not None and T > self.t_out:
            s *= 1 - 0.25 * eout((T - self.t_out) / self.fade_out)
        fl = p.get('float', 8)
        y += fl * math.sin(T * 1.6 + self.ph)
        rot = p.get('rot', 0) + p.get('wobble', 2) * math.sin(T * 1.1 + self.ph)
        a = ai * ao
        if self.glow is not None:
            put(img, self.glow, x, y, a * 0.9)
        put(img, self.sprite, x, y, a, s, rot)


class Text(El):
    def __init__(self, p, ctx):
        super().__init__(p, ctx)
        self.sprite = rich_text(p['t'], int(p.get('size', 72)), p.get('font', 'serif'), col(p.get('color'), CREAM),
                                col(p.get('hl'), GOLDHI), p.get('max_w', 920), p.get('lh', 1.15), p.get('align', 'center'),
                                p.get('tracking', 0), p.get('upper', False))
        if p.get('box'):
            b = self.sprite
            padx, pady = p.get('padx', 34), p.get('pady', 14)
            box = Image.new('RGBA', (b.width + 2 * padx, b.height + 2 * pady), (0, 0, 0, 0))
            d = ImageDraw.Draw(box)
            fill = col(p.get('box_fill'), (10, 15, 28))
            d.rounded_rectangle([2, 2, box.width - 3, box.height - 3], p.get('radius', min(40, box.height // 2)),
                                fill=fill + (p.get('box_alpha', 215),), outline=col(p.get('box_line'), GOLD) + (190,), width=3)
            box.alpha_composite(b, (padx, pady))
            self.sprite = box

    def draw(self, img, T):
        t, ai, ao = self.life(T)
        if ai <= 0 or ao <= 0:
            return
        p = self.p
        x, y, s = p['x'], p['y'], 1.0
        anim = p.get('anim', 'rise')
        if anim == 'rise':
            y += 26 * (1 - eout(t / 0.5))
        elif anim == 'pop':
            s = 0.6 + 0.4 * eback(t / 0.45)
        put(img, self.sprite, x, y, ai * ao, s, p.get('rot', 0))


class Burst(El):
    def __init__(self, p, ctx):
        super().__init__(p, ctx)
        self.c = col(p.get('color'), GOLDHI)
        self.R = p.get('r', 230)
        self.n = p.get('n', 14)

    def draw(self, img, T):
        t = T - self.t_in
        if t < 0 or t > 0.9:
            return
        u = eout(t / 0.75)
        a = 1 - clamp((t - 0.25) / 0.6)
        lay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        x, y, R = self.p['x'], self.p['y'], self.R
        for i in range(self.n):
            ang = 2 * math.pi * i / self.n + 0.2
            r0, r1 = R * (0.45 + 0.4 * u), R * (0.62 + 0.5 * u)
            d.line([(x + r0 * math.cos(ang), y + r0 * math.sin(ang)), (x + r1 * math.cos(ang), y + r1 * math.sin(ang))],
                   fill=self.c + (int(230 * a),), width=6)
        rr = R * (0.3 + 0.9 * u)
        d.ellipse([x - rr, y - rr, x + rr, y + rr], outline=self.c + (int(120 * a),), width=3)
        img.alpha_composite(lay)


class Dust(El):
    KINDS = {'snow': (CREAM, (2, 5), (0, 46), 0.7), 'dust': (GOLD, (1.5, 3.5), (0, -12), 0.55),
             'sparkle': (GOLDHI, (2, 4.5), (0, -8), 0.75), 'bubbles': (SKY, (2, 5), (0, -30), 0.6)}

    def __init__(self, p, ctx):
        super().__init__(p, ctx)
        c, sz, dr, a = self.KINDS[p.get('kind', 'dust')]
        self.parts = Particles(p.get('n', 40), tuple(p.get('box', (90, 560, 990, 1330))), p.get('seed', 7), c, sz, dr, a)

    def draw(self, img, T):
        t, ai, ao = self.life(T)
        if ai > 0 and ao > 0:
            self.parts.draw(img, T, ai * ao)


class Panel(El):
    """Rounded card. x,y = centre; w,h size. hl_at: time it gets the gold highlight."""

    def __init__(self, p, ctx):
        super().__init__(p, ctx)
        w, h, r = p['w'], p['h'], p.get('radius', 30)
        self.hl_at = ctx.at(p['hl_at']) if 'hl_at' in p else None
        tone = p.get('tone', 'dark')
        self.base = Image.new('RGBA', (w + 40, h + 40), (0, 0, 0, 0))
        d = ImageDraw.Draw(self.base)
        if tone == 'cream':
            d.rounded_rectangle([20 + 8, 20 + 8, w + 20 + 8, h + 20 + 8], r, fill=GOLD + (140,))
            d.rounded_rectangle([20, 20, w + 20, h + 20], r, fill=CREAM + (255,))
        else:
            d.rounded_rectangle([20, 20, w + 20, h + 20], r, fill=(12, 18, 33, 225), outline=CREAM + (60,), width=3)
        self.hl = Image.new('RGBA', self.base.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(self.hl)
        hc = col(p.get('hl_color'), GOLDHI)
        d.rounded_rectangle([14, 14, w + 26, h + 26], r + 6, outline=hc + (255,), width=7)
        self.hl_glow = self.hl.filter(ImageFilter.GaussianBlur(10))

    def draw(self, img, T):
        t, ai, ao = self.life(T)
        if ai <= 0 or ao <= 0:
            return
        p = self.p
        s = 0.9 + 0.1 * eback(t / 0.5)
        y = p['y'] + 30 * (1 - eout(t / 0.5))
        dim = 1.0
        if self.p.get('dim_at') is not None and T > self.ctx.at(self.p['dim_at']):
            dim = 1 - 0.45 * eout((T - self.ctx.at(self.p['dim_at'])) / 0.5)
        put(img, self.base, p['x'], y, ai * ao * dim, s)
        if self.hl_at is not None and T > self.hl_at:
            u = eout((T - self.hl_at) / 0.4)
            put(img, self.hl_glow, p['x'], y, ai * ao * u, s * (1 + 0.02 * u))
            put(img, self.hl, p['x'], y, ai * ao * u, s * (1 + 0.02 * u))


class Dots(El):
    """Grid of n dots; `hl` of them light up from hl_at. Good for '22 of 32 people'."""

    def __init__(self, p, ctx):
        super().__init__(p, ctx)
        self.hl_at = ctx.at(p['hl_at']) if 'hl_at' in p else None
        r = p.get('r', 18)
        self.off = glow_sprite(r, col(p.get('color'), (120, 128, 150)), 1.0)
        dot = Image.new('RGBA', (r * 2 + 4, r * 2 + 4), (0, 0, 0, 0))
        ImageDraw.Draw(dot).ellipse([2, 2, r * 2 + 1, r * 2 + 1], fill=col(p.get('color'), (120, 128, 150)) + (255,))
        self.off = dot
        on = Image.new('RGBA', (r * 2 + 4, r * 2 + 4), (0, 0, 0, 0))
        ImageDraw.Draw(on).ellipse([2, 2, r * 2 + 1, r * 2 + 1], fill=col(p.get('hl_color'), GOLDHI) + (255,))
        self.on = on
        self.glow = glow_sprite(int(r * 2.2), col(p.get('hl_color'), GOLDHI), 0.35)
        n, cols, gap = p['n'], p.get('cols', 8), p.get('gap', 64)
        rows = math.ceil(n / cols)
        self.pos = [(p['x'] + (i % cols - (cols - 1) / 2) * gap, p['y'] + (i // cols - (rows - 1) / 2) * gap) for i in range(n)]
        rng = np.random.default_rng(p.get('seed', 4))
        order = list(range(n))
        if p.get('shuffle', True):
            rng.shuffle(order)
        self.lit = set(order[:p.get('hl', 0)])
        self.rank = {k: j for j, k in enumerate(order[:p.get('hl', 0)])}

    def draw(self, img, T):
        t, ai, ao = self.life(T)
        if ai <= 0 or ao <= 0:
            return
        n = len(self.pos)
        dur = self.p.get('hl_dur', 1.6)
        for i, (x, y) in enumerate(self.pos):
            u = eback((t - i * 0.02) / 0.35)
            if u <= 0:
                continue
            a = ai * ao
            if self.hl_at is not None and i in self.lit:
                k = self.rank[i]
                v = eout((T - self.hl_at - k * dur / max(1, len(self.lit))) / 0.25)
                if v > 0:
                    put(img, self.glow, x, y, a * v * 0.8)
                    put(img, self.on, x, y, a * v, 1 + 0.15 * v)
                    if v < 1:
                        put(img, self.off, x, y, a * (1 - v), u)
                    continue
            put(img, self.off, x, y, a * 0.9, u)


class Number(El):
    def __init__(self, p, ctx):
        super().__init__(p, ctx)
        self.f = FONTS[p.get('font', 'serif')](int(p.get('size', 220)))
        self.c = col(p.get('color'), GOLDHI)
        self.cache = {}

    def txt(self, v):
        p = self.p
        d = p.get('decimals', 0)
        s = f'{v:,.{d}f}' if p.get('comma', True) else f'{v:.{d}f}'
        return p.get('prefix', '') + s + p.get('suffix', '')

    def draw(self, img, T):
        t, ai, ao = self.life(T)
        if ai <= 0 or ao <= 0:
            return
        p = self.p
        v = p.get('from', 0) + (p['value'] - p.get('from', 0)) * ease(t / p.get('dur', 1.2))
        s = self.txt(v)
        if s not in self.cache:
            self.cache[s] = text_sprite(s, self.f, self.c)
        put(img, self.cache[s], p['x'], p['y'] + 20 * (1 - eout(t / 0.5)), ai * ao)


class Curve(El):
    """Line chart drawn left->right. pts: [[u,v],...] in 0..1 (v up). markers: [{u,label,color,at}]"""

    def __init__(self, p, ctx):
        super().__init__(p, ctx)
        x0, y0, x1, y1 = p.get('box', (150, 640, 930, 1180))
        self.box = (x0, y0, x1, y1)
        P = [(x0 + u * (x1 - x0), y1 - v * (y1 - y0)) for u, v in p['pts']]
        self.path = catmull(P, 16)
        self.c = col(p.get('color'), ROSE)
        self.dur = p.get('dur', 2.2)
        self.marks = []
        for m in p.get('markers', []):
            u = m['u']
            xm = x0 + u * (x1 - x0)
            k = min(range(len(self.path)), key=lambda i: abs(self.path[i][0] - xm))
            spr = rich_text(m['label'], m.get('size', 40), m.get('font', 'monob'), col(m.get('color'), GOLDHI), max_w=400)
            self.marks.append((ctx.at(m.get('at'), self.t_in + self.dur), self.path[k], col(m.get('color'), GOLDHI), spr, m.get('side', 'up')))
        self.axis = None
        if p.get('axes', True):
            ax = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(ax)
            d.line([(x0, y1 + 8), (x1 + 20, y1 + 8)], fill=CREAM + (150,), width=3)
            d.line([(x0 - 8, y0 - 20), (x0 - 8, y1 + 8)], fill=CREAM + (150,), width=3)
            d.polygon([(x1 + 34, y1 + 8), (x1 + 16, y1 - 2), (x1 + 16, y1 + 18)], fill=CREAM + (150,))
            if p.get('xlabel'):
                s = text_sprite(p['xlabel'], MONO(26), CREAM, 3)
                ax.alpha_composite(s, (int(x1 - s.width + 20), int(y1 + 22)))
            if p.get('ylabel'):
                s = text_sprite(p['ylabel'], MONO(26), CREAM, 3).rotate(90, expand=True)
                ax.alpha_composite(s, (int(x0 - 22 - s.width), int(y0)))
            self.axis = ax

    def draw(self, img, T):
        t, ai, ao = self.life(T)
        if ai <= 0 or ao <= 0:
            return
        a = ai * ao
        if self.axis is not None:
            img.alpha_composite(faded(self.axis, a * 0.9))
        frac = ease(t / self.dur)
        lay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        n = max(2, int(len(self.path) * frac))
        seg = self.path[:n]
        if self.p.get('fill', True) and n > 2:
            m = mask(lambda d, k: d.polygon([(x * k, y * k) for x, y in seg] + [(seg[-1][0] * k, (self.box[3] + 6) * k), (seg[0][0] * k, (self.box[3] + 6) * k)], fill=255))
            lay.alpha_composite(layer(halftone(m * 0.35, 9) * a, self.c, 0.1))
        d = ImageDraw.Draw(lay)
        d.line(seg, fill=self.c + (int(255 * a),), width=self.p.get('width', 8), joint='curve')
        hx, hy = seg[-1]
        if frac < 1:
            d.ellipse([hx - 10, hy - 10, hx + 10, hy + 10], fill=CREAM + (int(255 * a),))
        img.alpha_composite(lay)
        for (tm, (mx, my), c, spr, side) in self.marks:
            u = eout((T - tm) / 0.45)
            if u <= 0:
                continue
            ml = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(ml)
            r = 16 * eback((T - tm) / 0.45)
            d.ellipse([mx - r, my - r, mx + r, my + r], fill=c + (int(255 * a * u),), outline=(12, 18, 33, int(255 * a * u)), width=4)
            ly = my - 60 if side == 'up' else my + 60
            d.line([(mx, my - 22 if side == 'up' else my + 22), (mx, ly)], fill=c + (int(200 * a * u),), width=3)
            img.alpha_composite(ml)
            put(img, spr, mx, ly - spr.height / 2 - 4 if side == 'up' else ly + spr.height / 2 + 4, a * u)


class Arrow(El):
    def __init__(self, p, ctx):
        super().__init__(p, ctx)
        (xa, ya), (xb, yb) = p['from'], p['to']
        bend = p.get('bend', 0.0)
        mx, my = (xa + xb) / 2, (ya + yb) / 2
        nx, ny = -(yb - ya), (xb - xa)
        cx, cy = mx + nx * bend, my + ny * bend
        self.path = [((1 - s) ** 2 * xa + 2 * (1 - s) * s * cx + s * s * xb, (1 - s) ** 2 * ya + 2 * (1 - s) * s * cy + s * s * yb)
                     for s in np.linspace(0, 1, 60)]
        self.c = col(p.get('color'), GOLDHI)

    def draw(self, img, T):
        t, ai, ao = self.life(T)
        if ai <= 0 or ao <= 0:
            return
        frac = eout(t / self.p.get('dur', 0.6))
        lay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        end = draw_path_partial(lay, self.path, frac, self.c, self.p.get('width', 7), ai * ao,
                                dash=(18, 12) if self.p.get('dashed') else None)
        if frac > 0.95:
            n = len(self.path)
            (x1, y1), (x2, y2) = self.path[-6], self.path[-1]
            ang = math.atan2(y2 - y1, x2 - x1)
            L = 30
            pts = [(x2, y2), (x2 - L * math.cos(ang - 0.45), y2 - L * math.sin(ang - 0.45)),
                   (x2 - L * math.cos(ang + 0.45), y2 - L * math.sin(ang + 0.45))]
            ImageDraw.Draw(lay).polygon(pts, fill=self.c + (int(255 * ai * ao),))
        img.alpha_composite(lay)


class Check(El):
    def __init__(self, p, ctx):
        super().__init__(p, ctx)
        self.kind = p.get('kind', 'check')
        self.c = col(p.get('color'), GOLDHI if self.kind == 'check' else ROSE)

    def draw(self, img, T):
        t, ai, ao = self.life(T)
        if ai <= 0 or ao <= 0:
            return
        x, y, S = self.p['x'], self.p['y'], self.p.get('size', 120)
        lay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        r = S / 2 * eback(t / 0.4)
        d.ellipse([x - r, y - r, x + r, y + r], fill=self.c + (int(240 * ai * ao),))
        f = eout((t - 0.15) / 0.35)
        if f > 0:
            if self.kind == 'check':
                pts = [(x - S * 0.22, y + S * 0.0), (x - S * 0.05, y + S * 0.17), (x + S * 0.25, y - S * 0.16)]
                L1 = 0.4
                seg = [pts[0], (pts[0][0] + (pts[1][0] - pts[0][0]) * min(1, f / L1), pts[0][1] + (pts[1][1] - pts[0][1]) * min(1, f / L1))]
                if f > L1:
                    g = (f - L1) / (1 - L1)
                    seg.append((pts[1][0] + (pts[2][0] - pts[1][0]) * g, pts[1][1] + (pts[2][1] - pts[1][1]) * g))
                d.line(seg, fill=NAVYTXT + (255,), width=int(S * 0.1), joint='curve')
            else:
                k = S * 0.2 * f
                d.line([(x - k, y - k), (x + k, y + k)], fill=NAVYTXT + (255,), width=int(S * 0.1))
                d.line([(x - k, y + k), (x + k, y - k)], fill=NAVYTXT + (255,), width=int(S * 0.1))
        img.alpha_composite(lay)


class Bar(El):
    """Horizontal bar from x (left edge) growing to frac*w."""

    def draw(self, img, T):
        t, ai, ao = self.life(T)
        if ai <= 0 or ao <= 0:
            return
        p = self.p
        x, y, w, h = p['x'], p['y'], p['w'], p.get('h', 46)
        f = p['frac'] * ease(t / p.get('dur', 0.9))
        lay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        d.rounded_rectangle([x, y - h / 2, x + w, y + h / 2], h // 2, fill=(255, 255, 255, int(28 * ai * ao)))
        if f > 0.01:
            d.rounded_rectangle([x, y - h / 2, x + max(h, w * f), y + h / 2], h // 2, fill=col(p.get('color'), GOLDHI) + (int(255 * ai * ao),))
        img.alpha_composite(lay)


class Clock(El):
    def __init__(self, p, ctx):
        super().__init__(p, ctx)
        R = p.get('r', 230)
        self.face = Image.new('RGBA', (R * 2 + 40, R * 2 + 40), (0, 0, 0, 0))
        d = ImageDraw.Draw(self.face)
        c = R + 20
        d.ellipse([c - R - 8 + 10, c - R - 8 + 10, c + R + 8 + 10, c + R + 8 + 10], fill=GOLD + (130,))
        d.ellipse([c - R - 8, c - R - 8, c + R + 8, c + R + 8], fill=CREAM + (255,))
        for i in range(60):
            a = math.radians(i * 6)
            r0 = R - (34 if i % 5 == 0 else 16)
            d.line([(c + r0 * math.sin(a), c - r0 * math.cos(a)), (c + (R - 6) * math.sin(a), c - (R - 6) * math.cos(a))],
                   fill=NAVYTXT + (255 if i % 5 == 0 else 140,), width=6 if i % 5 == 0 else 2)
        self.R = R

        def mins(s):
            h, m = s.split(':')
            return int(h) * 60 + int(m)
        self.m0, self.m1 = mins(p.get('from', '11:00')), mins(p.get('to', '15:00'))

    def draw(self, img, T):
        t, ai, ao = self.life(T)
        if ai <= 0 or ao <= 0:
            return
        p = self.p
        x, y, R = p['x'], p['y'], self.R
        put(img, self.face, x, y, ai * ao, 0.8 + 0.2 * eback(t / 0.5))
        m = self.m0 + (self.m1 - self.m0) * ease((t - p.get('delay', 0.4)) / p.get('dur', 2.0))
        lay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        ah = math.radians((m / 60.0 % 12) * 30)
        am = math.radians((m % 60) * 6)
        a = int(255 * ai * ao)
        d.line([(x, y), (x + R * 0.5 * math.sin(ah), y - R * 0.5 * math.cos(ah))], fill=NAVYTXT + (a,), width=16)
        d.line([(x, y), (x + R * 0.78 * math.sin(am), y - R * 0.78 * math.cos(am))], fill=ROSE + (a,), width=9)
        d.ellipse([x - 16, y - 16, x + 16, y + 16], fill=NAVYTXT + (a,))
        img.alpha_composite(lay)


EL = {'icon': Icon, 'text': Text, 'burst': Burst, 'particles': Dust, 'panel': Panel, 'dots': Dots, 'number': Number,
      'curve': Curve, 'arrow': Arrow, 'check': Check, 'cross': Check, 'bar': Bar, 'clock': Clock}


def make(p, ctx):
    p = dict(p)
    if p['el'] == 'cross':
        p['kind'] = 'cross'
    return EL[p['el']](p, ctx)


# ------------------------------------------------------------------ scenes
class Scene:
    def __init__(self, p, ctx):
        self.p, self.ctx = p, ctx
        self.t0, self.t1 = ctx.t0, ctx.t1
        self.label = p.get('label')
        self.els = [make(e, ctx) for e in p.get('elements', [])]
        c = p.get('camera', {})
        self.push, self.cx, self.cy = c.get('push', 0.04), c.get('cx', 540), c.get('cy', 930)
        self.captions = p.get('captions', True)

    def frame(self, T):
        img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        for e in self.els:
            e.draw(img, T)
        return img

    def camera(self, T):
        t = (T - self.t0) / max(0.1, self.t1 - self.t0)
        return 1.0 + self.push * ease(t), self.cx, self.cy


class EndCard(Scene):
    def __init__(self, p, ctx):
        super().__init__(p, ctx)
        self.label = None
        self.captions = False
        self.ring = Image.new('RGBA', (700, 700), (0, 0, 0, 0))
        d = ImageDraw.Draw(self.ring)
        d.ellipse([20, 20, 680, 680], outline=GOLD + (120,), width=2)
        d.ellipse([60, 60, 640, 640], outline=GOLD + (60,), width=1)
        for i in range(72):
            a = math.radians(i * 5)
            r0, r1 = (300, 330) if i % 6 == 0 else (316, 330)
            d.line([(350 + r0 * math.cos(a), 350 + r0 * math.sin(a)), (350 + r1 * math.cos(a), 350 + r1 * math.sin(a))],
                   fill=GOLD + (150 if i % 6 == 0 else 80,), width=2)
        lg = Image.open(LOGO_DARK).convert('RGBA')
        self.logo = lg.resize((420, int(lg.height * 420 / lg.width)), Image.LANCZOS)
        self.motto = text_sprite(p.get('motto', 'Redefining Hospitality Literacy'), SERIF_I(46), CREAM)
        self.follow = text_sprite(p.get('cta', 'FOLLOW FOR MORE  ·  QARYA.MY'), MONO(24), GOLDHI, 4)
        self.parts = Particles(40, (100, 500, 980, 1400), 31, GOLDHI, (1.5, 3.5), (0, -10), 0.6)
        self.glow = glow_sprite(380, GOLD, 0.25)

    def frame(self, T):
        t = T - self.t0
        img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        cy = 830 - int(0.15 * self.logo.height)
        put(img, self.glow, 540, cy, eout(t / 1.0))
        put(img, self.ring, 540, cy, 0.8 * eout(t / 1.2), 0.60 + 0.04 * eout(t / 1.5), t * 4)
        self.parts.draw(img, t, eout(t / 1.0))
        put(img, self.logo, 540, 830, eout((t - 0.2) / 0.7), 0.95 + 0.05 * eout((t - 0.2) / 0.9))
        line = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        lw = 110 * eout((t - 0.7) / 0.6)
        ly = 830 + self.logo.height // 2 + 44
        ImageDraw.Draw(line).line([(540 - lw, ly), (540 + lw, ly)], fill=GOLD + (220,), width=2)
        img.alpha_composite(line)
        put(img, self.motto, 540, ly + 62, eout((t - 0.9) / 0.7))
        put(img, self.follow, 540, 1400, eout((t - 1.6) / 0.6))
        return img

    def camera(self, T):
        return 1.0, 540, 960


def build_scenes(spec, tl):
    out = []
    for si, sp in enumerate(spec['scenes']):
        ctx = Ctx(tl, si)
        out.append(EndCard(sp, ctx) if sp.get('type') == 'end' else Scene(sp, ctx))
    return out
