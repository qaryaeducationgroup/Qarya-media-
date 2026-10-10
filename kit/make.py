#!/usr/bin/env python3
"""Build an explainer reel from a spec.

usage: python3 kit/make.py episodes/<id>/spec.json <step> [args]
steps:
  voice              TTS + word timings  -> build/timeline.json (re-run after any script change)
  preview [t,t,...]  contact sheet -> build/preview.jpg (default: 3 frames per scene)
  still <t>          one full-size frame -> build/still_<t>.png
  mix                music + sfx + master -> build/final_mix.wav
  video [--jobs N]   render frames -> build/video.mp4
  deliver            final mp4 + cover -> out/
  check              ASR / loudness / format gate on the final mp4
  all                voice, mix, video, deliver, check
"""
import os, sys, json, time, subprocess, multiprocessing as mp

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import FPS


def paths(spec_path):
    ep = os.path.dirname(os.path.abspath(spec_path))
    b, o = os.path.join(ep, 'build'), os.path.join(ep, 'out')
    os.makedirs(b, exist_ok=True)
    os.makedirs(o, exist_ok=True)
    return ep, b, o


def load(spec_path):
    spec = json.load(open(spec_path))
    ep, b, o = paths(spec_path)
    tlp = os.path.join(b, 'timeline.json')
    tl = json.load(open(tlp)) if os.path.exists(tlp) else None
    return spec, tl, ep, b, o


def _part(args):
    spec_path, start, end, out = args
    from render import Renderer
    spec, tl, *_ = load(spec_path)
    Renderer(spec, tl).video(out, start, end, log_every=300)
    return out


def video(spec_path, jobs=2):
    spec, tl, ep, b, o = load(spec_path)
    nf = int(round(tl['dur'] * FPS))
    cuts = [round(nf * k / jobs) for k in range(jobs + 1)]
    parts = [(spec_path, cuts[k], cuts[k + 1], os.path.join(b, f'part{k}.mp4')) for k in range(jobs)]
    t = time.time()
    with mp.get_context('fork').Pool(jobs) as pool:
        pool.map(_part, parts)
    lst = os.path.join(b, 'parts.txt')
    open(lst, 'w').write(''.join(f"file '{p[3]}'\n" for p in parts))
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy',
                    os.path.join(b, 'video.mp4')], check=True)
    print(f'  video: {nf} frames in {time.time() - t:.0f}s')


def slug(spec):
    import re
    return 'Qarya_' + re.sub(r'[^A-Za-z0-9]+', '_', spec['title']).strip('_')


def main():
    spec_path, step = sys.argv[1], sys.argv[2]
    spec, tl, ep, b, o = load(spec_path)
    if step in ('voice', 'all'):
        import voice
        tl = voice.build(spec, b)
    if step == 'preview':
        from render import Renderer
        R = Renderer(spec, tl)
        if len(sys.argv) > 3:
            ts = [float(x) for x in sys.argv[3].split(',')]
        else:
            ts = []
            for s in tl['scenes']:
                d = s['t1'] - s['t0']
                ts += [round(s['t0'] + 0.7, 2), round(s['t0'] + d * 0.55, 2), round(s['t1'] - 0.35, 2)]
        R.contact(ts, os.path.join(b, 'preview.jpg'))
        print('  ->', os.path.join(b, 'preview.jpg'))
    if step == 'still':
        from render import Renderer
        from PIL import Image
        t = float(sys.argv[3])
        p = os.path.join(b, f'still_{t:.2f}.png')
        Image.fromarray(Renderer(spec, tl).frame(int(round(t * FPS)))).save(p)
        print('  ->', p)
    if step in ('mix', 'all'):
        import mix
        mix.build(spec, tl, b)
    if step in ('video', 'all'):
        jobs = int(sys.argv[sys.argv.index('--jobs') + 1]) if '--jobs' in sys.argv else 2
        video(spec_path, jobs)
    if step in ('deliver', 'all'):
        from deliver import deliver
        from render import Renderer
        from PIL import Image
        dst = os.path.join(o, slug(spec) + '.mp4')
        deliver(os.path.join(b, 'video.mp4'), os.path.join(b, 'final_mix.wav'), dst)
        ct = spec.get('cover_t', round(tl['scenes'][0]['t1'] - 0.6, 2))
        Image.fromarray(Renderer(spec, tl).frame(int(round(ct * FPS)))).convert('RGB').save(os.path.join(o, slug(spec) + '_cover.jpg'), quality=92)
    if step in ('check', 'all'):
        from check import check
        ok = check(os.path.join(o, slug(spec) + '.mp4'), tl, b)
        sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
