# Runtime resource profiles — minimal UI contract (URI-RUNTIME-VRAM-R1 candidate)

Status: CANDIDATE, not qualified, not integrated. The owner owns the decision to adopt it. The UI V2 thread owns all
presentation. This contract describes only what the runtime offers and how the controls below the chat box map onto it.
The frozen Runtime v1 profile stays the verified fallback.

## Controls and what each one costs

| Control | Values | Runtime effect | Reload? |
|---|---|---|---|
| Thinking | Off / On | Turn parameter `depth`: Off = `fast`, On = `normal` (768-token thinking budget, the qualified NORMAL tier). Core seams stay FAST either way. Unbounded thinking is never offered (frozen policy). | No. It applies per turn on the running server (verified: `chat_template_kwargs.enable_thinking` + `thinking_budget_tokens`). |
| Vision | Off / On | Vision projector off / on the GPU (or on the CPU, see the profile table). | Yes. llama.cpp b11425 cannot unload or load only the projector. |
| Context | 16K / 32K / 64K / 128K | `-c` of the server. | Yes. |
| (internal) MTP | on / off | Speculative draft head. It is not a UI control; the profile chooses it. | Yes. |

Thinking needs no new runtime interface: `POST /oi/v1/turns` already accepts `depth` (`reasoning_policy.USER_DEPTHS`).
The helper `runtime_profiles.thinking_depth(on)` gives the mapping.

## Runtime interface (Python, `uri_operational_intelligence/runtime_profiles.py`)

- `derive_config(frozen_cfg, ctx, vision, mtp)` gives the in-memory profile config. The frozen combination
  (32K, vision GPU, MTP on) returns the frozen object unchanged. Unmeasured combinations raise
  `PROFILE_NOT_MEASURED`. Admission never runs on an estimate.
- `describe(cfg)` gives `{id, ctx, vision, mtp, required_mib, qualified, frozen}`. The Brain host writes this as
  `profile` in its report (`brain_host.json`), so the UI can show what is loaded.
- `plan_change(current, context=, vision=, live_tokens=, confirm_shrink=)` gives
  `{reload, target, refused, profile_id}`. Refusals:
  - `CONTEXT_SMALLER_THAN_CONVERSATION`: the new context is smaller than the live conversation. The UI must ask the
    user and pass `confirm_shrink=True`. URI never discards context silently: the history stays in URI's own
    session store and only the KV cache is rebuilt.
  - `PROFILE_NOT_MEASURED` / `CONTEXT_UNSUPPORTED` / `VISION_MODE_UNKNOWN`.
- Brain host: `scripts/ws_brain_host.py --profile <ctx>,<vision>,<mtp>` starts a profile. The host budgets the GPU
  lease and the contention check with the profile's measured `required_mib`, not the frozen 15,626 MiB. Everything
  else is unchanged: lease, contention wait, quiet window, calibration, residency alert, stop and restart requests.

## Switching (Vision On/Off, Context change)

A change is a controlled restart: stop, VRAM release wait, start with the derived config, calibration. URI keeps the
conversation. Measured costs and the slot save/restore result are in `research/runtime_vram_r1/RUNTIME_VRAM_R1_REPORT.md`
(switch test). The UI must:

1. refuse or confirm any change while a turn runs (the worker already refuses host requests during a turn);
2. show the host states it already shows (STOPPING, RELEASE_WAIT, WAITING_FOR_GPU, STARTING, LOADING, CALIBRATING,
   READY / DEGRADED);
3. never fall back silently to another profile. If the target does not fit, the host waits with `GPU_CONTENDED`
   and its explanation, as it does today.

## Not yet wired (follow-up for the UI thread, after owner adoption)

- A host request action `reconfigure` carrying `{ctx, vision}`. Today `brain_health.ACTIONS` = restart / stop / start,
  and a profile is chosen at host start. This was left out on purpose until the profile set is qualified.
- Persisting the user's choice is a UI setting. It must not touch `local_brain.json`.
