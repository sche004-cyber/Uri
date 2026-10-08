# URI Phase 1 — Preservation Manifest

Date: 2026-10-05. Scope: preservation and architecture preparation only. This records backup validation, not milestone acceptance or functional qualification of donor implementations.

## Preserved installation and recovery boundary

Protected vault: `D:\URI-preservation\phase1-20261005-0037`, outside URI repositories. NTFS inheritance is disabled at the vault root; only the current Windows developer account and SYSTEM have FullControl. Child archives, recovery tooling and restore probes inherit that restriction. The backup includes secret-bearing files, but this report contains no credentials, database records or private transcripts.

Each archive uses AES-256-GCM authenticated 4 MiB frames with authenticated ordering and termination. A random key is wrapped using Windows current-user DPAPI in `key.dpapi`; it is never written in plaintext. Per-file SHA-256 values, exact private filenames and dirty patches are inside encrypted archive manifests. The table below publishes ciphertext hashes, safe aggregate counts and source-root identities. The vault also contains protected plaintext recovery probes, Git bundle/mirror and deployment staging; ACLs protect those copies. The vault is not entirely encrypted at rest.

Recovery was exercised under this Windows account. **This is not an independently portable disaster-recovery copy.** Losing the Windows profile/DPAPI recovery material can make encrypted archives and native credentials inaccessible. Preserve the current account/profile and D: drive. A separately approved portable key escrow/off-device backup would be needed for machine-loss recovery; none was silently created.

## Worktrees and Git state

| Archive | Original Git root | HEAD | Branch/state |
|---|---|---|---|
| worktree-00 | `C:/Users/cheta/Development/uri-agent` | `e8e3b65259c45fc823addc3ef8969425a265bd1b` | `refs/heads/master` |
| worktree-01 | `C:/Users/cheta/.codex/worktrees/batch-audit-canonical/_V1` | `62d564cf9d2fa25e5a9860d20dcc7070b112badb` | `refs/heads/codex/m36-m38-canonical-audit` |
| worktree-02 | `C:/Users/cheta/.codex/worktrees/harness-connections-console/_V1` | `62d564cf9d2fa25e5a9860d20dcc7070b112badb` | `refs/heads/codex/harness-connections-console` |
| worktree-03 | `C:/Users/cheta/.codex/worktrees/intent-discovery/_V1` | `62d564cf9d2fa25e5a9860d20dcc7070b112badb` | `detached` |
| worktree-04 | `C:/Users/cheta/.codex/worktrees/m33-audit-baseline/_V1` | `c2f583909a3d13d295c997c038b0ac724f787755` | `detached` |
| worktree-05 | `C:/Users/cheta/.codex/worktrees/m33-audit-candidate/_V1` | `d1feaf72f7b1322fe30cc21e2808d5eab09bcdf4` | `detached` |
| worktree-06 | `C:/Users/cheta/Development/Uri/_V1` | `62d564cf9d2fa25e5a9860d20dcc7070b112badb` | `refs/heads/codex/antigravity-harness-recon` |
| worktree-07 | `C:/Users/cheta/Development/uri-agent/.tmp_m33_1_batch4_baseline_5973f6d` | `5973f6db5e9b41b7c13d4e8da97cdaf244d4d237` | `detached` |
| worktree-08 | `C:/Users/cheta/Development/uri-batch-candidate` | `a87e15867bb697cf5cb306559d220e897518a4ff` | `refs/heads/candidate-m36-m37-m38` |
| worktree-09 | `C:/Users/cheta/Development/uri-dictation` | `f1e13e94679d0cd08f6a216d7824a3a3b92120cf` | `refs/heads/feature/uri-dictation` |
| worktree-10 | `C:/Users/cheta/Development/uri-m37-m39-integration` | `eb7369331e8c2ed7c7a8ea85db9ce1382fe3913f` | `refs/heads/experimental/desktop-recovery-repair` |
| worktree-11 | `C:/Users/cheta/Development/Uri_edge_experiments` | `e0950d401c10fd028c2d6dda2b08ef2f82219582` | `refs/heads/claude/project-thread-gb7z7s` |

