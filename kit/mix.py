"""Original synthesized music bed + SFX, ducked under the voice, mastered to -14 LUFS / -1.5 dBTP.

Writes <build>/music.wav, sfx.wav, final_mix.wav
"""
import os, json, re, subprocess
import numpy as np
from scipy.signal import fftconvolve, butter, sosfilt
import audio_io as aio
from config import LUFS
import scenes as S

SR = 48000
CHORDS = {'D': [50, 57, 62, 66, 69, 73, 76], 'Bm': [47, 54, 59, 62, 66, 69, 73], 'Em': [52, 59, 62, 66, 71, 74],
          'G': [43, 50, 55, 59, 62, 66, 69], 'A': [45, 52, 57, 61, 64, 69, 71], 'F#m': [42, 49, 54, 57, 61, 64, 69]}
PROG = ['D', 'Bm', 'Em', 'G', 'Bm', 'A', 'G', 'F#m', 'Em', 'A']


def hz(m):
    return 440 * 2 ** ((m - 69) / 12)


def loudness(path):
    r = subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-i', path, '-af', 'ebur128=peak=true', '-f', 'null', '-'],
                       capture_output=True, text=True).stderr
    s = r[r.rfind('Summary'):]
    I = float(re.search(r'I:\s+(-?[\d.]+) LUFS', s).group(1))
    tp = re.search(r'Peak:\s+(-?[\d.]+|-inf) dBFS', s)
    return I, float(tp.group(1)) if tp and tp.group(1) != '-inf' else -99.0


