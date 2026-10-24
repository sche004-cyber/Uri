"""V3.1 fallback review FB13 of 5e8a76d5 (no STRUCTURAL finding; plan PC-23). Generated sweeps, synthetic values."""
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


def _value(rng, n=None):
    n = n or rng.randint(10, 14)
    core = [rng.choice(string.ascii_letters) for _ in range(n - 2)]
    core.insert(rng.randrange(len(core)), rng.choice(string.digits))
    core.insert(rng.randrange(len(core)), rng.choice("!@#%^&*"))
    return "".join(core)


def _never_raw(texts_and_values):
    bad = []
    for t, v in texts_and_values:
        for dest in DESTS:
            refused, out = send(t, dest)
            if not refused and v in out:
                bad.append((t, dest))
    return bad


# --- R1-01: any punctuation between a credential label and its value -------------------------------------------------
LABELS = ["password", "Password", "PASSWORD", "passwd", "pwd", "passcode", "passphrase", "passwords", "pass phrase",
          "api key", "API_KEY", "secret", "token", "access token", "client_secret", "DB_PASSWORD"]
# Every ASCII punctuation mark, space-padded; unpadded except "." and "_" (stated residuals: "password.x9!", "password_x9!")
SEPS = [f" {c} " for c in string.punctuation] +[c for c in string.punctuation if c not in "._"] + \
       [" >> ", " ==> ", "\t", "\n", " "]


def test_fb13_r1_01_any_punctuation_between_label_and_value_never_carries_it():
    rng = random.Random(1301)
    cases = []
    for lab in LABELS:
        for sep in SEPS:
            v = _value(rng)
            cases.append((f"my {lab}{sep}{v} thanks", v))
    bad = _never_raw(cases)
    assert bad == [], (len(bad), bad[:5])


def test_pc23_a_pseudonym_token_ending_in_a_label_is_not_a_label():
    # Tokens are random: one ending in "pwd" made the output re-check refuse 2000 e-mail addresses (found in PC-23).
    out = "[[CONTACT_igailbcpejfjalbobepefljhanfpbbgh_uzqahjlfjueocpwd]] [[CONTACT_igailbcpejfjalbobepefljhanfpbbgh_bzmbm]]"
    assert not C.classify(out).categories()


@pytest.mark.parametrize("q", ["forgot password? Win10 laptop", "password.v2.json", "password #1 tip",
                               "password > Settings > Security", "password ** required", "my passwords are weak",
                               "pass phrase generator 2026", "api key | where to find", "token > 2 hours expiry",
                               "client_secret / required", "DB_PASSWORD; see docs v2", "password #2: use 12 chars",
                               "reset password - faq", "token is a JWT"])
def test_fb13_r1_01_ordinary_phrasings_stay_readable(q):
    assert send(q, "WEB_SEARCH") == (False, q)


# --- R1-02: tables and command lines -----------------------------------------------------------------------------------
FORMS = ["username\tpassword\nalice\t{v}", "| user | password |\n|---|---|\n| alice | {v} |", "| password | {v} |",
         "USER      PASSWORD\nalice     {v}", "username,password\nalice,{v}", "curl -u alice:{v} https://api.example.com/v1",
         "mysql -u root -p{v} -h db", "sshpass -p {v} ssh alice@host", "net use Z: \\\\server\\share /user:alice {v}",
         "login with alice / {v}", "creds: alice / {v}"]


@pytest.mark.parametrize("form", FORMS)
def test_fb13_r1_02_tables_and_command_lines_never_carry_the_value(form):
    rng = random.Random(hash(form) & 0xFFFF)
    cases = []
    for _ in range(10):
        v = _value(rng)
        cases.append((form.format(v=v), v))
    assert _never_raw(cases) == []


@pytest.mark.parametrize("q", ["| field | type |\n|---|---|\n| password | string |", "name,password\nalice,required",
                               "mysql -P 3306 -h db", "curl -u alice https://example.com", "login / signup page",
                               "Column A  Column B\nvalue 1  value 2"])
def test_fb13_r1_02_documentation_tables_and_commands_stay_readable(q):
    assert send(q, "WEB_SEARCH") == (False, q)


# --- R1-03: known-prefix keys split by any punctuation -----------------------------------------------------------------
PREFIX_BODY = {"AKIA": (16, string.ascii_uppercase + string.digits),
               "AIza": (35, string.ascii_letters + string.digits + "-_"),
               "ghp_": (36, string.ascii_letters + string.digits),
               "glpat-": (20, string.ascii_letters + string.digits + "-_")}