Each original worktree archive includes the working directory's file bytes, including ignored application data/build outputs and untracked files, plus saved HEAD/branch, porcelain status, staged and unstaged binary patches, tracked list and untracked list. Main's nested M33 baseline was captured independently. Common Git administration, objects, refs, indexes, hooks/config and registered-worktree metadata are separately encrypted. A standalone Git bundle includes all refs and each detached HEAD; it was verified, cloned as an independent mirror and checked with `git fsck --full` and object lookup for every original HEAD.

Do not restore raw Git administrative files over the active repository. Restore to new paths using the independent mirror/bundle and saved identities, then reconstruct staged/unstaged changes and untracked files. The raw metadata is preservation evidence for index/ref/worktree recovery; it is not a portable worktree registration transplant. `git worktree add` in a future recovery must bind the new paths explicitly. Dirty patches were replayed in vault-only standalone clones of the main and shortcut-targeted integration checkpoints.

## Archive catalogue and hashes

| Archive label | Files | Source bytes | Ciphertext bytes | Ciphertext SHA-256 |
|---|---:|---:|---:|---|
| worktree-00 | 20,648 | 4,555,218,024 | 1,963,966,384 | `441054467d945c1f729708b8f2d4c279f7add468ba0a7905a0bda0b405423b90` |
| worktree-01 | 1,446 | 88,093,681 | 20,121,894 | `af1b3f20be3b8cd00b3271485c45c3b09d963b82d601ceb280f209a9fe473954` |
| worktree-02 | 1,804 | 932,414,636 | 275,236,741 | `bc59009905b34fcaa0105d86392c33635f7df6312e86f6735e0f544de4f26891` |
| worktree-03 | 1,414 | 353,702,901 | 112,221,899 | `bd703c4638dce61f10eb417edaad4c33ce4f89d0a3aff9e64a5c896db983e5aa` |
| worktree-04 | 1,234 | 80,119,290 | 18,419,217 | `8a83e5d554151b5a79f64927c6b0b91d38de310fe17b895fad391900c98bf661` |
| worktree-05 | 1,345 | 138,133,396 | 38,624,983 | `7bd2e197b6af71a23763f85d911d050051a3a4b3eb9750ad0d25c1972e355748` |
| worktree-06 | 6,861 | 1,462,995,757 | 428,142,662 | `f75293a7459fe7c0df272aaf434616693998db4b406d004e743a8640a45416b8` |
| worktree-07 | 947 | 21,122,861 | 13,802,692 | `b2918de166e71c2e2d5c71b02f026338fa96fbe0b49daa6015e73fb1241e1ced` |
| worktree-08 | 1,438 | 87,935,282 | 20,094,037 | `ea994330812449d063e2cbe5401cb938433544191d80a922f25868e0dd4121d4` |
| worktree-09 | 5,680 | 1,355,240,520 | 1,032,473,628 | `90afc53fd2a32ab6fac9be731e7c9c832d99576f3fc61d92a24d4c25fce48b17` |
| worktree-10 | 2,645 | 994,220,965 | 293,517,322 | `90c7cbae8c29a99c81dda61dcc91f7fb5df5da9b841766637868da7e04bd8d43` |
| worktree-11 | 1,427 | 99,053,363 | 21,617,073 | `bce86d2fb27e6f8472ed93b9897becc6e9b070660132e9b8fc7fd2d09eec13b2` |
| git-common | 921 | 31,988,520 | 29,185,031 | `176fe1699df09734325ca76fd02a8e759d8364f6b6a814f03f4ddd41250ba99b` |
| git-bundle | 1 | 21,627,902 | 21,552,376 | `4a5c884eff4d2fc8e46cac587bf9ec4bd9d9720e06cbd93444f321174420046c` |
| claude-profile | 8,000 | 671,467,248 | 263,654,337 | `b43f8580f1d34147cc954bc068adcd05efb855117a6ae18155b58661adc2aeb4` |
| claude-config | 1 | 72,111 | 23,668 | `9e17636648d4f247a1543f22b9df73f0eef5af6f6bee131a9eb9caef9f8a3b8e` |
| codex-config | 63 | 304,187,386 | 75,472,835 | `5a30dad1b87b0d099accb559a1eca2fc65280c93ef64d8dcc1312a0b067e041f` |
| antigravity-profile | 3,149 | 395,124,891 | 60,983,370 | `f800225203caa90aa4a17b15b337fa19caa765893e361a90869477666b3a0fa2` |
| antigravity-app | 44 | 1,660,563 | 63,342 | `f5a7b93da06215d08f18b190d360cc6e449d5be02ca21717189262403a132a66` |
| antigravity-ide-app | 425 | 90,929,306 | 4,743,895 | `1c47310cd5c59f3505954e3c3f1da3e0b90759f27fd5e01d6eba4d2e4b635fd2` |
| gemini-profile | 5,966 | 902,129,854 | 257,306,028 | `ec127f5c8288dbeb24bc3c4abe2f26797059bf9e4256d4678457809760acedfe` |
| uri-localappdata | 35 | 147,774,085 | 134,517,149 | `def99b8fabaf5de4a27ea038947763fd341a8313231f3813d4927d14ec61fe62` |
| uri-client-prefs | 1 | 1,001 | 1,042 | `2414d08b405b8fad749b94226cae00a0ebbeb39f6d22548364847a64b542cf05` |
| uri-models | 1 | 35,335,380 | 33,624,894 | `28723145cd2febe166603183485ad44cf6bcb51a22b3e3fc87aa62364ebf8a30` |
| deployment | 4 | 6,295 | 2,890 | `191f090c09ffd37e8baf67f9f9ddc93112cf7c3742c5b80b46d956ba1dd2f975` |
| ollama-installation | 66 | 30,343,176,896 | 30,343,466,336 | `0badb668dc046e352d5bd57c8fdb11085b0cd666002bfea32247be0ca5bd2798` |
| lmstudio-installation | 3,523 | 41,975,076,209 | 41,982,551,596 | `ff33a9cae6e155f6c8125f80cc097b3c9378e5726342153de803ed88ccf7f9f1` |
| materialized-link-000 | 1 | 2,370 | 10,296 | `ed9d0ab1592eef2f5c02e5bcc934dba83bccbf4011a7d88a62b5d4b12c7c1d58` |
| materialized-link-001 | 1 | 483,546,902 | 483,555,636 | `3871a98923635afce3864d492430da41c1b560433cd0dffe3cbb64499c1bdce9` |
| materialized-link-002 | 1 | 2,203,239 | 2,211,896 | `adec0be61571c7c4fcbfbf5115b260b7ce955147d8c1c7b693c5453b0f14a00d` |
| materialized-link-003 | 1 | 459,861 | 471,096 | `0c76912d714bdf86cf88c93c277b907298c3a0a74bac2dd6f66d49e87e80c353` |
| materialized-link-004 | 1 | 483,546,902 | 483,555,636 | `0cc7b278dfacfcd3c8a833f83fb5b088f875727a9f2f1a9b0fb5402d8d3d031c` |
| materialized-link-005 | 1 | 2,370 | 10,296 | `6225d1601e9ce2d28bbec3b827bb62ac5f4c8808127c97caa2962471acba6c0d` |
| materialized-link-006 | 1 | 483,546,902 | 483,555,636 | `e50070e944e9373ef38bde789b5ff8a469efac6315db826d06254558207ff5d0` |
| materialized-link-007 | 1 | 2,203,239 | 2,211,896 | `b7e80e0e8943e8286806f41b7653dc2d7453784960f2b1375a2c0076beb35e51` |
| materialized-link-008 | 1 | 459,861 | 471,096 | `0e47293f3004d806bbe14f72c66abfa81fd3305afbe115612216fc9074b71594` |
| materialized-link-009 | 1 | 17,237 | 30,776 | `3c0a0e3d15692a9ca237b8bf81e10bbecd18e9740d25b7b4ea32c831d4d72b46` |
| external-reparse-target-000 | 36 | 121,518 | 194,616 | `b3366c1a26c16967935cab3046b7993afdf4346213e7454a3f7d798c5721fba1` |
| external-reparse-target-001 | 11 | 21,199 | 51,256 | `3211a403dd5875a5a26a10e24545fa5a1d411c5f9b837f4e0755487edce4d244` |
| external-reparse-target-002 | 33 | 134,897 | 204,856 | `f71176b9784cd251795605219de9bf0c09cb0ddb93136c6d76924d3499e7397c` |
| external-reparse-target-003 | 41 | 126,118 | 215,096 | `5c73ff8170d759a39a2e095535f343980304c696c20c46030d8d6f71f9a18c70` |
| external-reparse-target-004 | 12 | 34,228 | 61,496 | `c6b2fdcdcc1ccd447c955cf8886313ce8476cefa76423c241c13c9347b3bf980` |
| external-reparse-target-005 | 95 | 726,533 | 921,656 | `8681fe73ffa98791b03512d492fdf0a03b9dff6b38892686623eccdcd7d786dc` |
| reparse-map | 0 | 0 | 2,299 | `94cd2aa1b51d432f71c85b2217e4b84bead5749f1d3717081f95f719d9fb5ae8` |
| scheduler-prototype | 169 | 569,513 | 365,549 | `686fe1899189d24e9eb33c8da5a4642e0fb91808f28ad0963a946915948d7f35` |
| qwen-scheduler-benchmark | 185 | 368,648 | 219,560 | `2e581f53bb523ef07724f975562cd3be548e4fbda08c739eb9276355e82ea9d6` |
| readiness-audit | 31 | 1,656,915 | 444,221 | `f574ea883b54d7f296f25d9b9d7362e10e18ef905bb82b124fa5d2ce1e355ad0` |
| extra-link-target-000 | 22 | 37,452 | 16,512 | `4d09bc92f0284d107f37f7e2a2b6fcfcee4da03e6b04824dd9f1db524507ef92` |
| extra-link-target-001 | 20 | 73,873 | 20,218 | `c880cae95947ddd4c8b4077677104129ed0cf9da689ef3b367e00538f8e4ed85` |
| extra-link-target-002 | 36 | 121,518 | 48,924 | `eab8fcdf74daadbc638f98bb9dbb5db28780159fce049600532da76b0823fd1c` |
| extra-link-target-003 | 33 | 134,897 | 45,741 | `d6d57b67f5750ac805ee50464f73993daf310120eb6040f79303fa82dacb0286` |
| extra-link-map | 0 | 0 | 607 | `187cc068b525f73d7d22c9c5e26e3790ae2aadbdfc853f2add0a011601e860d9` |

