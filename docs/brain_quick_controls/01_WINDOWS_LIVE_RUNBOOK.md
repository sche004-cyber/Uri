# BRAIN-QUICK-CONTROLS: Windows live-test runbook (owner's PC)

The live journeys J1-J5 of `00_PLAN_AND_ACCEPTANCE_CRITERIA.md` section 3 run here. The code is reviewed and tested
on a Linux host first, but that host has no GPU, no Windows and no real app. So acceptance criteria AC2-AC4 and AC6-AC12
are only proven by this run.

Everything runs in a **new, separate** clone, runtime and client. Your normal URI installation, its preferences and
the canonical branch are not touched. Nothing here is integrated into canonical.

Run every command in your own PowerShell window, from the folder named in that step.

## 0. Before you start

1. Close the URI app and stop any Brain from your normal installation the way you normally do. Then check that
   nothing listens on the Brain port (the command must print nothing):

   ```powershell
   Get-NetTCPConnection -LocalPort 18470 -State Listen -ErrorAction SilentlyContinue
   ```

   The test launcher never stops a process on port 18470. With another Brain still running there, the test app
   attaches to it instead of starting its own. That Brain is not the one this test configures, so the app shows the
   Brain as not available and refuses every Vision or Context switch, and the journeys below cannot pass.
2. Close LM Studio and Ollama models that use the GPU. Keep Chrome closed until step J5.
3. Note the free GPU memory with nothing open:

   ```powershell
   (Get-Counter '\GPU Adapter Memory(*)\Dedicated Usage').CounterSamples |
     Sort-Object CookedValue -Descending | Select-Object -First 1 InstanceName, @{n='MiB';e={[int]($_.CookedValue/1MB)}}
   ```

## 1. Get the candidate

```powershell
cd C:\Users\cheta\Development
git -c core.autocrlf=false clone --branch claude/brain-quick-controls-ghikbt https://github.com/sche004-cyber/Uri uri-bqc
cd uri-bqc
git log --oneline -1          # write down this commit id; the evidence must name it
```

`core.autocrlf=false` matters: some frozen-scope anchor files fail their hash check under `autocrlf=true`.

## 2. Materialize a test runtime and provision a fresh client

This uses the venv of your working-system runtime (`uri-ws-hard`). Use another runtime venv if that is the one you
normally use. The source venv is copied, never changed.

```powershell
cd C:\Users\cheta\Development\uri-bqc
C:\Users\cheta\Development\uri-ws-hard\.venv\Scripts\python.exe scripts\oi_materialize_test_runtime.py `
  C:\Users\cheta\Development\uri-bqc-run --venv C:\Users\cheta\Development\uri-ws-hard\.venv
cd C:\Users\cheta\Development\uri-bqc-run
.venv\Scripts\python.exe scripts\ws_provision.py --name bqc-first
```

Find the new client folder, and define the exit command for the test Brain (the app has no Stop Brain button, and the
Brain host otherwise keeps running for 8 hours). Keep this PowerShell window open: later steps use `$oi` and
`Exit-TestBrain`.

```powershell
$cur = Get-Content -Raw C:\Users\cheta\Development\uri-bqc-run\work\c1\ws-current.json | ConvertFrom-Json
$cli = Get-Content -Raw $cur.client_manifest | ConvertFrom-Json
$oi  = Join-Path $cli.client_root 'control\oi'
$oi
function Exit-TestBrain {
  # The Brain host's own exit file (scripts/ws_brain_host.py): it stops the Brain, frees the GPU lease and exits.
  New-Item -ItemType File -Force C:\Users\cheta\Development\uri-bqc-run\work\oi\state\runtime_v1.stop | Out-Null
  $report = Join-Path $oi 'brain_host.json'
  if (-not (Test-Path $report)) { 'No Brain host report: nothing to stop'; return }
  $until = (Get-Date).AddSeconds(180)
  do {
    Start-Sleep 2
    $r = Get-Content -Raw $report | ConvertFrom-Json
    if ($r.detail -eq 'HOST_EXIT') { 'Brain host exited'; return }
  } until ((Get-Date) -gt $until)
  "Brain host did not exit within 3 minutes (state $($r.state), $($r.detail)). Paste this line into the thread.
}
```

## 3. Build the app and self-test the launcher

```powershell
cd C:\Users\cheta\Development\uri-bqc\uri_ui
flutter build windows --release
cd C:\Users\cheta\Development\uri-bqc
.\"Launch URI Working System.bat" -RuntimeRoot C:\Users\cheta\Development\uri-bqc-run `
  -UiRoot C:\Users\cheta\Development\uri-bqc -SelfTest
```

The self-test must report no problems. If it lists any, stop and paste its output into the thread.

## 4. First-time user: launch

```powershell
.\"Launch URI Working System.bat" -RuntimeRoot C:\Users\cheta\Development\uri-bqc-run `
  -UiRoot C:\Users\cheta\Development\uri-bqc
