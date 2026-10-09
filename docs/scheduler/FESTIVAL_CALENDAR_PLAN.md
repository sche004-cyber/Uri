# URI Festival Calendar — Plan

> **Correction (2026-10-09, calendar `2026-10-09.verified`).** §2 below describes the first version, whose dates came from secondary transcriptions and whose Sikkim records were unverified. Every date has since been read from the notification documents themselves, three Sikkim dates and the 2026 Bakrid date were corrected, ten Sikkim festivals were added, and the owner can now correct or dispute any record. See FESTIVAL_CALENDAR_VERIFICATION.md. §4 below is the regenerated list.

Status: data and scheduling rule implemented and tested; **the recurring festival schedule is NOT activated**. Activation
requires the owner to approve the list and dates below (in the UI: Dashboard → Scheduled tasks → *Festival GIFs (2 days
before)* → *Activate*, which binds the confirmation to the proposal's sha256).

## 1. Acceptance criteria

| id | criterion | result |
|---|---|---|
| F-AC1 | Dates come from cited authoritative notifications, with provenance per record | met for Government of India 2026/2027 (secondary transcriptions of the DoPT O.M.s, disclosed); Sikkim **not met** (see §3) |
| F-AC2 | Lunar festivals are never assumed to repeat on the same Gregorian date | met: dates are per year from the notification; e.g. Diwali 2026-11-08 vs 2027-10-29 (test `test_calendar_relative_two_days_before_in_ist`) |
| F-AC3 | One GIF exactly two calendar days before each selected festival, in Asia/Kolkata, at a configurable time | met: `offset_days: -2`, `time` (default 09:00) |
| F-AC4 | No duplicate tasks on overlap or calendar refresh | met: occurrence key `festival:year`; refresh moves/withdraws (test `test_calendar_refresh_moves_not_duplicates`); two different festivals on the same day (2027-08-15 Independence Day + Milad-un-Nabi) are two keys, one GIF each, never merged silently |
| F-AC5 | Owner approves the list and dates before activation | met by design (`PROPOSED` jobs never run; confirmation needs the proposal hash) |

## 2. Sources

| source id | notification | how obtained | verification |
|---|---|---|---|
| `dopt_2026_closed` | DoP&T O.M. F.No.12/2/2023-JCA dated 03.07.2025, Annexure-I (closed holidays 2026, Delhi/New Delhi) | staffnews.in transcription | secondary transcription of an official O.M. |
| `dopt_2026_restricted` | same O.M., Annexure-II (restricted holidays 2026) | staffnews.in transcription | secondary transcription |
| `dopt_2027_closed` | DoP&T O.M. F.No.12/2/2023-JCA dated 16.07.2026, Annexure-I (gazetted holidays 2027) | staffnews.in transcription | secondary transcription |
| `dopt_2027_restricted` | same O.M., Annexure-II (restricted holidays 2027) | staffnews.in transcription | secondary transcription |
| `sikkim_2026_secondary` | Government of Sikkim Notification 89/Home/2025 dated 11.10.2025, Gazette Extraordinary No. 391 | greythr.com aggregator table | **conflicting**: it lists Tihar/Laxmi Puja on 2026-10-13 while Diwali is 2026-11-08 nationally |

`https://www.india.gov.in/calendar` returned HTTP 403 to the research tool; the primary PDFs were not fetched. This does not
block activation because the owner approves every date, but the records are labelled as transcriptions.

## 3. Rules

- **Observed dates**: the notified holiday date is used as the festival date (e.g. Holi 2026-03-04 nationally; some states
  observe Holika Dahan/Dolyatra on 2026-03-03 — that is a different record, `restricted`). Moon-sighting festivals (Eid,
  Muharram, Milad-un-Nabi) may shift by a day after the notification; a corrected calendar version moves the occurrence.
- **Regional festivals**: records carry `regions`; the default selection is national. Sikkim records (Losar, Saga Dawa, Pang
  Lhabsol, Lhabab Duechen, Losoong/Namsoong) are present but `unverified`: they appear in the proposal under "Not scheduled
  until you confirm their dates" and are never scheduled until the owner confirms them (`Calendar.confirm`, recorded with
  `confirmed_by` and a note, version suffix `+confirm`).
- **Solemn observances** (Good Friday, Muharram) are listed for completeness, `greeting_appropriate: false`; proposing a
  greeting GIF for them is refused (`NOT_A_GREETING_OCCASION`).
- **National observances** (Republic Day, Independence Day, Gandhi Jayanti) are selectable but not in the default.
- **Deadline**: a GIF that could not be produced before the festival day starts (00:00 IST) becomes `MISSED` unless the owner
  reschedules it explicitly.
- **Refresh**: `Scheduler.refresh_calendar(new_version)` records the diff (`calendar.refreshed`), moves changed occurrences,
  withdraws removed ones, and inserts new years; already-produced artifacts are never touched.
