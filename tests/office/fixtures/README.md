# URI Office test fixtures

## excel_financial_sample.xlsx

- **What:** Microsoft's public "Financial Sample" workbook, the Power BI sample data set. All figures are fictional; there is no personal data.
- **Source:** `https://go.microsoft.com/fwlink/?LinkID=521962`, which redirected to `https://download.microsoft.com/download/1/4/E/14EDED28-6C58-4055-A65C-23B4DA81C4DE/Financial%20Sample.xlsx`.
- **Downloaded:** 2026-10-11, 83,418 bytes, with approval from the development session.
- **SHA-256:** `c3f17156ab7c192571ecfc742e88c16a4b7243a4d4b4a420fcb68dec44e10196`. `test_excel_saved_fixture.py` checks this hash.
- **Saved by Excel:** `docProps/app.xml` says `Microsoft Excel`, AppVersion 15.0300.
- **Contents that matter for the tests:**
  - a real `xl/sharedStrings.xml` (count 4216, uniqueCount 50);
  - `mc:Ignorable="x14ac"` markup;
  - an Excel table (`xl/tables/table1.xml`, A1:P701);
  - `customXml` parts.
- **Checked absent:** VBA, external links and data connections.
- **Why:** openpyxl, which made every other fixture here, writes inline strings and no shared-string table. Excel-saved files are what owners actually open.