Source bytes and file counts can overlap: separate snapshots intentionally preserve related roots, reparse targets and Git history independently. Ciphertext hashes prove archive byte identity, not functionality. File manifests and authenticated read-back establish byte recoverability.

Critical recovery helpers are hashed separately below. A complete copied-runtime hash list is stored privately as `RECOVERY_HASHES.json`; final report/package hashes are recorded in `PACKAGE.json` after report finalization. The DPAPI file hash identifies the wrapped key bytes and does not expose the AES key.

The final recovery toolkit and final reports are additionally encrypted and read-back checked after these report hashes are finalized. Their ciphertext hashes are recorded in `PACKAGE.json`; these two supporting archives are separate from the payload catalogue/totals below to avoid a self-referential report hash.

| Recovery artifact relative to vault | SHA-256 |
|---|---|
| `key.dpapi` | `666cfd0531925214b984453c6598f1a22751da3ce1ca02e1fe61129bb45506d1` |
| `preserve.py` | `d4f8c3ea6e1354f3e3685dafe5415462a1d90921290dd15e9cddb9494a653369` |
| `preserve_models.py` | `4cbef451d1cd8ae01718225f3430beaa76d429900aff6a03cc78a1870703e81b` |
| `verify_final.py` | `3faa477a5973ce56a10b7c437e65ced9e5dbe1553e8002ed58b5968a7e67dc27` |
| `audit_coverage.py` | `47ac1c3671915db640231f65e7a4b40585c0c1c7b34e77277d9b8aae438c20e6` |
| `RESTORE_README.md` | `146ac9bc4fdb697e78a122e52b70cf60eb2e8803fcb8477d1eb696b14a025d6f` |
| `recovery-runtime/Python/python.exe` | `85b71d8c6ec1905935f74be0c9869aae198d00e98f39df699ec66f9c5a84cecd` |

