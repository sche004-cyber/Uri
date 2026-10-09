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

    def transcribe(self, audio, final, hotwords=""):
        self.calls.append((len(audio), final))
        self.hotwords = hotwords
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


def test_selected_microphone_is_used(env):
    env.svc.listen_start("c1", "Mic B", 60)
    assert wait_for(env.events, "listen.started")["device"] == "Mic B"
    env.svc.listen_cancel("c1")


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
    sp.failed = set()
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


def test_user_vocabulary_reaches_the_recogniser_and_is_sanitised(env):
    env.svc.listen_start("c1", None, 60, "Gangtok; Tshering <script> Bhutia")
    env.sd.streams[-1].feed(speech())
    env.svc.listen_stop("c1")
    wait_for(env.events, "listen.final")
    assert env.svc.recogniser.hotwords == "Gangtok; Tshering <script> Bhutia"
    assert env.mod.bias_words("Gangtok; Tshering <script> Bhutia") == "URI Gangtok Tshering script Bhutia"
    assert env.mod.bias_words("") == "URI"
    assert len(env.mod.bias_words("x" * 5000)) <= 4 + env.mod.VOCAB_MAX_CHARS


def make_speaker(env, tmp_path, render):
    mod = env.mod
    env.svc.capture = None
    sp = mod.Speaker.__new__(mod.Speaker)
    sp.svc = env.svc
    sp.tmp = tmp_path
    sp.gen = 0
    sp.lock = threading.Lock()
    sp.ps_lock = threading.Lock()
    sp.render_q, sp.play_q = mod.queue.Queue(), mod.queue.Queue()
    sp.stop_flag = threading.Event()
    sp.current = None
    sp.started_ids = set()
    sp.failed = set()
    sp._render = render
    threading.Thread(target=sp._render_loop, daemon=True).start()
    threading.Thread(target=sp._play_loop, daemon=True).start()
    return sp


