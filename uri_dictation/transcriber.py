"""Warm faster-whisper transcriber with a deliberately conservative CUDA fallback."""

from __future__ import annotations

from pathlib import Path
import threading


class WarmTranscriber:
    def __init__(self, models_dir: Path, language: str = "en") -> None:
        self._models_dir = models_dir
        self._language = language
        self._model = None
        self._model_lock = threading.RLock()
        self.device = "cuda"
        self._model_name = "large-v3-turbo"
        self._compute_type = "int8_float16"
        if not self._cuda_is_available():
            self._use_cpu_fallback()

    @staticmethod
    def _cuda_is_available() -> bool:
        try:
            import ctranslate2

            return ctranslate2.get_cuda_device_count() > 0
        except Exception:
            return False

    def _use_cpu_fallback(self) -> None:
        self.device = "cpu"
        self._model_name = "small"
        self._compute_type = "int8"

    @property
    def label(self) -> str:
        return f"{self.device} ({self._model_name})"

    def ensure_loaded(self) -> None:
        with self._model_lock:
            if self._model is not None:
                return
            from faster_whisper import WhisperModel

            self._models_dir.mkdir(parents=True, exist_ok=True)
            try:
                self._model = WhisperModel(
                    self._model_name,
                    device=self.device,
                    compute_type=self._compute_type,
                    download_root=str(self._models_dir),
                )
            except Exception:
                if self.device != "cuda":
                    raise
                self._use_cpu_fallback()
                self._model = WhisperModel(
                    self._model_name,
                    device=self.device,
                    compute_type=self._compute_type,
                    download_root=str(self._models_dir),
                )

    def transcribe(self, audio):
        with self._model_lock:
            self.ensure_loaded()
            segments, _ = self._model.transcribe(
                audio,
                vad_filter=True,
                language=self._language,
                beam_size=1,
            )
            return " ".join(segment.text.strip() for segment in segments).strip()

    def transcribe_preview(self, audio):
        """Transcribe a display-only rolling window without prior-text context."""
        with self._model_lock:
            self.ensure_loaded()
            segments, _ = self._model.transcribe(
                audio,
                vad_filter=True,
                language=self._language,
                beam_size=1,
                condition_on_previous_text=False,
                without_timestamps=True,
            )
            return " ".join(segment.text.strip() for segment in segments).strip()
