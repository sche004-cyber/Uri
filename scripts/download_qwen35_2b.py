import os
import sys
import time
import urllib.request

DEST_DIR = r"C:\Users\cheta\.lmstudio\models\Qwen\Qwen3.5-2B-GGUF"
FILENAME = "Qwen3.5-2B-Q4_K_M.gguf"
DEST_PATH = os.path.join(DEST_DIR, FILENAME)
URL = f"https://huggingface.co/openresearchtools/Qwen3.5-2B-GGUF/resolve/main/{FILENAME}"

def download():
    os.makedirs(DEST_DIR, exist_ok=True)
    if os.path.exists(DEST_PATH):
        existing_size = os.path.getsize(DEST_PATH)
        print(f"File already exists at {DEST_PATH} with size {existing_size} bytes.")
        # Check remote size
        req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"}, method="HEAD")
        with urllib.request.urlopen(req) as resp:
            total_size = int(resp.headers.get("Content-Length", 0))
        if existing_size == total_size and total_size > 0:
            print("File is complete and matches remote size.")
            return
        else:
            print(f"Size mismatch (local: {existing_size}, remote: {total_size}). Resuming or restarting...")
    
    print(f"Starting download from {URL} to {DEST_PATH}...")
    headers = {"User-Agent": "Mozilla/5.0"}
    
    start_time = time.time()
    last_print = start_time
    downloaded = 0
    
    req = urllib.request.Request(URL, headers=headers)
    with urllib.request.urlopen(req) as resp:
        total_size = int(resp.headers.get("Content-Length", 0))
        print(f"Total size: {total_size / (1024**2):.2f} MB ({total_size} bytes)")
        
        with open(DEST_PATH, "wb") as f:
            chunk_size = 1024 * 1024 * 4  # 4MB chunks
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
                    print(f"Downloaded: {downloaded / (1024**2):.2f} / {total_size / (1024**2):.2f} MB ({pct:.1f}%) at {speed:.2f} MB/s", flush=True)
                    last_print = now

    final_size = os.path.getsize(DEST_PATH)
    print(f"Download complete: {DEST_PATH} ({final_size} bytes)")

if __name__ == "__main__":
    download()
