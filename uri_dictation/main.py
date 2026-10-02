"""URI Dictation standalone Windows entry point."""
from __future__ import annotations
import ctypes
import queue
import threading
import traceback
import textwrap
from dataclasses import replace
from enum import Enum, auto
from pathlib import Path
from typing import Callable
from cleanup import cleanup_transcript
from config import load_config, load_dictionary, save_polish_enabled
from pipeline import DictationPipeline
from polish import Polisher
from platform_io import PynputKeySender, WindowsClipboard
from recording import MemoryRecorder
from transcriber import WarmTranscriber

ROOT = Path(__file__).resolve().parent
_MUTEX = None


class _PanelState(Enum):
    HIDDEN = auto()
    LISTENING = auto()
    TRANSCRIBING = auto()
    POLISHING = auto()


class _PanelCommandState:
    """UI-thread-only state which rejects preview results after release."""
    def __init__(self) -> None:
        self.state = _PanelState.HIDDEN

    def apply(self, action: str) -> bool:
        if action == "listening":
            self.state = _PanelState.LISTENING
        elif action == "transcribing":
            self.state = _PanelState.TRANSCRIBING
        elif action == "polishing":
            self.state = _PanelState.POLISHING
        elif action == "hide":
            self.state = _PanelState.HIDDEN
        return action != "preview" or self.state is _PanelState.LISTENING


def waveform_bar_geometry(levels: list[float], *, width: int = 560, height: int = 44,
                          count: int = 48, smoothing: float = 0.85) -> list[tuple[float, float, float]]:
    """Return centre-mirrored bar coordinates, with the newest level at right."""
    values = ([0.0] * count + [min(1.0, max(0.0, float(value))) for value in levels])[-count:]
    midline = height / 2
    spacing = width / count
    smoothed = 0.0
    bars = []
    for index, value in enumerate(values):
        smoothed = max(smoothed * smoothing, value)
        half_height = max(1.0, smoothed * (height / 2 - 2))
        bars.append(((index + 0.5) * spacing, midline - half_height, midline + half_height))
    return bars


