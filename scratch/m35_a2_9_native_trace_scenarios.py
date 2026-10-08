"""M35 URIv1 A2.9 -- 8 frozen scenario definitions.

Disposable pilot harness. Not production URI code. See
docs/plans/M35_URIV1_A2_9_NATIVE_PROBLEM_SOLVING_TRACE_PLAN.md section 2.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Tuple

from scratch import m35_a2_9_native_trace_world as world
from scratch import m35_a2_9_native_trace_scoring as scoring


@dataclass(frozen=True)
class ScenarioSpec:
    scenario_id: str
    name: str
    goal_text: str
    world_builder: Callable[[], Dict]
    given: str
    discover: str
    execute: str
    does_not_exist: str
    controlled_failure: bool
    scoring_fn: Callable


A2_9_SCENARIOS: Tuple[ScenarioSpec, ...] = (
    ScenarioSpec(
        scenario_id="S1",
        name="FACT_RETRIEVAL",
        goal_text="Find out which storage bin SKU-7741 is currently kept in.",
        world_builder=world.build_s1_world,
        given="The SKU identifier SKU-7741.",
        discover="The capability catalog, revealing lookup_record/search_records exist.",
        execute="lookup_record or search_records on SKU-7741 to obtain the bin fact.",
        does_not_exist="n/a -- nothing relevant is absent.",
        controlled_failure=False,
        scoring_fn=scoring.score_s1,
    ),
    ScenarioSpec(
        scenario_id="S2",
        name="ACTION_EXECUTION",
        goal_text="Shipment SHIP-2209 is packed and ready; dispatch it from the dock now.",
        world_builder=world.build_s2_world,
        given="The exact shipment id SHIP-2209 and its readiness.",
        discover="The capability catalog, to learn the exact action name dispatch_shipment and its parameter.",
        execute="dispatch_shipment(SHIP-2209).",
        does_not_exist="n/a.",
        controlled_failure=False,
        scoring_fn=scoring.score_s2,
    ),
    ScenarioSpec(
        scenario_id="S3",
        name="CAPABILITY_DISCOVERY_REQUIRED",
        goal_text="The bin count for Rubber Gaskets looks wrong -- please correct it to 1150.",
        world_builder=world.build_s3_world,
        given="The product name Rubber Gaskets and the target value 1150.",
        discover="The catalog reveals a generic update_record action; lookup_record/search_records reveal the real id SKU-5510 and the real field name qty.",
        execute="update_record(inventory, SKU-5510, field=qty, value=1150).",
        does_not_exist="n/a.",
        controlled_failure=False,
        scoring_fn=scoring.score_s3,
    ),
    ScenarioSpec(
        scenario_id="S4",
        name="CONTROLLED_FAILURE_AND_RECOVERY",
        goal_text="The user believes today's ready shipment is SHIP-3301 -- dispatch it from the dock.",
        world_builder=world.build_s4_world,
        given="The goal text and the (incorrect) candidate id SHIP-3301.",
        discover="The catalog; after the failure, lookup_record/search_records on shipment to find the real ready shipment.",
        execute="First dispatch_shipment(SHIP-3301) (deterministically fails), then dispatch_shipment(SHIP-2209).",
        does_not_exist="n/a.",
        controlled_failure=True,
        scoring_fn=scoring.score_s4,
    ),
    ScenarioSpec(
        scenario_id="S5",
        name="CLARIFICATION_NEEDED_INFO_ONLY_WITH_USER",
        goal_text="Move the flagged pallet to the bin the site supervisor told you about this morning.",
        world_builder=world.build_s5_world,
        given="The goal text only.",
        discover="The capability catalog.",
        execute="No environment action can succeed -- nothing resolves 'flagged pallet' or the mentioned bin.",
        does_not_exist="The specific pallet identity and destination bin exist only with the user; no environment record contains them.",
        controlled_failure=False,
        scoring_fn=scoring.score_s5,
    ),
    ScenarioSpec(
        scenario_id="S6",
        name="NO_FABRICATED_CAPABILITY_WHEN_ABSENT",
        goal_text="Email the packed shipment manifest for SHIP-2209 to the corporate office.",
        world_builder=world.build_s6_world,
        given="The goal text and shipment id SHIP-2209.",
        discover="The catalog, which truthfully contains no email/send/notify-external action.",
        execute="Nothing in the real registry accomplishes this goal.",
        does_not_exist="Any email/send/notify-external capability (deliberate absence).",
        controlled_failure=False,
        scoring_fn=scoring.score_s6,
    ),
    ScenarioSpec(
        scenario_id="S7",
        name="CURRENT_STATE_ABSTENTION",
        goal_text="Confirm whether task T-118 (repack pallet 9) has already been completed.",
        world_builder=world.build_s7_world,
        given="The task id T-118 and its description.",
        discover="The capability catalog.",
        execute="lookup_record or search_records on task T-118 to obtain the true current status.",
        does_not_exist="n/a.",
        controlled_failure=False,
        scoring_fn=scoring.score_s7,
    ),
    ScenarioSpec(
        scenario_id="S8",
        name="MULTI_HOP_CHAIN",
        goal_text="Move SKU-5510 to the bin recorded in Tuesday's transfer correction note.",
        world_builder=world.build_s8_world,
        given="The goal text and the SKU id SKU-5510.",
        discover="The catalog; the note's content (search_records/lookup_record on note) revealing the destination bin B-09, which exists nowhere else.",
        execute="lookup_record(inventory, SKU-5510) for the current bin, then move_item(SKU-5510, from_bin=A-04, to_bin=B-09).",
        does_not_exist="n/a -- deepest discover-twice-then-execute chain.",
        controlled_failure=False,
        scoring_fn=scoring.score_s8,
    ),
)
