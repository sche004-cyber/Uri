from config import DEFAULT_HOTKEY, DEFAULT_LANGUAGE, DEFAULT_MINIMUM_HOLD_SECONDS, load_config


class FakePath:
    def __init__(self, content=None):
        self.content = content

    def read_text(self, encoding):
        if self.content is None:
            raise OSError("missing")
        return self.content


def test_missing_config_uses_defaults():
    config = load_config(FakePath())
    assert (config.hotkey, config.minimum_hold_seconds, config.language) == (DEFAULT_HOTKEY, DEFAULT_MINIMUM_HOLD_SECONDS, DEFAULT_LANGUAGE)


def test_partial_config_keeps_missing_defaults():
    config = load_config(FakePath('{"hotkey": "CTRL+WIN"}'))
    assert config.hotkey == "ctrl+win"
    assert config.minimum_hold_seconds == DEFAULT_MINIMUM_HOLD_SECONDS
    assert config.language == DEFAULT_LANGUAGE