@pytest.mark.parametrize("sep", [".", "_", "/", ",", ":", ";", "|", "+", " ", "-", "\n"])
def test_fb13_r1_03_fixed_length_keys_split_by_punctuation_are_refused(sep):
    rng = random.Random(1303)
    cases = []
    for prefix, (n, alphabet) in PREFIX_BODY.items():
        for _ in range(5):
            body = "".join(rng.choice(alphabet) for _ in range(n))
            text = f"my key {prefix}" + sep.join(body[i:i + 4] for i in range(0, n, 4)) + " please"
            cases.append((text, body[4:8]))                 # one whole group: it is contiguous in the text
    assert _never_raw(cases) == []


@pytest.mark.parametrize("q", ["sk-learn.preprocessing.StandardScaler docs", "AKIA is the AWS key prefix",
                               "sk-learn tutorial for 2026"])
def test_fb13_r1_03_module_paths_and_prose_stay_readable(q):
    assert send(q, "WEB_SEARCH") == (False, q)


# --- R1-04: PGP and PuTTY private keys are CREDENTIAL, whole ------------------------------------------------------------
def _armour(rng, lines=6):
    return "\n".join("".join(rng.choice(string.ascii_letters + string.digits + "+/") for _ in range(64))
                     for _ in range(lines)) + "\nhGflRtU+yOKhJXvb\n=Ab3d"


@pytest.mark.parametrize("kind", ["pgp", "putty"])
def test_fb13_r1_04_private_key_blocks_are_refused_whole(kind):
    rng = random.Random(1304)
    body = _armour(rng)
    if kind == "pgp":
        text = f"-----BEGIN PGP PRIVATE KEY BLOCK-----\n\n{body}\n-----END PGP PRIVATE KEY BLOCK-----"
    else:
        text = ("PuTTY-User-Key-File-3: ssh-ed25519\nEncryption: none\nComment: test\nPublic-Lines: 2\n"
                f"AAAAC3NzaC1lZDI1NTE5\nAAAAIGx\nPrivate-Lines: 1\n{body}\nPrivate-MAC: 0a1b2c3d4e5f")
    assert C.CREDENTIAL in C.classify(text).categories()
    for dest in ("WEB_SEARCH", "EXTERNAL_MODEL", "EXTERNAL_AGENT"):
        assert send(text, dest)[0], dest
    refused, out = send(text, "LOG")
    assert refused or ("hGflRtU" not in out and "Ab3d" not in out)


# --- R1-05: the cost bound applies to every reading --------------------------------------------------------------------
@pytest.mark.parametrize("unit", ["ａ／", "a%2F", "a&#47;", "a/"])
def test_fb13_r1_05_pathological_text_in_any_reading_is_refused_fast(unit):
    text = unit * 8000
    t0 = time.perf_counter()
    assert send(text, "WEB_SEARCH")[0] == "PRIVACY_INPUT_TOO_COMPLEX"
    refused, out = send(text, "LOG")
    assert not refused and "a/a/" not in out
    assert time.perf_counter() - t0 < 1.0


# --- R1-06: passport, CVV and defanged e-mail forms --------------------------------------------------------------------
@pytest.mark.parametrize("text,value", [("passport number, K1234567", "1234567"), ("passport (K1234567)", "1234567"),
                                        ("K1234567 is my passport number", "1234567"),
                                        ("passport K-1234567", "1234567"), ("passport no: K 1234567", "1234567"),
                                        ("CVV(123)", "123"), ("alice.smith<at>example<dot>com", "alice.smith")])
def test_fb13_r1_06_near_forms_never_carry_the_value(text, value):
    assert _never_raw([(text, value)]) == []


# --- the new patterns stay linear -----------------------------------------------------------------------------------
@pytest.mark.parametrize("unit", ["password | ", "curl -u ", "a,b\n", "x\ty\n", "| a | b |\n", "AKIA.", "passport ",
                                  "login a / ", "mysql -p", "-----BEGIN PGP PRIVATE KEY BLOCK-----", "a-", "a.b+"])
def test_pc23_new_patterns_stay_linear(unit):
    # Either classification is fast, or the matching-cost bound refuses the text before classification. The reused
    # Assist URL-userinfo rules are quadratic on long [a-z0-9+.-] runs ("AKIA." x 13108: 9 s); scan_cost counts them.
    text = (unit * (65536 // len(unit) + 1))[:65536]
    t0 = time.perf_counter()
    if C.reading_cost(text) > C.MAX_SCAN_COST:
        assert send(text, "WEB_SEARCH")[0] == "PRIVACY_INPUT_TOO_COMPLEX"
    else:
        C.classify(text)
    assert time.perf_counter() - t0 < 2.0, unit
