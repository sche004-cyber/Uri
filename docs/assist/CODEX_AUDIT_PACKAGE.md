# Codex audit package — W1 Web Intelligence and A0 URI Assist

**Status: NOT PERFORMED.** Codex was not installed or reachable in the cloud session that built this work. No Codex
verdict exists. The interim review recorded in §5 was done by a separate Claude agent that did not write the code;
it is not the audit of record and does not make anything INDEPENDENTLY ACCEPTED.

## 1. Scope

| Item | Value |
|---|---|
| Repository | `github.com/sche004-cyber/Uri` |
| Branch | `ccr-cab5ed06-9hwyc4` |
| Base | `ffdf534` (canonical tip, 2026-10-10) |
| Range | `git diff ffdf534..<branch tip>`. Milestone commits (local branches, same content reachable from the session branch): W1 `885483b` + repair `db7c02c` (`milestone/w1-web-intelligence-20261010`); A0 `f140506`, `be5bc6c` + repair `1844b48` (`milestone/a0-assist-foundation-20261010`, stacked on W1); docs after them. REA research: `cea2a77` (`research/rea-discovery-20261010`, research only) |
| Code under review | `uri_web/**`, `uri_assist/**` (incl. `browser_extension/`), `scripts/run_uri_integrated_worker.py` (dispatch lines), `scripts/oi_materialize_test_runtime.py`, `tests/phase2a/test_frozen_core.py` (ALLOWED_NEW lines only), `uri_ui/lib/living/{assist/**, integration/oi_conversation.dart, living_app.dart, living_scope.dart, presentation/**, screens/companion_mode_view.dart, screens/dashboard_mode_view.dart}` |
| Tests | `tests/web/**`, `tests/assist/**`, `uri_ui/test/living/assist_mode_test.dart` |
| Governing documents | `docs/assist/00_PLAN_AND_ACCEPTANCE_CRITERIA.md` (W1-AC1..16, A0-AC1..13), `A0_UI_INTERACTION_SPEC.md`, `03_PERMISSION_AND_DATA_FLOW.md` |

## 2. Prompt for Codex (read-only)

> Review `git diff ffdf534..HEAD` on branch `ccr-cab5ed06-9hwyc4` read-only. You did not write this code. Judge it
> against `docs/assist/00_PLAN_AND_ACCEPTANCE_CRITERIA.md`. Report HIGH/MEDIUM/LOW findings with file:line and a
> concrete reproduction. In particular:
> 1. SSRF: any URL, address form, redirect, DNS answer sequence, proxy setting or robots fetch that makes
>    `uri_web.safe_fetch.SafeFetcher` connect to a non-public address, or connect somewhere other than the address it
>    validated.
> 2. Prompt injection: any path by which retrieved text (page, feed, social post, search snippet) or a shared Assist
>    observation changes what is fetched, reaches the Brain outside a data block, survives `synthesize.verify`
>    as an instruction, link or unsupported number, or closes the data-block delimiter.
> 3. Access control: any way to observe or suggest without a current grant; any stale observation accepted after
>    pause/revoke/expiry/target change/new grant; any permission implying another; entire-screen without the second
>    confirmation; any grant surviving a worker restart; any Insert/Act path.
> 4. Redaction: any password, OTP, card, token, hidden-field or secret-shaped value that leaves the page
>    (`browser_extension/snapshot.js`) or survives `uri_assist.perception.normalise`.
> 5. Worker hook: any change to the behaviour of existing OI or worker commands; guard/read-root regressions; the
>    `OiConversation` assist-frame diversion; Dart exhaustiveness for the new mode.
> 6. Frozen boundary: confirm no protected path changed (`python scripts/ws_frozen_check.py` on the PC, where the
>    Phase 1 checkpoint zip exists).
> Give a verdict: ACCEPT / ACCEPT WITH FINDINGS / REJECT.

## 3. Gates to run on the PC alongside the review

```
python scripts/ws_frozen_check.py                      # must print "ok": true (zip present on the PC)
python -I -m pytest -c scripts/phase2d_pytest.ini --rootdir=. tests/ws tests/oi tests/a2ui tests/web tests/assist
cd uri_ui && flutter test
```

## 4. Evidence already produced (cloud, Linux)

See `W1_QUALIFICATION.md` §3 and `A0_QUALIFICATION.md` §3 for exact counts, and `evidence/` for raw outputs.

## 5. Interim independent review (Claude agent, not Codex)

Recorded in `INTERIM_REVIEW.md` with each finding, the repair commit and the test that fails without it. Verdict
ACCEPT WITH FINDINGS (no HIGH); all MEDIUM findings repaired; two LOW items carried as limitations. Codex should
re-examine F3 (lexical verification limits) and F5 (redaction rule completeness) in particular.
