"""Registered A2UI action names. A surface may name only these; the renderer maps each to ONE client call.

Context schema kinds: "str", "str?", "bool", "int", "sha256", "time" (HH:MM), "date" (YYYY-MM-DD), "date?",
"keys" (list of slugs, <= 80), "enum:a|b". Every action context also carries `surface_digest` (added by the renderer,
checked by the authority), so it is not listed here.

`authority` names who executes and re-validates the action. `confirms` marks actions that commit something the owner
must have seen: their context must carry the bound hash of the exact thing shown.
"""

ACTIONS = {
    # Scheduler: festival schedule proposal (authority: scheduler engine; owner check + proposal SHA-256)
    "scheduler.revise_proposal": {"authority": "scheduler", "confirms": False,
                                  "context": {"selection": "keys", "time": "time", "offset_days": "enum:1|2|3|5|7"}},
    "scheduler.confirm_proposal": {"authority": "scheduler", "confirms": True,
                                   "context": {"proposal_sha256": "sha256", "selection": "keys", "time": "time",
                                               "offset_days": "enum:1|2|3|5|7"}},
    "scheduler.discard_proposal": {"authority": "scheduler", "confirms": False, "context": {}},
    # Scheduler: artifact review (authority: scheduler engine; owner check + artifact SHA-256 re-hashed on disk)
    "scheduler.review_artifact": {"authority": "scheduler", "confirms": True,
                                  "context": {"artifact_sha256": "sha256", "decision": "enum:approve|regenerate|reject"}},
    "scheduler.refine_artifact": {"authority": "scheduler", "confirms": True,
                                  "context": {"artifact_sha256": "sha256", "instruction": "str"}},
    # Scheduler: festival calendar review (authority: scheduler engine; append-only owner corrections)
    "calendar.correct_record": {"authority": "scheduler", "confirms": False,
                                "context": {"record": "str", "start": "date?", "note": "str?",
                                            "correction": "enum:set_date|dispute|accept"}},
    # URI Office: commit or decline one shown change set (authority: uri_office service; owner check + change SHA-256,
    # the target is re-read and must still hold the shown "before" state)
    "office.apply_change": {"authority": "office", "confirms": True, "context": {"change_sha256": "sha256"}},
    "office.reject_change": {"authority": "office", "confirms": True, "context": {"change_sha256": "sha256"}},
    # Presentation only
    "surface.dismiss": {"authority": "renderer", "confirms": False, "context": {}},
}

MAX_CONTEXT_STRING = 500
