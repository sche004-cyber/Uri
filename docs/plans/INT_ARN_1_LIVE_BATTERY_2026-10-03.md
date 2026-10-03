# INT-ARN-1 live battery, 2026-10-03

Desktop backend at 25c9ebe, URI_INT_ARN_1_ENABLED=1 and URI_INT_ARN_1_DIAGNOSTICS=1, local Ollama, test account, run by Claude with int_arn_1_live_battery.py. One fresh session per case; the first case of each run includes a model load.

## Findings

- Neither Brain proposed reference_slots in any of 16 decisions, so no clarification card was ever built. The INT-ARN-1 card path is never triggered by these local Brains.
- gemma4:12b asked a correct plain-language "which one?" question in all three ambiguous cases (two reports, two budgets, convert ambiguous report) and executed nothing there.
- qwen3.5:9b never asked: with two similar files it read both and answered about both; for the ambiguous conversion it refused because only PDF converts.
- Three turns returned "The Brain route is unavailable" with no diagnostics (gemma: compare_them, earlier_turn; qwen: chat_control). With the flag on, a canonical fallback is blocked instead of handled; this is a defect.
- Warm latency 4 to 10 s per turn. The model unload guard worked live: switching Brain left only the active large model loaded.

## Cases

| Brain | Case | Mode | Capability | Slots | Execution | Reply (truncated) |
|---|---|---|---|---|---|---|
| gemma4:12b | single_attachment | single_action | read_attached_file | False | success | The Q3 2025 sales report shows a total of 215 units sold: 120 in the North and 95 in the South. |
| gemma4:12b | similar_reports | clarification | read_attached_file | False | not_executed | I see two files: 'q3_report.txt' and 'q4_report.txt'. Which one would you like me to summarize? |
| gemma4:12b | compare_them | - | - | None | not_executed | The Brain route is unavailable. Please try again. |
| gemma4:12b | two_budgets | clarification | read_attached_file | False | not_executed | You have two budget files attached (budget_2025.csv and budget_2026.csv). Which one would you like me to open? |
| gemma4:12b | named_file | single_action | read_attached_file | False | success | The Q4 2025 sales report shows a total of 240 units sold, with 135 units in the North and 105 units in the Sou |
| gemma4:12b | earlier_turn | - | - | None | not_executed | The Brain route is unavailable. Please try again. |
| gemma4:12b | chat_control | conversation | - | False | not_applicable | 7 plus 5 is 12. |
| gemma4:12b | consequential_ambiguous | clarification | convert_document | False | not_executed | You have two reports attached (q3_report.txt and q4_report.txt). Which one would you like me to convert to Wor |
| qwen3.5:9b | single_attachment | single_action | read_attached_file | False | success | The attached file, *q3_report.txt*, is a brief sales report for Q3 2025. It lists North region sales at 120 un |
| qwen3.5:9b | similar_reports | single_action | read_attached_file | False | success | The sales reports for Q3 and Q4 2025 show a steady increase in performance. In Q3, total sales reached 215 uni |
| qwen3.5:9b | compare_them | single_action | read_attached_file | False | success | Q3 2025 sales totaled 215 units (North: 120, South: 95), while Q4 2025 sales reached 240 units (North: 135, So |
| qwen3.5:9b | two_budgets | single_action | read_attached_file | False | success | I have read the two attached budget files: `budget_2025.csv` and `budget_2026.csv`.  **Budget 2025:** *   **Re |
| qwen3.5:9b | named_file | single_action | read_attached_file | False | success | Q4 2025 sales totaled 240 units: North region sold 135 units, and South region sold 105 units. |
| qwen3.5:9b | earlier_turn | single_action | read_attached_file | False | success | I have read the two attached files: `q3_report.txt` and `q4_report.txt`.  - **Q3 2025:** North sold 120 units, |
| qwen3.5:9b | chat_control | - | - | None | not_executed | The Brain route is unavailable. Please try again. |
| qwen3.5:9b | consequential_ambiguous | single_action | convert_document | False | input_required | I cannot convert the attached `.txt` files directly to Word; I need a PDF file to perform this conversion. Ple |
