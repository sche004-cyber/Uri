import pandas as pd
from openpyxl import Workbook
df = pd.read_excel("sales.xlsx", sheet_name="Sales", usecols=["Region", "Amount"])
total = df["Amount"].sum()
out = Workbook(); o = out.active; o.title = "Summary"
o.append(["Total"]); o.append([int(total)])
out.save("summary.xlsx")
