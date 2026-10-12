"""Local developer provisioning; secrets are written only protected at client."""
import argparse
from pathlib import Path
import sys
import json

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from uri_core.client_runtime.manifest import provision_client


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--server-manifest", required=True)
    p.add_argument("--client-root", required=True)
    p.add_argument("--principal", required=True)
    p.add_argument("--grant", action="append", default=[])
    p.add_argument("--mode", default="office")
    a = p.parse_args()
    try:
        path = provision_client(a.server_manifest, a.client_root, a.principal, a.grant, a.mode)
        print(json.dumps({"result": "PROVISIONED", "manifest": str(path)}))
        return 0
    except Exception:
        print('{"result":"REFUSED","code":"CLIENT_PROVISIONING_REFUSED"}')
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
