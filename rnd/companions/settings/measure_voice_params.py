"""Measures which voice parameters really change the audio, per engine.

Run from the repository root on Windows:

    python rnd/companions/settings/measure_voice_params.py <out dir>

For one voice per engine it renders the same sentence through the client's own
bridge (uri_ui/assets/voice/voice_engine.ps1, verb "render") at the default
settings and at each extreme of rate, pitch and volume, then measures:

  * duration (s)            -> rate
  * median f0 (Hz)          -> pitch, by autocorrelation over voiced frames
  * active RMS (dBFS)       -> volume

A parameter is reported SUPPORTED only if both extremes move the measurement in
the expected direction by more than a threshold (duration 10 %, f0 5 %, level
3 dB). The Companion Settings page offers a parameter for an engine only when
this table says SUPPORTED. Writes voice_params.json and prints a markdown table.
"""
import json
import math
import os
import struct
import subprocess
import sys
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
BRIDGE = os.path.join(ROOT, 'uri_ui', 'assets', 'voice', 'voice_engine.ps1')
TEXT = ("The quick brown fox jumps over the lazy dog. "
        "URI is listening, thinking, and ready to help you today.")
VOICES = [('sapi', 'Microsoft Zira Desktop'), ('onecore', 'Microsoft Mark')]
VARIANTS = {
    'default': {},
    'rate-10': {'URI_VOICE_RATE': '-10'}, 'rate+10': {'URI_VOICE_RATE': '10'},
    'pitch-10': {'URI_VOICE_PITCH': '-10'}, 'pitch+10': {'URI_VOICE_PITCH': '10'},
    'volume30': {'URI_VOICE_VOLUME': '30'},
}


def render(engine, name, extra, path):
    env = dict(os.environ)
    env.update({'URI_VOICE_VERB': 'render', 'URI_VOICE_ENGINE': engine,
                'URI_VOICE_NAME': name, 'URI_VOICE_TEXT': TEXT, 'URI_VOICE_OUT': path})
    env.update(extra)
    subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', BRIDGE],
                   env=env, check=True, capture_output=True)


def read(path):
    with wave.open(path, 'rb') as w:
        ch, width, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if width != 2:
        raise ValueError(f'{path}: {width * 8}-bit audio')
    x = struct.unpack('<%dh' % (len(raw) // 2), raw)
    if ch > 1:
        x = x[::ch]
    return [v / 32768 for v in x], rate


def frames(x, rate, ms=30):
    n = int(rate * ms / 1000)
    return [x[i:i + n] for i in range(0, len(x) - n, n)]


def rms(f):
    return math.sqrt(sum(v * v for v in f) / len(f)) if f else 0.0


def f0(f, rate):
    lo, hi = int(rate / 400), int(rate / 60)
    m = sum(f) / len(f)
    g = [v - m for v in f]
    e = sum(v * v for v in g)
    if e <= 0:
        return None
    best, lag = 0.0, None
    for k in range(lo, min(hi, len(g) - 1)):
        c = sum(g[i] * g[i + k] for i in range(0, len(g) - k, 2)) * 2 / e
        if c > best:
            best, lag = c, k
    return rate / lag if lag and best > 0.5 else None


def measure(path):
    x, rate = read(path)
    fs = frames(x, rate)
    levels = [rms(f) for f in fs]
    peak = max(levels) if levels else 0
    active = [f for f, l in zip(fs, levels) if l > peak * 0.1]
    voiced = [p for p in (f0(f, rate) for f in active[::2]) if p]
    voiced.sort()
    act_rms = math.sqrt(sum(rms(f) ** 2 for f in active) / len(active)) if active else 0
    first = next((i for i, l in enumerate(levels) if l > peak * 0.1), 0)
    last = len(levels) - next((i for i, l in enumerate(reversed(levels)) if l > peak * 0.1), 0)
    return {
        'duration_s': round((last - first) * 0.03, 2),
        'f0_hz': round(voiced[len(voiced) // 2], 1) if voiced else None,
        'level_dbfs': round(20 * math.log10(act_rms), 1) if act_rms > 0 else None,
        'rate': rate,
    }


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    result = {}
    for engine, name in VOICES:
        m = {}
        for tag, extra in VARIANTS.items():
            path = os.path.join(out, f'{engine}_{tag}.wav')
            render(engine, name, extra, path)
            m[tag] = measure(path)
        d = m['default']
        verdict = {
            'rate': m['rate-10']['duration_s'] > d['duration_s'] * 1.10
            and m['rate+10']['duration_s'] < d['duration_s'] * 0.90,
            'pitch': bool(m['pitch-10']['f0_hz'] and m['pitch+10']['f0_hz'] and d['f0_hz'])
            and m['pitch-10']['f0_hz'] < d['f0_hz'] * 0.95 and m['pitch+10']['f0_hz'] > d['f0_hz'] * 1.05,
            'volume': m['volume30']['level_dbfs'] is not None and d['level_dbfs'] is not None
            and m['volume30']['level_dbfs'] < d['level_dbfs'] - 3,
        }
        result[engine] = {'voice': name, 'measurements': m, 'supported': verdict}
    with open(os.path.join(out, 'voice_params.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(result, f, indent=2)
    print('| engine | voice | variant | duration s | median f0 Hz | active level dBFS |')
    print('|---|---|---|---|---|---|')
    for engine, r in result.items():
        for tag, v in r['measurements'].items():
            print(f"| {engine} | {r['voice']} | {tag} | {v['duration_s']} | {v['f0_hz']} | {v['level_dbfs']} |")
    print()
    for engine, r in result.items():
        s = r['supported']
        print(f"{engine}: " + ', '.join(f"{k} {'SUPPORTED' if v else 'NOT SUPPORTED'}" for k, v in s.items()))


if __name__ == '__main__':
    main()