## Native state, credentials, deployment and models

Preserved account roots include `.claude`, `.claude.json`, top-level `.codex` configuration/authentication files, `.gemini`, `.antigravity`, Antigravity/Antigravity IDE application configuration, URI LocalAppData, shared Flutter preferences and the discovered URI model root. The twelve repository worktrees include their private workspaces, SQLite databases, environment/configuration files, virtual environments and qualified milestone artifacts. Codex's complete unrelated session/cache history was not copied; URI worktrees and the identified account/configuration files were.

Full Ollama and LM Studio installation/model roots are preserved without changing model selection or loading any model. Existing empty/incomplete model artifacts are retained as found; backup success does not make them usable. Symlink files are materialized into supplemental archives with source/target metadata; directory reparse mappings and targets are recorded separately. Restore links only after confirming the destination and ownership; a restored regular file is not automatically equivalent to a live symlink.

Separate roots `C:\Users\cheta\Development\scheduler_proto`, `qwen_scheduler_benchmark` and `URI_readiness_audit_2026-09-30` are additionally captured, including their source/untracked files and any independent Git administration. These are preservation-only development/evidence donors, not part of the authoritative Core. They are fully restored into vault-only probes and hash checked; independent repositories are fsck checked there.

`deployment` preserves copies of both URI shortcuts, exported `URIServer` task XML and relevant URI/provider/harness User/Machine environment entries in a private file. It does not install or re-register any task. Credential Manager, TPM/browser account secrets, process-only environment secrets, remote account recovery and credentials outside discovered roots are not independently proven recoverable. Native authentication may still require reauthorization after profile/machine changes. No preserved credential was provisioned into the new worktree.

