# Festival calendar — independent verification (2026-10-09)

Calendar version `2026-10-09.verified` (`uri_scheduler/data/in_festivals.json`). This record supersedes the source
statements in FESTIVAL_CALENDAR_PLAN.md §2 (which described secondary transcriptions and an unverified Sikkim table).

## 1. Acceptance criteria (defined before the check)

| id | criterion | result |
|---|---|---|
| V-AC1 | Every scheduled date is read from the notification document itself, not from a web page that summarises it | **met** for all 77 records (§3) |
| V-AC2 | Each document is identified by issuer, number, date and SHA-256 of the file that was read | **met** (§2) |
| V-AC3 | Official Central and Sikkim Government sources are preferred; where only a copy was obtainable, that is stated | **met**: Sikkim from sikkim.gov.in; DoPT O.M.s from copies (§2, limitation L1) |
| V-AC4 | Disagreements between the stored data and the documents are corrected and listed, not overwritten silently | **met** (§4) |
| V-AC5 | Disputed or unverified dates are never active | **met**: no date is active until the owner approves a selection; the owner can dispute any record (§5) |
| V-AC6 | No date is guessed for a year that is not notified | **met**: Sikkim 2027 is absent |

## 2. Documents read

| source id | document | file obtained from | SHA-256 | how it was read |
|---|---|---|---|---|
| `dopt_2026_closed`, `dopt_2026_restricted` | DoP&T O.M. F.No.12/2/2023-JCA dated 03.07.2025, holidays 2026 (Annexure-I, Annexure-II) | staffnews.in mirror of the O.M. PDF | `eee083ef…3d4df834` | image-only scan; pages 1, 4, 5, 6 read as images |
| `dopt_2026_bakrid_change` | DoP&T O.M. F.No.12/3/2023-JCA dated 22.05.2026: Id-ul-Zuha holiday 28.05.2026 in place of 27.05.2026 (Delhi/New Delhi) | icmr.gov.in (ICMR circular of 25.05.2026 forwarding the O.M.) | `1068516b…8959a5` | text layer: subject line and attached O.M. header |
| `dopt_2027_closed`, `dopt_2027_restricted` | DoP&T O.M. F.No.12/2/2023-JCA dated 16.07.2026, holidays 2027 | gconnect.in and staffnews.in mirrors: **byte-identical** files | `ad93132c…2b4d2fc1` | text layer (`pdftotext -layout` and `-raw`) |
| `sikkim_2026_gazette_391` | Government of Sikkim, Home Department, Notification No. 89/Home/2025 dated 10.10.2025, Sikkim Government Gazette Extraordinary No. 391 of 11.10.2025 | **sikkim.gov.in** (official gazette search, `uploads/Gazette/391_20251105.pdf`) | `43cbe130…932986c9` | image-only scan; all pages read as images |

The DoPT circulars portal (`doptcirculars.nic.in`, holiday list) lists both O.M.s with the same dates (entries 7/3/2025
for 2026 and 7/16/2026 for 2027) and the 22.05.2026 Bakrid change, but its download links are empty for these entries
and `utilities.cept.gov.in` (Department of Posts copy) returned an empty body. This is limitation L1.

Full hashes are in the calendar file (`sources[].document_sha256`). The documents themselves are not committed.

## 3. Check performed

A script compared every stored occurrence with a table transcribed from the documents
(`docs/scheduler/evidence/festival_verify_dopt.py`; it was run against the calendar before the corrections): 2026 Annexure-I (17) and Annexure-II rows used by the calendar, 2027
Annexure-I (17) and Annexure-II rows used. Result: **55 of 55 Government of India occurrences agree**, except the
2026 Id-ul-Zuha record (changed by the 22.05.2026 O.M.; see §4). The Sikkim records were compared by hand against both
gazette tables (41 public-holiday rows, 7 restricted rows), and every gazette weekday was recomputed: 43 of 44 agree;
the gazette labels "Chhat Puja 15th November, 2026" Tuesday although 2026-11-15 is a Sunday (the date agrees with DoPT).

## 4. Corrections made (history kept)

