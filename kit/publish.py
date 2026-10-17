#!/usr/bin/env python3
"""Put finished videos on the `media` branch so Metricool can fetch them by public URL.

usage: python3 kit/publish.py episodes/<id>/out/<file>.mp4 [more files...]
prints: the raw.githubusercontent.com URL of each file

Metricool copies the media to its own storage when a post is created, so a file only has to be
on the media branch at scheduling time. The media branch only holds recent files. When it passes ~400 MB it is rebuilt as a fresh
single commit with only the files changed in the last 21 days (old posts are already on the networks).
"""
import os, sys, re, shutil, subprocess, time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WT = os.path.join(os.path.dirname(REPO), 'qarya-media-media')
BR = 'media'


def git(*a, cwd=REPO, check=True):
    r = subprocess.run(['git'] + list(a), cwd=cwd, capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError(f'git {" ".join(a)}: {r.stderr.strip()}')
    return r.stdout.strip()


def owner_repo():
    url = git('remote', 'get-url', 'origin')
    m = re.search(r'github\.com[:/]+([^/]+)/([^/.]+)', url)
    if not m:
        raise RuntimeError('cannot read owner/repo from origin: ' + url)
    return m.group(1), m.group(2)


def worktree():
    if os.path.isdir(WT):
        git('fetch', 'origin', BR, check=False)
        git('reset', '--hard', f'origin/{BR}', cwd=WT, check=False)
        return
    has = git('ls-remote', '--heads', 'origin', BR, check=False)
    if has:
        git('fetch', 'origin', f'{BR}:{BR}', check=False)
        git('worktree', 'add', WT, BR)
    else:
        git('worktree', 'add', '--detach', WT)
        git('checkout', '--orphan', BR, cwd=WT)
        git('rm', '-rf', '.', cwd=WT, check=False)
        open(os.path.join(WT, 'README.md'), 'w').write('Media files for scheduled posts. Rebuilt periodically; do not rely on history.\n')
        git('add', 'README.md', cwd=WT)
        git('commit', '-m', 'media branch', cwd=WT)


def size_mb():
    tot = 0
    for root, _, fs in os.walk(WT):
        if '.git' in root:
            continue
        tot += sum(os.path.getsize(os.path.join(root, f)) for f in fs)
    return tot / 1e6


def prune(days=21):
    keep = []
    now = time.time()
    for f in os.listdir(WT):
        p = os.path.join(WT, f)
        if f.startswith('.') or not os.path.isfile(p):
            continue
        if f == 'README.md' or now - os.path.getmtime(p) < days * 86400:
            keep.append(f)
    tmp = WT + '-keep'
    os.makedirs(tmp, exist_ok=True)
    for f in keep:
        shutil.copy2(os.path.join(WT, f), tmp)
    git('checkout', '--orphan', BR + '-new', cwd=WT)
    git('rm', '-rf', '.', cwd=WT, check=False)
    for f in keep:
        shutil.copy2(os.path.join(tmp, f), WT)
    git('add', '-A', cwd=WT)
    git('commit', '-m', f'media branch rebuilt {time.strftime("%Y-%m-%d")}', cwd=WT)
    git('branch', '-M', BR, cwd=WT)
    git('push', '-f', 'origin', BR, cwd=WT)
    shutil.rmtree(tmp)
    print(f'  pruned media branch, kept {len(keep)} files')


def main(files):
    worktree()
    for f in files:
        shutil.copy2(f, os.path.join(WT, os.path.basename(f)))
    git('add', '-A', cwd=WT)
    if git('status', '--porcelain', cwd=WT):
        git('commit', '-m', 'add ' + ', '.join(os.path.basename(f) for f in files), cwd=WT)
    git('push', 'origin', f'HEAD:{BR}', cwd=WT)
    if size_mb() > 400:
        prune()
    o, r = owner_repo()
    try:   # canonical capitalisation (e.g. Qarya-media-) for the public URL
        full = subprocess.run(['gh', 'api', f'repos/{o}/{r}', '--jq', '.full_name'], capture_output=True, text=True).stdout.strip()
        if '/' in full:
            o, r = full.split('/', 1)
    except Exception:
        pass
    for f in files:
        print(f'https://raw.githubusercontent.com/{o}/{r}/{BR}/{os.path.basename(f)}')


if __name__ == '__main__':
    main(sys.argv[1:])
