"""USER-authenticated qualification routes, explicitly enabled on a loopback server."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, StrictBool
from typing import Literal

ROUTE_CLASSIFICATIONS = {
    ('POST', '/desktop/harness-test/prepare'): 'USER',
    ('POST', '/desktop/harness-test/{approval_id}/approve'): 'USER',
    ('GET', '/desktop/harness-test/providers'): 'USER',
    ('POST', '/desktop/harness-test/providers/refresh'): 'USER',
    ('POST', '/desktop/harness-test/tasks/prepare'): 'USER',
    ('GET', '/desktop/harness-test/tasks'): 'USER',
    ('POST', '/desktop/harness-test/tasks/{approval_id}/start'): 'USER',
    ('GET', '/desktop/harness-test/tasks/{task_id}'): 'USER',
    ('POST', '/desktop/harness-test/tasks/{task_id}/cancel'): 'USER',
    ('POST', '/desktop/harness-test/tasks/{task_id}/recover'): 'USER',
}

class Approval(BaseModel):
    authorized: StrictBool
    class Config:
        extra = 'forbid'


class Selection(BaseModel):
    provider: Literal['claude_code', 'antigravity', 'codex']
    class Config:
        extra = 'forbid'


class Recovery(Approval):
    action: Literal['choose', 'wait', 'local', 'stop']


def router_for(service, authenticated_principal, controller=None):
    from .controller import HarnessController
    controller = controller or HarnessController(service)
    router = APIRouter(prefix='/desktop/harness-test')

    @router.get('/providers')
    def providers(principal=Depends(authenticated_principal)):
        return controller.providers(user_id=principal.user_id)

    @router.post('/providers/refresh')
    def refresh(principal=Depends(authenticated_principal)):
        return controller.providers(refresh=True, user_id=principal.user_id)

    @router.post('/tasks/prepare')
    def selected_prepare(body: Selection, principal=Depends(authenticated_principal)):
        try:
            return controller.prepare(principal.user_id, body.provider)
        except PermissionError:
            raise HTTPException(403, 'Selected harness is ineligible; no task submitted') from None
        except ValueError:
            raise HTTPException(409, 'Preparation capacity reached') from None

    @router.get('/tasks')
    def tasks(principal=Depends(authenticated_principal)):
        return controller.list_tasks(principal.user_id)

    @router.post('/tasks/{approval_id}/start')
    def start(approval_id: str, body: Approval, principal=Depends(authenticated_principal)):
        try:
            return controller.start(principal.user_id, approval_id, body.authorized)
        except PermissionError:
            raise HTTPException(403, 'Approval unavailable, run busy or harness ineligible') from None

    @router.get('/tasks/{task_id}')
    def task(task_id: str, principal=Depends(authenticated_principal)):
        try:
            return controller.get(principal.user_id, task_id)
        except PermissionError:
            raise HTTPException(404, 'Task unavailable') from None

    @router.post('/tasks/{task_id}/cancel')
    def cancel(task_id: str, principal=Depends(authenticated_principal)):
        try:
            return controller.cancel(principal.user_id, task_id)
        except PermissionError:
            raise HTTPException(404, 'Task unavailable') from None

    @router.post('/tasks/{task_id}/recover')
    def recover(task_id: str, body: Recovery, principal=Depends(authenticated_principal)):
        try:
            return controller.recover(principal.user_id, task_id, body.action, body.authorized)
        except PermissionError:
            raise HTTPException(403, 'Recovery unauthorized or alternative unqualified; work retained') from None

    @router.post('/prepare')
    def prepare(principal=Depends(authenticated_principal)):
        try:
            return service.prepare(principal.user_id)
        except ValueError:
            raise HTTPException(409, 'Test capacity reached') from None

    @router.post('/{approval_id}/approve')
    def approve(approval_id: str, body: Approval, principal=Depends(authenticated_principal)):
        try:
            if 'claude_code' in controller.registry.quota_blocked:
                raise PermissionError('QUOTA_RECOVERY_REQUIRED')
            return service.execute(principal.user_id, approval_id, body.authorized)
        except PermissionError:
            raise HTTPException(403, 'Approval missing, expired, consumed or unauthorized') from None
        except Exception:
            # Never serialize CLI stderr, exception messages or private paths to the client.
            raise HTTPException(503, 'Harness test failed; check CLI installation and login manually. Approval consumed.') from None

    return router
