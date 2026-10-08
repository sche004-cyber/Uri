import httpx
import json

payload = {
    "model": "lfm2.5-350m",
    "messages": [
        {"role": "system", "content": "You are a tiny semantic worker. Output valid JSON only matching the schema. No explanations, no markdown."},
        {"role": "user", "content": "Task: Calculate total revenue for Q3 from revenue.csv\nInstruction: Identify the target filename and select exactly one intent from {'CALCULATE', 'EXTRACT'}.\nGuidelines:\n- Use EXTRACT when retrieving or reading existing text verbatim.\n- Use CALCULATE when deriving, aggregating, or computing sums/totals from numeric data.\nSchema: {\"decision\": \"LOCAL\", \"intent\": \"<intent_choice>\", \"target\": \"<filename>\"}\nReturn ONLY valid JSON."}
    ],
    "temperature": 0.0
}
res = httpx.post("http://127.0.0.1:1234/v1/chat/completions", json=payload)
raw = res.json()["choices"][0]["message"]["content"]
print("RAW CONTENT:", repr(raw))
clean = raw.strip()
if clean.startswith("```json"): clean = clean[7:]
if clean.startswith("```"): clean = clean[3:]
if clean.endswith("```"): clean = clean[:-3]
data = json.loads(clean.strip())
print("PARSED:", data)
print("TYPE OF INTENT:", type(data.get("intent")), data.get("intent"))
