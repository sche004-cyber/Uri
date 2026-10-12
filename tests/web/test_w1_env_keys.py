"""Owner decision D3 (2026-10-11): W1 reads the Tavily key from the development folder's .env, never exposing it."""
import os
from pathlib import Path

from uri_web import search as S

SECRET = "tvly-THIS-IS-A-TEST-VALUE-0123456789"


def test_env_file_supplies_tavily_key(tmp_path):
    env = tmp_path / ".env"
    env.write_text(f"# comment\nOTHER_SECRET=nope\nexport TAVILY_API_KEY=\"{SECRET}\"\nBRAVE_API_KEY=\n", encoding="utf-8")
    keys = S.load_env_keys([env])
    assert keys == {"tavily_api_key": SECRET}  # only the provider names; empty values ignored; nothing else kept
    assert "OTHER_SECRET" not in os.environ and os.environ.get("TAVILY_API_KEY") != SECRET  # env untouched


def test_json_file_wins_and_earlier_env_file_wins(tmp_path):
    a, b = tmp_path / "a.env", tmp_path / "b.env"
    a.write_text("TAVILY_API_KEY=first\n")
    b.write_text("TAVILY_API_KEY=second\nSEARXNG_URL=https://searx.example\n")
    env = S.load_env_keys([tmp_path / "missing.env", a, b])
    assert env == {"tavily_api_key": "first", "searxng_url": "https://searx.example"}
    merged = S.merge_keys({"tavily_api_key": "from-json"}, env)
    assert merged["tavily_api_key"] == "from-json" and merged["searxng_url"] == "https://searx.example"


def test_oversized_or_unreadable_env_is_skipped(tmp_path):
    big = tmp_path / ".env"
    big.write_text("TAVILY_API_KEY=x\n" + "#" * 70_000)
    assert S.load_env_keys([big, tmp_path]) == {}


def test_key_from_env_file_never_appears_in_provider_errors_or_repr(tmp_path):
    env = tmp_path / ".env"
    env.write_text(f"TAVILY_API_KEY={SECRET}\n")
    providers = S.providers_from_keys(S.merge_keys({}, S.load_env_keys([env])))
    tav = providers[0]
    assert SECRET not in repr(tav) and SECRET not in str(vars(tav).get("name", ""))
    # error reporting without the key is covered by the W1-AC8 provider tests



def test_worker_reads_dev_folder_env_via_materialization_receipt():
    src = Path("scripts/run_uri_integrated_worker.py").read_text(encoding="utf-8")
    assert "load_env_keys" in src and "candidate_source" in src and "merge_keys" in src
