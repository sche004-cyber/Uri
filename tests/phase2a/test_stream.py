"""Stream parsing: byte splitting, tails, golden fixtures (REAL captures + SYNTHETIC), schema-drift tolerance."""
from pathlib import Path

import pytest

from uri_supervisor.executors import CLAUDE_CODE, CODEX_CLI, FORBIDDEN_FLAGS, ExecutorSpec, ExecutorSpecError
from uri_supervisor.stream import LineSplitter, interpret_line

FIX = Path(__file__).parent / "fixtures" / "streams"


def run_fixture(name, spec):
    sp, out, tail_seen = LineSplitter(), [], False
    data = (FIX / name).read_bytes()
    for i in range(0, len(data), 7):               # hostile 7-byte chunking
        for line, complete in sp.feed(data[i:i + 7]):
            out.append(interpret_line(line, spec.rules, complete))
    tail = sp.flush_tail()
    if tail:
        out.append(interpret_line(tail, spec.rules, False))
    return out


def labels(its):
    return [s[0] for it in its for s in it.semantics]


def test_splitter_splits_only_on_newline_and_keeps_tail():
    sp = LineSplitter()
    assert sp.feed(b'{"a":1}\r\n{"b"') == [(b'{"a":1}\r\n', True)]
    assert sp.feed(b':2}\n') == [(b'{"b":2}\n', True)]
    assert sp.feed(b'partial') == []
    assert sp.flush_tail() == b'partial'
    assert sp.flush_tail() == b''


def test_splitter_does_not_split_on_other_separators():
    sp = LineSplitter()
    # U+2028 / U+0085 / lone CR must not split lines
    raw = '{"t":"a\u2028b\u0085c"}'.encode() + b"\r{\"x\":1}\n"
    assert sp.feed(raw) == [(raw, True)]


def test_real_claude_auth_failure_is_not_a_success_claim():
    """REAL capture (claude 2.1.287): subtype is 'success' but is_error is true and the text is an auth failure."""
    its = run_fixture("real_claude_2_1_287_auth_failure.ndjson", CLAUDE_CODE)
    ls = labels(its)
    assert "terminal_error_claim" in ls
    assert "terminal_success_claim" not in ls, "naive subtype=='success' parsing would call an auth failure a success"
    assert "session" in ls


def test_real_codex_model_rejected_is_error_claim():
    its = run_fixture("real_codex_0_158_0_model_rejected.ndjson", CODEX_CLI)
    ls = labels(its)
    assert ls.count("terminal_error_claim") == 1 and "terminal_success_claim" not in ls
    assert "error_event" in ls and "session" in ls and "warning" in ls


def test_synthetic_claude_success_and_unknown_fields():
    ls = labels(run_fixture("SYNTHETIC_claude_success.ndjson", CLAUDE_CODE))
    assert ls.count("terminal_success_claim") == 1 and "session" in ls


def test_interrupted_streams_have_no_terminal():
    for name, spec in (("SYNTHETIC_claude_interrupted_no_result.ndjson", CLAUDE_CODE),
                       ("SYNTHETIC_codex_interrupted.ndjson", CODEX_CLI)):
        ls = labels(run_fixture(name, spec))
        assert not {"terminal_success_claim", "terminal_error_claim"} & set(ls), name


def test_truncated_terminal_looking_tail_is_never_authoritative():
    its = run_fixture("SYNTHETIC_claude_truncated_result.ndjson", CLAUDE_CODE)
    assert its[-1].parse_status == "incomplete_line"
    assert "terminal_success_claim" not in labels(its)


def test_claude_error_subtype_is_error():
    ls = labels(run_fixture("SYNTHETIC_claude_error_max_turns.ndjson", CLAUDE_CODE))
    assert "terminal_error_claim" in ls and "terminal_success_claim" not in ls


def test_codex_failed_command_and_text_success_are_separate_facts():
    its = run_fixture("SYNTHETIC_codex_failed_command_text_success.ndjson", CODEX_CLI)
    tool = [s for it in its for s in it.semantics if s[0] == "tool_result"][0]
    assert tool[1]["exit_code"] == 1
    assert labels(its).count("terminal_success_claim") == 1      # the executor DID claim success; URI must not believe it


def test_unknown_events_and_fields_tolerated():
    its = run_fixture("SYNTHETIC_codex_unknown_events.ndjson", CODEX_CLI)
    assert all(it.parse_status == "ok" for it in its)
    assert "terminal_success_claim" in labels(its)


@pytest.mark.parametrize("raw,status", [(b"not json\n", "invalid_json"), (b"[1,2]\n", "not_object"), (b"\xff\xfe\n", "invalid_utf8"),
                                        (b"\n", "ok"), (b'{"type":"turn.completed"}\r\n', "ok")])
def test_line_statuses(raw, status):
    it = interpret_line(raw, CODEX_CLI.rules, True)
    assert it.parse_status == status


def test_incomplete_line_never_yields_semantics_even_if_valid_json():
    it = interpret_line(b'{"type":"turn.completed"}', CODEX_CLI.rules, False)
    assert it.semantics == () and it.parse_status == "incomplete_line"


def test_type_strictness_true_is_not_one():
    # a rule requiring literal True must not match 1 (JSON ints vs bools)
    it = interpret_line(b'{"type":"result","subtype":"success","is_error":1}\n', CLAUDE_CODE.rules, True)
    assert "terminal_success_claim" not in [s[0] for s in it.semantics]


def test_spec_refuses_bypass_flags_and_roundtrips():
    spec = ExecutorSpec("x", "python", ("--dangerously-skip-permissions",))
    with pytest.raises(ExecutorSpecError):
        spec.build_argv(resolved_executable="python")
    assert ExecutorSpec.from_json(CODEX_CLI.to_json()).spec_sha256() == CODEX_CLI.spec_sha256()
    assert "--dangerously-bypass-approvals-and-sandbox" in FORBIDDEN_FLAGS


def test_env_never_forwards_api_keys():
    env = CLAUDE_CODE.build_env({"PATH": "p", "ANTHROPIC_API_KEY": "secret", "CLAUDE_CODE_OAUTH_TOKEN": "t", "RANDOM": "x"})
    assert "ANTHROPIC_API_KEY" not in env and "RANDOM" not in env and env["CLAUDE_CODE_OAUTH_TOKEN"] == "t"
