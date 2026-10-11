# SETTINGS-1: everything set up in the app, no .env (owner decision D28)

Owner, 2026-10-11: "I want everything front loaded, so later we will not keep a .env." Branch from the canonical tip
after IDN-1 and before LINK-REP-1 (LINK-REP-1 then only adds the URLhaus check behind the slot built here).

## What the owner sees
- **Settings > Security** (new file `uri_ui/lib/screens/settings/security_screen.dart`): key slots for Tavily
  (web search), URLhaus (scam check), Brave Search, and the SearXNG address. Save / Remove / Test per slot; after
  saving only "Key saved" is shown, never any characters (D27).
- **Settings > Connections** section in the same new screen (non-secret): Ollama address, model and timeout; Tesseract
  path; local model paths; Google credentials folder. Plain-word status per item ("Ollama: connected").
- First start after the update: any values still in `.env` are imported once, the owner is told in one line
  ("Moved 3 settings from .env into URI. You can delete .env."), and from then on URI never needs `.env`.

## How it is stored
- Secrets: the existing encrypted per-user store (`uri_core/core/provider_keys.py`, Fernet), extended to these slots.
- **Fix found while planning:** the launchers set a fixed default store password (`uri_local_dev_secret_key_v1`)
  when none is set, so anyone with the encrypted file and URI's code can decrypt it. Replace it with a random
  per-install secret protected by Windows DPAPI (stdlib `ctypes`, no new dependency), tied to the Windows user. On
  Linux/test, a random secret in a user-only file. A store written with the old default is re-encrypted once.
- Non-secret settings: the existing per-user settings store.
- Real environment variables still override, for developers and CI only; nothing requires them.

## Frozen files
- `uri_ui/lib/screens/settings/settings_shell.dart`: the one tab entry (approved, D26).
- If the key-save endpoint needs `uri_core/app/server.py`: ask the owner for that named exception at plan time;
  otherwise use existing provider-key endpoints.

## Acceptance criteria (draft)
| # | Criterion |
|---|---|
| S-AC1 | With no `.env` file at all, every feature that has its setting saved in the app works. |
| S-AC2 | Existing `.env` values are imported once on first start, the owner is told in one plain line, and the import never repeats or overwrites a value saved in the app. |
| S-AC3 | No key is ever shown (not even partly), logged, or included in reports, events or A2UI output; only "Key saved". |
| S-AC4 | The fixed default store password is gone; a store encrypted with it is re-encrypted with the per-install secret; a copied store file cannot be decrypted on another machine or Windows user (DPAPI test on the PC: NOT VERIFIED until run there). |
| S-AC5 | Removing a slot clears it; Test reports a plain result; status lines use plain words (D18). |
| S-AC6 | Only the approved frozen line changes (driver protected-path check). Each new test fails on the pre-change commit. |
