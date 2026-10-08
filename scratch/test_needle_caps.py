import sys
from pathlib import Path
sys.path.insert(0, ".")

from uri_v1.turn.needle_decoder import NeedleBridgeTransport, default_venv_python

bridge_script = Path("uri_v1/turn/needle_bridge_runtime.py")
transport = NeedleBridgeTransport(default_venv_python(), bridge_script)

system_prompt = (
    "You are URI Needle 3, selecting an eligible capability for the user task.\n"
    "Select the capability that exactly matches the user request.\n"
    "Always call select_capability."
)

schema = {
    "name": "select_capability",
    "description": "Select the single eligible capability for the task.",
    "parameters": {
        "type": "object",
        "properties": {
            "capability": {
                "type": "string",
                "enum": [
                    "uri.edge.workbook_inspect",
                    "uri.edge.script_workbook_diagnose",
                    "uri.edge.script_workbook_literal_remap"
                ],
                "description": "The selected capability."
            }
        },
        "required": ["capability"],
        "additionalProperties": False
    }
}

cases = [
    "Inspect the structure, sheet names, and column headers of payroll.xlsx",
    "Diagnose why process_data.py fails to access columns in sales.xlsx",
    "Remap literal column header 'qty' to 'quantity' in transform.py for sales.xlsx"
]

transport.load()
for p in cases:
    transport.reset()
    resp = transport.decode(p, system=system_prompt, schema=schema, max_new_tokens=100)
    print("\nPrompt:", p)
    print("Function calls:", resp.get("function_calls"))
    print("Suppressed calls:", resp.get("suppressed_calls"))
    print("Reasoning:", resp.get("reasoning"))
    print("Latency ms:", resp.get("_bridge_latency_ms"))

transport.close()
