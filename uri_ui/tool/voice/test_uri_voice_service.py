"""Unit tests for uri_ui/assets/voice/uri_voice_service.py with fake audio devices.

Run with the voice runtime:  %LOCALAPPDATA%\\URI\\voice\\venv\\Scripts\\python.exe -I -m pytest uri_ui/tool/voice
(numpy is needed; faster-whisper, sounddevice and the speakers are replaced by fakes).
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
import threading
import time
import types
from pathlib import Path

import numpy as np
import pytest

SVC_PATH = Path(__file__).resolve().parents[2] / "assets" / "voice" / "uri_voice_service.py"


def load_module():
    spec = importlib.util.spec_from_file_location("uri_voice_service_under_test", SVC_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeStream:
    def __init__(self, sd, **kw):
        self.sd = sd
        self.kw = kw
        self.callback = kw.get("callback")
        self.active = False
        self.aborted = False
        sd.streams.append(self)

    def start(self):
        self.active = True

    def abort(self):
        self.aborted = True
        self.active = False

    def close(self):
        self.active = False

    def feed(self, samples):
        for i in range(0, len(samples), 320):
            blk = samples[i:i + 320].reshape(-1, 1).astype("float32")
            self.callback(blk, len(blk), None, None)


class FakeOutput:
    def __init__(self, sd, samplerate, channels, dtype, blocksize, callback, finished_callback):
        self.sd, self.cb, self.done, self.block = sd, callback, finished_callback, blocksize
        self.thread = None

    def __enter__(self):
        def run():
            buf = np.zeros((self.block, 1), dtype="float32")
            try:
                while True:
                    self.cb(buf, self.block, None, None)
                    time.sleep(0.001)
            except (self.sd.CallbackStop, self.sd.CallbackAbort):
                pass
            self.done()

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *a):
        self.thread.join(2)


def fake_sd():
    sd = types.SimpleNamespace()
    sd.streams = []

    class CallbackStop(Exception):
        pass

    class CallbackAbort(Exception):
        pass

    sd.CallbackStop, sd.CallbackAbort = CallbackStop, CallbackAbort
    sd.query_hostapis = lambda: [{"name": "Windows WASAPI", "default_input_device": 1}]
    sd.query_devices = lambda: [
        {"name": "Speakers", "hostapi": 0, "max_input_channels": 0, "default_samplerate": 48000},
        {"name": "Mic A", "hostapi": 0, "max_input_channels": 1, "default_samplerate": 48000},
        {"name": "Mic B", "hostapi": 0, "max_input_channels": 1, "default_samplerate": 48000},
    ]
    sd.WasapiSettings = lambda auto_convert: {"auto_convert": auto_convert}
    sd.InputStream = lambda **kw: FakeStream(sd, **kw)
    sd.OutputStream = lambda **kw: FakeOutput(sd, **kw)
    return sd


class FakeRecogniser:
    def __init__(self, text="hello there", words=None, fail=False):
        self.text, self.fail = text, fail
        self.words = words if words is not None else [("hello", 0.9), ("there", 0.3)]
        self.calls = []
        self.ready = threading.Event()
        self.ready.set()
        self.model = object()
        self.error = None
        self.load_ms = 1

    def transcribe(self, audio, final):
        self.calls.append((len(audio), final))
        if self.fail:
            raise RuntimeError("decoder crashed")
        return self.text, self.words if final else [], []


@pytest.fixture()
def env(monkeypatch, tmp_path):
    mod = load_module()
    out = io.StringIO()
    events = []

    def emit(ev, **data):
        events.append({"ev": ev, **data})

    monkeypatch.setattr(mod, "emit", emit)
    monkeypatch.setattr(mod, "microphone_privacy", lambda: {"state": "allowed", "detail": "test"})
    sd = fake_sd()

    class FakeSpeaker:
        def __init__(self):
            self.stops = []
            self.spoken = []

        def stop(self, reason="stopped"):
            self.stops.append(reason)

        def speak(self, *a):
            self.spoken.append(a)

        def close(self):
            pass

    svc = mod.Service.__new__(mod.Service)
    svc.sd = sd
    svc.args = None
    svc.recogniser = FakeRecogniser()
    svc.speaker = FakeSpeaker()
    svc.capture = None
    svc.cap_lock = threading.Lock()
    return types.SimpleNamespace(mod=mod, svc=svc, sd=sd, events=events, out=out)


def wait_for(events, ev, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        for e in events:
            if e["ev"] == ev:
                return e
        time.sleep(0.01)
    raise AssertionError(f"no {ev} in {[e['ev'] for e in events]}")


def speech(seconds=1.5, amp=0.2):
    t = np.arange(int(16000 * seconds)) / 16000
    return (amp * np.sin(2 * np.pi * 220 * t)).astype("float32")


def test_capture_reports_level_onset_and_final_with_uncertain_words(env):
    env.svc.listen_start("c1", None, 60)
    st = wait_for(env.events, "listen.started")
    assert st["device"] == "Mic A"  # the Windows default input
    stream = env.sd.streams[-1]
    assert stream.kw["samplerate"] == 16000 and stream.kw["extra_settings"] == {"auto_convert": True}
    stream.feed(np.zeros(3200, dtype="float32") + 0.001)
    stream.feed(speech())
    assert wait_for(env.events, "listen.speech")["id"] == "c1"
    assert any(e["ev"] == "listen.level" for e in env.events)
    env.svc.listen_stop("c1")
    closed = wait_for(env.events, "listen.closed")
    assert closed["reason"] == "released" and stream.aborted
    fin = wait_for(env.events, "listen.final")
    assert fin["text"] == "hello there" and fin["reason"] == "completed"
    assert fin["uncertain"] == ["there"]  # probability 0.3 < 0.45
    assert env.svc.recogniser.calls[-1][1] is True


def test_selected_microphone_is_used_and_a_missing_one_is_refused(env):
    env.svc.listen_start("c1", "Mic B", 60)
    assert wait_for(env.events, "listen.started")["device"] == "Mic B"
    env.svc.listen_cancel("c1")
    env.events.clear()
    env.svc.listen_start("c2", "Unplugged Mic", 60)
    err = wait_for(env.events, "listen.error")
    assert err["code"] == "MIC_NOT_FOUND"
    assert env.svc.capture is None


def test_denied_privacy_switch_never_opens_the_device(env, monkeypatch):
    monkeypatch.setattr(env.mod, "microphone_privacy", lambda: {"state": "denied", "detail": "blocked for desktop apps"})
    env.svc.listen_start("c1", None, 60)
    assert wait_for(env.events, "listen.error")["code"] == "MIC_DENIED"
    assert env.sd.streams == []


def test_cancel_closes_the_microphone_and_produces_no_transcript(env):
    env.svc.listen_start("c1", None, 60)
    stream = env.sd.streams[-1]
    stream.feed(speech())
    env.svc.listen_cancel("c1")
    time.sleep(0.2)
    assert stream.aborted
    assert [e["reason"] for e in env.events if e["ev"] == "listen.closed"] == ["cancelled"]
    assert not any(e["ev"] == "listen.final" for e in env.events)


def test_silence_gives_no_speech_without_calling_the_recogniser(env):
    env.svc.listen_start("c1", None, 60)
    env.sd.streams[-1].feed(np.zeros(16000, dtype="float32") + 0.0005)
    env.svc.listen_stop("c1")
    fin = wait_for(env.events, "listen.final")
    assert fin["text"] == "" and fin["reason"] == "no_speech"
    assert not any(final for _, final in env.svc.recogniser.calls)


def test_length_bound_stops_capture_and_still_transcribes(env):
    env.svc.listen_start("c1", None, 1.0)
    env.sd.streams[-1].feed(speech(1.3))
    closed = wait_for(env.events, "listen.closed")
    assert closed["reason"] == "max_length"
    assert wait_for(env.events, "listen.final")["text"] == "hello there"


def test_recogniser_failure_is_reported(env):
    env.svc.recogniser = FakeRecogniser(fail=True)
    env.svc.listen_start("c1", None, 60)
    env.sd.streams[-1].feed(speech())
    env.svc.listen_stop("c1")
    assert wait_for(env.events, "listen.error")["code"] == "RECOGNIZER_FAILED"


def test_opening_the_microphone_stops_uri_speaking_first(env):
    env.svc.listen_start("c1", None, 60)
    assert env.svc.speaker.stops == ["interrupted"]


def test_microphone_that_sends_only_zeros_is_flagged(env, monkeypatch):
    monkeypatch.setattr(env.mod, "PARTIAL_EVERY_S", 0.05)
    env.svc.listen_start("c1", None, 60)
    cap = env.svc.capture
    cap.started -= 2.0  # pretend 2 s have passed
    env.sd.streams[-1].feed(np.zeros(8000, dtype="float32"))
    w = wait_for(env.events, "listen.warning")
    assert w["code"] == "MIC_SILENT"
    env.svc.listen_cancel("c1")


def test_uncertain_spans_follow_the_contract():
    mod = load_module()
    text = "Meet Mr. Tshering at Gangtok."
    spans = mod.uncertain_spans(text, [("Meet", 0.9), ("Mr.", 0.4), ("Tshering", 0.2), ("Gangtok.", 0.1), ("zzz", 0.1)])
    assert spans == ["Mr", "Tshering", "Gangtok"]
    assert all(s in text for s in spans)
    many = [(f"w{i}", 0.1) for i in range(50)]
    assert len(mod.uncertain_spans(" ".join(w for w, _ in many), many)) == 32


def test_speaker_plays_in_order_measures_levels_and_stops(env, monkeypatch, tmp_path):
    mod = env.mod
    svc = env.svc
    svc.capture = None
    sp = mod.Speaker.__new__(mod.Speaker)
    sp.svc = svc
    sp.tmp = tmp_path
    sp.gen = 0
    sp.lock = threading.Lock()
    sp.ps_lock = threading.Lock()
    sp.render_q, sp.play_q = mod.queue.Queue(), mod.queue.Queue()
    sp.stop_flag = threading.Event()
    sp.current = None
    sp.started_ids = set()
    import wave

    def render(text, voice, out):
        n = int(8000 * (0.3 if text != "long" else 5.0))
        with wave.open(str(out), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(8000)
            w.writeframes((np.full(n, 3000, dtype="<i2")).tobytes())

    sp._render = render
    threading.Thread(target=sp._render_loop, daemon=True).start()
    threading.Thread(target=sp._play_loop, daemon=True).start()
    sp.speak("u1", "one", {}, False)
    sp.speak("u1", "two", {}, True)
    ended = wait_for(env.events, "speak.ended")
    assert ended["reason"] == "completed"
    kinds = [e["ev"] for e in env.events if e.get("id") == "u1"]
    assert kinds[0] == "speak.started" and "speak.chunk" in kinds and "speak.level" in kinds
    lv = [e["rms"] for e in env.events if e["ev"] == "speak.level"]
    assert max(lv) > 0.05  # level of the audio actually played (3000/32768 = 0.09)
    assert list(tmp_path.iterdir()) == []  # rendered audio deleted after playback
    env.events.clear()
    sp.speak("u2", "long", {}, True)
    wait_for(env.events, "speak.started")
    sp.stop("interrupted")
    end = wait_for(env.events, "speak.ended")
    assert end["reason"] == "interrupted"
    time.sleep(0.2)
    after = [e for e in env.events if e["ev"] == "speak.level" and env.events.index(e) > env.events.index(end)]
    assert len(after) <= 1  # at most the block already in flight


def test_speak_is_refused_while_the_microphone_is_open(env, tmp_path):
    mod = env.mod
    sp = mod.Speaker.__new__(mod.Speaker)
    sp.svc = env.svc
    sp.lock = threading.Lock()
    sp.stop_flag = threading.Event()
    sp.gen = 0
    sp.render_q = mod.queue.Queue()
    env.svc.capture = object()
    sp.speak("u1", "hello", {}, True)
    assert env.events[-1] == {"ev": "speak.ended", "id": "u1", "reason": "refused_listening"}
    assert sp.render_q.empty()


def test_model_integrity_failure_is_reported(tmp_path):
    mod = load_module()
    (tmp_path / "model.bin").write_bytes(b"tampered")
    (tmp_path / "URI_MODEL_MANIFEST.json").write_text(json.dumps(
        {"files": {"model.bin": {"bytes": 8, "sha256": "0" * 64}}}), encoding="utf-8")
    r = mod.Recogniser(tmp_path, 1)
    assert r.ready.wait(10)
    assert r.model is None and r.error[0] == "MODEL_INTEGRITY"


def test_speech_from_the_first_block_is_transcribed(env):
    """Regression (found 2026-10-09): talking at the instant of the press made the
    noise floor equal to speech, onset never fired and the words were dropped."""
    env.svc.listen_start("c1", None, 60)
    env.sd.streams[-1].feed(speech(1.5, amp=0.2))
    assert wait_for(env.events, "listen.speech")["id"] == "c1"
    env.svc.listen_stop("c1")
    fin = wait_for(env.events, "listen.final")
    assert fin["reason"] == "completed" and fin["text"] == "hello there"


def test_punctuation_only_transcript_is_no_speech(env):
    """Regression (live run 3, 2026-10-09): room noise transcribed as "." was sent as a turn."""
    env.svc.recogniser = FakeRecogniser(text=".", words=[])
    env.svc.listen_start("c1", None, 60)
    env.sd.streams[-1].feed(speech(0.8, amp=0.02))
    env.svc.listen_stop("c1")
    fin = wait_for(env.events, "listen.final")
    assert fin["text"] == "" and fin["reason"] == "no_speech"
