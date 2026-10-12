# Phase 2A power-loss qualification plan (NOT EXECUTED)

Power loss and OS write reordering cannot be tested by killing a process. `os._exit` and process termination leave
the kernel page cache intact, so every committed WAL frame survives regardless of `synchronous`. This plan exists so
the durability claim can be tested honestly; it requires a throwaway VM and was not run on this machine.

## What the configuration claims

* `journal_mode=WAL`, `synchronous=FULL`, set and read back on every connection (`Ledger.durability_report`).
* Per the SQLite WAL documentation, with `synchronous=FULL` the WAL is synced on every commit, so a transaction that
  returned from `COMMIT` is durable across power loss, assuming the storage honours flush requests.
* Every authoritative write (admission, intent, SPAWNING marker, process identity, decision) is its own transaction.

## Harness (VM, Windows 11, virtual disk with write-cache disabled or a flush-honouring emulator)

1. Run a worker that loops: submit task, admit, declare intent, mark SPAWNING, record identity, append stream lines.
   After each COMMIT it writes the committed sequence number to a SEPARATE host-visible channel (virtio serial or a
   network socket), never to the same disk.
2. Hard power-off the VM (hypervisor "power off", not guest shutdown) at random instants, 200+ iterations, including
   during checkpointing and during large transactions.
3. After boot, open the ledger and assert: (a) every sequence number the host saw acknowledged is present;
   (b) `PRAGMA integrity_check` is `ok`; (c) no attempt is in SPAWNING/RUNNING without a matching intent and admission
   row; (d) startup recovery reaches a decision for every in-flight attempt; (e) no effect-bearing attempt was retried
   without proof.
4. Repeat with a deliberately weakened control (`synchronous=NORMAL`) to confirm the harness can detect loss. If the
   control never loses an acknowledged commit, the harness is not strong enough and the result for FULL is meaningless.

## Pass criteria

All 200+ iterations satisfy (a)-(e) for FULL. The NORMAL control shows at least one lost acknowledged commit.

## Why it was not run here

It needs a VM with controllable virtual-disk caching and a hypervisor power-off, a destructive machine-level setup
outside this run's authority.