This is a URI source/state preservation package, not a full Windows image. System-wide Flutter SDK, native Claude/Codex/Antigravity desktop/CLI executables, OS services and third-party installers are inventoried dependencies rather than complete installation backups. URI's local build outputs and virtual-environment files inside the captured worktrees are retained; matching external tools may still need reinstatement in a future recovery. The copied Python/cryptography verifier is the independently exercised recovery runtime.

Generated `__pycache__` directories and specified native `Cache`, `GPUCache` and `Code Cache` trees were omitted. Main `.git` and the separately archived nested baseline are intentional separate captures. File/directory link coverage and any access-denied or absent-file exceptions are summarized below. Application data and source are not classified as expendable merely because Git ignores them.

## Executed recovery and integrity checks

- 52 payload archives authenticated and every archived file hash checked: 69,823 file entries, 86,548,924,515 source bytes. Zero observed source-file changes during these captures.
- All 12 original Git HEADs present in the verified independent bundle/mirror; mirror fsck passed.
- Full file restore and post-restore hashing passed for main (worktree-00) and desktop integration (worktree-10); native Claude configuration and Flutter preferences also restored and checked.
- 343 restored SQLite files passed integrity checking; 0 failed. No private table contents reported.
- Staged/unstaged binary patches applied successfully in fresh vault-only clones for main and integration. These checks exercise dirty-change reconstruction without modifying source checkouts.
- Recorded tracked/untracked file coverage: zero uncovered existing files and zero access-denied exclusions. Saved status covers deleted/absent paths (1 recorded path entries); bytecode caches are intentionally excluded.
- Supplemental link preservation: 10 materialized file links, 79 recorded directory reparse links and 6 independently archived external directory targets.
- Deliberate ciphertext alteration in memory was rejected by GCM authentication; the original archive was unchanged.
- Missing wrapped-key guard exercised in a vault-only test fixture: verification refuses to create a replacement key when encrypted archives exist.
- 25 additional model/link/prototype source archives matched fresh strict file-count/byte-count enumeration; zero unaccounted existing files or directory enumeration errors.
- Copied recovery interpreter successfully authenticated an archive under isolated Python flags, using only the copied verifier dependencies.
- Original main/integration Python, Dart and launcher files compared against restored bytes: worktree-00: 8,944 files, 0 differences, worktree-10: 876 files, 0 differences.
- Both original desktop/Start Menu shortcut hashes match their preserved copies. No shortcuts/tasks/services were replaced. Task export and relevant environment entries remain protected private preservation files.
- Separate scheduler prototypes and readiness-audit artifacts captured and fully restored/hash checked; 0 independent Git repositories additionally passed fsck in restored roots. Extra roots have 4 directory link mappings and 4 independently archived targets.
- Desktop-URI.lnk SHA-256: `635636716c35a050f8230776b135a74df6a0326f169f5210cd6b93459b6d65bf`.
- StartMenu-URI.lnk SHA-256: `bf809eb8170a732d86f9d1b69530b42b5b63ead0fd471f7d5e3256e3c150f5e9`.

