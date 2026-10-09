"""Controlled Brain-contention check for Companion Settings.

Starts its own Runtime v1 instance (the pinned llama.cpp b11425 binary, the
frozen model and argv, on a private port) and measures the companion while the
Brain generates, and the Brain's decode rate with and without the companion
running. Every process it starts is its own and is stopped at the end.

Run it under the machine-wide URI GPU lease, from the repository root of a
tree that has the lease module (e.g. the ws-hardening worktree), so no other
URI GPU workload starts alongside:

    python -m uri_operational_intelligence.gpu_lease run --purpose benchmark \
        --label "companion contention" --max-hold 1200 -- \
        python <this repo>/rnd/companions/settings/brain_contention.py <out dir>

Steps (default order, Brain first):
  1. start the server, wait until it answers /health;
  2. decode three times with nothing else running (baseline tok/s);
  3. for each companion frame-rate setting (fps144, adaptive, fps30): launch
     the profile perf harness (Lunar, Companion mode, 100 s) and, from second
     30 to second 70, keep the Brain decoding; record each request's tok/s;
  4. stop the server and write brain_contention.json.

With --ui-first the order is reversed, as when URI's window is already open
when the Brain starts: the companion (Lunar, adaptive, 360 s) starts first,
the server 10 s later; once healthy the Brain decodes for 120 s; the
companion keeps running 2 minutes more so recovery is visible. Writes
brain_contention_ui_first.json.
"""
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
RUN = os.path.join(HERE, 'run_companion_perf.ps1')
PORT = 18499
EXE = r'D:\uri-model-lab\runtime\llama-b11425-bin-win-vulkan-x64\llama-server.exe'
MODELS = r'D:\uri-model-lab\models\unsloth__Qwen3.6-35B-A3B-GGUF'
# The frozen Runtime v1 argv (runtime_v1.expected_argv) with only the port changed.
ARGV = [EXE, '-m', MODELS + r'\Qwen3.6-35B-A3B-UD-IQ3_S.gguf', '-c', '32768', '-ngl', '999', '-fa', 'on',
        '-ctk', 'q8_0', '-ctv', 'q8_0', '-np', '1', '--host', '127.0.0.1', '--port', str(PORT), '--jinja',
        '--reasoning-format', 'deepseek', '--no-webui', '--load-mode', 'none', '--cache-ram', '2048',
        '--mmproj', MODELS + r'\mmproj-F16.gguf', '-b', '2048', '-ub', '1024', '--slot-prompt-similarity', '0',
        '--checkpoint-min-step', '512', '--ctx-checkpoints', '16',
        '-md', 'D:/uri-model-lab/mtp/mtp-qwen36-35b-a3b-Q4_K_M.gguf', '--spec-type', 'draft-mtp',
        '--spec-draft-n-max', '2', '-otd', 'token_embd.weight=CPU']
PROMPT = "Here is a numbered list of forty everyday household objects, one per line:\n1."


