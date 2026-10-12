"""Owner decision D7 (2026-10-11): a sentence that states a quantity is shown only as a cited source sentence, word
for word. Shared assertion for the regression tests that used to expect such claims to be dropped."""


def only_source_quotes(v, sources, claim=None) -> bool:
    """Every shown claim is quoted, appears verbatim in one of ``sources`` and (when given) is not the claim's own
    wording - so a value the sources do not state can never be shown."""
    body = (claim or "").replace(" [1]", "").replace(" [2]", "").strip()
    return all(c.quoted and any(c.text in s for s in sources) and (not claim or c.text != body) for c in v.claims)
