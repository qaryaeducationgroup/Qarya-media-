"""Narration: Kokoro TTS per line -> assembled 48 kHz voice track -> Parakeet word timings.

Writes <build>/voice_raw.wav and <build>/timeline.json
"""
import os, json, re, wave, hashlib, subprocess
import numpy as np
from scipy.signal import resample_poly
from config import SHERPA, KOKORO, PARAKEET, VOICE_SID, VOICE_SPEED, sherpa_env
import audio_io as aio

SR = 48000
LEAD_IN = 0.30
SAY = {r'\bQarya\b': 'Karya', r'\bQEG\b': 'Q E G'}   # pronunciation fixes for the TTS only


def tts_text(t):
    for k, v in SAY.items():
        t = re.sub(k, v, t)
    return t


def synth(text, path, sid=VOICE_SID, speed=VOICE_SPEED):
    K = KOKORO
    cmd = [os.path.join(SHERPA, 'bin', 'sherpa-onnx-offline-tts'),
           f'--kokoro-model={K}/model.onnx', f'--kokoro-voices={K}/voices.bin', f'--kokoro-tokens={K}/tokens.txt',
           f'--kokoro-data-dir={K}/espeak-ng-data', f'--kokoro-dict-dir={K}/dict', f'--kokoro-lexicon={K}/lexicon-us-en.txt',
           f'--sid={sid}', f'--kokoro-length-scale={speed}', '--num-threads=2', f'--output-filename={path}', tts_text(text)]
    r = subprocess.run(cmd, capture_output=True, text=True, env=sherpa_env())
    if r.returncode or not os.path.exists(path):
        raise RuntimeError('TTS failed: ' + r.stderr[-800:])


def read_wav(p):
    w = wave.open(p)
    x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    return x, w.getframerate()


def asr_words(files):
    """Run Parakeet on several short wav files (16 kHz mono). Returns list of word lists (times relative to each file)."""
    M = PARAKEET
    cmd = [os.path.join(SHERPA, 'bin', 'sherpa-onnx-offline'), f'--encoder={M}/encoder.int8.onnx', f'--decoder={M}/decoder.int8.onnx',
           f'--joiner={M}/joiner.int8.onnx', f'--tokens={M}/tokens.txt', '--model-type=nemo_transducer', '--num-threads=2'] + files
    r = subprocess.run(cmd, capture_output=True, text=True, env=sherpa_env())
    res = [l for l in (r.stdout + r.stderr).splitlines() if l.startswith('{')]
    if len(res) != len(files):
        raise RuntimeError(f'ASR returned {len(res)} results for {len(files)} files')
    out = []
    for l in res:
        d = json.loads(l)
        ws = []
        for t, s, dd in zip(d['tokens'], d['timestamps'], d['durations']):
            if t.startswith(' ') or not ws:
                ws.append({'w': t.strip(), 's': s, 'e': s + dd})
            else:
                ws[-1]['w'] += t
                ws[-1]['e'] = max(ws[-1]['e'], s + dd)
        out.append(ws)
    return out


def lines_of(spec):
    L = []
    for si, sc in enumerate(spec['scenes']):
        for ln in sc.get('lines', []):
            tts, cap = ln[0], ln[1]
            pause = ln[2] if len(ln) > 2 else 0.4
            L.append({'scene': si, 'tts': tts, 'cap': cap, 'pause': pause})
    return L


def build(spec, bdir):
    os.makedirs(os.path.join(bdir, 'tts'), exist_ok=True)
    v = spec.get('voice', {})
    sid, speed = v.get('sid', VOICE_SID), v.get('speed', VOICE_SPEED)
    L = lines_of(spec)
    chunks = [np.zeros(int(LEAD_IN * SR), np.float32)]
    t = LEAD_IN
    asr_files = []
    for i, ln in enumerate(L):
        h = hashlib.md5(f"{tts_text(ln['tts'])}|{sid}|{speed}".encode()).hexdigest()[:12]
        p = os.path.join(bdir, 'tts', f'{h}.wav')
        if not os.path.exists(p):
            print(f'  tts {i:02d}: {ln["tts"]}', flush=True)
            synth(ln['tts'], p, sid, speed)
        x, sr = read_wav(p)
        y = resample_poly(x, SR // 1000, sr // 1000).astype(np.float32)
        env = np.convolve(np.abs(y), np.ones(480) / 480, 'same')
        idx = np.where(env > 10 ** (-48 / 20))[0]
        y = y[max(0, idx[0] - int(0.03 * SR)):min(len(y), idx[-1] + int(0.10 * SR))].copy()
        f = int(0.008 * SR)
        y[:f] *= np.linspace(0, 1, f)
        y[-f:] *= np.linspace(1, 0, f)
        ln['s'], ln['e'] = round(t, 3), round(t + len(y) / SR, 3)
        # 16 kHz copy for word timings
        a16 = os.path.join(bdir, 'tts', f'line{i:02d}_16k.wav')
        y16 = resample_poly(y, 1, 3).astype(np.float32)
        ww = wave.open(a16, 'w'); ww.setnchannels(1); ww.setsampwidth(2); ww.setframerate(16000)
        ww.writeframes((np.clip(y16, -1, 1) * 32767).astype(np.int16).tobytes()); ww.close()
        asr_files.append(a16)
        chunks += [y, np.zeros(int(ln['pause'] * SR), np.float32)]
        t += len(y) / SR + ln['pause']
    voice = np.concatenate(chunks)
    aio.write(os.path.join(bdir, 'voice_raw.wav'), voice, SR)
    print('  word timings ...', flush=True)
    words = asr_words(asr_files)
    for ln, ws in zip(L, words):
        ln['words'] = [{'w': w['w'], 's': round(ln['s'] + w['s'], 3), 'e': round(ln['s'] + w['e'], 3)} for w in ws]
        ln['heard'] = ' '.join(w['w'] for w in ws)
    dur = len(voice) / SR
    # scene windows: a scene starts a beat before its first line
    n = len(spec['scenes'])
    starts = []
    for si in range(n):
        first = [ln for ln in L if ln['scene'] == si]
        if si == 0:
            starts.append(0.0)
        elif first:
            starts.append(round(max(starts[-1] + 0.5, first[0]['s'] - spec.get('scene_lead', 0.32)), 3))
        else:
            starts.append(starts[-1] + spec['scenes'][si].get('dur', 2.0))
    tail = spec.get('tail', 0.6)
    total = max(dur + tail, starts[-1] + spec['scenes'][-1].get('min_dur', 3.0))
    scenes = [{'t0': starts[i], 't1': starts[i + 1] if i + 1 < n else total} for i in range(n)]
    tl = {'dur': round(total, 3), 'voice_dur': round(dur, 3), 'lines': L, 'scenes': scenes}
    json.dump(tl, open(os.path.join(bdir, 'timeline.json'), 'w'), indent=1)
    for ln in L:
        print(f"  {ln['s']:6.2f}-{ln['e']:6.2f} [s{ln['scene']}] {ln['tts']}")
    print(f'  voice {dur:.2f}s, video {total:.2f}s')
    return tl