SQLite checks used restored copies only, never original private databases. Whole application recovery, model inference, native subscription authentication, UI behavior and live RAR/ARN/Graphify qualification were not run. Recoverable bytes are distinct from working functionality.

Copies were captured without stopping services or using VSS. Per-file size/mtime checks detect observed changes during capture, but cannot establish an atomic cross-file/database transaction snapshot. Database/WAL/SHM/journal sidecars were copied with their workspace; passing integrity checks on restored copies is evidence for those copies, not proof of every live logical transaction. Future migration needs a separately authorized quiescent snapshot or supported online-backup procedure and logical checks.

## Restore procedure

1. Work under the same authorized Windows account and retain `key.dpapi`, the archives, `preserve.py` and `recovery-runtime`. Check the vault ACL before decrypting. Compare selected archive SHA-256 with the catalogue before restore.
2. Run the copied interpreter, which was successfully exercised without importing application code or depending on a repository virtual environment:

   ```powershell
   & 'D:\URI-preservation\phase1-20261005-0037\recovery-runtime\Python\python.exe' -I -S -B 'D:\URI-preservation\phase1-20261005-0037\preserve.py' worktree-01
   ```

   This authenticates/decrypts in memory and checks every archived file against its encrypted manifest; it does not restore into an installation.
3. To restore an archive not already probed, append `--restore`. It writes only to a new `vault\restore-probe\<label>` and refuses an existing destination. A preexisting probe requires a separately reviewed new restore destination; do not delete or overwrite it to bypass that guard. Consult the vault's `RESTORE_README.md` for the framing and fresh-destination procedure.
4. Use the verified bundle/mirror to reconstruct a new checkout at its saved full HEAD. Apply staged binary patch to the index, then unstaged patch; copy preserved untracked/ignored files and compare their private hashes. Preserve deletion/rename entries from saved status. Restore file/reparse mappings deliberately. Keep Git administration, destination paths and account profiles separate from active installations.
5. Recover an entire database family and its matching sidecars into a new private client workspace. Check SQLite integrity and logical ownership there. Do not overlay current data or run application startup against the restored source until it is scoped and authorized.
6. Restore native credentials only into the appropriate client/account through supported protected storage/profile recovery. Never put credentials in Git, reports or the server's shared state. Restored `.venv` files, native binaries and shortcuts may contain absolute paths and are not automatically relocatable; the copied backup verifier is the exercised recovery dependency.

No recovery procedure authorizes production data migration, shortcut replacement, service restart or donor-code promotion.

## Isolated integration environment

App-managed Git root: `C:\Users\cheta\.codex\worktrees\uri-phase1-integration\uri-agent`.

App workspace root: `C:\Users\cheta\.codex\worktrees\uri-phase1-integration\uri-agent\2026-10-05\uri-phase-0-runtime-inventory-and`.

Confirmed HEAD: `e8e3b65259c45fc823addc3ef8969425a265bd1b`; detached, with clean `git status --short` at preparation check. This is the accepted Core source anchor, not the dirty desktop integration composition. Creating it necessarily updated Git worktree administrative registration; it did not alter existing checkout files. No dependencies installed, application imports, server/model launches, credential copies or production code edits were performed in it. Future synthetic state roots and opt-in development launcher are design work, not existing runtime configuration.

## Scope limits and next step

The authoritative Core recommendation remains the accepted checkpoint; all dirty/master/V1/integration/Edge/dictation sources remain separate preserved donors. The architecture package is [Ownership](SERVER_CLIENT_OWNERSHIP.md), [Interface plan](SERVER_CLIENT_INTERFACE_PLAN.md), [Launcher plan](LAUNCHER_CONSOLIDATION_PLAN.md) and [Implementation plan](PHASE1_IMPLEMENTATION_PLAN.md).

The proposed first implementation milestone is C1: runtime identity and an opt-in server launcher, using the isolated accepted Core and synthetic state. No implementation starts in Phase 1. Historical data ownership, complete store-to-context method mapping, native harness containment/account isolation, UI build provenance and outstanding subscription qualification remain gates for later milestones.
