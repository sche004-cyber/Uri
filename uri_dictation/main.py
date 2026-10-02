"""URI Dictation standalone Windows entry point."""
from __future__ import annotations
import ctypes
import queue
import threading
import traceback
from pathlib import Path
from typing import Callable
from config import load_config, load_dictionary
from pipeline import DictationPipeline
from platform_io import PynputKeySender, WindowsClipboard
from recording import MemoryRecorder
from transcriber import WarmTranscriber

ROOT = Path(__file__).resolve().parent
_MUTEX = None


class ListeningPill:
    """Owns all Tk state on one dedicated UI thread."""
    def __init__(self) -> None:
        self._commands: queue.Queue[bool | None] = queue.Queue()
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, name="uri-dictation-ui", daemon=True)

    def start(self) -> None:
        self._thread.start()
        self._ready.wait()

    def show(self) -> None:
        self._commands.put(True)

    def hide(self) -> None:
        self._commands.put(False)

    def stop(self) -> None:
        self._commands.put(None)
        self._thread.join(timeout=2)

    def _run(self) -> None:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        pill = None
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
                if command and pill is None:
                    pill = tk.Toplevel(root)
                    pill.overrideredirect(True)
                    pill.attributes("-topmost", True)
                    pill.attributes("-alpha", 0.9)
                    tk.Label(pill, text="  Listening...  ", bg="#262626", fg="white", font=("Segoe UI", 11, "bold")).pack(padx=8, pady=5)
                    pill.geometry("+40+40")
                elif not command and pill is not None:
                    pill.destroy()
                    pill = None
            root.after(25, poll)
        self._ready.set()
        root.after(0, poll)
        root.mainloop()


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
        self._pill = ListeningPill()
        self._icon = None
        self._listener = None
        self.pipeline = DictationPipeline(self.transcriber, self.clipboard, self.key_sender, _TrayToast(self), self.dictionary, ROOT / "logs" / "timing.jsonl", error_logger=self._report_error)
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

    def _show_pill(self) -> None:
        self._pill.show()

    def _hide_pill(self) -> None:
        self._pill.hide()

    def _start_recording(self) -> None:
        if self._recording:
            return
        self._recording = True
        try:
            self.recorder.start()
            if "win" in self._hotkey_parts:
                self.key_sender.mark_hotkey_pressed()
            self._show_pill()
        except Exception as exc:
            self._recording = False
            self._report_error(exc)
            self._toast(f"Microphone unavailable: {exc}")

    def _finish_recording(self) -> None:
        if not self._recording:
            return
        self._recording = False
        self._hide_pill()
        try:
            audio, audio_seconds = self.recorder.stop()
        except Exception as exc:
            self._report_error(exc)
            return
        if audio_seconds >= self.config.minimum_hold_seconds:
            self._processor.submit(audio, audio_seconds)

    def _transcribe_and_paste(self, audio: object, audio_seconds: float) -> bool:
        try:
            return self.pipeline.process(audio, audio_seconds)
        except Exception as exc:
            self._report_error(exc)
            return False

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
        self._icon = pystray.Icon("uri_dictation", image, f"URI Dictation - {self.transcriber.label}", menu=pystray.Menu(pystray.MenuItem("Quit", self._quit)))
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
