"""Final encodes: a 2-pass H.264 file under the chat send limit, plus a cover image."""
import os, subprocess, tempfile
from config import SEND_LIMIT_MIB


def dur(p):
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p],
                                capture_output=True, text=True).stdout)


def deliver(video, audio, dst, target_mib=SEND_LIMIT_MIB, abr=256, preset='slow'):
    d = dur(video)
    total_k = target_mib * 1024 * 1024 * 8 / 1000 / d
    vk = int(min(14000, (total_k - abr) * 0.985))
    common = ['-c:v', 'libx264', '-preset', preset, '-profile:v', 'high', '-level', '4.2', '-pix_fmt', 'yuv420p',
              '-b:v', f'{vk}k', '-maxrate', f'{int(vk * 1.8)}k', '-bufsize', f'{int(vk * 3)}k',
              '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709']
    pl = os.path.join(tempfile.gettempdir(), 'qkit-2pass-' + os.path.basename(dst))
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', video] + common + ['-pass', '1', '-passlogfile', pl, '-an', '-f', 'null', '-'], check=True)
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', video, '-i', audio, '-map', '0:v', '-map', '1:a'] + common +
                   ['-pass', '2', '-passlogfile', pl, '-c:a', 'aac', '-b:a', f'{abr}k', '-ar', '48000', '-shortest', '-movflags', '+faststart', dst], check=True)
    print(f'  {os.path.basename(dst)}: {os.path.getsize(dst) / 1048576:.1f} MiB, video {vk} kbps, {d:.1f}s')
    return dst
