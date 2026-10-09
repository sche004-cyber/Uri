"""URI voice service: microphone capture, speech recognition and reply speech.

Runs as a child process of the URI client (``python -I uri_voice_service.py``)
and talks to it with one JSON object per line: commands on stdin, events on
stdout. It owns the audio devices; the client only renders what it reports.

Rules this process enforces itself, whatever the client asks:

* Half duplex. The microphone is never open while URI's audio plays. Opening
  the microphone first stops any reply in progress (``speak.ended`` with reason
  ``interrupted``); a speak request while the microphone is open is refused.
* Push to talk. Capture starts only on ``listen_start`` and ends on
  ``listen_stop`` / ``listen_cancel`` or at the length bound. There is no
  always-on listening.
* Local only. Recognition is faster-whisper on the CPU (int8) with the model
  files pinned by ``URI_MODEL_MANIFEST.json``; nothing is downloaded and no
  network is used. Speech output uses the Windows engines through
  ``voice_engine.ps1 serve``. Audio stays in memory; rendered reply sentences
  are written to a private temporary directory and deleted after playback.
* Transcripts are data. This process never interprets what was said.

Commands (stdin):
  {"cmd": "hello"}                                   -> ready
  {"cmd": "devices"}                                 -> devices
  {"cmd": "listen_start", "id", "device"?, "max_s"?, "vocabulary"?} -> listen.started | listen.error
  {"cmd": "listen_stop", "id"}                       -> listen.closed, listen.final
  {"cmd": "listen_cancel", "id"}                     -> listen.closed (no transcript)
  {"cmd": "speak", "id", "text", "voice", "final"}   -> speak.started / level / progress / ended
  {"cmd": "speak_stop"}                              -> speak.ended (stopped)
  {"cmd": "shutdown"}
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import wave
from pathlib import Path

SR = 16000  # recogniser sample rate
BLOCK = 320  # 20 ms at 16 kHz
ENGINE_NAME = "faster-whisper-base.en-int8"
PARTIAL_EVERY_S = 0.7
PARTIAL_WINDOW_S = 15.0
DEFAULT_MAX_S = 60.0
UNCERTAIN_BELOW = 0.45
ONSET_MIN = 0.008
ONSET_MAX = 0.02
# Below this block level for the whole capture nothing audible was recorded;
# anything above goes to the recogniser, whose VAD filter decides what is speech.
SILENT_PEAK = 0.004
# The assistant's own name. Without the bias "URI" came back as "You are I",
# "Yuri" or "Fury" in 6 of 6 real-microphone trials; with it 4 of 6 were right
# and "You are right" stayed unchanged (docs/voice/live/evidence/name_bias).
HOTWORDS = "URI"
# A user vocabulary (names, places) adds to the bias. On the 45-recording set a
# vocabulary of its local names took format-normalised WER from 3.9 % to 1.0 %
# with no sentence worse (docs/voice/live/evidence/stt/vocab_probe.json; the
# vocabulary came from the test sentences, so the gain is optimistic).
VOCAB_MAX_CHARS = 400


def bias_words(vocabulary: str) -> str:
    """The assistant's name plus the user's words: letters, digits, spaces,
    hyphens and apostrophes only, bounded in length."""
    clean = re.sub(r"[^A-Za-z0-9' -]+", " ", vocabulary or "")
    clean = " ".join(clean.split())[:VOCAB_MAX_CHARS]
    return (HOTWORDS + " " + clean).strip()

_out_lock = threading.Lock()


def emit(ev: str, **data) -> None:
    line = json.dumps({"ev": ev, **data}, ensure_ascii=False)
    with _out_lock:
        sys.stdout.write(line + "\n")
        sys.stdout.flush()


def log(msg: str) -> None:
    with _out_lock:
        sys.stderr.write(msg + "\n")
        sys.stderr.flush()


# ---------------------------------------------------------------- privacy


def microphone_privacy() -> dict:
    """Reads the Windows microphone privacy switches (read-only).

    Returns {"state": "allowed" | "denied" | "unknown", "detail": str}. The
    device-wide switch (HKLM), the user switch (HKCU) and the desktop-app switch
    (HKCU ...\\NonPackaged) must all allow access. Changing them is the user's
    action in Windows Settings; this process never writes the registry.
    """
    if sys.platform != "win32":
        return {"state": "unknown", "detail": "not Windows"}
    import winreg

    base = r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone"
    checks = [
        (winreg.HKEY_LOCAL_MACHINE, base, "device"),
        (winreg.HKEY_CURRENT_USER, base, "user"),
        (winreg.HKEY_CURRENT_USER, base + r"\NonPackaged", "desktop apps"),
    ]
    seen = []
    for hive, key, label in checks:
        try:
            with winreg.OpenKey(hive, key) as k:
                value, _ = winreg.QueryValueEx(k, "Value")
        except OSError:
            continue
        seen.append(label)
        if str(value).lower() == "deny":
            return {"state": "denied", "detail": f"Windows blocks microphone access for {label}"}
    return {"state": "allowed" if seen else "unknown", "detail": ", ".join(seen) or "no privacy keys found"}


# ---------------------------------------------------------------- devices


def list_devices(sd) -> dict:
    """Input devices on the WASAPI host API (the one Windows mixes for), with
    MME as the fallback when WASAPI lists none."""
    apis = sd.query_hostapis()
    devs = sd.query_devices()

    def api_index(name):
        for i, a in enumerate(apis):
            if a["name"] == name:
                return i
        return None

    rows = []
    for api_name in ("Windows WASAPI", "MME"):
        ai = api_index(api_name)
        if ai is None:
            continue
        default_in = apis[ai].get("default_input_device", -1)
        for i, d in enumerate(devs):
            if d["hostapi"] == ai and d["max_input_channels"] > 0:
                rows.append({"name": d["name"], "index": i, "api": api_name, "default": i == default_in,
                             "samplerate": d["default_samplerate"]})
        if rows:
            break
    return {"inputs": rows}


def resolve_device(sd, name: str | None):
    rows = list_devices(sd)["inputs"]
    if not rows:
        return None, "MIC_NOT_FOUND", "No microphone is connected or enabled."
    if name:
        for r in rows:
            if r["name"] == name:
                return r, None, None
        # The chosen device is unplugged: use the Windows default and say so
        # (listen.warning MIC_FALLBACK), as the settings page tells the user.
        for r in rows:
            if r["default"]:
                return r, "MIC_FALLBACK", f"The selected microphone is not available ({name}); using {r['name']}."
        return rows[0], "MIC_FALLBACK", f"The selected microphone is not available ({name}); using {rows[0]['name']}."
    for r in rows:
        if r["default"]:
            return r, None, None
    return rows[0], None, None


# ---------------------------------------------------------------- recogniser


class Recogniser:
    """faster-whisper on the CPU. Loaded once in the background; every use is
    serialised by a lock (the partial and final passes never overlap)."""

    def __init__(self, model_dir: Path, threads: int):
        self.model_dir = model_dir
        self.threads = threads
        self.lock = threading.Lock()
        self.model = None
        self.error: tuple[str, str] | None = None
        self.load_ms = None
        self.ready = threading.Event()
        threading.Thread(target=self._load, name="model-load", daemon=True).start()

    def _verify(self) -> None:
        manifest = self.model_dir / "URI_MODEL_MANIFEST.json"
        if not manifest.is_file():
            raise FileNotFoundError(f"model manifest missing: {manifest}")
        files = json.loads(manifest.read_text(encoding="utf-8-sig"))["files"]
        for name, meta in files.items():
            p = self.model_dir / name
            if not p.is_file() or p.stat().st_size != meta["bytes"]:
                raise ValueError(f"model file missing or wrong size: {name}")
            h = hashlib.sha256()
            with p.open("rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            if h.hexdigest() != meta["sha256"]:
                raise ValueError(f"model file hash mismatch: {name}")

    def _load(self) -> None:
        t = time.perf_counter()
        try:
            if not self.model_dir.is_dir():
                self.error = ("MODEL_MISSING", f"Speech model not found at {self.model_dir}")
                return
            try:
                self._verify()
            except (OSError, ValueError, KeyError) as e:
                self.error = ("MODEL_INTEGRITY", f"Speech model failed its integrity check: {e}")
                return
            from faster_whisper import WhisperModel

            self.model = WhisperModel(str(self.model_dir), device="cpu", compute_type="int8",
                                      cpu_threads=self.threads)
            self.load_ms = round((time.perf_counter() - t) * 1000)
        except Exception as e:  # noqa: BLE001 - reported to the client
            self.error = ("RECOGNIZER_FAILED", f"Speech model could not be loaded: {e}")
        finally:
            self.ready.set()
            emit("model", **self.state())

    def state(self) -> dict:
        """loading / ready / failed, with the reason and the load time."""
        if not self.ready.is_set():
            return {"state": "loading"}
        if self.model is None:
            code, msg = self.error or ("RECOGNIZER_FAILED", "speech model unavailable")
            return {"state": "failed", "code": code, "message": msg}
        return {"state": "ready", "load_ms": self.load_ms}

    def transcribe(self, audio, final: bool, hotwords: str = ""):
        if not self.ready.wait(30):
            raise RuntimeError("speech model still loading")
        if self.model is None:
            raise RuntimeError(self.error[1] if self.error else "speech model unavailable")
        with self.lock:
            segments, info = self.model.transcribe(
                audio,
                language="en",
                beam_size=5 if final else 1,
                vad_filter=final,
                word_timestamps=final,
                condition_on_previous_text=False,
                without_timestamps=not final,
                hotwords=bias_words(hotwords),
            )
            segs = [seg for seg in segments if is_speech_segment(seg)]
        text = " ".join(s.text.strip() for s in segs).strip()
        words = []
        if final:
            for s in segs:
                for w in s.words or []:
                    words.append((w.word.strip(), float(w.probability)))
        return text, words, segs


# Noise guard. The recogniser writes text for room noise ("Yeah.", "Yes you know
# you're right.", "I know. I know. ...") even after its VAD filter, which kept up to
# 3 s of noise as speech. Measured on 36 room-noise clips and the 45 real-microphone
# speech recordings (docs/voice/live/evidence/stt/noise_guard_segments.json): every
# speech segment had no_speech_prob <= 0.223, avg_logprob >= -0.956 and compression
# <= 1.12; every noise segment had no_speech_prob >= 0.311 (the repetition loop also
# compression 27). A segment is speech only if all three hold. Dropping too much is
# the safe direction: the user is told nothing was heard and repeats.
MAX_NO_SPEECH_PROB = 0.3
MIN_AVG_LOGPROB = -1.2
MAX_COMPRESSION = 2.4


def is_speech_segment(seg) -> bool:
    return (seg.no_speech_prob < MAX_NO_SPEECH_PROB and seg.avg_logprob > MIN_AVG_LOGPROB
            and seg.compression_ratio < MAX_COMPRESSION)


def uncertain_spans(text: str, words) -> list[str]:
    """Low-probability words that occur verbatim in the text (contract: each
    span must occur in raw; at most 32 spans of at most 200 characters)."""
    out = []
    for w, p in words:
        core = w.strip(" .,!?;:\"'()")
        if p < UNCERTAIN_BELOW and core and core in text and core not in out:
            out.append(core[:200])
        if len(out) >= 32:
            break
    return out


# ---------------------------------------------------------------- capture


class Capture:
    def __init__(self, svc: "Service", cid: str, device: dict, max_s: float, vocabulary: str = ""):
        import numpy as np

        self.np = np
        self.svc = svc
        self.id = cid
        self.device = device
        self.max_s = max_s
        self.vocabulary = vocabulary
        self.blocks: list = []
        self.samples = 0
        self.closed = threading.Event()
        self.reason = None
        self.onset = False
        self._loud = 0
        self.floor = None
        self.peak_rms = 0.0
        self.nonzero = False
        self.started = time.perf_counter()
        self.stream = None
        self.partial_thread = threading.Thread(target=self._partials, name="partials", daemon=True)

    def open(self) -> None:
        sd = self.svc.sd
        extra = None
        if self.device["api"] == "Windows WASAPI":
            extra = sd.WasapiSettings(auto_convert=True)
        self.stream = sd.InputStream(device=self.device["index"], samplerate=SR, channels=1, dtype="float32",
                                     blocksize=BLOCK, callback=self._cb, extra_settings=extra)
        self.stream.start()
        self.partial_thread.start()

    def _cb(self, indata, frames, t, status):  # audio thread: keep it short
        if self.closed.is_set():
            return
        x = indata[:, 0].copy()
        self.blocks.append(x)
        self.samples += len(x)
        rms = float(self.np.sqrt(self.np.mean(x * x))) if len(x) else 0.0
        if rms > 0:
            self.nonzero = True
        self.peak_rms = max(self.peak_rms, rms)
        # Onset (for the waveform only): three loud blocks over an adaptive
        # floor, the quietest block of the first 200 ms. The threshold is
        # capped, so a user who starts talking at the press (the floor is then
        # speech) is still detected. The transcript never depends on onset.
        if self.samples <= SR * 0.2 and rms > 0:
            self.floor = rms if self.floor is None else min(self.floor, rms)
        thr = min(ONSET_MAX, max(ONSET_MIN, (self.floor or 0) * 4))
        self._loud = self._loud + 1 if rms > thr else 0
        if not self.onset and self._loud >= 3:
            self.onset = True
            emit("listen.speech", id=self.id)
        emit("listen.level", id=self.id, rms=round(rms, 5), block_ms=round(1000 * len(x) / SR, 1))
        if self.samples >= self.max_s * SR:
            threading.Thread(target=self.svc.listen_stop, args=(self.id, "max_length"), daemon=True).start()

    def audio(self):
        if not self.blocks:
            return self.np.zeros(0, dtype="float32")
        return self.np.concatenate(self.blocks)

    def _partials(self) -> None:
        last = 0
        warned = False
        while not self.closed.wait(PARTIAL_EVERY_S):
            if not warned and not self.nonzero and time.perf_counter() - self.started > 1.5:
                warned = True
                emit("listen.warning", id=self.id, code="MIC_SILENT",
                     message="The microphone is sending silence. It may be muted, or Windows may be blocking it.")
            if self.samples - last < SR * 0.3 or self.samples < SR * 0.6 or self.peak_rms < SILENT_PEAK:
                continue
            last = self.samples
            a = self.audio()[-int(PARTIAL_WINDOW_S * SR):]
            try:
                text, _, _ = self.svc.recogniser.transcribe(a, final=False, hotwords=self.vocabulary)
            except Exception:  # noqa: BLE001 - a failed partial is not fatal
                continue
            if text and not self.closed.is_set():
                emit("listen.partial", id=self.id, text=text)

    def close(self, reason: str) -> None:
        self.reason = reason
        self.closed.set()
        try:
            if self.stream is not None:
                self.stream.abort()
                self.stream.close()
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------- speech output


class Speaker:
    """Renders reply sentences with the Windows engines and plays them here, so
    the level the companion shows is the level of the audio actually played."""

    def __init__(self, svc: "Service", engine_script: Path):
        self.svc = svc
        self.engine_script = engine_script
        self.tmp = Path(tempfile.mkdtemp(prefix="uri_voice_"))
        self.ps = None
        self.ps_lock = threading.Lock()
        self.gen = 0
        self.lock = threading.Lock()
        self.render_q: queue.Queue = queue.Queue()
        self.play_q: queue.Queue = queue.Queue()
        self.stop_flag = threading.Event()
        self.current = None  # utterance id being played
        self.started_ids: set[str] = set()
        # Utterances whose sentence failed: their later sentences are dropped,
        # so nothing is heard after the utterance was reported ended.
        self.failed: set[str] = set()
        threading.Thread(target=self._render_loop, name="render", daemon=True).start()
        threading.Thread(target=self._play_loop, name="play", daemon=True).start()
        threading.Thread(target=self._ensure_ps, name="ps-warm", daemon=True).start()

    # -- engine bridge
    def _ensure_ps(self):
        with self.ps_lock:
            if self.ps is not None and self.ps.poll() is None:
                return self.ps
            env = {**os.environ, "URI_VOICE_VERB": "serve"}
            self.ps = subprocess.Popen(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
                 str(self.engine_script)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            return self.ps

    def _render(self, text: str, voice: dict, out: Path) -> None:
        ps = self._ensure_ps()
        req = {"engine": voice.get("engine") or "sapi", "name": voice.get("name") or "",
               "rate": voice.get("rate", 0), "pitch": voice.get("pitch", 0), "volume": voice.get("volume", 100),
               "text": text, "out": str(out)}
        with self.ps_lock:
            ps.stdin.write((json.dumps(req, ensure_ascii=False) + "\n").encode("utf-8"))
            ps.stdin.flush()
            line = ps.stdout.readline().decode("utf-8", "replace").strip()
        if not line:
            raise RuntimeError("speech engine bridge stopped")
        r = json.loads(line)
        if not r.get("ok"):
            raise RuntimeError(r.get("error") or "speech engine error")

    # -- requests
    def speak(self, uid: str, text: str, voice: dict, final: bool) -> None:
        if self.svc.capture is not None:
            emit("speak.ended", id=uid, reason="refused_listening")
            return
        with self.lock:
            self.stop_flag.clear()
            gen = self.gen
        self.render_q.put((gen, uid, text, voice, final))

    def stop(self, reason: str = "stopped") -> None:
        with self.lock:
            self.gen += 1
            self.stop_flag.set()
            cur = self.current
        # Drain anything waiting.
        for q in (self.render_q, self.play_q):
            try:
                while True:
                    item = q.get_nowait()
                    if q is self.play_q and item and item[3]:
                        _unlink(item[3])
            except queue.Empty:
                pass
        self.started_ids.clear()
        if cur is not None:
            emit("speak.ended", id=cur, reason=reason)
            with self.lock:
                if self.current == cur:
                    self.current = None

    def _render_loop(self):
        n = 0
        while True:
            gen, uid, text, voice, final = self.render_q.get()
            if gen != self.gen:
                continue
            if uid in self.failed:
                self.play_q.put((gen, uid, "", None, final, None, 0))
                continue
            clean = text.strip()
            path = None
            err = None
            if clean:
                n += 1
                path = self.tmp / f"r{n}.wav"
                t = time.perf_counter()
                try:
                    self._render(clean, voice, path)
                except Exception as e:  # noqa: BLE001
                    err = str(e)
                    _unlink(path)
                    path = None
                render_ms = round((time.perf_counter() - t) * 1000)
            else:
                render_ms = 0
            if gen != self.gen:
                _unlink(path)
                continue
            self.play_q.put((gen, uid, clean, path, final, err, render_ms))

    def _play_loop(self):
        import numpy as np

        sd = self.svc.sd
        while True:
            try:
                item = self.play_q.get(timeout=0.25)
            except queue.Empty:
                # An utterance is open but its next sentence is not ready yet
                # (rendering, or URI is still writing it). Report the silence
                # that is actually playing, so the client's watchdog does not
                # mistake the gap for a lost voice service.
                cur = self.current
                if cur is not None:
                    emit("speak.level", id=cur, rms=0.0, block_ms=20.0)
                continue
            gen, uid, text, path, final, err, render_ms = item
            if gen != self.gen:
                _unlink(path)
                continue
            if uid in self.failed:
                _unlink(path)
                if final:
                    self.failed.discard(uid)
                continue
            if err:
                emit("speak.error", id=uid, code="TTS_FAILED", message=err)
                emit("speak.ended", id=uid, reason="failed")
                self._finish(uid)
                if not final:
                    self.failed.add(uid)
                continue
            if path is not None:
                try:
                    with wave.open(str(path), "rb") as w:
                        sr, ch, sw = w.getframerate(), w.getnchannels(), w.getsampwidth()
                        raw = w.readframes(w.getnframes())
                    _unlink(path)
                    if sw != 2:
                        raise ValueError(f"unsupported sample width {sw}")
                    pcm = np.frombuffer(raw, dtype="<i2").astype("float32") / 32768.0
                    if ch > 1:
                        pcm = pcm.reshape(-1, ch).mean(axis=1)
                except Exception as e:  # noqa: BLE001
                    _unlink(path)
                    emit("speak.error", id=uid, code="TTS_FAILED", message=f"unreadable speech audio: {e}")
                    emit("speak.ended", id=uid, reason="failed")
                    self._finish(uid)
                    if not final:
                        self.failed.add(uid)
                    continue
                with self.lock:
                    if gen != self.gen:
                        continue
                    self.current = uid
                if uid not in self.started_ids:
                    self.started_ids.add(uid)
                    emit("speak.started", id=uid, text=text, render_ms=render_ms)
                else:
                    emit("speak.chunk", id=uid, text=text, render_ms=render_ms)
                ok = self._play(uid, gen, pcm, sr, np, sd)
                if not ok:
                    continue  # stopped: stop() already reported it
            if final and gen == self.gen:
                emit("speak.ended", id=uid, reason="completed")
                self._finish(uid)

    def _finish(self, uid):
        with self.lock:
            if self.current == uid:
                self.current = None
        self.started_ids.discard(uid)

    def _play(self, uid, gen, pcm, sr, np, sd) -> bool:
        block = max(1, int(sr * 0.02))
        pos = [0]
        done = threading.Event()
        levels: queue.Queue = queue.Queue()

        def cb(outdata, frames, t, status):
            if self.stop_flag.is_set() or gen != self.gen:
                outdata[:] = 0
                raise sd.CallbackAbort
            chunk = pcm[pos[0]:pos[0] + frames]
            n = len(chunk)
            outdata[:n, 0] = chunk
            if n < frames:
                outdata[n:] = 0
            pos[0] += n
            levels.put((float(np.sqrt(np.mean(chunk * chunk))) if n else 0.0, n))
            if n < frames:
                raise sd.CallbackStop

        try:
            stream = sd.OutputStream(samplerate=sr, channels=1, dtype="float32", blocksize=block, callback=cb,
                                     finished_callback=done.set)
        except Exception as e:  # noqa: BLE001
            emit("speak.error", id=uid, code="PLAYBACK_FAILED", message=f"cannot open the speakers: {e}")
            emit("speak.ended", id=uid, reason="failed")
            self._finish(uid)
            self.failed.add(uid)
            return False
        last_progress = 0.0
        with stream:
            while not done.is_set():
                try:
                    rms, n = levels.get(timeout=0.05)
                except queue.Empty:
                    continue
                if gen != self.gen:
                    break
                emit("speak.level", id=uid, rms=round(rms, 5), block_ms=round(1000 * n / sr, 1))
                now = time.perf_counter()
                if now - last_progress > 0.1:
                    last_progress = now
                    emit("speak.progress", id=uid, ms=round(1000 * pos[0] / sr))
        return gen == self.gen and not self.stop_flag.is_set()

    def close(self):
        self.stop("stopped")
        with self.ps_lock:
            if self.ps is not None and self.ps.poll() is None:
                try:
                    self.ps.stdin.write(b"\n")
                    self.ps.stdin.flush()
                    self.ps.wait(2)
                except Exception:  # noqa: BLE001
                    self.ps.kill()
        shutil.rmtree(self.tmp, ignore_errors=True)


def _unlink(p):
    if p is None:
        return
    try:
        Path(p).unlink()
    except OSError:
        pass


# ---------------------------------------------------------------- service


class Service:
    def __init__(self, args):
        import sounddevice as sd

        self.sd = sd
        self.args = args
        self.recogniser = Recogniser(Path(args.model_dir), args.threads)
        self.speaker = Speaker(self, Path(args.engine_script))
        self.capture: Capture | None = None
        self.cap_lock = threading.Lock()

    def hello(self):
        # Answers at once. The model may still be loading (measured 3.3 s alone,
        # over 20 s while a Brain loaded from the same disk); a `model` event
        # follows when it is ready or has failed. Capture works meanwhile; the
        # final pass waits for the model.
        m = self.recogniser.state()
        emit("ready", engine=ENGINE_NAME, model=m, model_ok=m["state"] == "ready",
             model_error={"code": m["code"], "message": m["message"]} if m["state"] == "failed" else None,
             model_load_ms=m.get("load_ms"), privacy=microphone_privacy(), pid=os.getpid(),
             **list_devices(self.sd))

    def listen_start(self, cid: str, device: str | None, max_s: float, vocabulary: str = ""):
        priv = microphone_privacy()
        if priv["state"] == "denied":
            emit("listen.error", id=cid, code="MIC_DENIED", message=priv["detail"])
            return
        if self.recogniser.ready.is_set() and self.recogniser.model is None:
            code, msg = self.recogniser.error or ("RECOGNIZER_FAILED", "speech model unavailable")
            emit("listen.error", id=cid, code=code, message=msg)
            return
        # Half duplex: URI stops talking before the microphone opens.
        self.speaker.stop("interrupted")
        with self.cap_lock:
            if self.capture is not None:
                old = self.capture
                self.capture = None
                old.close("cancelled")
                emit("listen.closed", id=old.id, reason="cancelled")
            dev, code, msg = resolve_device(self.sd, device)
            if dev is None:
                emit("listen.error", id=cid, code=code, message=msg)
                return
            if code == "MIC_FALLBACK":
                emit("listen.warning", id=cid, code=code, message=msg)
            cap = Capture(self, cid, dev, max_s, vocabulary)
            try:
                cap.open()
            except Exception as e:  # noqa: BLE001
                cap.close("failed")
                emit("listen.error", id=cid, code="MIC_OPEN_FAILED", message=f"The microphone could not be opened: {e}")
                return
            self.capture = cap
        emit("listen.started", id=cid, device=dev["name"], api=dev["api"])

    def listen_stop(self, cid: str, reason: str = "released"):
        with self.cap_lock:
            cap = self.capture
            if cap is None or cap.id != cid:
                return
            self.capture = None
            cap.close(reason)
        emit("listen.closed", id=cid, reason=reason)
        threading.Thread(target=self._final, args=(cap,), name="final", daemon=True).start()

    def listen_cancel(self, cid: str):
        with self.cap_lock:
            cap = self.capture
            if cap is None or cap.id != cid:
                return
            self.capture = None
            cap.close("cancelled")
        emit("listen.closed", id=cid, reason="cancelled")

    def _final(self, cap: Capture):
        cap.partial_thread.join(timeout=10)
        audio = cap.audio()
        audio_ms = round(1000 * len(audio) / SR)
        if cap.peak_rms < SILENT_PEAK or len(audio) < SR * 0.25:
            emit("listen.final", id=cap.id, text="", reason="no_speech", engine=ENGINE_NAME, audio_ms=audio_ms,
                 transcribe_ms=0, uncertain=[])
            return
        t = time.perf_counter()
        try:
            text, words, _ = self.recogniser.transcribe(audio, final=True, hotwords=cap.vocabulary)
        except Exception as e:  # noqa: BLE001
            emit("listen.error", id=cap.id, code="RECOGNIZER_FAILED", message=f"Recognition failed: {e}")
            return
        ms = round((time.perf_counter() - t) * 1000)
        # A transcript without a single letter or digit ("." or "...") is the
        # recogniser's output for noise, not speech (live run 3, 2026-10-09:
        # 1.5 s of room noise came back as ".").
        if not re.search(r"[A-Za-z0-9]", text):
            text = ""
        emit("listen.final", id=cap.id, text=text, reason="completed" if text else "no_speech", engine=ENGINE_NAME,
             audio_ms=audio_ms, transcribe_ms=ms, uncertain=uncertain_spans(text, words))

    def run(self):
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                c = json.loads(line)
                cmd = c.get("cmd")
                if cmd == "hello":
                    threading.Thread(target=self.hello, daemon=True).start()
                elif cmd == "devices":
                    emit("devices", privacy=microphone_privacy(), **list_devices(self.sd))
                elif cmd == "listen_start":
                    self.listen_start(str(c["id"]), c.get("device") or None,
                                      min(float(c.get("max_s") or DEFAULT_MAX_S), 120.0),
                                      str(c.get("vocabulary") or ""))
                elif cmd == "listen_stop":
                    self.listen_stop(str(c["id"]))
                elif cmd == "listen_cancel":
                    self.listen_cancel(str(c["id"]))
                elif cmd == "speak":
                    self.speaker.speak(str(c["id"]), str(c.get("text") or ""), dict(c.get("voice") or {}),
                                       bool(c.get("final", True)))
                elif cmd == "speak_stop":
                    self.speaker.stop("stopped")
                elif cmd == "shutdown":
                    break
                else:
                    emit("error", code="UNKNOWN_COMMAND", message=str(cmd))
            except Exception as e:  # noqa: BLE001
                emit("error", code="BAD_COMMAND", message=str(e))
                log(traceback.format_exc())
        self.close()

    def close(self):
        with self.cap_lock:
            if self.capture is not None:
                self.capture.close("cancelled")
                emit("listen.closed", id=self.capture.id, reason="cancelled")
                self.capture = None
        self.speaker.close()
        emit("bye")


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--model-dir", default=os.path.join(os.environ.get("LOCALAPPDATA", ""), "URI", "models",
                                                       "faster-whisper-base.en"))
    p.add_argument("--engine-script", default=str(Path(__file__).with_name("voice_engine.ps1")))
    p.add_argument("--threads", type=int, default=4)
    args = p.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")
    try:
        Service(args).run()
    except ImportError as e:
        emit("fatal", code="VOICE_RUNTIME_MISSING", message=f"Voice runtime is not installed: {e}")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
