"""Summarise docs/ui_phase/perf/*.log into a Markdown table.

Each log holds "[perf] frames=N over 5s build p50=..ms p95=..ms raster p50=..ms p95=..ms total p95=..ms >16.7ms=K"
lines, one per 5-second window, from lib/living/perf_logger.dart. The first
window after launch is skipped (shader compile, first layout). Medians across
windows are reported so one outlier window does not dominate.
"""
import glob
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PERF = os.path.join(HERE, "..", "perf")
PAT = re.compile(
    r"frames=(\d+) over (\d+)s build p50=([\d.]+)ms p95=([\d.]+)ms raster p50=([\d.]+)ms "
    r"p95=([\d.]+)ms total p95=([\d.]+)ms >16\.7ms=(\d+)"
)

rows = []
for path in sorted(glob.glob(os.path.join(PERF, "*.log"))):
    name = os.path.basename(path)[:-4]
    windows = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = PAT.search(line)
            if m:
                windows.append([float(x) for x in m.groups()])
    if len(windows) < 2:
        rows.append((name, "no samples (see log)", "", "", "", "", ""))
        continue
    w = windows[1:]  # skip the warm-up window
    med = lambda i: statistics.median(x[i] for x in w)
    rows.append((
        name,
        f"{len(w)} x {int(w[0][1])}s",
        f"{med(0):.0f}",
        f"{med(2):.2f} / {med(3):.2f}",
        f"{med(4):.2f} / {med(5):.2f}",
        f"{med(6):.2f}",
        f"{med(7):.0f} (max {max(x[7] for x in w):.0f})",
    ))

print("| Scenario (log) | Windows | Frames / window | build p50 / p95 ms | raster p50 / p95 ms | total p95 ms | frames > 16.7 ms per window |")
print("|---|---|---|---|---|---|---|")
for r in rows:
    print("| " + " | ".join(str(c) for c in r) + " |")
if "--check" in sys.argv:
    sys.exit(0)
