"""LFM2.5-350M Semantic Decoder for URIv1 Step 1 (Batch A2.5 Stage 3).

Executes single-pass Step-1 semantic decoding backed by local LFM2.5-350M running
on LM Studio endpoint (http://127.0.0.1:1234/v1).

Supports:
- Mode A: LFM without deterministic RAR (Message + TurnFrame + ActiveContext)
- Mode B: LFM with deterministic RAR (Message + TurnFrame + ActiveContext + Deterministic RAR anchors)

Invariants:
- Exactly ONE inference per turn (no multi-call decomposition).
- Zero post-hoc semantic repair.
- Native json_schema constrained structured decoding.
"""

from __future__ import annotations

from enum import Enum
import json
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple, Union

from uri_v1.turn.active_context import ActiveContext
from uri_v1.turn.contracts import DecodedRequest
from uri_v1.turn.decoder import DecodeInput, SemanticDecoder
from uri_v1.turn.lfm_wire import (
    LFM_SYSTEM_PROMPT,
    LFM_WIRE_SCHEMA,
    LFM_WIRE_SCHEMA_NAME,
    build_lfm_mode_a_prompt,
    build_lfm_mode_b_prompt,
    normalize_lfm_wire,
)
from uri_v1.turn.needle_wire import DecodeError, DecodeErrorReason
from uri_v1.turn.rar_contracts import (
    RARCandidate,
    RAREvidence,
    RAROutcome,
    RARQuery,
)
from uri_v1.turn.rar_deterministic import resolve_rar_deterministic_extended
from uri_v1.turn.turn_frame import TurnFrame
from uri_v1.turn.turn_frame_builder import build_turn_frame


class LFMDecoderMode(str, Enum):
    """Evaluation modes for RAR Benefit Ablation."""

    MODE_A_WITHOUT_RAR = "mode_a_without_rar"
    MODE_B_WITH_RAR = "mode_b_with_rar"


