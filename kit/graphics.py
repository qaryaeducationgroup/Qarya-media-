#!/usr/bin/env python3
"""Render QEG graphics and carousels (1080x1440 PNG per slide) from a JSON spec with Playwright.

usage: python3 kit/graphics.py graphics/<QEG-####>.json [outdir]
spec: {"id": "QEG-0204", "footer": "...", "slides": [ {kind, kicker, head, body, bm, icon, icons, rows, cta, code} ... ]}
kinds: cover · statement · list · fees · cta.  *word* = gold.  Icons are Fluent emoji restyled by kit/icons.py.
"""
import os, sys, json, re, html, base64, io
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import FONTS, BRAND
import icons

W, H = 1080, 1440


def rich(t):
    t = html.escape(t)
    t = re.sub(r'\*(.+?)\*', r'<em>\1</em>', t)
    return t.replace('\n', '<br>')


def uri(path):
    return 'data:image/png;base64,' + base64.b64encode(open(path, 'rb').read()).decode()


_ic = {}
def icon_uri(name, size=300):
    k = (name, size)
    if k not in _ic:
        im = icons.icon(name, size)
        b = io.BytesIO(); im.save(b, 'PNG')
        _ic[k] = 'data:image/png;base64,' + base64.b64encode(b.getvalue()).decode()
    return _ic[k]


CSS = """
@font-face{font-family:QSerif;src:url(file://%(f)sDMSerifDisplay-Regular.ttf)}
@font-face{font-family:QSerifI;src:url(file://%(f)sDMSerifDisplay-Italic.ttf)}
@font-face{font-family:Pop;src:url(file://%(f)sPoppins-Medium.ttf);font-weight:500}
@font-face{font-family:Pop;src:url(file://%(f)sPoppins-SemiBold.ttf);font-weight:600}
@font-face{font-family:Pop;src:url(file://%(f)sPoppins-Bold.ttf);font-weight:700}
@font-face{font-family:Mono;src:url(file://%(f)sSpaceMono-Regular.ttf)}
@font-face{font-family:MonoB;src:url(file://%(f)sSpaceMono-Bold.ttf)}
*{margin:0;padding:0;box-sizing:border-box}
body{width:1080px;height:1440px;overflow:hidden;background:#0b101d}
.s{position:relative;width:1080px;height:1440px;overflow:hidden;color:#f0e4cc;font-family:Pop;
  background:radial-gradient(ellipse 900px 700px at 50% 38%,#1c2742 0%,#141c30 45%,#0b101d 100%)}
.ring{position:absolute;left:50%;top:520px;width:980px;height:980px;margin:-490px 0 0 -490px;border-radius:50%;
  border:2px solid rgba(212,172,88,.16)}
.ring2{position:absolute;left:50%;top:520px;width:860px;height:860px;margin:-430px 0 0 -430px;border-radius:50%;
  border:1px solid rgba(212,172,88,.10)}
.frame{position:absolute;inset:28px;border:2px solid rgba(212,172,88,.45);border-radius:6px}
.top{position:absolute;top:70px;left:80px;right:80px;display:flex;justify-content:space-between;align-items:center}
.top img{height:150px}
.num{font-family:Mono;font-size:26px;letter-spacing:4px;color:#d4ac58}
.main{position:absolute;top:210px;bottom:220px;left:90px;right:90px;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center}
.kicker{font-family:MonoB;font-size:30px;letter-spacing:7px;color:#f8cc64;margin-bottom:34px;text-transform:uppercase}
h1{font-family:QSerif;font-weight:400;font-size:92px;line-height:1.08;color:#f0e4cc}
h1.hm{font-size:80px} h1.hs{font-size:66px}
em{font-style:normal;color:#f8cc64}
.body{font-size:44px;line-height:1.38;color:#e6dcc6;margin-top:36px;font-weight:500}
.bm{font-family:QSerifI;font-size:40px;line-height:1.3;color:#d4ac58;margin-top:44px;padding-top:30px;border-top:2px solid rgba(212,172,88,.4)}
.ic{width:260px;height:260px;margin-bottom:40px;object-fit:contain}
.ics{display:flex;gap:40px;margin-bottom:40px}.ics img{width:190px;height:190px;object-fit:contain}
.rows{width:100%;margin-top:38px;display:flex;flex-direction:column;gap:22px}
.row{display:flex;align-items:center;gap:30px;background:rgba(240,228,204,.06);border:2px solid rgba(212,172,88,.35);border-radius:22px;padding:24px 34px;text-align:left}
.row img{width:110px;height:110px;flex:none}
.row .t{font-size:40px;line-height:1.3;font-weight:500}
.row .n{font-family:QSerif;font-size:64px;color:#f8cc64;flex:none;min-width:80px;text-align:center}
.fee{display:flex;justify-content:space-between;align-items:center;padding:22px 38px;border-radius:22px;background:rgba(240,228,204,.06);border:2px solid rgba(212,172,88,.35);text-align:left}
.fee .l{font-size:36px;line-height:1.25;font-weight:500;max-width:470px}
.fee .p{font-family:QSerif;font-size:68px;color:#f8cc64;white-space:nowrap}
.fee.hi{border-color:#f8cc64;background:rgba(248,204,100,.10)}
.wa{margin-top:44px;background:#d4ac58;color:#101626;border-radius:60px;padding:26px 50px;font-weight:700;font-size:46px}
.code{font-family:MonoB;font-size:34px;letter-spacing:5px;color:#f8cc64;margin-top:28px}
.answer{font-family:MonoB;font-size:34px;letter-spacing:3px;color:#101626;background:#f8cc64;border-radius:40px;padding:14px 34px;margin-bottom:46px}
.foot{position:absolute;left:28px;right:28px;bottom:28px;height:128px;border-top:2px solid rgba(212,172,88,.45);
  display:flex;align-items:center;justify-content:center;gap:26px;font-size:28px;font-weight:600;color:#f0e4cc;background:rgba(6,9,18,.55)}
.foot b{color:#f8cc64;font-weight:700}
.dot{color:#d4ac58}
.swipe{position:absolute;right:86px;bottom:190px;font-family:Mono;font-size:24px;letter-spacing:4px;color:#d4ac58}
"""


