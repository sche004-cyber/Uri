from pipeline import DictationPipeline


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
