"""URI Web Intelligence (milestone W1): a read-only research pipeline.

    Search -> Retrieve -> Extract -> Evaluate -> Synthesize -> Cite

Everything here is read-only. Nothing posts, logs in, submits, or follows an instruction found in a page. Retrieved
content is UNTRUSTED evidence (see `untrusted.py`): it can be quoted and cited, never obeyed, and it can never change
the query, the URL set, the provider, the budget or any permission.

This package is new and outside the frozen boundary (`scripts/ws_frozen_check.py`). It does not call the frozen
`uri_core/tools/fetch_url.py`, which has no address checks (SSRF-1); all retrieval goes through `safe_fetch`.
"""
