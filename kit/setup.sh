#!/usr/bin/env bash
# One-time setup for a fresh session. Idempotent: skips anything already present.
# Everything comes from github.com (the only reachable host besides package registries).
set -euo pipefail
CACHE="${QKIT_CACHE:-$HOME/.qkit}"
mkdir -p "$CACHE"
cd "$CACHE"
REL=https://github.com/k2-fsa/sherpa-onnx/releases/download

fetch() {  # url  dir-name
  if [ ! -d "$2" ]; then
    echo "fetching $2 ..."
    curl -sSL --retry 3 -o "$2.tar.bz2" "$1"
    tar xjf "$2.tar.bz2"
    rm -f "$2.tar.bz2"
  fi
}
fetch "$REL/v1.13.8/sherpa-onnx-v1.13.8-linux-x64-shared.tar.bz2" sherpa-onnx-v1.13.8-linux-x64-shared
fetch "$REL/tts-models/kokoro-multi-lang-v1_0.tar.bz2" kokoro-multi-lang-v1_0
fetch "$REL/asr-models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8.tar.bz2" sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8

if [ ! -d fluentui-emoji ]; then
  echo "fetching Fluent emoji (flat SVGs only) ..."
  git clone -q --depth 1 --filter=blob:none --sparse https://github.com/microsoft/fluentui-emoji.git fluentui-emoji
  (cd fluentui-emoji && git sparse-checkout set --no-cone '/assets/*/Flat/*' '/assets/*/Default/Flat/*' '/assets/*/metadata.json')
fi

# sanity checks
command -v ffmpeg >/dev/null || { echo "ffmpeg missing"; exit 1; }
DEC="$(ffmpeg -hide_banner -decoders 2>/dev/null || true)"
case "$DEC" in *librsvg*) ;; *) echo "WARNING: ffmpeg has no librsvg decoder; icons will fail";; esac
python3 -c "import numpy, scipy, cv2, PIL" || { echo "python deps missing (numpy scipy opencv pillow)"; exit 1; }
echo "qkit ready in $CACHE"
