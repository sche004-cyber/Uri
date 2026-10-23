"""Synthetic sensitive data for the M95 tests. Every value is generated or invented: no real person, account or key.

Checksummed identifiers (Aadhaar/Verhoeff, cards/Luhn, IBAN/mod-97) are computed so the detectors are tested on values
that pass the same checks real ones do. Benign text is written to look like ordinary work content.
"""
import random

from uri_privacy.classify import _VD, _VP

_INV = (0, 4, 3, 2, 1, 5, 6, 7, 8, 9)


def verhoeff_digit(body: str) -> str:
    c = 0
    for i, ch in enumerate(reversed(body)):
        c = _VD[c][_VP[(i + 1) % 8][int(ch)]]
    return str(_INV[c])


def aadhaar(rng):
    body = str(rng.randint(2, 9)) + "".join(str(rng.randint(0, 9)) for _ in range(10))
    d = body + verhoeff_digit(body)
    return f"{d[:4]} {d[4:8]} {d[8:]}"


def luhn_card(rng, prefix="4"):
    body = prefix + "".join(str(rng.randint(0, 9)) for _ in range(15 - len(prefix)))
    total = 0
    for i, ch in enumerate(reversed(body)):
        d = int(ch)
        if i % 2 == 0:
            d *= 2
            d -= 9 if d > 9 else 0
        total += d
    n = body + str((10 - total % 10) % 10)
    return " ".join(n[i:i + 4] for i in range(0, 16, 4))


def iban(rng, cc="DE"):
    bban = "".join(str(rng.randint(0, 9)) for _ in range(18))
    s = bban + "".join(str(int(ch, 36)) for ch in cc) + "00"
    check = 98 - int(s) % 97
    raw = f"{cc}{check:02d}{bban}"
    return " ".join(raw[i:i + 4] for i in range(0, len(raw), 4))


def pan(rng):
    L = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return ("".join(rng.choice(L) for _ in range(3)) + rng.choice("PCHFATBLJG") + rng.choice(L)
            + "".join(str(rng.randint(0, 9)) for _ in range(4)) + rng.choice(L))


def ssn(rng):
    return f"{rng.randint(100, 665):03d}-{rng.randint(10, 99):02d}-{rng.randint(1000, 9999):04d}"


def mobile(rng):
    d = str(rng.randint(6, 9)) + "".join(str(rng.randint(0, 9)) for _ in range(9))
    return rng.choice([f"+91 {d[:5]} {d[5:]}", f"{d[:5]} {d[5:]}", f"+91-{d}", d])


FIRST = ["Asha", "Ravi", "Meera", "Arjun", "Priya", "Kiran", "Neha", "Vikram", "Anita", "Suresh"]
LAST = ["Rao", "Iyer", "Sharma", "Patel", "Nair", "Gupta", "Reddy", "Das", "Menon", "Kulkarni"]
CITY = ["Bengaluru", "Mysuru", "Pune", "Chennai", "Kochi", "Hyderabad"]


def email(rng):
    return f"{rng.choice(FIRST).lower()}.{rng.choice(LAST).lower()}{rng.randint(1, 99)}@example.{rng.choice(['in', 'com', 'org'])}"


