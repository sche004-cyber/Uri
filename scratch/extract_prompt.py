import json

with open(r"C:\Users\cheta\.gemini\antigravity\brain\c23e9a03-c3ad-4e31-a74b-af76d82df119\.system_generated\logs\transcript_full.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        if '"step_index":2032' in line or '"step_index": 2032' in line:
            obj = json.loads(line)
            content = obj.get("content", "")
            with open("scratch/prompt_a2_5_stage3.txt", "w", encoding="utf-8") as out:
                out.write(content)
            print(f"Saved prompt. Length: {len(content)}")
            break
