"""The original malformed operation must be impossible under the new advertised schema.

Uses the already-installed PC JSON Schema validator; no runtime dependency is added.
These are contract tests, not evidence of live constrained model decoding.
"""
import copy

import jsonschema
import pytest

from uri_office import brain, ops
from uri_office.errors import OfficeError


def operation(**values):
    out = {k: None for k in ops.BRAIN_SCHEMA["properties"]["ops"]["items"]["required"]}
    out.update(values)
    return out


def valid(op, sources=None):
    schema = brain.schema_for("new", sources)
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema).is_valid({"message": "", "ops": [op]})


def test_original_null_name_reproduces_schema_runtime_disagreement():
    op = operation(op="add_sheet", name=None)
    assert jsonschema.Draft202012Validator(ops.BRAIN_SCHEMA).is_valid({"message": "", "ops": [op]})
    with pytest.raises(OfficeError) as exc:
        ops.to_cell_edits(op, engine="new", sheets=["Sheet1"])
    assert exc.value.code == "BAD_SHEET_NAME"
    assert not valid(op)


@pytest.mark.parametrize("name", [None, "", "x" * 32, "bad/name", "bad\\name", "bad:name", "bad?name",
                                   "bad*name", "[bad]", "bad\x00name", "bad\x0bname", "bad\ud800name", "bad\uffffname"])
@pytest.mark.parametrize("sources", [None, [], [{"source": "S1", "sheets": [{"name": "Data"}]}]])
def test_invalid_names_refused_by_schema_and_runtime(name, sources):
    op = operation(op="add_sheet", name=name)
    assert not valid(op, sources)
    with pytest.raises(OfficeError) as exc:
        ops.to_cell_edits(op, engine="new", sheets=["Sheet1"])
    assert exc.value.code == "BAD_SHEET_NAME"


@pytest.mark.parametrize("name", ["Summary", "x" * 31, "Résumé", "O'Brien", "日本語"])
def test_valid_names_remain_supported(name):
    op = operation(op="add_sheet", name=name)
    assert valid(op)
    assert ops.to_cell_edits(op, engine="new", sheets=["Sheet1"]) == [{"op": "add_sheet", "name": name}]


def test_empty_cell_copy_and_formula_keep_nullable_unused_name():
    for op in [operation(op="set_values", sheet="Sheet1", range="A1:A1", values=[[None]]),
               operation(op="set_formula", sheet="Sheet1", cell="B1", formula="=SUM(A1:A3)")]:
        assert valid(op)
        assert len(ops.to_cell_edits(op, engine="new", sheets=["Sheet1"])) == 1


def test_existing_global_schema_and_other_engines_unchanged():
    before = copy.deepcopy(ops.BRAIN_SCHEMA)
    brain.schema_for("new", [{"source": "S1", "sheets": [{"name": "Data"}]}])
    assert ops.BRAIN_SCHEMA == before
    assert brain.schema_for("google", None) == before
    assert brain.schema_for("local", None) == before


def test_duplicate_sheet_guard_remains_authoritative():
    op = operation(op="add_sheet", name="sheet1")
    assert valid(op)
    with pytest.raises(OfficeError) as exc:
        ops.to_cell_edits(op, engine="new", sheets=["Sheet1"])
    assert exc.value.code == "BAD_SHEET_NAME"
