"""M36 negation: further apostrophe look-alikes (probe ported from Codex line 379769f).

Verified as a real defect on 249660e by the Codex bridge audit: negated() missed
these glyphs, so "donʻt allow network" could satisfy an M38 elevation grant.
"""
from __future__ import annotations

import pytest

from tests.m37_edge_support import intake
from uri_v1.execution.harness.contracts import ElevationGrant
from uri_v1.memory.contracts import negated

@pytest.mark.parametrize("glyph", ["\u02bb", "\u201b", "\u2032", "\u2035", "\u275b", "\u275c"])
def test_additional_apostrophe_variants_fail_closed_for_elevation(glyph):
    text = f"don{glyph}t allow network for this run"
    assert negated(text)
    with pytest.raises(ValueError, match="EXPLICIT_ELEVATION_REQUIRED"):
        ElevationGrant.from_user(intake(text), "network", "run-1")


# Codex re-check of f8115d5 (parity with 379769f): NFKC normalization and the rest of
# the -n't vocabulary. Each is negated and refuses an M38 elevation grant.
@pytest.mark.parametrize("text", ["mightn't allow network", "shan\u02bbt allow network",
                                  "\uff44\uff4f\uff4e\uff07\uff54 allow network", "daren't allow network",
                                  "allow anything besides network", "allow network except for this run"])
def test_nfkc_and_remaining_nt_forms_are_negated(text):
    assert negated(text)
    with pytest.raises(ValueError):
        ElevationGrant.from_user(intake(text), "network", "run-1")