class LFMDecodeResult:
    """Outcome of an LFM2.5-350M decode invocation."""

    __slots__ = (
        "decoded_request",
        "error",
        "mode",
        "raw_wire",
        "raw_content",
        "prompt_tokens",
        "completion_tokens",
        "latency_ms",
        "rar_latency_ms",
        "turn_frame",
        "active_context",
        "rar_facts",
    )

    def __init__(
        self,
        *,
        decoded_request: Optional[DecodedRequest] = None,
        error: Optional[DecodeError] = None,
        mode: str = LFMDecoderMode.MODE_A_WITHOUT_RAR.value,
        raw_wire: Optional[Dict[str, Any]] = None,
        raw_content: Optional[str] = None,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        latency_ms: Optional[float] = None,
        rar_latency_ms: Optional[float] = None,
        turn_frame: Optional[TurnFrame] = None,
        active_context: Optional[ActiveContext] = None,
        rar_facts: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.decoded_request = decoded_request
        self.error = error
        self.mode = mode
        self.raw_wire = raw_wire
        self.raw_content = raw_content
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.latency_ms = latency_ms
        self.rar_latency_ms = rar_latency_ms
        self.turn_frame = turn_frame
        self.active_context = active_context
        self.rar_facts = rar_facts

    @property
    def ok(self) -> bool:
        return self.decoded_request is not None and self.error is None


class LFMSemanticDecoder(SemanticDecoder):
    """Step-1 Semantic Decoder backed by LFM2.5-350M via LM Studio."""

    def __init__(
        self,
        endpoint_url: str = "http://127.0.0.1:1234/v1/chat/completions",
        model_id: str = "lfm2.5-350m",
        timeout: float = 30.0,
        temperature: float = 0.0,
        max_tokens: int = 700,
    ) -> None:
        self.endpoint_url = endpoint_url
        self.model_id = model_id
        self.timeout = timeout
        self.temperature = temperature
        self.max_tokens = max_tokens

    def decode(self, input_data: DecodeInput) -> DecodedRequest:
        """Implements SemanticDecoder ABC interface in default Mode B."""
        result = self.decode_with_result(
            raw_text=input_data.raw_text,
            mode=LFMDecoderMode.MODE_B_WITH_RAR,
        )
        if result.decoded_request is not None:
            return result.decoded_request
        raise RuntimeError(f"LFM decode failed: {result.error}")

    decode_request = decode

    def decode_with_result(
        self,
        raw_text: str,
        *,
        active_context: Optional[ActiveContext] = None,
        turn_frame: Optional[TurnFrame] = None,
        mode: Union[str, LFMDecoderMode] = LFMDecoderMode.MODE_B_WITH_RAR,
    ) -> LFMDecodeResult:
        """Executes structured semantic decode under specified mode with timing."""
        if isinstance(mode, str):
            mode = LFMDecoderMode(mode)

        start_time = time.perf_counter()
        rar_latency = 0.0

        # Build TurnFrame if not provided
        if turn_frame is None:
            turn_frame = build_turn_frame(raw_text)

        rar_facts: Dict[str, Any] = {
            "resolved_anchors": {},
            "unresolved": [],
            "ambiguous_candidates": {},
        }

        # In Mode B, run deterministic RAR for candidate references
        if mode == LFMDecoderMode.MODE_B_WITH_RAR:
            rar_start = time.perf_counter()
            rar_facts = self._resolve_rar_for_turn(raw_text, turn_frame, active_context)
            rar_latency = (time.perf_counter() - rar_start) * 1000.0
            user_prompt = build_lfm_mode_b_prompt(
                raw_text, turn_frame=turn_frame, active_context=active_context, rar_facts=rar_facts
            )
        else:
            user_prompt = build_lfm_mode_a_prompt(
                raw_text, turn_frame=turn_frame, active_context=active_context
            )

        payload = {
            "model": self.model_id,
            "messages": [
                {"role": "system", "content": LFM_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": LFM_WIRE_SCHEMA_NAME,
                    "strict": True,
                    "schema": LFM_WIRE_SCHEMA,
                },
            },
        }

        try:
            req = urllib.request.Request(
                self.endpoint_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            total_lat = (time.perf_counter() - start_time) * 1000.0
            return LFMDecodeResult(
                error=DecodeError(
                    DecodeErrorReason.MALFORMED_OUTPUT,
                    f"LM Studio connection error: {e}",
                ),
                mode=mode.value,
                latency_ms=total_lat,
                rar_latency_ms=rar_latency,
                turn_frame=turn_frame,
                active_context=active_context,
                rar_facts=rar_facts,
            )
        except Exception as e:
            total_lat = (time.perf_counter() - start_time) * 1000.0
            return LFMDecodeResult(
                error=DecodeError(
                    DecodeErrorReason.MALFORMED_OUTPUT,
                    f"Inference exception: {e}",
                ),
                mode=mode.value,
                latency_ms=total_lat,
                rar_latency_ms=rar_latency,
                turn_frame=turn_frame,
                active_context=active_context,
                rar_facts=rar_facts,
            )

        total_lat = (time.perf_counter() - start_time) * 1000.0

        # Parse completion
        usage = resp_data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens")

        choices = resp_data.get("choices", [])
        if not choices:
            return LFMDecodeResult(
                error=DecodeError(
                    DecodeErrorReason.MISSING_REQUIRED_STRUCTURE,
                    "No choices returned by endpoint",
                ),
                mode=mode.value,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=total_lat,
                rar_latency_ms=rar_latency,
                turn_frame=turn_frame,
                active_context=active_context,
                rar_facts=rar_facts,
            )

        content = choices[0].get("message", {}).get("content", "")
        if not content:
            return LFMDecodeResult(
                error=DecodeError(
                    DecodeErrorReason.MISSING_REQUIRED_STRUCTURE,
                    "Empty content string returned",
                ),
                mode=mode.value,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=total_lat,
                rar_latency_ms=rar_latency,
                turn_frame=turn_frame,
                active_context=active_context,
                rar_facts=rar_facts,
            )

        try:
            wire_dict = json.loads(content)
        except json.JSONDecodeError as e:
            return LFMDecodeResult(
                error=DecodeError(
                    DecodeErrorReason.MALFORMED_OUTPUT,
                    f"Invalid JSON from model: {e}",
                ),
                raw_content=content,
                mode=mode.value,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=total_lat,
                rar_latency_ms=rar_latency,
                turn_frame=turn_frame,
                active_context=active_context,
                rar_facts=rar_facts,
            )

        decoded_request = normalize_lfm_wire(wire_dict, raw_text)

        return LFMDecodeResult(
            decoded_request=decoded_request,
            raw_wire=wire_dict,
            raw_content=content,
            mode=mode.value,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=total_lat,
            rar_latency_ms=rar_latency,
            turn_frame=turn_frame,
            active_context=active_context,
            rar_facts=rar_facts,
        )

    def _resolve_rar_for_turn(
        self,
        raw_text: str,
        turn_frame: TurnFrame,
        active_context: Optional[ActiveContext],
    ) -> Dict[str, Any]:
        """Runs deterministic RAR over candidate referring expressions in the turn."""
        facts: Dict[str, Any] = {
            "resolved_anchors": {},
            "unresolved": [],
            "ambiguous_candidates": {},
        }

        # Build candidate pool from ActiveContext
        candidates: List[RARCandidate] = []
        if active_context is not None:
            for art in active_context.active_artifacts:
                candidates.append(
                    RARCandidate(
                        id=art.id,
                        title=art.name,
                        candidate_type=art.artifact_type or "document",
                        recency_rank=0,
                    )
                )
            for ent in active_context.active_entities:
                candidates.append(
                    RARCandidate(
                        id=ent.id,
                        title=ent.name,
                        candidate_type=ent.category or "person",
                        recency_rank=0,
                    )
                )

        if not candidates or not turn_frame.candidate_references:
            return facts

        # Resolve each referring expression deterministically
        for cand_ref in turn_frame.candidate_references:
            ref_expr = cand_ref.expression
            evidence = RAREvidence(
                recency_hint="same" if ref_expr in ("same", "same thing") else None,
                negation_spans=turn_frame.negation_spans,
            )
            query = RARQuery(
                reference_expression=ref_expr,
                candidates=tuple(candidates),
                local_evidence=evidence,
            )
            trace = resolve_rar_deterministic_extended(query)
            res = trace.resolution

            if res.outcome == RAROutcome.RESOLVED and res.candidate_id:
                cand_title = next((c.title for c in candidates if c.id == res.candidate_id), res.candidate_id)
                facts["resolved_anchors"][ref_expr] = f"{res.candidate_id} ({cand_title})"
            elif res.outcome == RAROutcome.AMBIGUOUS:
                facts["ambiguous_candidates"][ref_expr] = list(res.ambiguous_candidate_ids)
            else:
                facts["unresolved"].append(ref_expr)

        return facts