class ListeningPill:
    """Owns all Tk state on one dedicated UI thread."""
    def __init__(self, recorder=None, waveform_enabled: bool = True) -> None:
        self._commands: queue.Queue[tuple[str, str | None] | None] = queue.Queue()
        self._recorder = recorder
        self._waveform_enabled = waveform_enabled
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, name="uri-dictation-ui", daemon=True)

    def start(self) -> None:
        self._thread.start()
        self._ready.wait()

    def show(self) -> None:
        self._commands.put(("listening", "Listening..."))

    def show_transcribing(self) -> None:
        self._commands.put(("transcribing", "Transcribing..."))

    def show_polishing(self, model: str) -> None:
        self._commands.put(("polishing", f"Polishing ({model})..."))

    def show_preview(self, text: str) -> None:
        self._commands.put(("preview", text))

    def hide(self) -> None:
        self._commands.put(("hide", None))

    def stop(self) -> None:
        self._commands.put(None)
        self._thread.join(timeout=2)

    def _run(self) -> None:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        pill = None
        state = _PanelCommandState()

        def redraw_waveform() -> None:
            if (pill is not None and state.state is _PanelState.LISTENING
                    and hasattr(pill, "_uri_waveform")):
                levels = self._recorder.levels(48) if self._recorder is not None else [0.0] * 48
                for item, (x, top, bottom) in zip(pill._uri_waveform_items, waveform_bar_geometry(levels)):
                    pill._uri_waveform.coords(item, x, top, x, bottom)
            root.after(33, redraw_waveform)

        def poll() -> None:
            nonlocal pill
            while True:
                try:
                    command = self._commands.get_nowait()
                except queue.Empty:
                    break
                if command is None:
                    if pill is not None:
                        pill.destroy()
                    root.destroy()
                    return
                action, text = command
                if not state.apply(action):
                    continue
                if action != "hide" and pill is None:
                    pill = tk.Toplevel(root)
                    pill.overrideredirect(True)
                    pill.attributes("-topmost", True)
                    pill.attributes("-alpha", 0.9)
                    if self._waveform_enabled:
                        waveform = tk.Canvas(pill, width=560, height=44, bg="#262626", highlightthickness=0)
                        waveform.pack(padx=14, pady=(8, 0))
                        pill._uri_waveform = waveform
                        pill._uri_waveform_items = [waveform.create_line(0, 22, 0, 22, fill="#4fc3f7", width=4, capstyle="round") for _ in range(48)]
                    label = tk.Label(pill, text=self._visible_text(text or ""), bg="#262626", fg="white", font=("Segoe UI", 11, "bold"), justify="left", wraplength=560)
                    label.pack(padx=14, pady=8)
                    pill._uri_label = label
                    pill.update_idletasks()
                    self._position(pill)
                    self._make_non_activating(pill)
                elif action != "hide" and pill is not None:
                    pill._uri_label.configure(text=self._visible_text(text or ""))
                    if hasattr(pill, "_uri_waveform"):
                        if state.state is _PanelState.LISTENING:
                            pill._uri_waveform.pack(padx=14, pady=(8, 0), before=pill._uri_label)
                        else:
                            pill._uri_waveform.pack_forget()
                    pill.update_idletasks()
                    self._position(pill)
                elif action == "hide" and pill is not None:
                    pill.destroy()
                    pill = None
            root.after(25, poll)
        self._ready.set()
        root.after(0, poll)
        root.after(0, redraw_waveform)
        root.mainloop()

    @staticmethod
    def _visible_text(text: str) -> str:
        """Approximate a 560 px, four-line panel while preserving the newest text."""
        lines = []
        for paragraph in text.splitlines() or [text]:
            lines.extend(textwrap.wrap(paragraph, width=70, break_long_words=False) or [""])
        return "\n".join(lines[-4:])

    @staticmethod
    def _position(panel) -> None:
        """Put the panel bottom-centre in the primary work area."""
        try:
            class RECT(ctypes.Structure):
                _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
            rect = RECT()
            ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(rect), 0)
            x = rect.left + (rect.right - rect.left - panel.winfo_reqwidth()) // 2
            y = rect.bottom - panel.winfo_reqheight() - 80
            panel.geometry(f"+{x}+{y}")
        except Exception:
            panel.geometry(f"+{(panel.winfo_screenwidth() - panel.winfo_reqwidth()) // 2}+{panel.winfo_screenheight() - panel.winfo_reqheight() - 80}")

    @staticmethod
    def _make_non_activating(panel) -> None:
        try:
            try:
                hwnd = int(panel.wm_frame(), 16)
            except Exception:
                hwnd = ctypes.windll.user32.GetParent(panel.winfo_id()) or panel.winfo_id()
            get = ctypes.windll.user32.GetWindowLongW
            set_ = ctypes.windll.user32.SetWindowLongW
            set_(hwnd, -20, get(hwnd, -20) | 0x08000000 | 0x00000080)  # WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
        except Exception:
            pass


class PreviewScheduler:
    """Periodically transcribes rolling audio while keeping UI work queued."""
    def __init__(self, recorder, transcriber, panel: ListeningPill, dictionary, interval_seconds: float, window_seconds: float, error_logger: Callable[[BaseException], None], *, thread_factory=threading.Thread) -> None:
        self._recorder = recorder
        self._transcriber = transcriber
        self._panel = panel
        self._dictionary = dictionary
        self._interval_seconds = interval_seconds
        self._window_seconds = window_seconds
        self._error_logger = error_logger
        self._thread_factory = thread_factory
        self._stopped = threading.Event()
        self._inflight = threading.Lock()
        self._schedule_lock = threading.Lock()
        self._ticker = None

    def start(self) -> None:
        self._ticker = self._thread_factory(target=self._run, name="uri-dictation-preview", daemon=True)
        self._ticker.start()

    def stop(self) -> None:
        self._stopped.set()
        # Ensure a tick already in progress cannot start fresh work after release.
        with self._schedule_lock:
            pass
        if self._ticker is not None:
            self._ticker.join(timeout=1)

    def _run(self) -> None:
        while not self._stopped.wait(self._interval_seconds):
            self.tick()

    def tick(self) -> bool:
        with self._schedule_lock:
            if self._stopped.is_set() or not self._inflight.acquire(blocking=False):
                return False
            audio = self._recorder.snapshot(self._window_seconds)
            if not len(audio) or self._stopped.is_set():
                self._inflight.release()
                return False
            truncated = self._recorder.is_window_truncated(self._window_seconds)
            self._thread_factory(target=self._preview, args=(audio, truncated), name="uri-dictation-preview-work", daemon=True).start()
            return True

    def _preview(self, audio, truncated: bool) -> None:
        try:
            text = cleanup_transcript(self._transcriber.transcribe_preview(audio), self._dictionary)
            if text and not self._stopped.is_set():
                self._panel.show_preview(("... " if truncated else "") + text)
        except Exception as exc:
            self._error_logger(exc)
        finally:
            self._inflight.release()


