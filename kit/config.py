"""Paths and brand constants shared by every kit module."""
import os

KIT = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(KIT)
CACHE = os.environ.get('QKIT_CACHE', os.path.expanduser('~/.qkit'))

FONTS = os.path.join(KIT, 'fonts') + '/'
BRAND = os.path.join(REPO, 'brand') + '/'
LOGO_DARK = BRAND + 'qih_logo_reversed_for_dark.png'   # full logo for the end card
CREST = BRAND + 'qih_crest_transparent.png'            # watermark

SHERPA = os.path.join(CACHE, 'sherpa-onnx-v1.13.8-linux-x64-shared')
KOKORO = os.path.join(CACHE, 'kokoro-multi-lang-v1_0')
PARAKEET = os.path.join(CACHE, 'sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8')
EMOJI = os.path.join(CACHE, 'fluentui-emoji', 'assets')
ICON_CACHE = os.path.join(CACHE, 'icons')

VOICE_SID = 3          # Kokoro af_heart
VOICE_SPEED = 1.12     # --kokoro-length-scale (higher = slower)
LUFS = -14.0
TRUE_PEAK = -1.5
SEND_LIMIT_MIB = 28.3  # chat file limit is 30 MiB


def sherpa_env():
    e = dict(os.environ)
    e['LD_LIBRARY_PATH'] = os.path.join(SHERPA, 'lib') + ':' + e.get('LD_LIBRARY_PATH', '')
    return e
