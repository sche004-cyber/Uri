"""Harness/provider options, recommendation and quota recovery. Never switches providers silently.

Harness selection is separate from Brain selection (standing rule: Claude Code / Codex / Antigravity are execution
providers selected per task; the resident Brain never shells out to them). This module only PRESENTS choices:

  * an option is usable only if the owner's policy offers it AND its qualification is current AND its
    authentication is OK AND its quota is not known to be exhausted; unusable options are still listed, with the
    reason, so the user sees why;
  * the recommendation is the user's own earlier explicit choice for this task when still usable, otherwise the first
    usable provider in the owner's preference order; a recommendation is never a selection;
  * `requires_user_choice` is False only when the user already chose, explicitly, a provider that is still usable;
  * on quota exhaustion the task keeps its checkpoint and the exhausted provider is excluded from the new options;
    the task resumes only on an explicit user choice.

Status sources: `documented_status()` reads the runtime authority manifest (a document, labelled as such);
`status_from_snapshot()` maps a live snapshot supplied by the Phase 2 client composition. Live qualification is
owned by Phase 2 (`uri_supervisor_bridge.qualification`); this module does not re-qualify anything.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

USABLE_QUALIFICATION = {"QUALIFIED", "QUALIFIED_RUN_SCOPED"}
DEFAULT_PREFERENCE = ("codex", "claude_code", "antigravity")


@dataclass
class HarnessStatus:
    provider: str
    display: str
    qualification: str           # QUALIFIED | QUALIFIED_RUN_SCOPED | BLOCKED | UNQUALIFIED | UNKNOWN
    auth: str = "UNKNOWN"        # OK | NOT_LOGGED_IN | UNKNOWN
    quota: str = "UNKNOWN"       # OK | EXHAUSTED | UNKNOWN
    offered_by_policy: bool = False
    source: str = "unknown"      # "documented" | "live_snapshot" | "test"
    detail: str | None = None

    def usable(self):
        return (self.offered_by_policy and self.qualification in USABLE_QUALIFICATION and self.auth == "OK"
                and self.quota != "EXHAUSTED")

    def why_not(self):
        if not self.offered_by_policy:
            return "NOT_OFFERED_BY_OWNER_POLICY"
        if self.qualification not in USABLE_QUALIFICATION:
            return "QUALIFICATION_" + self.qualification
        if self.auth != "OK":
            return "AUTH_" + self.auth
        if self.quota == "EXHAUSTED":
            return "QUOTA_EXHAUSTED"
        return None


@dataclass
class HarnessChoice:
    options: list
    recommendation: str | None
    recommendation_reason: str
    requires_user_choice: bool
    selected: str | None = None
    excluded: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


def choose(statuses, *, task_choice_history=(), explicit=None, preference=DEFAULT_PREFERENCE, exclude=()):
    """`explicit`: a provider the user named for THIS task (never inferred from text by a model)."""
    opts = []
    for s in statuses:
        excluded = s.provider in exclude
        opts.append({"provider": s.provider, "display": s.display, "usable": s.usable() and not excluded,
                     "why_not": "EXCLUDED_QUOTA_EXHAUSTED" if excluded else s.why_not(),
                     "qualification": s.qualification, "auth": s.auth, "quota": s.quota, "source": s.source})
    usable = {o["provider"] for o in opts if o["usable"]}
    if explicit:
        if explicit in usable:
            return HarnessChoice(opts, explicit, "user_selected_for_this_task", False, selected=explicit,
                                 excluded=list(exclude))
        return HarnessChoice(opts, None, "explicit_choice_not_usable:" + str(explicit), True, excluded=list(exclude))
    for prior in reversed(list(task_choice_history)):
        if prior in usable:
            return HarnessChoice(opts, prior, "your_earlier_choice_for_this_task", True, excluded=list(exclude))
    for p in preference:
        if p in usable:
            return HarnessChoice(opts, p, "first_usable_in_owner_preference", True, excluded=list(exclude))
    return HarnessChoice(opts, None, "no_usable_provider", True, excluded=list(exclude))


def documented_status(manifest_path=None):
    """Statuses as DOCUMENTED in docs/governance/URI_RUNTIME_AUTHORITY_MANIFEST.json (not a live check)."""
    root = Path(__file__).resolve().parents[1]
    p = Path(manifest_path or root / "docs/governance/URI_RUNTIME_AUTHORITY_MANIFEST.json")
    data = json.loads(p.read_text(encoding="utf-8")).get("harness_integrations") or {}

    def parse(key, provider, display):
        text = str(data.get(key) or "")
        up = text.upper()
        if up.startswith("NATIVE QUALIFIED"):
            q, auth = "QUALIFIED_RUN_SCOPED", "UNKNOWN"
        elif up.startswith("BLOCKED"):
            q, auth = "BLOCKED", "NOT_LOGGED_IN" if "LOGGED IN" in up else "UNKNOWN"
        else:
            q, auth = "UNQUALIFIED", "UNKNOWN"
        # Policy rows are owner decisions held in the server state root; the document cannot prove one exists.
        return HarnessStatus(provider, display, q, auth=auth, offered_by_policy=False, source="documented",
                             detail=text[:200])
    return [parse("codex_cli", "codex", "Codex CLI"), parse("claude_cli", "claude_code", "Claude Code"),
            parse("antigravity", "antigravity", "Antigravity")]


def status_from_snapshot(rows):
    """Map a live Phase 2 snapshot: [{provider, display, qualification, auth, quota, offered_by_policy, detail}]."""
    out = []
    for r in rows:
        out.append(HarnessStatus(r["provider"], r.get("display") or r["provider"], r.get("qualification", "UNKNOWN"),
                                 auth=r.get("auth", "UNKNOWN"), quota=r.get("quota", "UNKNOWN"),
                                 offered_by_policy=bool(r.get("offered_by_policy")), source="live_snapshot",
                                 detail=r.get("detail")))
    return out
