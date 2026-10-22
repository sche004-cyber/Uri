# Repair of review R7 findings (2026-10-21)

Pre-repair candidate `5b2a1427`. All 3 findings accepted. Regression proof: `test_r7_*` against the pre-repair code
(`5b2a1427` + new test file): **5 failed**; the legitimate-case test `test_r6_01_*` (torn bytes that prove the
continuation) passes on both, as intended. After repair: 129 passed.

| Finding | Repair | Test |
|---|---|---|
| R7-01 | `_torn_continues_batch`: the torn tail's canonical prefix (`{"actor":…,"batch":{"i":N,"id":"…"`) must name the incomplete batch and exactly the next index ⇒ no review; too short ⇒ recover and record ANCHOR_LOSS (`anchor_problems` note); naming something else ⇒ `LOSS_NOT_ACKNOWLEDGED` | `test_r7_01_*` (short tail recorded; truncated applied batch never hidden; wrong index refused), `test_r6_01_*` (proven continuation, no conflict) |
| R7-02 | duplicated fragment removed | `test_r7_02_*` |
| R7-03 | `init_host` unlinks host file and anchors on any failure in the locked section; a retry may reuse a segment that holds only its own HOST_REGISTERED events | `test_r7_03_*` |

Design note: a power loss can cut a line anywhere. When the cut is too early to prove what the line was, the tool
cannot distinguish a harmless mid-batch power loss from a truncated, already applied batch whose anchor refresh had
failed. It therefore proceeds (no refusal, no data blocked) but records one reviewable ANCHOR_LOSS, consistent with
ANCHORS_ADOPTED (architecture §17, §19).
