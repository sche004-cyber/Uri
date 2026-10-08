"""Run with .venv_voice/Scripts/python.exe -m unittest tests/test_uri_voice_input.py."""
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from scripts.uri_voice_transcribe import ready, capture
except ImportError:
    ready = capture = None


@unittest.skipIf(ready is None, 'Optional isolated voice dependencies unavailable')
class VoiceInputTests(unittest.TestCase):
    def test_control_requires_current_unmuted_authenticated_idle_lease(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'control.json'
            baseline = {'ready': True, 'muted': False, 'timestamp': time.time()*1000}
            path.write_text(json.dumps(baseline))
            self.assertTrue(ready(path))
            for change in [{'muted': True}, {'ready': False}, {'timestamp': 0},
                           {'timestamp': time.time()*1000+10000}]:
                path.write_text(json.dumps({**baseline, **change}))
                self.assertFalse(ready(path))
            path.write_text('broken')
            self.assertFalse(ready(path))

    def test_muted_capture_closes_device_without_reading_or_dispatch(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'control.json'
            path.write_text(json.dumps({'ready': True, 'muted': True,
                'timestamp': time.time()*1000}))
            with patch('scripts.uri_voice_transcribe.sd.InputStream') as device:
                result = capture(path, 15)
                self.assertEqual(len(result), 0)
                device.return_value.__enter__.return_value.read.assert_not_called()
                device.return_value.__exit__.assert_called_once()


if __name__ == '__main__':
    unittest.main()
