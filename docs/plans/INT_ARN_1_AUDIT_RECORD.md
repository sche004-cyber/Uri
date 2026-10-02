# INT-ARN-1 Independent Audit Record

Auditor: Codex CLI (gpt-6-sol), read-only, independent of the implementer runs. Claude ran all tests; the auditor could not run pytest in its read-only sandbox, so test results below are Claude-reported evidence.

| Round | HEAD audited | Verdict | Repair commit |
|---|---|---|---|
| 1 | 354389f | REJECT (2 blockers, 3 major) | af5c012 |
| 2 | af5c012 | REJECT (Change replay blocker, render deadline, flag-OFF prompt) | d24c9fd |
| 3 | d24c9fd | REJECT (replay after restart; Slice C fixture hid an executed action) | 61033c4 |
| 4 | 61033c4 | ACCEPT_WITH_AMENDMENTS | this record |

## Amendment (LOW, availability) - documented limitation

A durable execution marker (UNKNOWN) is written before every bound dispatch. If dispatch is never attempted, or a chain halts before a marked step, the marker stays. Change on that binding then fails closed until the binding expires, when the journal prunes the marker. Recovery path: the user makes a new request instead of using Change. Retaining an uncertain marker is the intended safety choice; clearing it is only safe where the runtime can prove dispatch did not begin.

## Still outstanding (live acceptance, not code repair)

- Held-out live source battery with the flag on.
- Live slot emission and follow-up with both gemma4:12b and a Qwen Brain.
- Two-user desktop run.
- Measured p50/p95 latency gates.

## Round 4 report (verbatim)

## Verdict: ACCEPT_WITH_AMENDMENTS

At `61033c4`, the round-3 replay blocker is repaired on the inspected paths. A bound canonical action gets a durable `UNKNOWN` marker before dispatch; an approved action gets one before its handler can run. Successful execution records `APPLIED` and clears the marker. If recording fails, the marker survives restart and blocks Change. I found **no new repair-required safety defect**. This is a source review, not a live acceptance verdict.

| Round-3 finding | Status | Evidence |
|---|---|---|
| Record failure permits replay after restart | **RESOLVED** | The marker is saved before canonical dispatch in [canonical_execution.py](/C:/Users/cheta/Development/uri-m37-m39-integration/uri_core/core/canonical_execution.py:201) and [line 1356](/C:/Users/cheta/Development/uri-m37-m39-integration/uri_core/core/canonical_execution.py:1356), and before approval dispatch in [approval_resumption.py](/C:/Users/cheta/Development/uri-m37-m39-integration/uri_core/core/approval_resumption.py:268). It is journaled in [store.py](/C:/Users/cheta/Development/uri-m37-m39-integration/uri_desktop_seams/reference_clarification/store.py:217); Change checks it in [service.py](/C:/Users/cheta/Development/uri-m37-m39-integration/uri_desktop_seams/reference_clarification/service.py:220) and [server.py](/C:/Users/cheta/Development/uri-m37-m39-integration/uri_core/app/server.py:1740). |
| Slice C fixture executes its setup action | **RESOLVED** | The setup now produces a real `awaiting_approval` record, asserts no handler call, and checks `APPLIED` after approval in [test_int_arn_1_slice_c.py](/C:/Users/cheta/Development/uri-m37-m39-integration/test_int_arn_1_slice_c.py:373). |
| Render slot held if thread start fails | **RESOLVED** | The start-failure branch releases the slot in [canonical_execution.py](/C:/Users/cheta/Development/uri-m37-m39-integration/uri_core/core/canonical_execution.py:188). |

**Amendment — LOW, availability:** A marker can remain when dispatch is never attempted or a chain halts before a marked step. For example, `_execute_canonical()` can return `None` after the marker is written; that path does not clear it ([canonical_execution.py](/C:/Users/cheta/Development/uri-m37-m39-integration/uri_core/core/canonical_execution.py:1356)). A halted chain clears markers for successful steps and retains them for other steps ([line 258](/C:/Users/cheta/Development/uri-m37-m39-integration/uri_core/core/canonical_execution.py:258)). Change then fails closed until binding expiry; expiry prunes the marker ([store.py](/C:/Users/cheta/Development/uri-m37-m39-integration/uri_desktop_seams/reference_clarification/store.py:195)). **Scenario:** a legitimate correction is temporarily blocked despite no action running. **Amendment:** document this behavior and its recovery path. A later bounded improvement could clear only markers for which the runtime can prove dispatch did not begin. Retaining an uncertain marker is the correct safety choice.

Multi-action chains mark all bound steps before chain dispatch; the recorder applies successful steps and retains uncertainty for the rest. The native tool loop rejects slot-bearing proposals before execution ([native_tool_loop.py](/C:/Users/cheta/Development/uri-m37-m39-integration/uri_core/core/native_tool_loop.py:286)). Approval resumption marks before consumption and dispatch, and the genuine awaiting-approval fixture exercises that route. The flag-OFF gate remains opt-in at [canonical_execution.py](/C:/Users/cheta/Development/uri-m37-m39-integration/uri_core/core/canonical_execution.py:107).

The diff from `354389f` changes no `uri_v1` or `orchestrator.py` file. Every changed `uri_core` and `uri_ui` blob matches its exact allowlist pin; I found no core-to-app import in the changed core modules. The earlier render deadline and flag-OFF prompt repairs remain resolved by inspection.

I did **not** run pytest: this read-only sandbox does not permit its writable temporary state. Claude’s reported 134 targeted and canonical passes, baseline-matching root regression, and frozen-guard passes remain externally reported evidence. The held-out live battery, both-model slot follow-up, two-user run, and measured latency gates remain **live acceptance work**, not code repairs established by this re-audit.