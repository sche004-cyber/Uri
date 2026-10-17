# URI Office: folders the owner allows (OD-R1): what was built and acceptance criteria

Owner decision OD-R1 (2026-10-16): configurable user-authorized folders on any drive (including D:), added explicitly,
folder-scoped, remembered, revocable and enforced consistently; no unrestricted access; traversal and symbolic-link
protections kept; a simple management UI. Finding UX-ROOT-1: Office opened files only under the user folder (M1 AC7),
so a file on D: was refused with "URI cannot use that location."

Branch `milestone/office-folder-access-20261016` from `d3b51d9e`, commit `ad9ef434`. To be merged onto the integrated
baseline before qualification (OD-A4).

## 1. Design

- `uri_office/grants.py`: allowed roots = the user folder (or `--allow-root`) plus the folders the owner added, kept in
  `state/folders.json` inside the user-only state folder and read back at start; a damaged list grants nothing extra.
- A folder is shape-checked like a file path: absolute local drive path; no network, device, stream or relative
  names; never a whole drive and never a system folder (Windows, Program Files, ProgramData); never through a
  junction or symbolic link. A folder inside an allowed one is already allowed; adding a parent replaces added
  children.
- Removal only for added folders, refused while a file from it is open or waiting to be saved (`FOLDER_IN_USE`).
- Every open and save-as grant checks the same roots (no second path).
- Service: `GET /folders`, `POST /folders/add`, `POST /folders/remove` (audited), behind the existing token, host and
  origin checks. Paths come from the owner's Windows folder dialog only.
- UI: "Folders" in the Office side bar and icon strip opens a dialog (list, Add folder..., Remove); the
  `PATH_REFUSED` message says where to allow the folder.

## 2. Acceptance criteria

| ID | Criterion | Evidence |
|---|---|---|
| FA-1 | A folder on another drive can be added; files in it open and save there; files outside every allowed folder are still refused | `tests/office/test_folder_access.py` |
| FA-2 | Drives, system folders, network/device/stream/relative paths, junctions and symbolic links are refused | tests |
| FA-3 | The list persists across restarts; a damaged list grants nothing extra | tests |
| FA-4 | Removal revokes access at once; refused while a file from it is in use (`FOLDER_IN_USE`) | tests |
| FA-5 | Routes refuse a bad token, host or origin; changes are audited | tests |
| FA-6 | UI: list, add (folder dialog), remove; refusal message points to Folders | `uri_ui/test/office/office_folders_test.dart` |
| FA-7 | Live: add a folder on D: through the real dialog, open and save a file there, remove it, the next open is refused | Stage 8 live journey |
| FA-8 | Independent review ACCEPT (or AwF) on the exact commit; gates pass | driver receipt |