```

There is no `brain_profile.json` yet, so the Brain starts with the development default: 32K context, Vision on,
speed boost off (decision BQC-D1, still open). Open the Workspace conversation. Next to the Brain status you should
see three controls: **Thinking**, **Vision** and **Context**.

Take a screenshot of each step marked 📷 and save it in `C:\Users\cheta\Development\uri-bqc-evidence` under the given
name.

| Step | What you do | What must happen |
|---|---|---|
| F1 📷 `f1-start.png` | Wait for the Brain to finish starting | The status says starting, then ready. Vision shows **On** only once the Brain is ready (never before). Context shows **32K**. |
| F2 📷 `f2-menus.png` | Open the Thinking menu, then the Context menu | Thinking: Auto, Off, On, Deep, each with a one-line explanation. Context: only the sizes offered for Vision on (32K, 64K); 64K is marked "tight on GPU memory, about 300 MB spare". |

## 5. Journeys

**J1 Thinking (no reload)**

| Step | What you do | What must happen |
|---|---|---|
| J1.1 | Set Thinking **Off**, ask "What is 17 × 23?" | Fast answer, no reasoning shown. Brain status never leaves ready. |
| J1.2 | Set Thinking **On**, ask "Explain briefly why the sky is blue." | Answer after visible reasoning, no reload. |
| J1.3 📷 `j1-auto.png` | Set Thinking **Auto** | Next answer is normal; the label shows Auto. |

**J2 Vision off, then on (reload, truthful status)**

| Step | What you do | What must happen |
|---|---|---|
| J2.1 | Click **Vision**, choose to turn it off | A confirmation says the Brain reloads in about 30 seconds and the conversation stays. |
| J2.2 📷 `j2-switching.png` | Confirm, and screenshot during the reload | The status shows **switching**, the ready dot is off, and Vision does not show On. |
| J2.3 📷 `j2-off.png` | Wait until ready | Vision **Off**, Context unchanged (32K). The Context menu now also lists 16K and 128K. |
| J2.4 | Turn Vision back on and confirm | The same switching state, then Vision **On** once ready. |

During J2, run this in a second PowerShell window and save the output as `j2-host.json`:

```powershell
Get-Content -Raw (Join-Path $oi 'brain_host.json')
```

**J3 Switch during a conversation**

| Step | What you do | What must happen |
|---|---|---|
| J3.1 | Tell URI "My project code name is Bluefin." Then ask one more ordinary question. | Normal answers. |
| J3.2 | Ask a long question ("Write a 300-word story about a lighthouse") and, while the answer is being written, look at the Vision and Context controls | Both are greyed out and cannot be opened. Nothing reloads. |
| J3.3 📷 `j3-after.png` | After the answer, switch Context to **64K** and confirm. When ready, ask "What is my project code name?" | Answers **Bluefin**. The earlier messages are still on screen. |
| J3.4 | Switch Context back to **32K** | Because the conversation is short, no shrink warning appears. |

**J4 Images**

Use any photo or screenshot (PNG, JPEG or WebP, any size; the app scales it down).

| Step | What you do | What must happen |
|---|---|---|
| J4.1 📷 `j4-on.png` | With Vision on, attach the image with the composer's attach button and ask "What is in this picture?" | The image appears as a chip before you send. The answer describes the picture correctly. |
| J4.2 | Attach the same image and ask "Save this picture to my documents" | Refused with a plain message that actions with pictures are not supported yet. The image is never silently dropped. |
| J4.2b | Attach the image and ask "Write an email to Bob describing this picture" | Refused: URI cannot write a document from a picture yet, and says to ask about the picture first. No draft opens. |
| J4.3 📷 `j4-off.png` | Turn Vision off, wait until ready, then try to attach an image | The app refuses the image and says Vision is off. |
| J4.4 | Ask "What was in the picture I sent earlier?" | URI must not describe new details as if it could still see the picture. The history keeps only "[Attached image: name]", never the picture (it may repeat what it said in J4.1). |

**J5 Larger context, speed boost and GPU memory**

Run the GPU memory command from step 0 after each switch and save all the readings in `j5-vram.txt`.

| Step | What you do | What must happen |
|---|---|---|
| J5.1 | With Vision off, choose Context **128K** | Ready, with no demotion warning. Note the memory. |
| J5.2 | Open Chrome with 4-6 ordinary tabs and ask a short question | Answer speed close to before (note any slowdown). Close Chrome. |
| J5.3 📷 `j5-speed.png` | Go to Settings and look at **Speed boost (MTP)** at 128K. Then switch Context to 32K and turn speed boost on. | At 128K the switch is greyed out and says it is available with Vision off at 16K or 32K. At 32K it turns on after a reload, and the Brain bar shows "Speed boost on". |
| J5.4 | Turn speed boost off, then Vision on (32K) | Back to the default profile. |

## 6. Returning user

1. Close the app, then run `Exit-TestBrain` and wait until it prints "Brain host exited". This makes the next launch
   start a new Brain host, which must read your saved choice.
2. Launch again with the command from step 4.
3. 📷 `r1-returning.png` The Brain starts with the **last** profile you chose (32K + Vision after J5.4), and Thinking
   shows the last non-Deep choice you made (Auto after J1.3).
4. Choose 64K with Vision off, close the app, run `Exit-TestBrain` and relaunch. It must come back as 64K with Vision off.

## 7. Collect the evidence

```powershell
$ev = 'C:\Users\cheta\Development\uri-bqc-evidence'
Copy-Item (Join-Path $oi 'brain_host.json'), (Join-Path $oi 'brain_profile.json') $ev -ErrorAction Continue
git -C C:\Users\cheta\Development\uri-bqc rev-parse HEAD | Out-File (Join-Path $ev 'commit.txt')
Compress-Archive -Path "$ev\*" -DestinationPath "$ev.zip" -Force
```

Upload `uri-bqc-evidence.zip` to this thread, and say which steps behaved differently from the table. Claude reviews
the evidence, records it in the UI qualification record, and repairs any failure. You don't need to judge the results
yourself.

## 8. Clean up (optional)

Close the app, run `Exit-TestBrain`, and delete `uri-bqc`, `uri-bqc-run` and `uri-bqc-evidence`. Your normal installation
was never changed.
