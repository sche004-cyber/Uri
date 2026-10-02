"""M20: a deterministic, non-authoritative "can this actually run right
now" snapshot of the capability catalogue.

CapabilityRegistry.is_executable already distinguishes "an execution
adapter exists" (status == "implemented") from "no adapter exists at
all" (planned/not_implemented). It does NOT distinguish "exists and
can run right now" from "exists but this runtime currently can't use
it" - a registry entry can be status="implemented" and
availability="unavailable_missing_dependency" (e.g. gmail_search
without a stored OAuth token) and still count as executable by that
property alone. That gap let a Brain proposal for such a capability be
validated, promoted to the real plan, and dispatched, only to fail at
execution - the exact "stops with a tool/skill-unavailable error"
symptom this module exists to prevent one layer earlier.

This module answers ONE question per capability - "is it usable right
now" - by combining two already-authoritative, already-existing
sources, duplicating neither:
    - CapabilityRegistry (status/availability/gap_reason/permissions/
      approval_requirement/risk) - unchanged, still the sole source of
      what a capability IS.
    - connection_status.list_connection_status() (real Gmail/Drive
      OAuth state) - unchanged, still the sole source of whether an
      external service is actually authorized on this host.

It never selects, ranks, or scores a capability - that remains
CapabilityPlanner's (deterministic fallback) and the Brain's
(everything else) job. It is purely a read-only composition layer, in
the same spirit as query_context.py: it decides nothing, it only
reports. Never imported by dispatcher.py/approval_gate.py, and never
itself a place execution or authorization logic lives.

Fail-safe direction: any failure while determining WHY a capability
might be blocked (a connection-status read failing, an unrecognized
permission) must never make the runtime MORE restrictive than it was
before this module existed - it degrades to "not blocked" for that
specific reason, never to "unusable". The one thing that is never
softened is CapabilityRegistry's own is_executable/gap_reason - if the
registry itself says a capability doesn't exist, this module never
overrides that.
"""

import os
from typing import Any, Dict, List, Optional

from uri_core.core.capability_registry import (
    CapabilityDescriptor,
    CapabilityRegistry,
)
from uri_core.core.connection_status import _repo_root, list_connection_status
from uri_core.core.google_auth_common import (
    load_usable_credentials,
    resolve_google_token_path,
)
from uri_core.services.google_errors import classify_google_error

_GOOGLE_TOOL_SCOPES = {
    "gmail_search": ("gmail", "gmail.readonly"),
    "gmail_find_draft": ("gmail", "gmail.readonly"),
    "gmail_create_draft": ("gmail", "gmail.compose"),
    "drive_search": ("drive", "drive.readonly"),
    "fetch_drive_spreadsheet": ("drive", "drive.readonly"),
    "drive_upload": ("drive", "drive.file"),
    "google_workspace_create": ("drive", "drive.file"),
}


def _google_tool_state(capability_id: str, user_id: Optional[str]) -> Optional[str]:
    """Current user's non-interactive OAuth state; no token content is returned."""
    service, scope = _GOOGLE_TOOL_SCOPES[capability_id]
    if not user_id:
        return "Sign in with Google in URI Connections for this user."
    if not os.path.isfile(os.path.join(_repo_root(), "credentials.json")):
        return "Configure credentials.json on the URI server using Google setup in Connections."
    token_path = resolve_google_token_path(user_id)
    if not os.path.isfile(token_path):
        return "Sign in with Google in URI Connections for this user."
    try:
        creds = load_usable_credentials(token_path=token_path, allow_refresh=False)
        if creds is None:
            creds = load_usable_credentials(token_path=token_path, allow_refresh=True)
        if creds is not None:
            required_scope = f"https://www.googleapis.com/auth/{scope}"
            has_scope = False
            if hasattr(creds, "has_scopes"):
                has_scope = creds.has_scopes([required_scope])
            elif hasattr(creds, "scopes") and creds.scopes:
                has_scope = required_scope in creds.scopes
            else:
                has_scope = True
            if has_scope:
                return None
            return classify_google_error("insufficient authentication scopes", api=service)["message"]
    except Exception as exc:
        issue = classify_google_error(exc, api=service)
        return issue.get("message") or str(exc)
    return "Sign in with Google in URI Connections for this user."


# Maps a registry-declared permission string to the connection_status
# service id it depends on, by prefix - the two vocabularies are
# already close (see capabilities_registry.json's "permissions" and
# connection_status.py's service ids "gmail"/"drive") but not
# identical, so this is a small, explicit, reviewable table rather
# than a guessed string transform. A permission with no entry here
# (external_web_search, read_user_attachments, system_command_execution,
# ...) simply has no connection-status dependency to check - it is
# never treated as blocked by this table.
_PERMISSION_SERVICE_PREFIXES = (
    ("gmail", "gmail"),
    ("google_drive", "drive"),
    ("drive", "drive"),
)


