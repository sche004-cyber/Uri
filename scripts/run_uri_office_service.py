"""Entry point the URI application uses to start the URI Office service on demand.

    <interpreter> -B -I scripts/run_uri_office_service.py run --state <dir> --parent-pid <app pid> [--brain-from-runtime]

`-I` keeps the interpreter isolated (no PYTHON* variables, no current-directory imports), so this script puts the URI
source folder it lives in on the import path itself and then runs `uri_office.service`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from uri_office.service import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
