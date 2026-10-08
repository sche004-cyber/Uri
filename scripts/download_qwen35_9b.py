import os
import sys
import time
import urllib.request

DEST_DIR = r"C:\Users\cheta\.lmstudio\models\Qwen\Qwen3.5-9B-GGUF"
FILENAME = "Qwen3.5-9B-Q4_K_M.gguf"
DEST_PATH = os.path.join(DEST_DIR, FILENAME)
URL = f"https://huggingface.co/openresearchtools/Qwen3.5-9B-GGUF/resolve/main/{FILENAME}"
EXPECTED_SIZE = 5629109056

def download():
    os.makedirs(DEST_DIR, exist_ok=True)
    if os.path.exists(DEST_PATH):
        existing_size = os.path.getsize(DEST_PATH)
        print(f"File exists at {DEST_PATH} with size {existing_size} bytes.")
        if existing_size == EXPECTED_SIZE:
            print(f"File is already fully downloaded and matches expected exact size ({EXPECTED_SIZE} bytes).")
            return
        else:
            print(f"Size mismatch: local={existing_size}, expected={EXPECTED_SIZE}. Restarting download...")

    print(f"Starting download from {URL} to {DEST_PATH}...")
    headers = {"User-Agent": "Mozilla/5.0"}

    start_time = time.time()
    last_print = start_time
    downloaded = 0

    req = urllib.request.Request(URL, headers=headers)
    with urllib.request.urlopen(req) as resp:
        total_size = int(resp.headers.get("Content-Length", 0))
        print(f"Remote Content-Length: {total_size} bytes ({total_size / (1024**3):.2f} GB)")

        with open(DEST_PATH, "wb") as f:
            chunk_size = 1024 * 1024 * 8  # 8MB chunks
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                now = time.time()
                if now - last_print >= 2.0 or downloaded == total_size:
                    elapsed = now - start_time
                    speed = (downloaded / (1024**2)) / max(elapsed, 0.001)
                    pct = (downloaded / total_size) * 100 if total_size else 0
                    print(
                        f"Downloaded: {downloaded / (1024**2):.2f} / {total_size / (1024**2):.2f} MB "
                        f"({pct:.1f}%) at {speed:.2f} MB/s",
                        flush=True
                    )
                    last_print = now

    final_size = os.path.getsize(DEST_PATH)
    print(f"Download complete: {DEST_PATH} ({final_size} bytes)")
    if final_size == EXPECTED_SIZE:
        print("VERIFIED: File size matches expected size exactly.")
    else:
        print(f"WARNING: File size {final_size} does not match expected {EXPECTED_SIZE}")

if __name__ == "__main__":
    download()