# Each positive: (category, template using {v}, generator)
def positives(n=40, seed=95):
    rng = random.Random(seed)
    gens = [
        ("GOV_ID", ["Aadhaar: {v}", "my aadhaar number is {v} for the KYC form", "UID {v}"], aadhaar),
        ("GOV_ID", ["PAN {v}", "Please file using PAN: {v}.", "pan no {v}"], pan),
        ("GOV_ID", ["SSN {v}", "social security {v} on the W-2"], ssn),
        ("GOV_ID", ["passport no. {v}", "Passport number: {v}"],
         lambda r: r.choice("JKLMNPRSTUVWZ") + "".join(str(r.randint(0, 9)) for _ in range(7))),
        ("FINANCIAL", ["card {v}", "charge it to {v} please", "Visa {v} exp 09/29"], luhn_card),
        ("FINANCIAL", ["IBAN {v}", "transfer to {v}"], iban),
        ("FINANCIAL", ["account no: {v}", "A/c {v} at the Jayanagar branch"],
         lambda r: "".join(str(r.randint(0, 9)) for _ in range(r.randint(10, 14)))),
        ("CONTACT", ["mail {v}", "reach me at {v} tomorrow", "cc: {v}"], email),
        ("CONTACT", ["call {v}", "my number is {v}", "WhatsApp {v} after 6"], mobile),
        ("ADDRESS", ["Flat {n}, {c} Road, Indiranagar", "House no {n}, 3rd Cross, {c} Layout"],
         lambda r: None),
        ("ADDRESS", ["pincode {v}", "{c}, {c2} - {v}"], lambda r: str(r.randint(110001, 855117))),
        ("CREDENTIAL", ["password: {v}", "the wifi password is {v}", "pwd={v}"],
         lambda r: "".join(r.choice("abcdefghjkmnpqrstuvwxyzABCDEFGH23456789!#") for _ in range(r.randint(8, 14)))),
        ("CREDENTIAL", ["OTP {v}", "your one-time code is {v}", "UPI PIN {v}", "verification code: {v}"],
         lambda r: "".join(str(r.randint(0, 9)) for _ in range(r.choice([4, 6])))),
        ("CREDENTIAL", ["key sk-{v}", "Authorization: Bearer {v}", "use tvly-{v} for search"],
         lambda r: "".join(r.choice("abcdefghijklmnopqrstuvwxyzABCDEFGHIJ0123456789") for _ in range(32))),
    ]
    out = []
    for cat, templates, gen in gens:
        for i in range(n):
            t = rng.choice(templates)
            v = gen(rng)
            text = t.format(v=v, n=rng.randint(2, 480), c=rng.choice(CITY), c2=rng.choice(CITY))
            out.append((cat, text, v))
    return out


BENIGN = [
    "Meeting moved to 2026-10-22 at 14:30 in room 4B.",
    "Order #12345678 shipped on 21/10/2026; invoice INV-2026-0042 attached.",
    "ISBN 978-0-306-40615-7 is the second edition.",
    "Upgrade from v3.11.2 to v3.12.0 before Friday.",
    "The quote is Rs 4,50,000 including GST of 18%.",
    "Asha Rao and Ravi Iyer reviewed the draft yesterday.",
    "Call the vendor about the 250 kg shipment of 12 crates.",
    "Population of the district was 1,23,45,678 in 2011.",
    "Train 12627 leaves at 19:20 from platform 3.",
    "Build 20261022.1 passed 1043 tests in 312 seconds.",
    "The password policy requires 12 characters and a symbol.",
    "Share the token of appreciation with the team.",
    "Our PIN code field validation rejects letters.",
    "Use a secret santa draw for the office party.",
    "Room temperature was 23.5 C at 10:15:44.",
    "Coordinates 12.9716, 77.5946 mark the office.",
    "Batch 7 had 98.6% yield across 4 lines.",
    "Compare Q3 revenue 4,512,330 with Q2 4,108,912.",
    "The keyboard shortcut is Ctrl+Shift+P.",
    "Version 1.0.0-rc.2 is tagged release-2026-10.",
    "Sector 5 survey covered 3,400 households.",
    "Read chapter 12, pages 145-178, before the seminar.",
    "Spreadsheet row 2048 has a formula error in column AA.",
    "The flight UK 812 departs Terminal 2 at 06:05.",
    "Average latency dropped from 420 ms to 310 ms.",
    "Please review the proposal for the Pune office.",
    "The lab ordered 1500 test tubes and 40 racks.",
    "Diwali falls on 8 November this year.",
    "Ticket URI-4821 is assigned to the Office team.",
    "Item code 4006381333931 is the barcode on the box.",
    "Session 3 of the workshop starts after lunch.",
    "Tax year 2025-26 closes on 31 March.",
    "The 2026 budget allocates 12.5 crore to schools.",
    "Water usage was 18,000 litres in September.",
    "The model has 35B parameters with 3B active.",
    "Font size 14 pt, line spacing 1.15, margins 2.54 cm.",
    "Grade 10 results: 412 students passed out of 430.",
    "Maintenance window is 02:00-04:00 IST on Sunday.",
    "The account manager will call back about the renewal.",
    "Board meeting minutes, item 4: approve the audit plan.",
]