def post(path, body, timeout=300):
    req = urllib.request.Request(f'http://127.0.0.1:{PORT}{path}', data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def healthy():
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{PORT}/health', timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def decode(n=256):
    t0 = time.time()
    r = post('/completion', {'prompt': PROMPT, 'n_predict': n, 'temperature': 0, 'cache_prompt': False})
    tm = r.get('timings', {})
    return {'t': round(t0, 2), 'tokens': tm.get('predicted_n'), 'tok_s': tm.get('predicted_per_second'),
            'wall_s': round(time.time() - t0, 2)}


def ui_first(out):
    log = open(os.path.join(out, 'llama_server_ui_first.log'), 'w', encoding='utf-8')
    perf = subprocess.Popen(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', RUN,
                             '-Identity', 'lunar', '-Fps', 'adaptive', '-Quality', 'full', '-Layout', 'shell',
                             '-Seconds', '360', '-OutDir', out, '-Tag', 'brain-ui-first-lunar-adaptive'],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    launched = time.time()
    server = None
    result = {'order': 'ui_first', 'started': time.strftime('%Y-%m-%dT%H:%M:%S'), 'perf_launched': round(launched, 2)}
    try:
        time.sleep(10)
        server = subprocess.Popen(ARGV, stdout=log, stderr=subprocess.STDOUT)
        t0 = time.time()
        while not healthy():
            if server.poll() is not None:
                raise RuntimeError('server exited during load')
            if time.time() - t0 > 400:
                raise RuntimeError('server not healthy after 400 s')
            time.sleep(2)
        result['load_s'] = round(time.time() - t0, 1)
        decode(32)
        gen_start = time.time()
        result['gen_start_s'] = round(gen_start - launched, 1)
        reqs = []
        while time.time() - gen_start < 120:
            reqs.append(decode())
        result['gen_end_s'] = round(time.time() - launched, 1)
        result['requests'] = reqs
        perf_out, _ = perf.communicate(timeout=600)
        result['runner'] = perf_out.strip().splitlines()[-1:]
        result['after_ui_exit'] = [decode() for _ in range(2)]
    finally:
        if perf.poll() is None:
            subprocess.run(['powershell', '-NoProfile', '-Command',
                            "Get-Process uri_ui -ErrorAction SilentlyContinue | "
                            "Where-Object { $_.Path -like '*uri-companion-voice*' } | Stop-Process -Force"],
                           check=False)
            perf.kill()
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=30)
            except subprocess.TimeoutExpired:
                server.kill()
        log.close()
        result['finished'] = time.strftime('%Y-%m-%dT%H:%M:%S')
        with open(os.path.join(out, 'brain_contention_ui_first.json'), 'w', encoding='utf-8', newline='\n') as f:
            json.dump(result, f, indent=1)
    print(json.dumps({k: v for k, v in result.items() if k != 'requests'}, indent=1))
    print('tok_s', [round(r['tok_s'], 1) for r in result.get('requests', [])])


def main():
    out = os.path.abspath(sys.argv[1])
    if '--ui-first' in sys.argv:
        os.makedirs(out, exist_ok=True)
        ui_first(out)
        return
    os.makedirs(out, exist_ok=True)
    log = open(os.path.join(out, 'llama_server.log'), 'w', encoding='utf-8')
    server = subprocess.Popen(ARGV, stdout=log, stderr=subprocess.STDOUT)
    perf = None
    result = {'argv_port': PORT, 'started': time.strftime('%Y-%m-%dT%H:%M:%S'), 'baseline': [], 'runs': {}}
    try:
        t0 = time.time()
        while not healthy():
            if server.poll() is not None:
                raise RuntimeError('server exited during load')
            if time.time() - t0 > 400:
                raise RuntimeError('server not healthy after 400 s')
            time.sleep(2)
        result['load_s'] = round(time.time() - t0, 1)
        decode(32)  # warm-up
        result['baseline'] = [decode() for _ in range(3)]
        for fps in ('fps144', 'adaptive', 'fps30'):
            tag = f'brain-lunar-{fps}'
            perf = subprocess.Popen(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', RUN,
                                     '-Identity', 'lunar', '-Fps', fps, '-Quality', 'full', '-Layout', 'shell',
                                     '-Seconds', '100', '-OutDir', out, '-Tag', tag],
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            launched = time.time()
            time.sleep(30)
            reqs = []
            while time.time() - launched < 70:
                reqs.append(decode())
            perf_out, _ = perf.communicate(timeout=300)
            result['runs'][fps] = {'perf_launched': round(launched, 2), 'requests': reqs,
                                   'runner': perf_out.strip().splitlines()[-1:]}
            time.sleep(5)
        result['after'] = [decode() for _ in range(2)]
    finally:
        # Never leave the measured app behind if a step failed mid-run.
        if perf is not None and perf.poll() is None:
            subprocess.run(['powershell', '-NoProfile', '-Command',
                            "Get-Process uri_ui -ErrorAction SilentlyContinue | "
                            "Where-Object { $_.Path -like '*uri-companion-voice*' } | Stop-Process -Force"],
                           check=False)
            perf.kill()
        server.terminate()
        try:
            server.wait(timeout=30)
        except subprocess.TimeoutExpired:
            server.kill()
        log.close()
        result['finished'] = time.strftime('%Y-%m-%dT%H:%M:%S')
        with open(os.path.join(out, 'brain_contention.json'), 'w', encoding='utf-8', newline='\n') as f:
            json.dump(result, f, indent=1)
    print(json.dumps({k: v for k, v in result.items() if k != 'runs'}, indent=1))
    for k, v in result['runs'].items():
        print(k, [r['tok_s'] for r in v['requests']])


if __name__ == '__main__':
    main()
