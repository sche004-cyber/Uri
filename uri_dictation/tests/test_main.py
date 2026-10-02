import threading
from unittest.mock import mock_open, patch

import main
from main import DictationApp, ListeningPill, SerializedProcessor


def test_listening_pill_queues_commands_without_creating_tk_on_caller_thread():
    pill = ListeningPill()
    pill.show()
    pill.hide()
    assert pill._commands.get_nowait() is True
    assert pill._commands.get_nowait() is False


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
