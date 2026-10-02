from config import (DEFAULT_HOTKEY, DEFAULT_LANGUAGE, DEFAULT_MINIMUM_HOLD_SECONDS,
                    DEFAULT_PREVIEW_ENABLED, DEFAULT_PREVIEW_INTERVAL_SECONDS,
                    DEFAULT_PREVIEW_WINDOW_SECONDS, DEFAULT_POLISH, DEFAULT_POLISH_MODEL,
                    DEFAULT_POLISH_TIMEOUT_SECONDS, DEFAULT_POLISH_NUM_CTX,
                    DEFAULT_POLISH_KEEP_ALIVE, load_config, save_polish_enabled)


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


def test_preview_defaults_and_invalid_values_are_safe():
    defaults = load_config(FakePath())
    assert (defaults.preview_enabled, defaults.preview_interval_seconds, defaults.preview_window_seconds) == (
        DEFAULT_PREVIEW_ENABLED, DEFAULT_PREVIEW_INTERVAL_SECONDS, DEFAULT_PREVIEW_WINDOW_SECONDS)
    invalid = load_config(FakePath('{"preview_enabled": "yes", "preview_interval_seconds": 0, "preview_window_seconds": false}'))
    assert (invalid.preview_enabled, invalid.preview_interval_seconds, invalid.preview_window_seconds) == (
        DEFAULT_PREVIEW_ENABLED, DEFAULT_PREVIEW_INTERVAL_SECONDS, DEFAULT_PREVIEW_WINDOW_SECONDS)


def test_polish_defaults_and_invalid_values_are_safe():
    defaults = load_config(FakePath())
    assert (defaults.polish, defaults.polish_model, defaults.polish_timeout_s, defaults.polish_num_ctx, defaults.polish_keep_alive) == (
        DEFAULT_POLISH, DEFAULT_POLISH_MODEL, DEFAULT_POLISH_TIMEOUT_SECONDS,
        DEFAULT_POLISH_NUM_CTX, DEFAULT_POLISH_KEEP_ALIVE)
    invalid = load_config(FakePath('{"polish": "yes", "polish_model": "", "polish_timeout_s": false, "polish_num_ctx": false, "polish_keep_alive": ""}'))
    assert (invalid.polish, invalid.polish_model, invalid.polish_timeout_s, invalid.polish_num_ctx, invalid.polish_keep_alive) == (
        DEFAULT_POLISH, DEFAULT_POLISH_MODEL, DEFAULT_POLISH_TIMEOUT_SECONDS,
        DEFAULT_POLISH_NUM_CTX, DEFAULT_POLISH_KEEP_ALIVE)
    assert load_config(FakePath('{"polish_timeout_s": 1e999}')).polish_timeout_s == DEFAULT_POLISH_TIMEOUT_SECONDS
    assert load_config(FakePath('{"polish_num_ctx": 0, "polish_keep_alive": 2}')).polish_num_ctx == DEFAULT_POLISH_NUM_CTX
    assert load_config(FakePath('{"polish_num_ctx": 0, "polish_keep_alive": 2}')).polish_keep_alive == DEFAULT_POLISH_KEEP_ALIVE
    configured = load_config(FakePath('{"polish_num_ctx": 32768, "polish_keep_alive": " 1h "}'))
    assert (configured.polish_num_ctx, configured.polish_keep_alive) == (32768, "1h")


def test_polish_toggle_persistence_retains_existing_keys():
    class WritableFakePath(FakePath):
        def write_text(self, text, encoding):
            self.content = text
    path = WritableFakePath('{"hotkey":"alt+x","other":{"keep":true}}')
    save_polish_enabled(path, False)
    import json
    assert json.loads(path.read_text(encoding="utf-8")) == {"hotkey": "alt+x", "other": {"keep": True}, "polish": False}
