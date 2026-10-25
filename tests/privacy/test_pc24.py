"""V3.1 fallback review FB14 of 09761bc1 (no STRUCTURAL finding; plan PC-24). Synthetic values only."""
import random
import string
import time

import pytest

from uri_privacy import PrivacyRefused
from uri_privacy import classify as C

from .helpers import TGateway

DESTS = ("WEB_SEARCH", "EXTERNAL_AGENT", "LOG")


def send(text, dest):
    try:
        return False, TGateway().prepare(text, requester="t", destination=dest, purpose="p", reversible=False).text
    except PrivacyRefused as exc:
        return exc.code, ""


def _secret(rng, n=12):
    core = [rng.choice(string.ascii_letters) for _ in range(n - 2)]
    core.insert(rng.randrange(len(core)), rng.choice(string.digits))
    core.insert(rng.randrange(len(core)), rng.choice("!@#%^&*"))
    return "".join(core)


def _never_raw(cases):
    bad = []
    for t, v in cases:
        for dest in DESTS:
            refused, out = send(t, dest)
            if not refused and v in out:
                bad.append((t, dest))
    return bad


# --- R1-04: what PC-23 refused and 5e8a76d5 sent - ordinary searches and documentation stay readable ------------------
READABLE = [
    "API key + OAuth2.0 comparison", "password + OAuth2 login flow", "password & OAuth2 vs SAML",
    "access token & refresh_token rotation", "password @ 1Password vault sharing", "storing passwords @ Bitwarden2024",
    "Settings > Password > Change2FA", "Settings > Security > API key > Regenerate_v2", "password ~ bcrypt12 rounds",
    "token | gpt-4o-mini price", "pass phrase | diceware_wordlist", "forgot password?Win11",
    "secret key + HMAC-SHA256 python", "private key + RSA-4096 generate", "client secret & PKCE_flow",
    "name,city,pin\nRavi,Bengaluru,560034\nAsha,Pune,411001", "Name\tCity\tPIN\nRavi\tBengaluru\t560034\n",
    "| Model | Token | Price |\n|---|---|---|\n| gpt-x | 8,192 | $0.01 |\n", "token\tfreq\nthe\t1000\n2026\t5\n<s>\t1\n",
    "token,pos\nrun3,VERB\nC++,NOUN\n", "| password | ******** |", "| token | <your-token> |",
    "Secret    Value\nDB_HOST   db-1.local\n", "ID  PIN   STATUS\n17  1234  ok\n",
    "curl -u alice:<password> https://example.test", "mysql -pYOUR_PASSWORD", "net use Z: \\\\server\\share /user:alice *",
    "login with alice / see_the_wiki", "sign in with Google / GitHub_SSO", "login with SSO / SAML2.0",
    "how to convert a PuTTY-User-Key-File-3: file to OpenSSH", "passwords -> Python3 example",
    "passwords / OAuth2.0 comparison", "how to use passwords / Argon2id comparison",
]


@pytest.mark.parametrize("q", READABLE)
def test_fb14_r1_04_ordinary_text_is_not_refused(q):
    refused, out = send(q, "WEB_SEARCH")
    assert not refused, q


# --- R1-01: dash runs and mixed punctuation between a label and its value --------------------------------------------
SEPS = [" -- ", " --> ", " - > ", " - - ", " —— ", ' :" ', " :: ", ":- ", " // ", " -=> ", " ~> ", " |> "]
LABELS = ["password", "passwd", "api key", "secret", "token", "client_secret", "DB_PASSWORD", "AWS_SECRET_ACCESS_KEY"]


def test_fb14_r1_01_punctuation_runs_never_carry_a_secret_shaped_value():
    rng = random.Random(1401)
    cases = []
    for lab in LABELS:
        for sep in SEPS:
            v = _secret(rng)
            cases.append((f"my {lab}{sep}{v} thanks", v))
    assert _never_raw(cases) == []


def test_fb14_r1_01_mixed_case_api_keys_after_punctuation_never_carry_the_value():
    rng = random.Random(1402)
    cases = []
    for lab in ("api key", "token", "access token", "client_secret"):
        for sep in (" | ", " > ", " # ", " -- "):
            v = "".join(rng.choice(string.ascii_letters + string.digits) for _ in range(22)) + "aZ9"
            cases.append((f"{lab}{sep}{v}", v))
    assert _never_raw(cases) == []


# --- R1-02: table layouts ---------------------------------------------------------------------------------------------
TABLES = ["user\tTemp Password\nalice\t{v}", "| user | API Token |\n|---|---|\n| alice | {v} |",
          '"user","password"\n"alice","{v}"', "user;password\nalice;{v}", "user | password\n--- | ---\nalice | {v}",
          "name,Secret Key\nalice,{v}", "host\tAccess Key\nweb\t{v}", "user,New password\nalice,{v}",
          "user,Wi-Fi password\nhome,{v}"]


@pytest.mark.parametrize("form", TABLES)
def test_fb14_r1_02_table_layouts_never_carry_the_value(form):
    rng = random.Random(len(form))
    assert _never_raw([(form.format(v=v), v) for v in (_secret(rng) for _ in range(5))]) == []


# --- R1-03: more command-line tools -----------------------------------------------------------------------------------
CLI = ["docker login -u alice -p {v} registry.example.test", "sqlcmd -S db -U sa -P {v}", "redis-cli -h db -a {v} ping",
       "mongosh --username alice --password {v}", "7z a -p{v} out.7z dir", "zip -P {v} out.zip f.txt",
       "smbclient //srv/share -U alice%{v}", "xfreerdp /v:host /u:alice /p:{v}", "net user alice {v} /add",
       "htpasswd -b .htpasswd alice {v}", "ldapsearch -x -D cn=admin -w {v}", "ssh-keygen -t ed25519 -N {v} -f key"]


@pytest.mark.parametrize("form", CLI)
def test_fb14_r1_03_command_line_passwords_never_leave(form):
    rng = random.Random(len(form) + 7)
    assert _never_raw([(form.format(v=v), v) for v in (_secret(rng) for _ in range(5))]) == []


# --- R1-05: key groups split by ~ \ = # * -------------------------------------------------------------------------------
@pytest.mark.parametrize("sep", ["~", "\\", "=", "#", "*"])
def test_fb14_r1_05_fixed_length_keys_split_by_more_marks_are_refused(sep):
    rng = random.Random(1405)
    cases = []
    for _ in range(10):
        body = "".join(rng.choice(string.ascii_uppercase + string.digits) for _ in range(16))
        cases.append((f"key AKIA{sep.join(body[i:i + 4] for i in range(0, 16, 4))} please", body[4:8]))
    assert _never_raw(cases) == []


# --- R1-06: the cost bound covers the placeholder-free re-check reading ------------------------------------------------
def test_fb14_r1_06_placeholder_free_reading_is_bounded():
    # Under the bound as written; the digit runs become placeholders, and taking them out joins the "a/" runs.
    text = ("a/" * 50 + "123 456 789") * 580 + "a/" * 50
    assert C.reading_cost(text) <= C.MAX_SCAN_COST
    t0 = time.perf_counter()
    send(text, "EXTERNAL_MODEL")
    send(text, "LOG")
    assert time.perf_counter() - t0 < 5.0