- **2028+**: the DoPT list for a year is published around July of the previous year; until a new calendar version is loaded,
  no occurrences exist for that year (nothing is guessed).

## 4. Proposed list for owner approval (default selection marked **yes**; all upcoming records shown)

Default selection (`MAJOR_DEFAULT`): Holi, Ram Navami, Mahavir Jayanti, Buddha Purnima, Id-ul-Fitr, Id-ul-Zuha, Janmashtami,
Dussehra, Diwali, Guru Nanak Jayanti, Christmas, Milad-un-Nabi. The owner may add any `published` record (e.g. Ganesh
Chaturthi, Onam, Raksha Bandhan, Chhath Puja) or confirm a Sikkim record.

| festival date | festival | key | regions | category | in default selection | GIF due | source |
|---|---|---|---|---|---|---|---|
| 2026-10-19..10-23 | Durga Puja (Dasain), Sikkim | `dasain_sikkim` | sikkim | regional_major | no | 2026-10-17 09:00 IST | `sikkim_2026_gazette_391` |
| 2026-10-20 | Dussehra (Vijaya Dashami) | `dussehra` | national | major | **yes** | 2026-10-18 09:00 IST | `dopt_2026_closed` |
| 2026-10-29 | Karva Chauth | `karva_chauth` | north_india | regional_major | no | 2026-10-27 09:00 IST | `dopt_2026_restricted` |
| 2026-11-01 | Lhabab Duechen | `lhabab_duechen` | sikkim | regional_major | no | 2026-10-30 09:00 IST | `sikkim_2026_gazette_391` |
| 2026-11-08 | Diwali (Deepavali) | `diwali` | national | major | **yes** | 2026-11-06 09:00 IST | `dopt_2026_closed` |
| 2026-11-09 | Govardhan Puja | `govardhan_puja` | national | regional_major | no | 2026-11-07 09:00 IST | `dopt_2026_restricted` |
| 2026-11-09..11-11 | Laxmi Puja (Deepawali / Tihar), Sikkim | `tihar_sikkim` | sikkim | regional_major | no | 2026-11-07 09:00 IST | `sikkim_2026_gazette_391` |
| 2026-11-11 | Bhai Dooj | `bhai_dooj` | national | regional_major | no | 2026-11-09 09:00 IST | `dopt_2026_restricted` |
| 2026-11-15 | Chhath Puja | `chhath_puja` | bihar, jharkhand | regional_major | no | 2026-11-13 09:00 IST | `dopt_2026_restricted` |
| 2026-11-24 | Guru Nanak Jayanti | `guru_nanak_jayanti` | national | major | **yes** | 2026-11-22 09:00 IST | `dopt_2026_closed` |
| 2026-11-30 | Sakewa | `sakewa` | sikkim | regional_major | no | 2026-11-28 09:00 IST | `sikkim_2026_gazette_391` |
| 2026-12-07 | Kagyed Dance | `kagyed_dance` | sikkim | regional_major | no | 2026-12-05 09:00 IST | `sikkim_2026_gazette_391` |
| 2026-12-09..12-14 | Losoong / Namsoong | `losoong_namsoong` | sikkim | regional_major | no | 2026-12-07 09:00 IST | `sikkim_2026_gazette_391` |
| 2026-12-15 | Chasok Tongnam | `chasok_tongnam` | sikkim | regional_major | no | 2026-12-13 09:00 IST | `sikkim_2026_gazette_391` |
| 2026-12-25 | Christmas | `christmas` | national | major | **yes** | 2026-12-23 09:00 IST | `dopt_2026_closed` |
| 2026-12-28 | Barahimijong | `barahimijong` | sikkim | regional_major | no | 2026-12-26 09:00 IST | `sikkim_2026_gazette_391` |
| 2026-12-30 | Tamu Lochar | `tamu_lochar` | sikkim | regional_major | no | 2026-12-28 09:00 IST | `sikkim_2026_gazette_391` |
| 2027-01-14 | Makar Sankranti | `makar_sankranti` | national | regional_major | no | 2027-01-12 09:00 IST | `dopt_2027_restricted` |
| 2027-01-15 | Pongal | `pongal` | tamil_nadu | regional_major | no | 2027-01-13 09:00 IST | `dopt_2027_restricted` |
| 2027-01-26 | Republic Day | `republic_day` | national | national_observance | no | 2027-01-24 09:00 IST | `dopt_2027_closed` |
| 2027-02-11 | Basant Panchami | `basant_panchami` | national | regional_major | no | 2027-02-09 09:00 IST | `dopt_2027_restricted` |
| 2027-03-06 | Maha Shivratri | `maha_shivratri` | national | regional_major | no | 2027-03-04 09:00 IST | `dopt_2027_restricted` |
| 2027-03-10 | Id-ul-Fitr | `eid_ul_fitr` | national | major | **yes** | 2027-03-08 09:00 IST | `dopt_2027_closed` |
| 2027-03-23 | Holi | `holi` | national | major | **yes** | 2027-03-21 09:00 IST | `dopt_2027_closed` |
| 2027-03-26 | Good Friday | `good_friday` | national | solemn | no | 2027-03-24 09:00 IST | `dopt_2027_closed` |
| 2027-04-07 | Ugadi / Gudi Padwa | `ugadi_gudi_padwa` | karnataka, andhra_pradesh, telangana, maharashtra | regional_major | no | 2027-04-05 09:00 IST | `dopt_2027_restricted` |
| 2027-04-14 | Vaisakhi | `vaisakhi` | punjab | regional_major | no | 2027-04-12 09:00 IST | `dopt_2027_restricted` |
| 2027-04-15 | Ram Navami | `ram_navami` | national | major | **yes** | 2027-04-13 09:00 IST | `dopt_2027_closed` |
| 2027-04-19 | Mahavir Jayanti | `mahavir_jayanti` | national | major | **yes** | 2027-04-17 09:00 IST | `dopt_2027_closed` |
| 2027-05-17 | Id-ul-Zuha (Bakrid) | `eid_ul_zuha` | national | major | **yes** | 2027-05-15 09:00 IST | `dopt_2027_closed` |
| 2027-05-20 | Buddha Purnima | `buddha_purnima` | national | major | **yes** | 2027-05-18 09:00 IST | `dopt_2027_closed` |
| 2027-06-16 | Muharram | `muharram` | national | solemn | no | 2027-06-14 09:00 IST | `dopt_2027_closed` |
| 2027-07-05 | Rath Yatra | `rath_yatra` | odisha | regional_major | no | 2027-07-03 09:00 IST | `dopt_2027_restricted` |
| 2027-08-15 | Independence Day | `independence_day` | national | national_observance | no | 2027-08-13 09:00 IST | `dopt_2027_closed` |
| 2027-08-15 | Milad-un-Nabi (Id-e-Milad) | `milad_un_nabi` | national | major | **yes** | 2027-08-13 09:00 IST | `dopt_2027_closed` |
| 2027-08-17 | Raksha Bandhan | `raksha_bandhan` | national | regional_major | no | 2027-08-15 09:00 IST | `dopt_2027_restricted` |
| 2027-08-25 | Janmashtami | `janmashtami` | national | major | **yes** | 2027-08-23 09:00 IST | `dopt_2027_closed` |
| 2027-09-04 | Ganesh Chaturthi | `ganesh_chaturthi` | national, maharashtra | regional_major | no | 2027-09-02 09:00 IST | `dopt_2027_restricted` |
| 2027-09-12 | Onam | `onam` | kerala | regional_major | no | 2027-09-10 09:00 IST | `dopt_2027_restricted` |
| 2027-10-02 | Gandhi Jayanti | `gandhi_jayanti` | national | national_observance | no | 2027-09-30 09:00 IST | `dopt_2027_closed` |
| 2027-10-09 | Dussehra (Vijaya Dashami) | `dussehra` | national | major | **yes** | 2027-10-07 09:00 IST | `dopt_2027_closed` |
| 2027-10-18 | Karva Chauth | `karva_chauth` | north_india | regional_major | no | 2027-10-16 09:00 IST | `dopt_2027_restricted` |
| 2027-10-29 | Diwali (Deepavali) | `diwali` | national | major | **yes** | 2027-10-27 09:00 IST | `dopt_2027_closed` |
| 2027-10-30 | Govardhan Puja | `govardhan_puja` | national | regional_major | no | 2027-10-28 09:00 IST | `dopt_2027_restricted` |
| 2027-10-31 | Bhai Dooj | `bhai_dooj` | national | regional_major | no | 2027-10-29 09:00 IST | `dopt_2027_restricted` |
| 2027-11-04 | Chhath Puja | `chhath_puja` | bihar, jharkhand | regional_major | no | 2027-11-02 09:00 IST | `dopt_2027_restricted` |
| 2027-11-14 | Guru Nanak Jayanti | `guru_nanak_jayanti` | national | major | **yes** | 2027-11-12 09:00 IST | `dopt_2027_closed` |
| 2027-12-25 | Christmas | `christmas` | national | major | **yes** | 2027-12-23 09:00 IST | `dopt_2027_closed` |

## 5. Owner decisions needed

1. Approve (or edit) the default selection and execution time (09:00 IST).
2. ~~Confirm or correct the five Sikkim 2026 dates against the gazette.~~ Done 2026-10-09 from the gazette itself (FESTIVAL_CALENDAR_VERIFICATION.md §4). Decide whether any Sikkim festival joins the selection.
3. Decide whether greeting text may be non-Latin (needs libraqm-enabled Pillow; a dependency change).
