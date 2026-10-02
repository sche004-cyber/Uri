import threading
import numpy as np
from unittest.mock import mock_open, patch

import main
from main import (DictationApp, ListeningPill, PreviewScheduler, SerializedProcessor,
                  _PanelCommandState, waveform_bar_geometry)
from transcriber import WarmTranscriber


def test_listening_pill_queues_commands_without_creating_tk_on_caller_thread():
    pill = ListeningPill()
    pill.show()
    pill.hide()
    assert pill._commands.get_nowait() == ("listening", "Listening...")
    assert pill._commands.get_nowait() == ("hide", None)


def test_late_preview_is_ignored_after_transcribing_starts():
    state = _PanelCommandState()
    assert state.apply("listening")
    assert state.apply("preview")
    assert state.apply("transcribing")
    assert not state.apply("preview")
    assert state.apply("polishing")
    assert not state.apply("preview")


def test_waveform_geometry_is_mirrored_smoothed_and_places_newest_level_right():
    bars = waveform_bar_geometry([.1, 1.0], width=48, height=44, count=4)
    assert len(bars) == 4
    assert all(top < 22 < bottom and top + bottom == 44 for _, top, bottom in bars)
    heights = [bottom - top for _, top, bottom in bars]
    assert heights[-1] > heights[-2] > heights[0]
    assert bars[-1][0] > bars[0][0]


class _ManualThread:
    def __init__(self, target, args=(), **_kwargs):
        self.target = target
        self.args = args
    def start(self):
        pass
    def join(self, timeout=None):
        pass
    def run(self):
        self.target(*self.args)


def test_preview_scheduler_skips_inflight_work_stops_on_release_and_prefixes_truncation():
    class Recorder:
        def snapshot(self, _window): return np.ones(16000, dtype="float32")
        def is_window_truncated(self, _window): return True
    class Transcriber:
        def transcribe_preview(self, _audio): return "hello world"
    class Panel:
        def __init__(self): self.messages = []
        def show_preview(self, text): self.messages.append(text)

    threads = []
    def factory(**kwargs):
        thread = _ManualThread(**kwargs)
        threads.append(thread)
        return thread

    panel = Panel()
    scheduler = PreviewScheduler(Recorder(), Transcriber(), panel, {}, .8, 15, lambda _exc: None, thread_factory=factory)
    assert scheduler.tick()
    assert not scheduler.tick()  # first preview has not completed
    threads[-1].run()
    assert panel.messages == ["... hello world"]
    scheduler.stop()
    assert not scheduler.tick()


def test_preview_never_uses_clipboard_key_sender_or_transcript_logging():
    class Recorder:
        def snapshot(self, _window): return np.ones(4, dtype="float32")
        def is_window_truncated(self, _window): return False
    class Transcriber:
        def transcribe_preview(self, _audio): return "private dictated phrase"
    class Panel:
        def show_preview(self, _text): pass

    scheduler = PreviewScheduler(Recorder(), Transcriber(), Panel(), {}, .8, 15, lambda _exc: None, thread_factory=threading.Thread)
    assert scheduler.tick()
    # A preview has no pipeline reference: only the panel command path is available.
    assert not hasattr(scheduler, "_clipboard")
    assert not hasattr(scheduler, "_key_sender")
    assert not hasattr(scheduler, "_timing_path")


def test_preview_disabled_does_not_start_a_scheduler():
    app = DictationApp.__new__(DictationApp)
    app._recording = False
    app._hotkey_parts = set()
    app.recorder = type("Recorder", (), {"start": lambda self: None})()
    app.key_sender = type("Keys", (), {})()
    app._pill = type("Pill", (), {"show": lambda self: None})()
    app.config = type("Config", (), {"preview_enabled": False})()
    app._preview_scheduler = None
    app._report_error = lambda _exc: None
    app._toast = lambda _message: None
    app._start_recording()
    assert app._preview_scheduler is None


def test_final_transcription_waits_for_preview_model_use():
    preview_entered = threading.Event()
    release_preview = threading.Event()
    events = []

    class Segment:
        text = "text"
    class Model:
        def transcribe(self, _audio, **kwargs):
            if kwargs.get("condition_on_previous_text") is False:
                events.append("preview-enter")
                preview_entered.set()
                release_preview.wait(1)
                events.append("preview-exit")
            else:
                events.append("final-enter")
            return [Segment()], None

    transcriber = WarmTranscriber.__new__(WarmTranscriber)
    transcriber._model_lock = threading.RLock()
    transcriber._model = Model()
    transcriber._language = "en"
    transcriber.ensure_loaded = lambda: None
    preview = threading.Thread(target=lambda: transcriber.transcribe_preview(np.ones(2, dtype="float32")))
    final = threading.Thread(target=lambda: transcriber.transcribe(np.ones(2, dtype="float32")))
    preview.start()
    assert preview_entered.wait(1)
    final.start()
    assert events == ["preview-enter"]
    release_preview.set()
    preview.join()
    final.join()
    assert events == ["preview-enter", "preview-exit", "final-enter"]


def test_serialized_processor_does_not_interleave_work_items():
    entered = threading.Event()
    release = threading.Event()
    events = []

    def process(audio, _seconds):
        events.append(("start", audio))
        if audio == "first":
            entered.set()
            release.wait(1)
        events.append(("end", audio))
        return True

    worker = SerializedProcessor(process)
    worker.submit("first", 1.0)
    assert entered.wait(1)
    worker.submit("second", 1.0)
    release.set()
    worker.stop()
    assert events == [("start", "first"), ("end", "first"), ("start", "second"), ("end", "second")]


def test_win_hotkey_marks_a_noname_key_once_per_recording_without_enter():
    class Recorder:
        def start(self):
            pass

    class Keys:
        def __init__(self):
            self.marks = 0
            self.enter = 0
        def mark_hotkey_pressed(self):
            self.marks += 1

    class Pill:
        def show(self):
            pass

    app = DictationApp.__new__(DictationApp)
    app._recording = False
    app._hotkey_parts = {"ctrl", "win"}
    app.recorder = Recorder()
    app.key_sender = Keys()
    app._pill = Pill()
    app._report_error = lambda _exc: None
    app._toast = lambda _message: None
    app._start_recording()
    app._start_recording()
    assert app.key_sender.marks == 1
    assert app.key_sender.enter == 0


def test_unhandled_exception_is_written_without_transcript_or_audio():
    app = DictationApp.__new__(DictationApp)
    messages = []
    app._toast = messages.append

    output = mock_open()
    with patch("pathlib.Path.mkdir"), patch("pathlib.Path.open", output):
        try:
            raise RuntimeError("microphone device failed")
        except RuntimeError as exc:
            app._report_error(exc)

    handle = output.return_value.__enter__.return_value
    logged = "".join(call.args[0] for call in handle.write.call_args_list)
    assert "RuntimeError: microphone device failed" in logged
    assert "private dictated phrase" not in logged
    assert "audio-bytes-123" not in logged
    assert messages == ["URI Dictation encountered an error"]