def wav_render(seconds):
    import wave

    def render(text, voice, out):
        if text == "boom":
            raise RuntimeError("engine failed")
        with wave.open(str(out), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(8000)
            w.writeframes(np.full(int(8000 * seconds), 3000, dtype="<i2").tobytes())
    return render


def test_r1_4_a_failed_sentence_drops_the_rest_of_its_utterance(env, tmp_path):
    sp = make_speaker(env, tmp_path, wav_render(0.2))
    sp.speak("u1", "boom", {}, False)
    sp.speak("u1", "after", {}, True)
    end = wait_for(env.events, "speak.ended")
    assert end["reason"] == "failed"
    time.sleep(0.8)
    assert not any(e["ev"] in ("speak.started", "speak.chunk") and e.get("id") == "u1" for e in env.events)
    assert "u1" not in sp.failed  # forgotten after its last sentence
    env.events.clear()
    sp.speak("u2", "fine", {}, True)  # later utterances are unaffected
    assert wait_for(env.events, "speak.ended")["reason"] == "completed"


def test_r1_3_a_gap_between_sentences_reports_silence(env, tmp_path):
    sp = make_speaker(env, tmp_path, wav_render(0.2))
    sp.speak("u1", "one", {}, False)
    wait_for(env.events, "speak.started")
    time.sleep(1.2)  # URI has not written the next sentence yet
    # The clip's own last (empty) block reports one zero level at most; the gap
    # reports silence every 250 ms (old code: one zero level, then nothing).
    zeros = [e for e in env.events if e["ev"] == "speak.level" and e["rms"] == 0.0]
    assert len(zeros) >= 3
    sp.speak("u1", "two", {}, True)
    assert wait_for(env.events, "speak.ended")["reason"] == "completed"


def test_r1_5_unplugged_choice_falls_back_to_the_default_with_a_warning(env):
    env.svc.listen_start("c1", "Unplugged Mic", 60)
    st = wait_for(env.events, "listen.started")
    assert st["device"] == "Mic A"
    w = wait_for(env.events, "listen.warning")
    assert w["code"] == "MIC_FALLBACK" and "Unplugged Mic" in w["message"]


def test_noise_segments_are_not_speech():
    """Regression (2026-10-09): room noise came back as "Yeah." / "Yes you know you're
    right." / "I know. I know. ..." after the VAD filter."""
    mod = load_module()
    seg = lambda text, nsp, lp, cr: types.SimpleNamespace(text=text, no_speech_prob=nsp, avg_logprob=lp,
                                                          compression_ratio=cr, words=[])
    # Measured noise segments (noise_guard_segments.json)
    assert not mod.is_speech_segment(seg("Yeah.", 0.422, -1.56, 0.38))
    assert not mod.is_speech_segment(seg("Evans Evans Evans", 0.354, -1.32, 2.06))
    assert not mod.is_speech_segment(seg("I know. I know.", 0.476, -0.083, 26.95))
    # Measured speech segments with the weakest scores
    assert mod.is_speech_segment(seg("Stop.", 0.179, -0.956, 0.6))
    assert mod.is_speech_segment(seg("Stop", 0.223, -0.362, 0.6))

    class FakeModel:
        def transcribe(self, audio, **kw):
            return iter([seg("Yeah.", 0.42, -1.56, 0.38), seg("Open the dashboard.", 0.16, -0.6, 0.9)]), None

    r = mod.Recogniser.__new__(mod.Recogniser)
    r.lock = threading.Lock()
    r.ready = threading.Event()
    r.ready.set()
    r.model = FakeModel()
    r.error = None
    text, words, segs = r.transcribe(np.zeros(16000, dtype="float32"), final=True)
    assert text == "Open the dashboard."


def test_hello_answers_at_once_while_the_model_loads(env):
    """Regression (2026-10-09): hello blocked 20 s and then reported model_ok false
    with no error (the load was hung, see the preload test); the client showed Ready."""
    r0 = env.svc.recogniser
    r0.state = types.MethodType(env.mod.Recogniser.state, r0)
    r0.ready.clear()
    r0.model = None
    t = time.time()
    env.svc.hello()
    assert time.time() - t < 2
    r = wait_for(env.events, "ready")
    assert r["model"] == {"state": "loading"} and r["model_error"] is None


def test_native_modules_are_imported_before_worker_threads_start():
    """Regression (2026-10-09): concurrent native imports in two worker threads hung
    the model load. main() must preload them before Service() starts any thread."""
    import ast

    tree = ast.parse(SVC_PATH.read_text(encoding="utf-8"))
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    calls = [c.func.id if isinstance(c.func, ast.Name) else getattr(c.func, "attr", "")
             for c in ast.walk(main) if isinstance(c, ast.Call)]
    assert "preload_native_modules" in calls
    order = [n for n in calls if n in ("preload_native_modules", "Service")]
    assert order.index("preload_native_modules") < order.index("Service")
    pre = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "preload_native_modules")
    imported = {a.name for n in ast.walk(pre) if isinstance(n, ast.Import) for a in n.names}
    assert {"numpy", "sounddevice", "faster_whisper"} <= imported


def test_decoding_is_bounded():
    """Regression (2026-10-09): room noise made the decoder loop with temperature
    fallback (51 CPU-seconds for one 8 s capture)."""
    mod = load_module()
    seen = {}

    class FakeModel:
        def transcribe(self, audio, **kw):
            seen.update(kw)
            return iter([]), None

    r = mod.Recogniser.__new__(mod.Recogniser)
    r.lock = threading.Lock()
    r.ready = threading.Event()
    r.ready.set()
    r.model = FakeModel()
    r.error = None
    r.transcribe(np.zeros(16000 * 10, dtype="float32"), final=True)
    assert seen["temperature"] == 0.0
    assert seen["max_new_tokens"] == 10 * mod.TOKENS_PER_SECOND + 16


def test_partials_wait_for_detected_speech(env, monkeypatch):
    monkeypatch.setattr(env.mod, "PARTIAL_EVERY_S", 0.05)
    env.svc.listen_start("c1", None, 60)
    noise = (np.random.default_rng(1).standard_normal(16000 * 2) * 0.005).astype("float32")
    env.sd.streams[-1].feed(noise)  # above the silence gate, below onset
    time.sleep(0.4)
    assert not any(final is False for _, final in env.svc.recogniser.calls)
    env.svc.listen_cancel("c1")
