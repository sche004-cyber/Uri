"""URI A2UI: a presentation contract for agent-produced interfaces (docs/a2ui/A2UI_ARCHITECTURE.md).

Wire format: a subset of A2UI v0.9.1 (createSurface / updateComponents / updateDataModel / deleteSurface, client
`action`). Catalog: `uri:a2ui/catalog/v1`, a restricted set of components whose properties are whitelisted.

This package only describes and validates interfaces. It holds no authority: it cannot approve, execute, send or
change state. A surface names actions; the renderer maps a name to one registered client call; the owner of the
capability re-validates every action. Every definition is treated as untrusted until `validate` accepts it.

  catalog   component and theme whitelist, limits
  actions   registered action names and their context schemas
  validate  message / surface / action validation (stable error codes)
  surface   Surface: components + data model + bound read-only data + allowed actions -> messages and digest
"""

from .catalog import CATALOG_ID, VERSION  # noqa: F401
from .validate import A2uiInvalid  # noqa: F401

__all__ = ["CATALOG_ID", "VERSION", "A2uiInvalid"]
