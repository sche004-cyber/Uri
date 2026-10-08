"""C6 offline client readiness, reusing the exact C3 manifest validator.

No legacy preferences, UI launch, native account discovery or migration.
This is a preflight component; live UI parity remains an independent gate.
"""
from pathlib import Path

from uri_core.client_runtime.manifest import ClientManifest
from uri_core.core.runtime_identity import sha


def client_preflight(manifest_path):
    manifest = manifest_path if isinstance(manifest_path, ClientManifest) else ClientManifest(manifest_path)
    m = manifest.data
    ui = m["ui_binary"]
    ui_valid = False
    if ui is not None:
        # Manifest validation checks binary digest. Requiring its placement
        # inside this new installation prevents legacy build adoption here.
        path = Path(ui).resolve()
        ui_valid = path.is_relative_to(Path(m["client_root"]).resolve()) and sha(path) == m["ui_sha256"]
    return {"schema_version": "uri.client.v1", "client_id": m["client_id"],
            "server_id": m["server_id"], "worker_manifest": "VALIDATED",
            "ui_build": "PINNED_IN_CLIENT_INSTALLATION" if ui_valid else "CLIENT_UI_PENDING_C6",
            "ui_parity": "NOT_LIVE_QUALIFIED", "native_adapter": "NOT_LIVE_QUALIFIED",
            "migration": "NOT_AUTHORIZED", "production_cutover": False}
