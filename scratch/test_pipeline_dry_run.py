import json
import os
import sys
import time
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from uri_v1.turn.needle_decoder import NeedleBridgeTransport, default_venv_python
from experimental.edge_model_tests.verifier import EdgeTaskVerifier
from experimental.edge_model_tests.deterministic_path import DeterministicBaseline

# Load battery
battery_path = ROOT / "experimental" / "edge_model_tests" / "battery.json"
with open(battery_path, "r", encoding="utf-8") as f:
    battery = json.load(f)

cases = battery["cases"]
print(f"Loaded {len(cases)} cases.")