# Harder cases written after the first corpus run returned 100 % / 0 FP (that run was self-fitted: the templates were
# written next to the detectors). These are formats and traps the detectors were NOT tuned for; misses here are real.
HARD_POSITIVES = [
    ("FINANCIAL", "card 4111-1111-1111-1111 expires soon"),
    ("FINANCIAL", "Card number:4532015112830366"),
    ("CONTACT", "Mail ASHA.RAO@EXAMPLE.IN today"),
    ("CONTACT", "phone (080) 2345 6789 ext 12"),
    ("CONTACT", "+44 20 7946 0958 is the London office"),
    ("CONTACT", "call 080-23456789"),
    ("CONTACT", "contact: 1-800-555-0199"),
    ("GOV_ID", "Aadhaar 2345-6789-0124"),
    ("GOV_ID", "pan: abcpe1234f"),
    ("ADDRESS", "No. 14, 2nd Main Road, Jayanagar 4th Block, Bengaluru 560011"),
    ("ADDRESS", "Plot 22/B, Sector 21 Road, Navi Mumbai"),
    ("CREDENTIAL", "login: asha / pass: Tr0ub4dor&3"),
    ("CREDENTIAL", "the PIN for the locker is 4821"),
    ("CREDENTIAL", "here is the code: 482913 (valid 5 minutes)"),
    ("CREDENTIAL", "ghp_" + "a" * 36),
    ("CREDENTIAL", "postgres://admin:S3cretPass@db.internal:5432/app"),
    ("FINANCIAL", "IFSC SBIN0001234 account 00011122233344"),
    ("CONTACT", "asha dot rao at example dot in"),          # obfuscated e-mail: expected miss (documented limitation)
]
HARD_BENIGN = [
    "IMEI 490154203237518 is printed on the box.",            # 15-digit Luhn-valid: card trap
    "Commit 9f3a1c2b7d4e5f60718293a4b5c6d7e8f9012345 fixed it.",  # 40-hex: SECRET_LIKE trap
    "Order 234567890123 shipped.",                             # 12 digits: Aadhaar trap (Verhoeff passes 1 in 10)
    "Tracking AWB 7845123690 via Bluedart.",                   # 10 digits starting 7: mobile trap
    "Invoice total 9876543210 paise.",                         # 10 digits starting 9: mobile trap
    "Call centre hours are 9 to 5, Monday to Friday.",
    "The confidential interval is 95% (statistics).",         # marker false friend
    "Room 560 on floor 11.",
    "Patent US 10,123,456 B2 cites prior art.",
    "Use SHA-256 e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 as the empty digest.",
]


# HELD-OUT set: written after the classifier fixes and measured once without further tuning (the result is recorded
# in docs/privacy/evidence/measurements.json whatever it is). Do not tune the detectors against this list.
HELD_OUT_POSITIVES = [
    ("CONTACT", "Send the forms to k.menon77@example.org before noon."),
    ("CONTACT", "Her mobile: 9988776655"),
    ("CONTACT", "Office line 044-28123456, ask for accounts."),
    ("CONTACT", "Ring +1 (415) 555-0132 after 9 pm PST."),
    ("GOV_ID", "UIDAI number 4321 8765 2109 on file"),
    ("GOV_ID", "PAN card AAECR1234K belongs to the trust"),
    ("GOV_ID", "My SSN is 512-44-7788."),
    ("FINANCIAL", "Mastercard 5555 5555 5555 4444 was declined."),
    ("FINANCIAL", "Bank account number 50100234567891 (HDFC)."),
    ("FINANCIAL", "Wire to GB82 WEST 1234 5698 7654 32 today."),
    ("ADDRESS", "Deliver to House No. 7, MG Road, Kochi"),
    ("ADDRESS", "Postal code: 600042"),
    ("CREDENTIAL", "Netbanking password is Mango#2026!"),
    ("CREDENTIAL", "Your OTP for login is 739204. Do not share it."),
    ("CREDENTIAL", "export OPENAI_API_KEY=sk-proj-abcdefghijklmnopqrstuvwxyz012345"),
    ("CREDENTIAL", "ATM pin: 8812"),
    ("CREDENTIAL", "token = ghs_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"),
]
HELD_OUT_BENIGN = [
    "The 3:2 ratio held across 18 trials in 2025.",
    "Pages 1024-2048 of the log were rotated.",
    "Call me when the report is ready.",
    "Profit margin improved to 14.2% in FY26.",
    "Ward 198 recorded 7,312 voters.",
    "The PIN code lookup service is down.",
    "Section 80C allows deductions up to 1.5 lakh.",
    "GSTIN format is 15 characters long.",
    "Check the confidence score threshold of 0.85.",
    "Zip the files into release_20261022.zip.",
    "Batch number 4500012345 failed QC.",
    "Train 22691 Rajdhani arrives at 06:40.",
    "Weight 72.5 kg, height 175 cm.",
    "Visit https://example.com/docs?page=2 for details.",
    "Token ring networks were replaced by Ethernet.",
]
