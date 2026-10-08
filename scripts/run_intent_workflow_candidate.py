"""Opt-in isolated composition; never launches an external execution harness."""
import argparse
import os
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--enable-intent-preparation', action='store_true', required=True)
    parser.add_argument('--enable-brain-requests', action='store_true', help='Explicitly permit requests through the existing URI Brain router')
    parser.add_argument('--bridge-dir', type=Path)
    parser.add_argument('--port', type=int, default=8022)
    parser.add_argument('--state-dir', type=Path, default=ROOT / 'scratch' / 'intent_candidate_state')
    args = parser.parse_args()
    state = args.state_dir.resolve()
    state.mkdir(parents=True, exist_ok=True)
    os.chdir(state)
    os.environ.setdefault('URI_EXTERNAL_CREDENTIAL_SECRET', secrets.token_urlsafe(48))
    from uri_core.app.server import app, _get_user_context, _resolve_authenticated_principal
    from uri_core.core.model_reasoning_gateway import ModelReasoningGateway
    from uri_v1.desktop_harness.controller import HarnessController
    from uri_v1.desktop_harness.routes import router_for as harness_router
    from uri_v1.desktop_harness.service import DesktopHarnessService
    from uri_v1.memory.log import MemoryLog
    from uri_v1.memory.sources import SourceRegistry
    from experimental.intent_workflow.context import ExistingContext, bridge_source
    from experimental.intent_workflow.controller import IntentController, DISCOVERY_INSTRUCTIONS
    from uri_core.core.model_reasoning_adapter import OllamaReasoningAdapter
    from experimental.intent_workflow.routes import router_for
    service = DesktopHarnessService(state / 'harness')
    harness = HarnessController(service)
    def memory(user_id):
        log = MemoryLog(user_id, service.root / 'private')
        return log, SourceRegistry(log)
    def reasoner(user_id):
        existing = _get_user_context(user_id).orchestrator.model_reasoning_gateway
        gateway = ModelReasoningGateway(policy_path=ROOT / 'URI_Model_Centric_Architecture_Docs/URI_AI_OPERATING_POLICY.md',
                                     soul_path=ROOT / 'URI_Model_Centric_Architecture_Docs/soul.md',
                                     registry_path=ROOT / 'uri_workspace/capabilities_registry.json',
                                     model_callable=OllamaReasoningAdapter(principal=existing.model_callable._principal, system_prompt=DISCOVERY_INSTRUCTIONS) if args.enable_brain_requests else None,
                                     instruction=DISCOVERY_INSTRUCTIONS)
        from uri_core.core.model_router import get_router
        from uri_core.config.model_roles import ROLE_REASONING
        plan = get_router().resolve(ROLE_REASONING, getattr(existing.model_callable, '_principal', None))
        gateway.reasoning_route = dict(provider=plan.provider_id, model=plan.model)
        return gateway
    controller = IntentController(state / 'intent_checkpoints',
                                  context=ExistingContext(_get_user_context, memory=memory,
                                      bridge=bridge_source(args.bridge_dir.resolve()) if args.bridge_dir else None),
                                  reasoner=reasoner, executors=lambda user: harness.providers(user_id=user)['providers'])
    app.include_router(router_for(controller, _resolve_authenticated_principal))
    app.include_router(harness_router(service, _resolve_authenticated_principal, controller=harness))
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=args.port, access_log=False)


if __name__ == '__main__':
    main()