class SerializedProcessor:
    """Runs dictation work serially so clipboard use cannot overlap."""
    def __init__(self, process: Callable[[object, float], bool]) -> None:
        self._process = process
        self._items: queue.Queue[tuple[object, float] | None] = queue.Queue()
        self._thread = threading.Thread(target=self._run, name="uri-dictation-worker", daemon=True)
        self._thread.start()

    def submit(self, audio: object, audio_seconds: float) -> None:
        self._items.put((audio, audio_seconds))

    def stop(self) -> None:
        self._items.put(None)
        self._thread.join(timeout=2)

    def _run(self) -> None:
        while (item := self._items.get()) is not None:
            self._process(*item)


class DictationApp:
    def __init__(self) -> None:
        self.config = load_config(ROOT / "config.json")
        self.dictionary = load_dictionary(ROOT / "dictionary.json")
        self.recorder = MemoryRecorder()
        self.transcriber = WarmTranscriber(ROOT / "models" / "cache", self.config.language)
        self.clipboard = WindowsClipboard()
        self.key_sender = PynputKeySender()
        self._recording = False
        self._held: set[str] = set()
        self._hotkey_parts = {part.strip().lower() for part in self.config.hotkey.split("+") if part.strip()}
        self._pill = ListeningPill(self.recorder, self.config.waveform_enabled)
        self._preview_scheduler: PreviewScheduler | None = None
        self._icon = None
        self._listener = None
        self._polisher = Polisher(
            self.config.polish, self.config.polish_model, self.config.polish_timeout_s,
            self.config.polish_num_ctx, self.config.polish_keep_alive, self.config.polish_edge_model,
        )
        self.pipeline = DictationPipeline(
            self.transcriber, self.clipboard, self.key_sender, _TrayToast(self), self.dictionary,
            ROOT / "logs" / "timing.jsonl", polisher=self._polisher, error_logger=self._report_error,
            on_polishing=self._pill.show_polishing,
        )
        self._processor = SerializedProcessor(self._transcribe_and_paste)

    def _toast(self, message: str) -> None:
        if self._icon is not None:
            self._icon.notify(message, "URI Dictation")

    def _report_error(self, exc: BaseException) -> None:
        """Persist diagnostics without recording transcript or audio data."""
        path = ROOT / "logs" / "error.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            traceback.print_exception(type(exc), exc, exc.__traceback__, file=handle)
        self._toast("URI Dictation encountered an error")

    def _report_preview_error(self, exc: BaseException) -> None:
        """Preview failures are diagnostic-only and never expose transcript text."""
        path = ROOT / "logs" / "error.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            traceback.print_exception(type(exc), exc, exc.__traceback__, file=handle)

    def _show_pill(self) -> None:
        self._pill.show()

    def _hide_pill(self) -> None:
        self._pill.hide()

    def _toggle_polish(self, *_args) -> None:
        self._polisher.enabled = not self._polisher.enabled
        self.config = replace(self.config, polish=self._polisher.enabled)
        save_polish_enabled(ROOT / "config.json", self._polisher.enabled)
        if self._icon is not None:
            self._icon.title = self._tray_tooltip()

    def _tray_tooltip(self) -> str:
        polish = (self.config.polish_edge_model or self.config.polish_model) if self._polisher.enabled else "off"
        return f"URI Dictation - {self.transcriber.label} - polish: {polish}"

    def _start_recording(self) -> None:
        if self._recording:
            return
        self._recording = True
        try:
            self.recorder.start()
            if "win" in self._hotkey_parts:
                self.key_sender.mark_hotkey_pressed()
            self._show_pill()
            if getattr(getattr(self, "config", None), "preview_enabled", False):
                self._preview_scheduler = PreviewScheduler(
                    self.recorder, self.transcriber, self._pill, self.dictionary,
                    self.config.preview_interval_seconds, self.config.preview_window_seconds,
                    self._report_preview_error,
                )
                self._preview_scheduler.start()
        except Exception as exc:
            self._recording = False
            self._report_error(exc)
            self._toast(f"Microphone unavailable: {exc}")

    def _finish_recording(self) -> None:
        if not self._recording:
            return
        self._recording = False
        if self._preview_scheduler is not None:
            self._preview_scheduler.stop()
            self._preview_scheduler = None
        try:
            audio, audio_seconds = self.recorder.stop()
        except Exception as exc:
            self._report_error(exc)
            return
        if audio_seconds >= self.config.minimum_hold_seconds:
            self._pill.show_transcribing()
            self._processor.submit(audio, audio_seconds)
        else:
            self._hide_pill()

    def _transcribe_and_paste(self, audio: object, audio_seconds: float) -> bool:
        try:
            return self.pipeline.process(audio, audio_seconds)
        except Exception as exc:
            self._report_error(exc)
            return False
        finally:
            self._hide_pill()

    def _key_name(self, key) -> str:
        value = str(key).lower().removeprefix("key.").strip("'")
        if "ctrl" in value:
            return "ctrl"
        if "cmd" in value or "win" in value:
            return "win"
        return value

    def _on_press(self, key) -> None:
        self._held.add(self._key_name(key))
        if self._hotkey_parts.issubset(self._held):
            self._start_recording()

    def _on_release(self, key) -> None:
        self._held.discard(self._key_name(key))
        if self._recording and not self._hotkey_parts.issubset(self._held):
            self._finish_recording()

    def run(self) -> None:
        import pystray
        from PIL import Image, ImageDraw
        from pynput.keyboard import Listener
        image = Image.new("RGB", (64, 64), "#282828")
        ImageDraw.Draw(image).ellipse((16, 10, 48, 46), fill="#4fc3f7")
        self._icon = pystray.Icon(
            "uri_dictation", image, self._tray_tooltip(),
            menu=pystray.Menu(
                pystray.MenuItem("Polish", self._toggle_polish, checked=lambda _item: self._polisher.enabled),
                pystray.MenuItem("Quit", self._quit),
            ),
        )
        self._listener = Listener(on_press=self._on_press, on_release=self._on_release)
        self._listener.start()
        self._pill.start()
        threading.Thread(target=self._preload_model, daemon=True).start()
        self._icon.run()
        self._shutdown()

    def _quit(self, *_args) -> None:
        self._shutdown()
        if self._icon is not None:
            self._icon.stop()

    def _shutdown(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
        if self._preview_scheduler is not None:
            self._preview_scheduler.stop()
            self._preview_scheduler = None
        self._pill.stop()
        self._processor.stop()

    def _preload_model(self) -> None:
        try:
            self.transcriber.ensure_loaded()
        except Exception as exc:
            self._report_error(exc)
            self._toast("Dictation model could not be loaded")


class _TrayToast:
    def __init__(self, app: DictationApp) -> None:
        self._app = app
    def show(self, message: str) -> None:
        self._app._toast(message)


def _acquire_single_instance() -> bool:
    global _MUTEX
    _MUTEX = ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\URIDictationSingleInstance")
    return bool(_MUTEX) and ctypes.GetLastError() != 183


if __name__ == "__main__":
    if _acquire_single_instance():
        DictationApp().run()