def _connection_status_by_service() -> Dict[str, Dict[str, str]]:
    """service_id -> {"status", "detail"} for every known external
    service. Never raises - a failure here degrades to an empty dict,
    which _permission_blocked_by then treats as "nothing known to be
    blocked" (fail-open, per this module's docstring)."""

    try:
        services = list_connection_status()
    except Exception:
        return {}

    by_service: Dict[str, Dict[str, str]] = {}

    for service in services:
        if not isinstance(service, dict):
            continue
        service_id = service.get("id")
        if isinstance(service_id, str):
            by_service[service_id] = service

    return by_service


def _permission_blocked_by(
    permissions: List[str],
    connection_by_service: Dict[str, Dict[str, str]],
) -> List[str]:
    """Plain-language reasons this capability's declared permissions
    are currently blocked by a real, unauthorized external service -
    never guessed, only ever derived from connection_status's real
    state. Empty list when nothing is blocked, connection status is
    unknown, or the capability declares no service-backed permission
    at all."""

    reasons: List[str] = []

    for permission in permissions:

        permission_text = str(permission)
        permission_lower = permission_text.lower()

        service_id = None

        for prefix, mapped_service in _PERMISSION_SERVICE_PREFIXES:
            if permission_lower.startswith(prefix):
                service_id = mapped_service
                break

        if service_id is None:
            continue

        service_state = connection_by_service.get(service_id)

        if not isinstance(service_state, dict):
            continue

        if service_state.get("status") == "connected":
            continue

        detail = service_state.get("detail") or service_state.get("status")

        reasons.append(f"{permission_text}: {detail}")

    return reasons


def _feasibility_entry(
    descriptor: CapabilityDescriptor,
    connection_by_service: Dict[str, Dict[str, str]],
    user_id: Optional[str] = None,
) -> Dict[str, Any]:

    if user_id is not None and descriptor.id in _GOOGLE_TOOL_SCOPES:
        google_reason = _google_tool_state(descriptor.id, user_id)
        if google_reason:
            blocked_by = [google_reason]
            gap_reason = "blocked_by_permission"
            usable = False
        else:
            blocked_by = []
            if not descriptor.is_executable:
                gap_reason = descriptor.gap_reason or "not_implemented"
                usable = False
            else:
                gap_reason = None
                usable = True
    else:
        try:
            blocked_by = _permission_blocked_by(
                list(descriptor.permissions), connection_by_service
            )
        except Exception:
            blocked_by = []

        usable = (
            descriptor.is_executable
            and descriptor.gap_reason is None
            and not blocked_by
        )
        gap_reason = (
            None if usable else (descriptor.gap_reason or "blocked_by_permission")
        )

    return {
        "id": descriptor.id,
        "description": descriptor.description,
        "reads_current_attachments": descriptor.reads_current_attachments,
        "foundational": descriptor.foundational,
        "usable": usable,
        "gap_reason": gap_reason,
        "blocked_by": blocked_by,
        "requires_approval": descriptor.approval_requirement
        == "user_approval_required",
        "risk": descriptor.risk,
        "interface": descriptor.interface,
    }


class CapabilityFeasibility:
    """Deterministic, read-only, non-authoritative. See module
    docstring. One instance is cheap to construct and safe to call
    once per turn - both underlying reads are small local JSON/file
    checks, no network calls."""

    def __init__(
        self,
        registry_path: str = "uri_workspace/capabilities_registry.json",
        capability_registry: Optional[CapabilityRegistry] = None,
        user_id: Optional[str] = None,
    ):
        self.capability_registry = (
            capability_registry
            if capability_registry is not None
            else CapabilityRegistry(registry_path=registry_path)
        )
        self.user_id = user_id

    def snapshot(self) -> Dict[str, Dict[str, Any]]:
        """capability_id -> feasibility entry for every descriptor
        CapabilityRegistry knows about (implemented AND planned/
        not_implemented alike, matching list_capabilities()'s own
        scope). Never raises: a registry read failure degrades to an
        empty snapshot, which every caller in this codebase treats as
        "nothing extra known" rather than "everything is unusable" -
        see orchestrator.py's use sites."""

        try:
            descriptors = self.capability_registry.list_capabilities()
        except Exception:
            return {}

        try:
            services = (
                list_connection_status(user_id=self.user_id)
                if self.user_id
                else list_connection_status()
            )
            connection_by_service = {
                s["id"]: s
                for s in services
                if isinstance(s, dict) and isinstance(s.get("id"), str)
            }
        except Exception:
            connection_by_service = {}

        return {
            descriptor.id: _feasibility_entry(
                descriptor, connection_by_service, user_id=self.user_id
            )
            for descriptor in descriptors
            if isinstance(descriptor, CapabilityDescriptor)
        }

    def usable_ids(self) -> set:
        """The subset of the snapshot that is genuinely usable right
        now - implemented, not runtime-gapped, and not blocked by an
        unauthorized permission. Never raises."""

        try:
            return {
                capability_id
                for capability_id, entry in self.snapshot().items()
                if entry.get("usable")
            }
        except Exception:
            return set()

