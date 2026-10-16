# UI-V2-POSTINT — receipts branch and legacy runtime review (2026-10-16)

Read-only investigation, except the owner-authorised push of the receipts branch. Nothing was disabled, deleted,
stopped or reconfigured.

## Receipts branch `receipts/ui-v2-20261016`

| Check | Result |
|---|---|
| Commit | `74044f771dc842c79158278f691f08739f2df0d3`, parent `2eff03d0` (the integrated canonical commit) |
| Scope | 5 added files, all under `docs/ui_v2/completion/integration/`; nothing else changed |
| Integrity | all 5 files parse as JSON; `driver_receipt_UI-V2-COMPLETION-r2.json` sha256 `841e5d97…` equals the driver's `receipt.json`; `UI-V2-COMPLETION-r2-authorized.json` sha256 `0224bf12…` equals the config hash bound in the event chain (OWNER_UNBLOCK seq 16 and 20) |
| Provenance | the driver state `uri-ui-v2c-run/lifecycle/r2` verifies (`lifecycle verify`: ok, no errors; 26 events) |
| Push (owner-authorised 2026-10-16) | `git push uri-repo 74044f77…:refs/heads/receipts/ui-v2-20261016` → `* [new branch]`; `ls-remote` shows `74044f77…`; canonical `integration/git-sync-20261008` still `2eff03d0…` (unchanged) |

The existing receipts were not rewritten.

## Legacy scheduled task `\URIServer`

Evidence collected 2026-10-16 (task query, process and port checks), consistent with
`uri-fcv-recovery-20261014/LEGACY_ISOLATION_RECORD_20261015.md`:

| Question | Finding |
|---|---|
| What does it run? | `cmd.exe /c "C:\Users\cheta\Development\uri-agent\.venv\Scripts\python.exe" "…\uri-agent\scripts\run_uri_server.py" --port 8000 >> …\uri_workspace\logs\uri_server.log`, start in `C:\Users\cheta\Development\uri-agent` (branch `master` @ `e8e3b652`, legacy `uri_core.app.server`), trigger: at logon of `cheta`, InteractiveToken. Its `uri_core/tools/fetch_url.py` is the pre-SSRF blob `f0970062…`. |
| Is it running? | No. State `Ready`, last run 15-10-2026 08:54:15, last result -1 (stopped during FCV-R isolation); nothing listens on 127.0.0.1:8000. It **will start again at the next logon** while enabled. |
| Does active URI functionality depend on it? | No. The integrated UI V2 path (production `main()` with a client manifest) uses the paired runtime and the integrated worker on its own ports (18300–18339; this run 18301). The classic interface inside the working system refuses the legacy address (`LegacyServerBlocked`, `uri_ui/lib/main.dart`). The live qualification harness never contacts port 8000. |
| What replaced it? | The working-system installation (`scripts/ws_provision.py` + paired Core + `run_uri_integrated_worker.py`), launched per installation; `scripts/launch_uri_working_system.ps1` "never stops, reconfigures or contacts the legacy instance, the scheduled task \URIServer". No production launcher for the new runtime is authorised yet (that would be a cutover). |
| Would disabling it interrupt current URI operation? | Not the qualified working system. It would stop the legacy dev server from starting at logon, which only the older `_V1` launchers (`Launch URI Harness.bat`, `Launch URI Voice.bat` → `_V1\scripts\launch_uri.ps1`) expect: they `Start-ScheduledTask URIServer` when port 8000 is unhealthy, and re-install the task **only when it is missing**. Disabled, `Start-ScheduledTask` fails ("The task is disabled"), so those legacy launchers would report that the backend did not start. |

Recommendation (needs separate owner approval, elevated): disable, do not delete (deleting re-opens the `_V1`
re-install branch):

```powershell
Disable-ScheduledTask -TaskPath '\' -TaskName 'URIServer'
(Get-ScheduledTask -TaskName URIServer).State   # expect: Disabled
```

Undo: `Enable-ScheduledTask -TaskPath '\' -TaskName 'URIServer'`. The task XML backup from 2026-10-15 is in
`C:\Users\cheta\Development\uri-canonical-evidence\containment_20261015_legacy_isolation\URIServer.xml`.

## Other URI installations and executable copies

| Item | Risk to runtime qualification | Proposal |
|---|---|---|
| `URI.lnk` in the Start menu and on the OneDrive desktop → `uri-m37-m39-integration\Launch URI.bat` (branch `experimental/desktop-recovery-repair` @ `eb736933`) | A manual click starts its own server on port 8000 with the pre-SSRF `fetch_url.py`. It does not touch the task. | Owner decision: move both shortcuts to a backup folder (`uri_containment.ps1` C-2) or keep. |
| Built `uri_ui.exe` copies in 13 worktrees (`uri-agent` Debug 2026-09-17 / Release 2026-09-29, `uri-ui-v2*`, `uri-fire-companion*`, `uri-office-u2-a`, `uri-ui-v2c`) | None for this qualification: `run_live_ui.py` builds and runs the candidate's own Debug binary from `uri-ui-v2p` and records its sha256; `live_session.py` samples only the candidate's `uri_ui.exe` path. A manually started older binary could hold the GPU or port; the harness waits for a FREE lease and asserts its port is unused. | Keep (other workstreams' evidence). Deletion not proposed. |
| `%APPDATA%\com.example\uri_ui\shared_preferences.json` (`serverBaseUrl = http://127.0.0.1:8000`) | None: the harness redirects APPDATA/LOCALAPPDATA to `fixtures/`; the working system blocks the legacy address. | Keep (owner data). |
| `C:\Users\cheta\AppData\Local\URI\` (engines, gpu, models, office, voice, desktop secrets) | Shared machine state used by current components (GPU lease, models). | Keep. |

No installation, user data or configuration was deleted or changed.
