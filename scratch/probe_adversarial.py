"""Prototyping adversarial safety suite for RAR Phase 0."""

from uri_v1.turn.rar_contracts import (
    RARBasis,
    RARCandidate,
    RARDeterministicAnchor,
    RAREvidence,
    RARFailureClass,
    RARDriverRule,
    RAROutcome,
    RARQuery,
    RARResolution,
)
from uri_v1.turn.rar_deterministic import resolve_rar_deterministic_extended

def make_cand(cid, title, ctype="document", tags=(), aliases=(), rank=0, is_att=False):
    return RARCandidate(
        id=cid,
        title=title,
        candidate_type=ctype,
        domain_tags=tuple(tags),
        exact_aliases=tuple(aliases),
        recency_rank=rank,
        is_attachment=is_att,
    )

def run_probe():
    cases = []
    
    # 1. Duplicate titles
    cases.append(("ADV-01-dup-titles", RARQuery(
        reference_expression="Project Proposal.pdf",
        candidates=(make_cand("c1", "Project Proposal.pdf"), make_cand("c2", "Project Proposal.pdf")),
    ), RAROutcome.AMBIGUOUS, None))
    
    # 2. Shuffled order of duplicate titles
    cases.append(("ADV-02-shuffled-dup", RARQuery(
        reference_expression="Project Proposal.pdf",
        candidates=(make_cand("c2", "Project Proposal.pdf"), make_cand("c1", "Project Proposal.pdf")),
    ), RAROutcome.AMBIGUOUS, None))

    # 3. Misleading lexical overlap - absent entity "sports"
    cases.append(("ADV-03-misleading-lexical-sports", RARQuery(
        reference_expression="the sports sanction letter",
        candidates=(
            make_cand("c1", "Hostel Sanction Letter", tags=("hostel", "sanction")),
            make_cand("c2", "Academic Fee Sanction Letter", tags=("academic", "fees")),
        ),
    ), RAROutcome.UNKNOWN, None))

    # 4. Stale active pointer - type mismatch with active
    cases.append(("ADV-04-stale-active-pointer", RARQuery(
        reference_expression="the audio recording",
        candidates=(
            make_cand("c1", "Committee Minutes.docx", ctype="document", tags=("recently_discussed",)),
            make_cand("c2", "Budget Overview.xlsx", ctype="spreadsheet"),
        ),
        local_evidence=RAREvidence(recency_hint="same", target_type_hint="audio"),
    ), RAROutcome.UNKNOWN, None))

    # 5. Two equally plausible "previous" candidates (tied recency rank)
    cases.append(("ADV-05-tied-previous", RARQuery(
        reference_expression="the previous decision",
        candidates=(
            make_cand("c1", "Decison 1", rank=1),
            make_cand("c2", "Decision 2", rank=1),
        ),
        local_evidence=RAREvidence(recency_hint="previous"),
    ), RAROutcome.AMBIGUOUS, None))

    # 6. Missing timestamps / all zero ranks with "latest"
    cases.append(("ADV-06-missing-timestamps", RARQuery(
        reference_expression="the latest audit",
        candidates=(
            make_cand("c1", "Audit Draft", rank=0),
            make_cand("c2", "Audit Review", rank=0),
        ),
        local_evidence=RAREvidence(recency_hint="latest"),
    ), RAROutcome.AMBIGUOUS, None))

    # 7. Contradictory recency metadata for "earlier"
    cases.append(("ADV-07-contradictory-recency", RARQuery(
        reference_expression="the earlier order",
        candidates=(
            make_cand("c1", "Office Order Alpha", rank=0),
            make_cand("c2", "Office Order Beta", rank=0),
        ),
        local_evidence=RAREvidence(recency_hint="earlier"),
    ), RAROutcome.AMBIGUOUS, None))

    # 8. Irrelevant distractor candidates with exact alias
    cases.append(("ADV-08-distractors-with-alias", RARQuery(
        reference_expression="ORD-994",
        candidates=(
            make_cand("d1", "Lab Policy Memo", tags=("lab",)),
            make_cand("d2", "Vendor Quotation", tags=("vendor",)),
            make_cand("d3", "Meeting Notes", tags=("notes",)),
            make_cand("target", "Office Order 994", aliases=("ORD-994",)),
        ),
    ), RAROutcome.RESOLVED, "target"))

    # 9. Same title across different target types (no type hint -> ambiguous)
    cases.append(("ADV-09-same-title-diff-types", RARQuery(
        reference_expression="Annual Report",
        candidates=(
            make_cand("doc1", "Annual Report.pdf", ctype="document"),
            make_cand("aud1", "Annual Report.mp3", ctype="audio"),
        ),
    ), RAROutcome.AMBIGUOUS, None))

    # 10. Multiple pronouns
    cases.append(("ADV-10-multiple-pronouns", RARQuery(
        reference_expression="it and that one",
        candidates=(
            make_cand("c1", "Doc A"),
            make_cand("c2", "Doc B"),
        ),
    ), RAROutcome.AMBIGUOUS, None))

    # 11. Multiple references of different types
    cases.append(("ADV-11-cross-reference", RARQuery(
        reference_expression="the spreadsheet and the email",
        candidates=(
            make_cand("s1", "Q3 Sheet.xlsx", ctype="spreadsheet"),
            make_cand("e1", "Notification.eml", ctype="email"),
        ),
    ), RAROutcome.AMBIGUOUS, None))

    # 12. Negated candidate
    cases.append(("ADV-12-negated-candidate", RARQuery(
        reference_expression="the proposal",
        candidates=(
            make_cand("p_draft", "Draft Proposal", tags=("draft",)),
            make_cand("p_final", "Final Proposal", tags=("final",)),
        ),
        local_evidence=RAREvidence(negation_spans=("draft proposal",)),
    ), RAROutcome.RESOLVED, "p_final"))

    # 13. "not that one"
    cases.append(("ADV-13-not-that-one", RARQuery(
        reference_expression="not that one",
        candidates=(
            make_cand("c1", "Primary Memo", tags=("rejected_in_turn",)),
            make_cand("c2", "Secondary Memo"),
        ),
        local_evidence=RAREvidence(negation_spans=("that one",)),
    ), RAROutcome.AMBIGUOUS, None))

    # 14. "the other one" with contrast
    cases.append(("ADV-14-the-other-one", RARQuery(
        reference_expression="the other one",
        candidates=(
            make_cand("c1", "Option A", tags=("rejected_in_turn",)),
            make_cand("c2", "Option B"),
        ),
        local_evidence=RAREvidence(negation_spans=("Option A",), recency_hint="other"),
    ), RAROutcome.RESOLVED, "c2"))

    # 15. Revised vs original
    cases.append(("ADV-15-original-vs-revised", RARQuery(
        reference_expression="the original memo",
        candidates=(
            make_cand("v1", "Budget Memo", rank=1, tags=("original",)),
            make_cand("v2", "Budget Memo Revised", rank=0, tags=("revised",)),
        ),
        local_evidence=RAREvidence(recency_hint="original"),
    ), RAROutcome.RESOLVED, "v1"))

    # 16. Candidate with strong TF-IDF overlap but wrong semantic identity (absent year 2024)
    cases.append(("ADV-16-strong-overlap-wrong-year", RARQuery(
        reference_expression="2024 campus carbon emission audit",
        candidates=(
            make_cand("c2023", "2023 campus carbon emission audit"),
            make_cand("c2022", "2022 campus energy audit"),
        ),
    ), RAROutcome.UNKNOWN, None))

    # 17. Insufficient metadata (empty candidate types with type hint)
    cases.append(("ADV-17-insufficient-metadata", RARQuery(
        reference_expression="the report",
        candidates=(
            make_cand("c1", "Report A", ctype=""),
            make_cand("c2", "Report B", ctype=""),
        ),
        local_evidence=RAREvidence(target_type_hint="document"),
    ), RAROutcome.AMBIGUOUS, None))

    # 18. Zero candidates
    cases.append(("ADV-18-zero-candidates", RARQuery(
        reference_expression="the invoice",
        candidates=(),
    ), RAROutcome.UNKNOWN, None))

    # 19. One valid candidate among many distractors with exact ID
    cases.append(("ADV-19-valid-among-distractors", RARQuery(
        reference_expression="INV-4001",
        candidates=(
            make_cand("d1", "Memo 1"),
            make_cand("d2", "Memo 2"),
            make_cand("d3", "Memo 3"),
            make_cand("INV-4001", "Vendor Invoice 4001"),
        ),
    ), RAROutcome.RESOLVED, "INV-4001"))

    # 20. Ambiguous ownership
    cases.append(("ADV-20-ambiguous-ownership", RARQuery(
        reference_expression="his proposal",
        candidates=(
            make_cand("c1", "Dean Proposal", tags=("faculty",)),
            make_cand("c2", "Director Proposal", tags=("director",)),
        ),
    ), RAROutcome.AMBIGUOUS, None))

    # 21. Absent specific person name
    cases.append(("ADV-21-absent-person-name", RARQuery(
        reference_expression="Dr. Sen's lab requisition",
        candidates=(
            make_cand("c1", "Dr. Verma's lab requisition"),
            make_cand("c2", "Hostel maintenance requisition"),
        ),
        local_evidence=RAREvidence(target_type_hint="document"),
    ), RAROutcome.UNKNOWN, None))

    # 22. Tied TF-IDF scores shuffled
    cases.append(("ADV-22-tied-lexical-shuffled", RARQuery(
        reference_expression="quarterly financial analysis",
        candidates=(
            make_cand("c1", "Quarterly Analysis Summary"),
            make_cand("c2", "Financial Analysis Summary"),
        ),
    ), RAROutcome.AMBIGUOUS, None))

    print(f"Running {len(cases)} adversarial cases...")
    wrong_bindings = 0
    passed = 0
    for name, query, exp_outcome, exp_cand in cases:
        trace = resolve_rar_deterministic_extended(query)
        res = trace.resolution
        is_wrong_binding = False
        if res.outcome == RAROutcome.RESOLVED:
            if exp_outcome != RAROutcome.RESOLVED or res.candidate_id != exp_cand:
                is_wrong_binding = True
                wrong_bindings += 1
        
        is_pass = (res.outcome == exp_outcome) and (res.candidate_id == exp_cand)
        if is_pass:
            passed += 1
        else:
            print(f"[{name}] FAIL: got outcome={res.outcome.value} cand={res.candidate_id} rule={trace.rule_used.value} | exp outcome={exp_outcome.value} cand={exp_cand} | WRONG_BINDING={is_wrong_binding}")

    print(f"\nTotal: {len(cases)}, Passed: {passed}, Failed: {len(cases)-passed}, Wrong Bindings: {wrong_bindings}")

if __name__ == "__main__":
    run_probe()
