"""Diff uri_scheduler festival data against dates transcribed from the DoPT O.M. PDFs (2026: scan read page by page;
2027: text layer). Usage: python -I verify.py <in_festivals.json>"""
import json, sys

# (year, key) -> (date, annexure)
REF = {
    # 2026 Annexure-I (O.M. 03.07.2025, scanned page 4)
    (2026, "republic_day"): ("2026-01-26", "I"), (2026, "holi"): ("2026-03-04", "I"),
    (2026, "eid_ul_fitr"): ("2026-03-21", "I"), (2026, "ram_navami"): ("2026-03-26", "I"),
    (2026, "mahavir_jayanti"): ("2026-03-31", "I"), (2026, "good_friday"): ("2026-04-03", "I"),
    (2026, "buddha_purnima"): ("2026-05-01", "I"), (2026, "eid_ul_zuha"): ("2026-05-27", "I"),
    (2026, "muharram"): ("2026-06-26", "I"), (2026, "independence_day"): ("2026-08-15", "I"),
    (2026, "milad_un_nabi"): ("2026-08-26", "I"), (2026, "janmashtami"): ("2026-09-04", "I"),
    (2026, "gandhi_jayanti"): ("2026-10-02", "I"), (2026, "dussehra"): ("2026-10-20", "I"),
    (2026, "diwali"): ("2026-11-08", "I"), (2026, "guru_nanak_jayanti"): ("2026-11-24", "I"),
    (2026, "christmas"): ("2026-12-25", "I"),
    # 2026 Annexure-II page 6 (entries 19-34)
    (2026, "onam"): ("2026-08-26", "II"), (2026, "raksha_bandhan"): ("2026-08-28", "II"),
    (2026, "ganesh_chaturthi"): ("2026-09-14", "II"), (2026, "karva_chauth"): ("2026-10-29", "II"),
    (2026, "govardhan_puja"): ("2026-11-09", "II"), (2026, "bhai_dooj"): ("2026-11-11", "II"),
    (2026, "chhath_puja"): ("2026-11-15", "II"),
    # 2027 Annexure-I (O.M. 16.07.2026)
    (2027, "republic_day"): ("2027-01-26", "I"), (2027, "eid_ul_fitr"): ("2027-03-10", "I"),
    (2027, "holi"): ("2027-03-23", "I"), (2027, "good_friday"): ("2027-03-26", "I"),
    (2027, "ram_navami"): ("2027-04-15", "I"), (2027, "mahavir_jayanti"): ("2027-04-19", "I"),
    (2027, "eid_ul_zuha"): ("2027-05-17", "I"), (2027, "buddha_purnima"): ("2027-05-20", "I"),
    (2027, "muharram"): ("2027-06-16", "I"), (2027, "independence_day"): ("2027-08-15", "I"),
    (2027, "milad_un_nabi"): ("2027-08-15", "I"), (2027, "janmashtami"): ("2027-08-25", "I"),
    (2027, "gandhi_jayanti"): ("2027-10-02", "I"), (2027, "dussehra"): ("2027-10-09", "I"),
    (2027, "diwali"): ("2027-10-29", "I"), (2027, "guru_nanak_jayanti"): ("2027-11-14", "I"),
    (2027, "christmas"): ("2027-12-25", "I"),
    # 2027 Annexure-II
    (2027, "makar_sankranti"): ("2027-01-14", "II"), (2027, "pongal"): ("2027-01-15", "II"),
    (2027, "basant_panchami"): ("2027-02-11", "II"), (2027, "maha_shivratri"): ("2027-03-06", "II"),
    (2027, "ugadi_gudi_padwa"): ("2027-04-07", "II"), (2027, "vaisakhi"): ("2027-04-14", "II"),
    (2027, "rath_yatra"): ("2027-07-05", "II"), (2027, "raksha_bandhan"): ("2027-08-17", "II"),
    (2027, "ganesh_chaturthi"): ("2027-09-04", "II"), (2027, "onam"): ("2027-09-12", "II"),
    (2027, "karva_chauth"): ("2027-10-18", "II"), (2027, "govardhan_puja"): ("2027-10-30", "II"),
    (2027, "bhai_dooj"): ("2027-10-31", "II"), (2027, "chhath_puja"): ("2027-11-04", "II"),
}

data = json.load(open(sys.argv[1], encoding="utf-8"))
seen, bad, unref = set(), [], []
for f in data["festivals"]:
    for o in f["occurrences"]:
        k = (o["year"], f["festival_key"])
        seen.add(k)
        if k not in REF:
            unref.append((k, o["start"], o["status"], o["source"]))
        elif REF[k][0] != o["start"]:
            bad.append((k, o["start"], REF[k][0]))
missing = sorted(k for k in REF if k not in seen)
print("checked", len(seen & set(REF)), "| mismatches", bad, "| not in data", missing)
print("not covered by DoPT reference:")
for u in unref:
    print("  ", u)
