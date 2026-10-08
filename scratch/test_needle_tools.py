import sys
from pathlib import Path
sys.path.insert(0, ".")

from uri_v1.turn.needle_decoder import NeedleBridgeTransport, default_venv_python

bridge_script = Path("uri_v1/turn/needle_bridge_runtime.py")
transport = NeedleBridgeTransport(default_venv_python(), bridge_script)

tools = [
    {
        "name": "uri_edge_workbook_inspect",
        "description": "Inspect structure, sheet names, and column headers of a workbook",
        "parameters": {"type": "object", "properties": {"target": {"type": "string"}}, "required": ["target"]}
    },
    {
        "name": "uri_edge_script_workbook_diagnose",
        "description": "Diagnose why a script fails to access columns in a workbook",
        "parameters": {"type": "object", "properties": {"script": {"type": "string"}, "workbook": {"type": "string"}}, "required": ["script", "workbook"]}
    },
    {
        "name": "uri_edge_script_workbook_literal_remap",
        "description": "Remap literal column headers in a script for a workbook",
        "parameters": {"type": "object", "properties": {"script": {"type": "string"}, "old_col": {"type": "string"}, "new_col": {"type": "string"}}, "required": ["script", "old_col", "new_col"]}
    }
]

cases = [
    "Inspect the structure, sheet names, and column headers of payroll.xlsx",
    "Diagnose why process_data.py fails to access columns in sales.xlsx",
    "Remap literal column header 'qty' to 'quantity' in transform.py for sales.xlsx"
]

transport.load()
for p in cases:
    transport.reset()
    envelope = transport._request({
        "operation": "decode",
        "system": "You are Needle 3. Select and call the appropriate tool for the user request.",
        "schema": tools[0], # wait, decode takes one schema or tools?
        "text": p,
        "max_new_tokens": 100
    })
