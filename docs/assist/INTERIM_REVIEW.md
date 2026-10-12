# Interim independent review — W1 and A0 (Claude agent, NOT the Codex audit of record)

Reviewer: a separate Claude agent that did not write the code, read-only, with throwaway scripts outside the repo.
Reviewed: `ffdf534..74b24eb` (W1 `885483b`, A0 `74b24eb`). Verdict: **ACCEPT WITH FINDINGS** (no HIGH; 7 MEDIUM incl.
one LOW-MEDIUM; LOW items). This review does not make anything INDEPENDENTLY ACCEPTED; Codex remains required.

Each finding was checked against the code by the implementer before repair. Each repair has a test that **fails on
the pre-repair commit** (run and recorded: W1 tests against `885483b`, A0 tests against the pre-repair A0 `be5bc6c`;
the only passing ones are intended controls such as "a faithful claim still passes").

| # | Sev. | Finding (short) | Accepted? | Repair (branch commit) | Regression test |
|---|---|---|---|---|---|
| F1 | MED | research events race ahead of the reply carrying the job id; UI drops them → Research tab hangs | yes | W1 `db7c02c` deferred start + `release()`; A0 `1844b48` worker releases after reply; UI early-event buffer + status polling | `test_f1_*` (py), `a research event that races ahead…`, `a lost finished event…` (Dart) |
| F2 | MED | worker clears the environment → search keys never reach providers | yes | W1 `db7c02c` `load_search_keys` / `providers_from_keys`; A0 `1844b48` key file `control/web/search_keys.json` under the client root | `test_f2_key_file_configures_providers_without_env` |
| F3 | MED | lexical verifier accepts negated claims and scattered support; unflagged steering; missing hidden-text forms | yes | W1 `db7c02c`: support from ONE sentence, polarity (negation + antonym pairs), `addresses_summariser` flag, more hidden forms; UI wording "checked against the sources" | `test_f3_*` (12 cases) |
| F4 | MED (latent) | `assist_ask` blocks the worker command thread up to 60 s; Stop/user turn wait behind it | yes | A0 `1844b48`: job thread + cancel token (streamed), Stop/Pause/new grant/user turn cancel; answer discarded if the grant changed | `test_f4_*` (4) , Dart async-answer tests |
| F5 | MED (latent) | OTP/PIN names (`totp`, `smsOtp`, `userPin`, `verification code`, `pw`, `cvn`), dotted/NBSP card numbers, `contenteditable=""` leak; JS layer weaker than Python | yes | A0 `1844b48`: word-split name matching in both layers, short-code rule (postal codes exempt), card separators, JS parity, any contenteditable | `test_f5_*` incl. real-Chromium parity on `tricky_fields.html` |
| F6 | MED (proxy mode) | `%2e` / `_` hosts and single-label names pass in proxy mode | yes | W1 `db7c02c`: LDH after IDNA; proxy mode refuses single-label and unresolvable names unless allow-listed | `test_f6_*` |
| F7 | LOW-MED | OI `BrainClient` trusts env/registry proxies; loopback guarantee is only a URL check | yes | W1 `db7c02c` `loopback_client()` (subclass, `trust_env=False`; accepted OI class unchanged); A0 `1844b48` worker uses it for W1/A0 | `test_f7_loopback_client_never_trusts_env` |
| L1 | LOW | hidden inputs (CSRF) counted as unlocated sensitive fields → screenshots refused on most forms | yes | `unlocated_sensitive` ignores hidden/not-visible fields | `test_low_hidden_inputs_…` |
| L2 | LOW | target check vacuous when the snapshot has no `target_id` | yes | adapters must bind the target (`TARGET_UNBOUND`) | `test_low_adapter_must_bind_the_target` |
| L3 | LOW | research cancel cannot stop a running Brain synthesis; user turn may queue behind it (≤ ~6 s at 700 tokens) | **partly** | not repaired: W1 synthesis still uses `complete_json` without a token. Carried as limitation **L-W1-3** | — |
| L4 | LOW | `_progress` map unbounded | yes | bounded | `test_f1_progress_entries_are_bounded` |
| L5 | LOW | stale scope line after worker restart until next action | yes | controller listens to `OiConversation` and resets at once | Dart `worker restart clears the shown grant…` |
| L6 | LOW | total deadline checked between chunks only; `iter_bytes` decompresses; no dual-stack fallback | partly | compressed bodies refused and raw bytes counted (repaired); deadline overrun ≤ read timeout and no dual-stack fallback **carried** (L-W1-4) | `test_compressed_body_refused` |
| L7 | LOW | unguarded import of new packages at worker start | yes | guarded; commands refused if load fails | worker hook guard test |
| L8 | LOW | evidence file `baseline_flutter_linux_ffdf534.txt` records HEAD `885483b` | yes (correction) | the Flutter baseline run happened after the W1 commit (W1 changed no Dart file, so the result is equivalent); file name kept, this record is the correction | — |

Repair-induced defects found by the implementer while repairing (recorded for auditability):
- The first F5 rewrite stopped matching joined words such as `cardnumber` (caught by the real-Chromium test; fixed
  before commit with optional spaces in multi-word patterns).
- The first F5 camel-case rule over-matched `hotpot`/`spinner`/`pinnacle` (caught by a probe; replaced by word
  splitting before commit).
- The first Dart repair left the poll timer running after the result arrived (caught by a widget test; fixed).
