"""Quality gate for a finished episode: re-transcribe the final audio and compare with the script,
check loudness, duration, size and format. Exit code 1 if anything fails."""
import os, re, sys, json, difflib, subprocess, wave
import numpy as np
from voice import asr_words
from mix import loudness
from scenes import numwords


def toks(s):
    out = []
    for w in re.sub(r'[^a-z0-9\' ]', ' ', s.lower().replace('-', ' ').replace(',', '')).split():
        w = w.strip("'")
        if w.isdigit() and len(w) <= 6:
            out += numwords(int(w))
        elif w:
            out.append(w)
    return out


def check(final_mp4, tl, bdir, max_mib=30.0):
    ok = True
    # split audio into the narration lines (timeline) so ASR stays accurate
    wav = os.path.join(bdir, 'check16k.wav')
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', final_mp4, '-ac', '1', '-ar', '16000', wav], check=True)
    w = wave.open(wav)
    x = np.frombuffer(w.readframes(w.getnframes()), np.int16)
    files = []
    for i, ln in enumerate(tl['lines']):
        a, b = int(max(0, ln['s'] - 0.1) * 16000), int((ln['e'] + 0.1) * 16000)
        p = os.path.join(bdir, f'check_{i:02d}.wav')
        ww = wave.open(p, 'w'); ww.setnchannels(1); ww.setsampwidth(2); ww.setframerate(16000)
        ww.writeframes(x[a:b].tobytes()); ww.close()
        files.append(p)
    heard = asr_words(files)
    bad = 0
    total = 0
    for ln, ws in zip(tl['lines'], heard):
        a, b = toks(ln['tts']), toks(' '.join(w['w'] for w in ws))
        sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
        miss = 0
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag != 'equal' and ''.join(a[i1:i2]) != ''.join(b[j1:j2]):   # 'peak end' vs 'peakend' is fine
                miss += max(i2 - i1, j2 - j1)
        total += len(a)
        bad += miss
        if miss / max(1, len(a)) > 0.25:
            print(f'  ASR mismatch: "{ln["tts"]}"  ->  "{" ".join(w["w"] for w in ws)}"')
    wer = bad / max(1, total)
    print(f'  word error vs script: {wer * 100:.1f}%')
    if wer > 0.12:
        ok = False
    I, tp = loudness(final_mp4)
    print(f'  loudness {I:.1f} LUFS, peak {tp:.1f} dBTP')
    if abs(I + 14) > 1.0 or tp > -0.5:
        ok = False
    info = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_name,width,height,r_frame_rate:format=duration,size',
                                      '-of', 'json', final_mp4], capture_output=True, text=True).stdout)
    v = [s for s in info['streams'] if s.get('width')][0]
    d = float(info['format']['duration'])
    mib = int(info['format']['size']) / 1048576
    print(f"  {v['codec_name']} {v['width']}x{v['height']} {v['r_frame_rate']}  {d:.1f}s  {mib:.1f} MiB")
    if (v['width'], v['height']) != (1080, 1920) or not (15 <= d <= 90) or mib > max_mib:
        ok = False
    print('  CHECK', 'PASSED' if ok else 'FAILED')
    return ok
