import subprocess, numpy as np


def read(path, sr=48000):
    r = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', path, '-f', 'f32le', '-ac', '1', '-ar', str(sr), '-'],
                       capture_output=True, check=True)
    return np.frombuffer(r.stdout, np.float32).copy()


def write(path, arr, sr):
    arr = np.ascontiguousarray(arr, np.float32)
    ch = 1 if arr.ndim == 1 else arr.shape[1]
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'f32le', '-ar', str(sr), '-ac', str(ch), '-i', '-',
                    '-c:a', 'pcm_f32le', path], input=arr.tobytes(), check=True)
