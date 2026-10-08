"""Bounded post-wake CPU STT. Never executes commands or stores raw audio."""
from __future__ import annotations

import argparse
import json
import os
import time
import ctypes
from ctypes import wintypes
from pathlib import Path

import numpy as np
import sounddevice as sd


def peak_memory_bytes() -> int | None:
    """Measure the real interpreter, not Windows' small venv redirector."""
    if os.name != 'nt':
        return None
    class Counters(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in (
                'PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage',
                'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage',
                'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi = ctypes.WinDLL('psapi', use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE,
        ctypes.POINTER(Counters), wintypes.DWORD]
    if psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),
                                  ctypes.byref(counters), counters.cb):
        return counters.PeakWorkingSetSize
    return None


def ready(path: Path) -> bool:
    try:
        state = json.loads(path.read_text(encoding='utf-8-sig'))
        age = time.time() * 1000 - state['timestamp']
        return state['ready'] and not state['muted'] and 0 <= age < 6000
    except (OSError, ValueError, KeyError, TypeError):
        return False


def capture(control: Path, maximum: float, device=None) -> np.ndarray:
    blocks = []
    started = time.monotonic()
    heard = False
    quiet = 0
    # Signal energy determines the bounded capture window, never command intent.
    with sd.InputStream(samplerate=16000, channels=1, dtype='float32',
                        blocksize=3200, device=device) as stream:
        while time.monotonic() - started < maximum and ready(control):
            block, overflow = stream.read(3200)
            if overflow:
                raise RuntimeError('Microphone capture overflow')
            blocks.append(block[:, 0].copy())
            energy = float(np.sqrt(np.mean(block * block)))
            if energy >= 0.004:
                heard = True
                quiet = 0
            else:
                quiet += 1
            if heard and quiet >= 7:
                break
            if not heard and time.monotonic() - started > min(6, maximum):
                break
    if not heard or not ready(control):
        return np.array([], dtype=np.float32)
    return np.concatenate(blocks)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--timeout', type=float, default=15)
    parser.add_argument('--audio', type=Path)  # explicit test fixture only
    args = parser.parse_args()
    if not 5 <= args.timeout <= 60:
        raise ValueError('Invalid command timeout')
    control = args.directory / 'control.json'
    output = args.directory / 'transcript.json'
    selected = os.environ.get('URI_VOICE_MICROPHONE') or None
    if selected and selected.isdigit():
        selected = int(selected)
    audio = args.audio if args.audio else capture(control, args.timeout, selected)
    if not args.audio and not len(audio):
        result = {'text': '', 'audio_seconds': 0, 'stt_ms': 0}
    else:
        from faster_whisper import WhisperModel
        root = Path(os.environ['LOCALAPPDATA']) / 'URI/models/faster-whisper-base.en'
        start = time.monotonic()
        model = WhisperModel(str(root), device='cpu', compute_type='int8',
                             cpu_threads=4, num_workers=1, local_files_only=True)
        loaded = time.monotonic()
        segments, info = model.transcribe(audio, language='en', beam_size=3,
            vad_filter=True, condition_on_previous_text=False)
        text = ' '.join(segment.text.strip() for segment in segments).strip()
        result = {'text': text if args.audio or ready(control) else '',
            'audio_seconds': info.duration,
            'model_load_ms': round((loaded-start)*1000),
            'stt_ms': round((time.monotonic()-loaded)*1000)}
    result['peak_ram_bytes'] = peak_memory_bytes()
    temporary = args.directory / 'transcript.tmp'
    temporary.write_text(json.dumps(result), encoding='utf-8')
    temporary.replace(output)


if __name__ == '__main__':
    main()