_css = None
def css():
    global _css
    if _css is None:
        _css = re.sub(r'url\(file://%\(f\)s([^)]+)\)', lambda m: "url(data:font/ttf;base64," + base64.b64encode(open(FONTS + m.group(1), 'rb').read()).decode() + ")", CSS)
    return _css


def slide_html(spec, i, sl, logo):
    n = len(spec['slides'])
    k = sl.get('kind', 'statement')
    parts = []
    if sl.get('answer'):
        parts.append(f'<div class="answer">{rich(sl["answer"])}</div>')
    if sl.get('icon'):
        parts.append(f'<img class="ic" src="{icon_uri(sl["icon"])}">')
    if sl.get('icons'):
        parts.append('<div class="ics">' + ''.join(f'<img src="{icon_uri(x, 220)}">' for x in sl['icons']) + '</div>')
    if sl.get('kicker'):
        parts.append(f'<div class="kicker">{rich(sl["kicker"])}</div>')
    if sl.get('head'):
        parts.append(f'<h1 class="h{sl.get("hsize", "")}">{rich(sl["head"])}</h1>')
    if sl.get('body'):
        parts.append(f'<div class="body">{rich(sl["body"])}</div>')
    if sl.get('rows'):
        rr = []
        for r in sl['rows']:
            lead = f'<img src="{icon_uri(r["icon"], 160)}">' if r.get('icon') else f'<div class="n">{rich(r.get("n", ""))}</div>'
            rr.append(f'<div class="row">{lead}<div class="t">{rich(r["t"])}</div></div>')
        parts.append('<div class="rows">' + ''.join(rr) + '</div>')
    if sl.get('fees'):
        ff = ''.join(f'<div class="fee{" hi" if f.get("hi") else ""}"><div class="l">{rich(f["l"])}</div><div class="p">{f["p"]}</div></div>' for f in sl['fees'])
        parts.append(f'<div class="rows">{ff}</div>')
    if sl.get('wa'):
        parts.append(f'<div class="wa">WhatsApp 019-862 6704</div><div class="code">TYPE {sl["wa"]}</div>')
    if sl.get('bm'):
        parts.append(f'<div class="bm">{rich(sl["bm"])}</div>')
    if sl.get('after'):
        parts.append(f'<div class="body">{rich(sl["after"])}</div>')
    num = f'{i + 1} / {n}' if n > 1 else spec.get('tag', '')
    swipe = '<div class="swipe">SWIPE →</div>' if (n > 1 and i == 0) else ''
    foot = spec.get('footer', '<b>WhatsApp 019-862 6704</b><span class="dot">·</span>Qarya@akademi-ai.my<span class="dot">·</span>qarya.my')
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>{css()}</style></head><body>
<div class="s"><div class="ring"></div><div class="ring2"></div><div class="frame"></div>
<div class="top"><img src="{logo}"><div class="num">{num}</div></div>
<div class="main">{''.join(parts)}</div>{swipe}<div class="foot">{foot}</div></div></body></html>'''


def render(spec_path, outdir=None):
    from playwright.sync_api import sync_playwright
    spec = json.load(open(spec_path))
    outdir = outdir or os.path.join(os.path.dirname(os.path.abspath(spec_path)), 'out')
    os.makedirs(outdir, exist_ok=True)
    logo = uri(BRAND + 'qih_logo_reversed_for_dark.png')
    out = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={'width': W, 'height': H}, device_scale_factor=1)
        for i, sl in enumerate(spec['slides']):
            pg.set_content(slide_html(spec, i, sl, logo))
            pg.wait_for_timeout(250)
            over = pg.evaluate('''() => { const m=document.querySelector('.main'); const r=m.getBoundingClientRect();
               let bad=[]; m.querySelectorAll('*').forEach(e=>{const q=e.getBoundingClientRect(); if(q.width&&(q.top<r.top-1||q.bottom>r.bottom+1||q.left<r.left-1||q.right>r.right+1)) bad.push(e.className||e.tagName)});
               return bad }''')
            if over:
                print(f'  ! slide {i + 1} overflow: {over}')
            name = f"{spec['id']}{spec.get('suffix', '')}-{i + 1}.png" if len(spec['slides']) > 1 else f"{spec['id']}{spec.get('suffix', '')}.png"
            f = os.path.join(outdir, name)
            pg.screenshot(path=f, clip={'x': 0, 'y': 0, 'width': W, 'height': H})
            out.append(f)
        b.close()
    for f in out:
        print(f)
    return out


if __name__ == '__main__':
    render(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
