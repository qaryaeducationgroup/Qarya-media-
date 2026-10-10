"""Frame renderer: background, scenes with crossfades + camera, label, captions, watermark, grain."""
import math, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from engine import *
import scenes as S
from config import CREST

XF = 0.5   # crossfade seconds


def make_bg():
    g = radial(540, 900, 900, 1300)
    base = np.empty((H, W, 3), np.float32)
    for c in range(3):
        base[..., c] = BG0[c] + (BG1[c] - BG0[c]) * g ** 1.2
    base *= (1 + 0.12 * paper_noise())[..., None]
    rng = np.random.default_rng(2)
    fib = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(fib)
    for _ in range(900):
        x, y = rng.uniform(0, W), rng.uniform(0, H)
        a = rng.uniform(0, 6.28)
        l = rng.uniform(6, 26)
        d.line([(x, y), (x + l * math.cos(a), y + l * math.sin(a))], fill=int(rng.uniform(10, 40)), width=1)
    base += (np.asarray(fib, np.float32) / 255.0 * 18)[..., None]
    vig = radial(540, 960, 900, 1250)
    base *= (0.55 + 0.45 * np.clip(vig * 1.6, 0, 1))[..., None]
    return base


def label_sprite(txt):
    return text_sprite(txt, MONO(30), CREAM, 3)


def series_sprite(series='HOSPITALITY 101'):
    return text_sprite(series, MONO(22), GOLDHI, 6)