def build(spec, tl, bdir):
    DUR = tl['dur']
    N = int(DUR * SR)
    t = np.arange(N) / SR
    rng = np.random.default_rng(spec.get('seed', 11))
    sc = tl['scenes']
    # ---- chord plan: one chord per scene, a second one inside long scenes, end on D
    plan = []
    k = 0
    for i, s in enumerate(sc):
        if spec['scenes'][i].get('type') == 'end':
            plan.append(('D', s['t0']))
            continue
        plan.append((PROG[k % len(PROG)], s['t0']))
        k += 1
        if s['t1'] - s['t0'] > 7.5:
            plan.append((PROG[k % len(PROG)], (s['t0'] + s['t1']) / 2))
            k += 1
    pad = np.zeros((N, 2))
    for j, (name, st) in enumerate(plan):
        en = plan[j + 1][1] if j + 1 < len(plan) else DUR
        a, b = int(max(0, st - 1.2) * SR), min(N, int((en + 2.0) * SR))
        tt = np.arange(b - a) / SR
        L = len(tt)
        env = np.minimum(1, tt / 1.8) * np.minimum(1, np.maximum(0, (L / SR - tt)) / 2.0)
        for q, m in enumerate(CHORDS[name]):
            f, amp = hz(m), 0.05 / (1 + 0.25 * q)
            for h in range(1, 6):
                for det, pan in ((-0.0025, 0.35), (0.0025, 0.65)):
                    ph = rng.uniform(0, 6.28)
                    s_ = amp * (1 / h ** 1.7) * np.sin(2 * np.pi * f * h * (1 + det) * tt + ph) * (1 + 0.15 * np.sin(2 * np.pi * 0.11 * tt + q))
                    pad[a:b, 0] += s_ * env * (1 - pan) * 1.4
                    pad[a:b, 1] += s_ * env * pan * 1.4
    pad += (0.035 * (np.sin(2 * np.pi * hz(38) * t) + 0.3 * np.sin(2 * np.pi * hz(50) * t)) * np.minimum(1, t / 3) * np.minimum(1, (DUR - t) / 2.5))[:, None]
    pl = np.zeros((N, 2))
    tp = 0.9
    while tp < DUR - 2.5:
        name = [c for c, s_ in plan if s_ <= tp][-1]
        m = rng.choice(CHORDS[name][3:]) + 12
        n = int(2.2 * SR)
        tt = np.arange(n) / SR
        f = hz(m)
        s_ = (np.sin(2 * np.pi * f * tt) + 0.35 * np.sin(2 * np.pi * 2 * f * tt) * np.exp(-tt / 0.25) + 0.12 * np.sin(2 * np.pi * 4.2 * f * tt) * np.exp(-tt / 0.08)) * np.exp(-tt / 0.9) * (1 - np.exp(-tt / 0.004))
        i = int(tp * SR)
        m2 = min(n, N - i)
        pan = rng.uniform(0.3, 0.7)
        pl[i:i + m2, 0] += 0.035 * s_[:m2] * (1 - pan)
        pl[i:i + m2, 1] += 0.035 * s_[:m2] * pan
        tp += rng.choice([1.2, 1.6, 2.0, 2.4])
    mus = pad + pl
    air = sosfilt(butter(2, [2500, 7000], btype='band', fs=SR, output='sos'), rng.standard_normal((N, 2)), axis=0) * 0.004 * (1 + 0.5 * np.sin(2 * np.pi * 0.07 * t))[:, None]
    mus += air
    ir_n = int(3.2 * SR)
    it = np.arange(ir_n) / SR
    ir = rng.standard_normal((ir_n, 2)) * np.exp(-it / 0.75)[:, None]
    ir = sosfilt(butter(2, 5000, fs=SR, output='sos'), ir, axis=0)
    ir /= np.sqrt((ir ** 2).sum(0))
    wet = np.stack([fftconvolve(mus[:, c], ir[:, c])[:N] for c in range(2)], 1)
    mus = sosfilt(butter(2, 40, btype='high', fs=SR, output='sos'), 0.65 * mus + 0.55 * wet, axis=0)

    # ---- SFX
    sfx = np.zeros(N)

    def add(sig, at, g=1.0):
        i = int(at * SR)
        if i < 0:
            sig, i = sig[-i:], 0
        m = min(len(sig), N - i)
        if m > 0:
            sfx[i:i + m] += g * sig[:m]

    def whoosh(d=0.9):
        n = int(d * SR)
        x = rng.standard_normal(n)
        tt = np.arange(n) / SR
        out = np.zeros(n)
        for q in range(0, n, 2400):
            fc = 300 + 3200 * (q / n) ** 1.3
            out[q:q + 2400] = sosfilt(butter(2, [max(60, fc * 0.6), min(20000, fc * 1.4)], btype='band', fs=SR, output='sos'), x[q:q + 2400])
        out = np.convolve(out, np.ones(200) / 200, 'same')
        out /= np.abs(out).max()
        return out * np.sin(np.pi * np.clip(tt / d, 0, 1)) ** 2 * 10 ** (-24 / 20)

    def boom():
        tt = np.arange(int(2.0 * SR)) / SR
        return np.sin(2 * np.pi * (55 * np.exp(-tt / 0.6) + 38) * tt) * np.exp(-tt / 0.7) * (1 - np.exp(-tt / 0.01)) * 10 ** (-14 / 20)

    def shimmer():
        n = int(3.0 * SR)
        tt = np.arange(n) / SR
        s_ = np.zeros(n)
        for q, m in enumerate([86, 90, 93, 97, 98, 102]):
            d = int(q * 0.07 * SR)
            s_[d:] += np.sin(2 * np.pi * hz(m) * tt[:n - d]) * np.exp(-tt[:n - d] / 1.1) * (1 - np.exp(-tt[:n - d] / 0.01))
        return s_ / np.abs(s_).max() * 10 ** (-26 / 20)

    def pop(m=86):
        tt = np.arange(int(0.25 * SR)) / SR
        return (np.sin(2 * np.pi * hz(m) * tt) * np.exp(-tt / 0.05) + 0.4 * np.sin(2 * np.pi * hz(m + 12) * tt) * np.exp(-tt / 0.03)) * 10 ** (-30 / 20)

    def tick():
        tt = np.arange(int(0.05 * SR)) / SR
        return rng.standard_normal(len(tt)) * np.exp(-tt / 0.004) * 10 ** (-30 / 20)

    FX = {'whoosh': whoosh, 'boom': boom, 'shimmer': shimmer, 'pop': pop, 'tick': tick}
    for i, s in enumerate(sc):
        if i > 0:
            add(whoosh(), s['t0'] - 0.55)
        ctx = S.Ctx(tl, i)
        sp = spec['scenes'][i]
        if sp.get('type') == 'end':
            add(shimmer(), s['t0'] + 0.2)
        for cue in sp.get('sfx', []):
            add(FX[cue['type']](), ctx.at(cue.get('at')), cue.get('gain', 1.0))
        if sp.get('auto_pops', True):
            notes = [86, 88, 90, 93]
            for q, e in enumerate(sp.get('elements', [])):
                if e['el'] in ('icon', 'check', 'panel', 'cross'):
                    add(pop(notes[q % 4]), ctx.at(e.get('at'), ctx.t0) + 0.03)

    # ---- voice + ducking
    v = aio.read(os.path.join(bdir, 'voice_raw.wav'))
    v = np.pad(v, (0, max(0, N - len(v))))[:N]
    venv = np.convolve(np.abs(v), np.ones(2400) / 2400, 'same')
    act = (venv > 10 ** (-40 / 20)).astype(float)
    duck = np.convolve(act, np.ones(int(0.35 * SR)) / int(0.35 * SR), 'same')
    mus *= (1 - 0.45 * np.clip(duck, 0, 1))[:, None]
    aio.write(os.path.join(bdir, 'music.wav'), mus.astype(np.float32), SR)
    aio.write(os.path.join(bdir, 'sfx.wav'), sfx.astype(np.float32), SR)

    # ---- master: limited voice, bed ~15 LU under the voice, then loudness + peak control
    vp = os.path.join(bdir, 'voice_proc.wav')
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', os.path.join(bdir, 'voice_raw.wav'), '-af',
                    'highpass=f=70,alimiter=limit=0.70:level=disabled:attack=3:release=50', '-ar', str(SR), '-c:a', 'pcm_f32le', vp], check=True)
    vI, _ = loudness(vp)
    mI, _ = loudness(os.path.join(bdir, 'music.wav'))
    gm = 10 ** (((vI - spec.get('music_under', 15.0)) - mI) / 20)
    vv = aio.read(vp)
    vv = np.pad(vv, (0, max(0, N - len(vv))))[:N]
    mix = np.stack([vv, vv], 1) + mus * gm + (sfx * gm * 1.6)[:, None]
    pre = os.path.join(bdir, 'premix.wav')
    aio.write(pre, mix.astype(np.float32), SR)
    I, _ = loudness(pre)
    out = os.path.join(bdir, 'final_mix.wav')
    g = LUFS - I
    for _ in range(3):
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', pre, '-af',
                        f'volume={g:.2f}dB,alimiter=limit=0.80:level=disabled:attack=2:release=60', '-ar', str(SR), '-c:a', 'pcm_s24le', out], check=True)
        I2, tp2 = loudness(out)
        if abs(I2 - LUFS) < 0.4:
            break
        g += LUFS - I2
    print(f'  mix: {I2:.1f} LUFS, true peak {tp2:.1f} dBTP')
    return out
