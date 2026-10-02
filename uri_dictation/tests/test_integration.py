import pytest

from integration import paste_text


class FakeClipboard:
    def __init__(self, text="old clipboard"):
        self.text = text
        self.history = []

    def get_text(self):
        return self.text

    def snapshot(self):
        return self.text

    def restore(self, snapshot):
        self.history.append(snapshot)
        self.text = snapshot

    def set_text(self, text):
        self.history.append(text)
        self.text = text


class FakeKeys:
    def __init__(self, fail=False):
        self.pastes = 0
        self.enter = 0
        self.fail = fail

    def paste(self):
        self.pastes += 1
        if self.fail:
            raise RuntimeError("paste failed")


def test_paste_saves_and_restores_clipboard():
    clipboard = FakeClipboard()
    keys = FakeKeys()
    assert paste_text("hello", clipboard, keys, wait=lambda _: None)
    assert clipboard.text == "old clipboard"
    assert clipboard.history == ["hello", "old clipboard"]
    assert keys.pastes == 1
    assert keys.enter == 0


def test_clipboard_restores_when_paste_fails():
    clipboard = FakeClipboard()
    with pytest.raises(RuntimeError):
        paste_text("hello", clipboard, FakeKeys(fail=True), wait=lambda _: None)
    assert clipboard.text == "old clipboard"


def test_empty_transcript_inserts_nothing_and_never_sends_enter():
    clipboard = FakeClipboard()
    keys = FakeKeys()
    assert not paste_text("   ", clipboard, keys, wait=lambda _: None)
    assert clipboard.history == []
    assert keys.pastes == 0
    assert keys.enter == 0


def test_paste_restores_an_opaque_non_text_clipboard_snapshot():
    class RichClipboard(FakeClipboard):
        def __init__(self):
            super().__init__(None)
            self.rich = {"bitmap": b"pixels", "files": ("a.txt",)}

        def snapshot(self):
            return self.rich

        def restore(self, snapshot):
            self.history.append(snapshot)
            self.rich = snapshot

    clipboard = RichClipboard()
    assert paste_text("hello", clipboard, FakeKeys(), wait=lambda _: None)
    assert clipboard.rich == {"bitmap": b"pixels", "files": ("a.txt",)}
