"""Authenticated preparation-only routes. No executor/run endpoint is present."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, StrictInt, constr


class Request(BaseModel):
    session_id: constr(min_length=1, max_length=128)
    request: constr(min_length=1, max_length=2000)
    model_config = ConfigDict(extra='forbid')


class Revision(BaseModel):
    revision: StrictInt
    model_config = ConfigDict(extra='forbid')


class Response(Revision):
    answer: constr(min_length=1, max_length=2000) | None = None
    correction: constr(min_length=1, max_length=2000) | None = None


class Selection(Revision):
    executor: constr(min_length=1, max_length=128)


def router_for(controller, authenticated_principal):
    router = APIRouter(prefix='/desktop/intent', tags=['provisional-intent-preparation'])
    def invoke(fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (PermissionError, FileNotFoundError):
            raise HTTPException(404, 'Intent unavailable') from None
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None

    @router.post('/begin')
    def begin(body: Request, principal=Depends(authenticated_principal)):
        return invoke(controller.begin, principal.user_id, body.session_id, body.request)

    @router.get('/{cycle_id}')
    def get(cycle_id: str, principal=Depends(authenticated_principal)):
        return invoke(controller.get, principal.user_id, cycle_id)

    @router.post('/{cycle_id}/respond')
    def respond(cycle_id: str, body: Response, principal=Depends(authenticated_principal)):
        return invoke(controller.update, principal.user_id, cycle_id, body.revision, answer=body.answer, correction=body.correction)

    @router.post('/{cycle_id}/accept')
    def accept(cycle_id: str, body: Revision, principal=Depends(authenticated_principal)):
        return invoke(controller.accept, principal.user_id, cycle_id, body.revision)

    @router.post('/{cycle_id}/executor')
    def select(cycle_id: str, body: Selection, principal=Depends(authenticated_principal)):
        return invoke(controller.choose, principal.user_id, cycle_id, body.revision, body.executor)

    @router.post('/{cycle_id}/deny')
    def deny(cycle_id: str, body: Revision, principal=Depends(authenticated_principal)):
        return invoke(controller.deny, principal.user_id, cycle_id, body.revision)
    return router