def caption_sprite(markup, fs=42, max_w=900):
    while True:
        rows = []
        for ln in markup.split('\n'):
            segs = []
            for k, p in enumerate(ln.split('*')):
                if p:
                    hl = k % 2 == 1
                    segs.append((p, SANSB(fs) if hl else SANS(fs), GOLDHI if hl else CREAM, hl))
            rows.append(segs)
        widths = [sum(f.getlength(p) for p, f, c, h in r) for r in rows]
        if max(widths) <= max_w or fs <= 30:
            break
        fs -= 2
    lh = int(fs * 1.38)
    padx, pady = 30, 18
    bw, bh = int(max(widths)) + 2 * padx, lh * len(rows) + 2 * pady - 6
    im = Image.new('RGBA', (bw + 8, bh + 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([4, 4, bw + 3, bh + 3], 12, fill=(10, 15, 28, 205), outline=CREAM + (46,), width=2)
    y = 4 + pady
    for r, wdt in zip(rows, widths):
        x = 4 + (bw - wdt) / 2
        for p, f, c, hl in r:
            d.text((x, y + fs), p, font=f, fill=c, anchor='ls')
            if hl:
                core = p.rstrip('.,?!:;')
                d.line([(x, y + fs + 8), (x + f.getlength(core), y + fs + 8)], fill=GOLDHI + (200,), width=2)
            x += f.getlength(p)
        y += lh
    return im


def watermark():
    c = Image.open(CREST).convert('RGBA')
    c = c.resize((92, int(c.height * 92 / c.width)), Image.LANCZOS)
    wm = Image.new('RGBA', (c.width + 24, c.height + 24), (0, 0, 0, 0))
    sh = Image.new('RGBA', wm.size, (0, 0, 0, 0))
    sh.paste(Image.new('RGBA', c.size, (0, 0, 0, 255)), (12, 15), c)
    wm.alpha_composite(sh.filter(ImageFilter.GaussianBlur(5)))
    wm.putalpha(wm.getchannel('A').point(lambda v: int(v * 0.35)))
    wm.alpha_composite(c, (12, 12))
    return wm


def cam(img, z, cx, cy):
    if abs(z - 1) < 0.002 and cx == 540 and cy == 960:
        return img
    w, h = W / z, H / z
    x0 = clamp(cx - w / 2, 0, W - w)
    y0 = clamp(cy - h / 2, 0, H - h)
    return img.transform((W, H), Image.EXTENT, (x0, y0, x0 + w, y0 + h), Image.BICUBIC)


class Renderer:
    def __init__(self, spec, tl):
        self.spec, self.tl = spec, tl
        self.DUR = tl['dur']
        self.NF = int(round(self.DUR * FPS))
        self.BG = make_bg()
        rng = np.random.default_rng(8)
        g = [rng.standard_normal((H // 2, W // 2)).astype(np.float32) for _ in range(10)]
        self.GRAIN = [np.asarray(Image.fromarray(((x * 40) + 128).clip(0, 255).astype(np.uint8)).resize((W, H), Image.BILINEAR), np.float32) - 128 for x in g]
        self.scenes = S.build_scenes(spec, tl)
        self.series = series_sprite(spec.get('series', 'HOSPITALITY 101'))
        self.labels = {id(sc): label_sprite(sc.label) for sc in self.scenes if sc.label}
        self.end_t = next((sc.t0 for sc in self.scenes if isinstance(sc, S.EndCard)), self.DUR + 10)
        self.caps = []
        L = tl['lines']
        for k, ln in enumerate(L):
            if not self.scenes[ln['scene']].captions:
                continue
            nxt = L[k + 1]['s'] if k + 1 < len(L) else 1e9
            self.caps.append((ln['s'] - 0.06, min(ln['e'] + 0.35, nxt - 0.08), caption_sprite(ln['cap'])))
        self.wm = watermark()

    def active(self, T):
        out = []
        sc = self.scenes
        for i, s in enumerate(sc):
            st = s.t0
            en = sc[i + 1].t0 if i + 1 < len(sc) else self.DUR + 1
            a = 1.0
            if i > 0:
                a = min(a, clamp((T - (st - XF / 2)) / XF))
            if i + 1 < len(sc):
                a = min(a, clamp(((en + XF / 2) - T) / XF))
            if a > 0:
                out.append((s, a))
        return out

    def ui(self, canvas, T):
        wa = 0.82 * (1 - eout((T - (self.end_t - 0.4)) / 0.4))
        if wa > 0.01:
            put(canvas, self.wm, 982, 452, wa)
        # series line stays put; the scene label hands over cleanly (old out, then new in)
        sa = eout(T / 0.6) * (1 - eout((T - (self.end_t - 0.4)) / 0.4))
        if sa > 0.01:
            put(canvas, self.series, 540, 437, sa)
        for i, sc in enumerate(self.scenes):
            lab = self.labels.get(id(sc))
            if lab is None:
                continue
            nxt = self.scenes[i + 1].t0 if i + 1 < len(self.scenes) else 1e9
            t = T - sc.t0
            a_in = eout((t - (0.05 if i else 0.15)) / 0.35)
            a_out = clamp((nxt - 0.02 - T) / 0.22)
            a = a_in * a_out
            if a > 0.01:
                put(canvas, lab, 540, 470 - 6 * (1 - eout(t / 0.5)), a)
        for s, e, sp in self.caps:
            if s <= T < e:
                u = eout((T - s) / 0.18)
                o = 1 - eout((T - (e - 0.15)) / 0.15)
                put(canvas, sp, 540, 1420 + 10 * (1 - u), u * o)

    def frame(self, i):
        T = i / FPS
        out = Image.fromarray(self.BG.clip(0, 255).astype(np.uint8), 'RGB').convert('RGBA')
        for sc, a in self.active(T):
            c = sc.frame(T)
            z, cx, cy = sc.camera(T)
            c = cam(c, z, cx, cy)
            if a < 0.999:
                c.putalpha(c.getchannel('A').point(lambda v: int(v * a)))
            out.alpha_composite(c)
        self.ui(out, T)
        arr = np.asarray(out.convert('RGB'), np.float32)
        arr += self.GRAIN[i % len(self.GRAIN)][..., None] * 0.20
        arr *= 1 + 0.012 * math.sin(T * 9.1) * math.sin(T * 3.7)
        arr *= min(1.0, T / 0.5) * min(1.0, (self.DUR - T) / 0.6)
        return arr.clip(0, 255).astype(np.uint8)

    def contact(self, times, path, cols=6):
        tiles = [Image.fromarray(self.frame(int(round(t * FPS)))).resize((360, 640), Image.LANCZOS) for t in times]
        cols = min(cols, len(tiles))
        rows = math.ceil(len(tiles) / cols)
        sheet = Image.new('RGB', (cols * 364, rows * 664), 'white')
        d = ImageDraw.Draw(sheet)
        for k, (im, t) in enumerate(zip(tiles, times)):
            x, y = (k % cols) * 364, (k // cols) * 664
            sheet.paste(im, (x, y + 22))
            d.text((x + 4, y + 4), f't={t:.2f}', fill='black')
        sheet.save(path, quality=88)

    def video(self, path, start=0, end=None, log_every=150):
        end = self.NF if end is None else end
        p = subprocess.Popen(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
                              '-r', str(FPS), '-i', 'pipe:0', '-vf', 'scale=out_color_matrix=bt709:out_range=tv,format=yuv420p',
                              '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '12', '-color_primaries', 'bt709',
                              '-color_trc', 'bt709', '-colorspace', 'bt709', path], stdin=subprocess.PIPE)
        for i in range(start, end):
            p.stdin.write(self.frame(i).tobytes())
            if i % log_every == 0:
                print('  frame', i, '/', end, flush=True)
        p.stdin.close()
        p.wait()
