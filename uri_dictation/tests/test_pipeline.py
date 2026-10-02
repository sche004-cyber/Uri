import json

from pipeline import DictationPipeline
from polish import Polisher


class FakeClipboard:
    def __init__(self):
        self.text = "original"

    def get_text(self):
        return self.text

    def snapshot(self):
        return self.text

    def restore(self, snapshot):
        self.text = snapshot

    def set_text(self, text):
        self.text = text


class FakeKeys:
    def __init__(self):
        self.pastes = 0
        self.enter = 0

    def paste(self):
        self.pastes += 1


class FakeToast:
    def __init__(self):
        self.messages = []

    def show(self, message):
        self.messages.append(message)


class FakeTimingPath:
    def __init__(self):
        self.parent = self
        self.records = []

    def mkdir(self, **kwargs):
        pass

    def open(self, *args, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def write(self, text):
        self.records.append(text)


class FailingTranscriber:
    device = "cpu (small)"

    def transcribe(self, audio):
        raise RuntimeError("model error")


def test_failed_transcript_inserts_nothing_and_never_sends_enter():
    clipboard = FakeClipboard()
    keys = FakeKeys()
    toast = FakeToast()
    timing = FakeTimingPath()
    pipeline = DictationPipeline(FailingTranscriber(), clipboard, keys, toast, {}, timing, wait=lambda _: None)

    assert not pipeline.process([], 1.0)
    assert clipboard.text == "original"
    assert keys.pastes == 0
    assert keys.enter == 0
    assert toast.messages == ["Dictation failed"]
    assert "transcript" not in timing.records[0]


def test_pipeline_reports_exception_to_error_logger_without_transcript():
    errors = []
    pipeline = DictationPipeline(FailingTranscriber(), FakeClipboard(), FakeKeys(), FakeToast(), {}, FakeTimingPath(), wait=lambda _: None, error_logger=errors.append)

    assert not pipeline.process(["private audio"], 1.0)
    assert len(errors) == 1
    assert type(errors[0]) is RuntimeError


def test_timing_records_polish_fields_without_transcript_text():
    class Transcriber:
        device = "cpu (small)"
        def transcribe(self, _audio): return "private words for testing"
    timing = FakeTimingPath()
    polisher = Polisher(True, "test-model", 1, http_post=lambda *_args: b'{"message":{"content":"Private words for testing."}}')
    pipeline = DictationPipeline(Transcriber(), FakeClipboard(), FakeKeys(), FakeToast(), {}, timing, polisher=polisher, wait=lambda _: None)

    assert pipeline.process([], 1.0)
    record = json.loads(timing.records[0])
    assert {"polish_ms", "polish_model", "polish_used", "polish_fallback_reason", "polish_escalated"} <= record.keys()
    assert record["polish_model"] == "test-model"
    assert record["polish_used"] is True
    assert record["polish_fallback_reason"] is None
    assert record["polish_escalated"] is False
    assert "private words for testing" not in timing.records[0].casefold()


def test_polish_failure_toasts_and_pastes_deterministic_cleanup():
    class Transcriber:
        device = "cpu (small)"
        def transcribe(self, _audio): return "um private words for testing"
    class Clipboard(FakeClipboard):
        def __init__(self):
            super().__init__()
            self.history = []
        def set_text(self, text):
            self.history.append(text)
            super().set_text(text)
    clipboard, toast = Clipboard(), FakeToast()
    polisher = Polisher(True, "test-model", 1, http_post=lambda *_args: b'{"message":{"content":""}}')
    pipeline = DictationPipeline(Transcriber(), clipboard, FakeKeys(), toast, {}, FakeTimingPath(), polisher=polisher, wait=lambda _: None)

    assert pipeline.process([], 1.0)
    assert clipboard.history == ["private words for testing"]
    assert toast.messages == ["Pasted unpolished: empty"]


def test_escalated_polish_records_actual_model_and_updates_status():
    class Transcriber:
        device = "cpu (small)"
        def transcribe(self, _audio): return "private words for testing"
    timing, toast, statuses = FakeTimingPath(), FakeToast(), []

    def post(_url, body, _timeout):
        model = json.loads(body)["model"]
        return b'{"message":{"content":""}}' if model == "edge" else b'{"message":{"content":"Private words for testing."}}'

    pipeline = DictationPipeline(
        Transcriber(), FakeClipboard(), FakeKeys(), toast, {}, timing,
        polisher=Polisher(True, "main", 1, polish_edge_model="edge", http_post=post),
        wait=lambda _: None, on_polishing=statuses.append,
    )

    assert pipeline.process([], 1.0)
    record = json.loads(timing.records[0])
    assert (record["polish_model"], record["polish_escalated"]) == ("main", True)
    assert statuses == ["edge", "main (escalated)"]
    assert toast.messages == ["Polished by main (escalated)"]
