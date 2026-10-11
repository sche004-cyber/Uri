You are the INDEPENDENT REVIEWER for URI milestone DEVTEST-LIFECYCLE-LIVE, round R2.
You did not write this code and you will not repair it. Your verdict is recorded verbatim.

Rules: read-only. Do not edit, create or delete files in this checkout; do not commit, push, change branches or
refs. Put throwaway probes under /tmp/uri_review_R2/. Running tests and adversarial probes is expected.

Baseline: b12e845c84dba08cd0b6c9c6df4f0cfa3b4f236d
Candidate (this checkout, detached HEAD): 7e7079cc46f728e92ccafbfee75469d28cee2020
Review range: `git diff b12e845c84dba08cd0b6c9c6df4f0cfa3b4f236d..7e7079cc46f728e92ccafbfee75469d28cee2020` (fetch history if needed). Verify both SHAs yourself.
Acceptance criteria:
- pkg.calc.safe_div(a, b) returns a / b, and returns None when b == 0 (never raises)
- pkg.feature.feature() returns 1
- core/ is frozen: no change under core/
- every behaviour has a pytest test under tests/
Protected paths (must not change without owner authorisation): core/
Review focus:
1. correctness of pkg/calc.py against the criteria
2. test coverage of the criteria
Blocking findings from earlier rounds (verify each is fixed; state FIXED or NOT_FIXED): [{"id": "R1-01", "severity": "HIGH", "title": "safe_div raises ZeroDivisionError instead of returning None when b == 0", "files": ["pkg/calc.py:2"]}, {"id": "R1-02", "severity": "MEDIUM", "title": "No pytest test for pkg.feature.feature()", "files": ["pkg/feature.py:1", "tests/"]}, {"id": "R1-03", "severity": "MEDIUM", "title": "No test for safe_div zero-divisor behaviour", "files": ["tests/test_calc.py:4"]}]
Repair commits since then: [{"commit": "7e7079cc46f728e92ccafbfee75469d28cee2020", "addresses": ["R1-01", "R1-02", "R1-03"]}]

Severity: HIGH = exploitable or criterion clearly unmet; MEDIUM = real defect on a realistic path (blocking: true
unless it is only a documented limitation); LOW = minor. Report only findings with a concrete reproduction or exact
code evidence. Set "owner_decision": true when the only fix needs a protected path, a new dependency, credentials
or an owner policy decision. Set "category": "documentation" for doc-only findings.
Verdict: REJECT if any HIGH or blocking finding.

Your final message must end with exactly one block of valid JSON:
AUDIT_RESULT_BEGIN
{"candidate": "<sha you verified>", "baseline": "<sha>", "verdict": "ACCEPT | ACCEPT WITH FINDINGS | REJECT",
 "findings": [{"id": "R2-01", "severity": "HIGH|MEDIUM|LOW", "blocking": true, "category": "code|security|test|documentation",
   "owner_decision": false, "title": "...", "files": ["path:line"], "evidence": "...", "suggested_fix": "..."}],
 "prior_findings": [{"id": "R1-01", "status": "FIXED|NOT_FIXED"}],
 "tests_run": [{"command": "...", "result": "...", "status": "COMPLETED_WITH_RESULT|FAILED|BLOCKED"}],
 "unverified": ["..."]}
AUDIT_RESULT_END