| record | was | now | evidence |
|---|---|---|---|
| `eid_ul_zuha` 2026 | 2026-05-27 (`dopt_2026_closed`) | **2026-05-28** (`dopt_2026_bakrid_change`); the old value is kept in the record's `corrects` field | change O.M. 22.05.2026 |
| `saga_dawa` 2026 | 2026-06-04, unverified (aggregator) | **2026-05-31**, published | gazette row 15 |
| `pang_lhabsol` 2026 | 2026-09-02, unverified | **2026-08-28**, published | gazette row 22 |
| `lhabab_duechen` 2026 | 2026-12-10, unverified | **2026-11-01**, published | gazette row 29 |
| `losar` 2026 | 2026-02-18, unverified | 2026-02-18, published | gazette row 5 |
| `losoong_namsoong` 2026 | 2026-12-09, unverified | 2026-12-09 to 2026-12-14, published | gazette row 33 |
| `buddha_purnima`, `diwali` regions | national + sikkim | national | Sikkim observes Saga Dawa (05-31) and Laxmi Puja (11-09..11) instead |
| sources `dopt_*` | "secondary transcription", web-page URLs | "om_document_read", PDF URL + hash | §2 |
| source `sikkim_2026_secondary` | cited by 5 records | cited by none; kept and marked `superseded` | §2 |

The aggregator table that the first calendar used (greythr) was wrong for three of the five Sikkim dates. That is why the
first version kept them unverified, and that decision was correct.

## 5. Sikkim festivals added (all `regional_major`, region `sikkim`, not in the default selection)

Maghe Sankranti (2026-01-15), Sonam Lochhar (01-19), Bhumchu (03-03), Durga Puja/Dasain (10-19..10-23), Laxmi Puja /
Tihar (11-09..11-11), Sakewa (11-30), Kagyed Dance (12-07), Chasok Tongnam (12-15), Barahimijong (12-28), Tamu Lochar
(12-30). Other gazette rows (birthdays, foundation days, Indrajatra, Teej, Bhanu Jayanti, Nepali Bhasa Manyata Diwas,
Drukpa Tshe-zi, Tendong Lho Rum Faat, Guru Rimpoche's Thungkar Tshechu, Nyengpa Guzom, Puhgal Parim, Teyongsi Sirijunga
Sawan Tongnam) were not added; the owner can ask for any of them.

**Sikkim 2027:** not notified yet (the 2026 list was notified on 10.10.2025, so the 2027 list is expected about
October 2026). No Sikkim 2027 date exists in the calendar. When it is notified, the owner can enter the dates as
corrections (`set_date` adds a year), or a new calendar version can be shipped.

## 6. Owner review and correction

- `GET /calendar` (scheduler API) lists every record with its status, source title, URL, verification method and
  document hash, and any owner correction.
- `POST /calendar/correct` with `{festival_key, year, action, start?, end?, note}`; `action` is `set_date`, `dispute`
  or `accept`. Corrections are append-only rows in the scheduler state (`calendar_correction`, update/delete refused by
  triggers), each audited as a `calendar.corrected` event in the hash chain, re-applied on every start, and never
  written into the shipped calendar file.
- Effects on scheduled work: a corrected date of an active job becomes `AWAITING_CONFIRMATION`
  (`DATE_CHANGED_SINCE_CONFIRMATION`); a disputed record is withdrawn (`CALENDAR_WITHDRAWN`); an accepted record that
  was withdrawn comes back as `AWAITING_CONFIRMATION` (`RESTORED_BY_CALENDAR`), never straight to `SCHEDULED`.
- Tests: `test_owner_corrections_are_pure_and_validated`, `test_owner_calendar_corrections_move_dispute_restore_and_survive_restart`,
  `test_calendar_v2_every_record_cites_a_read_document`.

## 7. Limitations and their effect

| id | limitation | effect on the verdict |
|---|---|---|
| L1 | The DoPT O.M. files were obtained from staff-news mirrors, not from dopt.gov.in (no file served). For 2027 two independent mirrors gave identical bytes; the official portal lists the same O.M.s | Low. Dates are the O.M.'s own tables. The owner approves every date before use |
| L2 | Moon-sighting festivals (Id-ul-Fitr, Id-ul-Zuha, Muharram, Milad-un-Nabi) can be moved by a later O.M. (as happened for Bakrid 2026) | The owner can correct them; a corrected date waits for confirmation |
| L3 | Gazette dates are government holiday dates; local religious observance can differ (e.g. Holi 03-03 in Sikkim vs 03-04 nationally) | Records are separate per region; the owner chooses |
| L4 | Scanned documents were read visually (no OCR engine installed); the 2026 tables were transcribed by the agent | Medium-low. The weekday cross-check found no reading error in 44 Sikkim rows; DoPT 2026 rows are also consistent with the 2027-independent secondary transcriptions used before |

## 8. Time-sensitive item for the owner

If the default selection is approved, the **first GIF is due 2026-10-18 09:00 IST** (Dussehra, 2026-10-20). If the
Sikkim Dasain record is selected, it is due 2026-10-17 09:00 IST. Neither can run until (a) the owner approves the
selection and (b) the scheduler's Claude profile is logged in and the live test passes.
