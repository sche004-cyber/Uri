# Camera, voice and Gemma environment evidence — 2026-10-04

Stage 1 snapshot, recorded before implementation. Direct User request grants
Codex bounded implementation authority for this initiative; no release authority,
independent audit, freeze or unrelated milestone advancement is implied.

Branch `codex/antigravity-harness-recon`, HEAD `62d564cf9d2fa25e5a9860d20dcc7070b112badb`.
The worktree contains extensive pre-existing changes, preserved.

* D: capacity 1,000,185,262,080 bytes; free 697,975,984,128 bytes.
  Existing Camera 1 recordings: 13 segments, 3,133,081,993 bytes. Even crediting
  these against decimal 700 GB leaves 1,109,066,121 bytes for headroom. A
  conservative 20 GB free-space margin is not sustainable. Binary 700 GiB
  is also infeasible. Storage configuration and new recording are STOPPED.
* Existing recorder: `D:\Camera\Tapo_C210_Windows_Recorder\tapo_recorder`.
  Credentials are Windows DPAPI PSCredential XML; no secrets copied or printed.
  Its config has Camera 1 only, 350 GB **total**, 14 days. Shared `stop.flag`,
  timestamp-based active-file protection and startup-only shared cleanup do
  not satisfy independent ownership, caps or control. Existing scripts not run.
* Camera 1 192.168.1.5:554: authenticated ffprobe returned H.264 2304x1296
  and pcm_alaw audio. A latest existing segment has readable H.264 and duration
  3247.874767 seconds. No ffmpeg recorder process is running.
* Bounded TCP/554 discovery across 192.168.1.1–254 found only Camera 1.
  User subsequently identifies Camera 2 as 192.168.1.11. Direct ping succeeds
  (3 ms); TCP/554 connection fails. Wi-Fi on the PC is unnecessary for this
  same-router connection. Camera model/RTSP enablement and path remain unknown.
* Existing speech adapter `uri_core/core/edge/adapters/speech.py` is a
  benchmark adapter, not an always-on desktop voice integration. Global Python
  lacks sounddevice/vosk/faster-whisper/pyttsx3. Windows System.Speech has
  `MS-1033-80-DESK` en-US and opens the default Sennheiser microphone.
* LM Studio server is running on 1234, Gemma `google/gemma-4-26b-a4b-qat`
  loaded, 16384 context, 15.63 GB model. Existing OpenAICompatibleProvider
  request rejects absent credentials with ProviderAuthenticationError (~0.04s).
  No provider key/config files found in this checkout's user directories.
  No credential scraping, auth bypass, provider substitution or speculative download.
* Existing launcher expects a Release desktop build; initially only Debug
  exists. URIServer scheduled task targets protected legacy `uri-agent`, not
  this checkout. Port 8000 health unavailable. Release build attempted.

Audio device enumeration and recognizer initialization are **not** proof of
wake recognition, command transcription or audible speaker output. Provider
availability is **not** canonical Brain/UI acceptance.
