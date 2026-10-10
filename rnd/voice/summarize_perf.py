"""Summarises a perf directory written by run_matrix.ps1 / run_perf.ps1.

Run: python rnd/voice/summarize_perf.py <perf dir>
Prints one markdown table row per run. The last two columns exist only for
runs sampled after the sampler learned to record system CPU and other
processes holding more than 1 GB of VRAM.
"""
import csv
import glob
import json
import os
import sys

D = sys.argv[1]


def avg(v):
    return sum(v) / len(v) if v else 0.0


print('| run | frames | fps | build p50/p99 ms | raster p50/p90/p99/max ms '
      '| frames >16.7 ms | CPU % avg/max | GPU 3D % avg/max | adapter 3D % avg '
      '| VRAM MB avg/max | RSS MB start/end | system CPU % avg | other process >1 GB VRAM |')
print('|---|---|---|---|---|---|---|---|---|---|---|---|---|')
invalid = []
for jf in sorted(glob.glob(os.path.join(D, '*.json'))):
    if jf.endswith('.gpu_advise.json'):
        continue                              # the P-GOV-1 advisory record of a run, not a run
    tag = os.path.basename(jf)[:-5]
    try:
        verdict = json.load(open(os.path.join(D, tag + '.gpu_advise.json'), encoding='utf-8-sig')).get('verdict')
    except (OSError, ValueError):
        verdict = None                        # runs made before the advisory existed
    if verdict not in (None, 'GO'):
        invalid.append(f"{tag} (gpu advisory {verdict})")   # run_perf.ps1 marked it RUN_INVALID
        continue
    j = json.load(open(jf))
    o = j['overall']
    fps = o['frames'] / (o['t_ms'] / 1000)
    rows = list(csv.DictReader(open(os.path.join(D, tag + '.samples.csv'))))

    def col(k):
        return [float(r[k]) for r in rows if r.get(k) not in (None, '')]

    rss = j['rss_bytes']
    if 'system_cpu_pct' in rows[0]:
        sc = col('system_cpu_pct')
        # The machine's Processor counter fails (PDH c0000bb8), which the
        # sampler records as 0; report that as missing, not as idle.
        sys_cpu = f"{avg(sc):.0f}" if any(sc) else 'not captured'
        fv = col('foreign_vram_gb')
        hit = sum(1 for v in fv if v > 0)
        foreign = f"max {max(fv):.1f} GB in {hit}/{len(fv)} samples" if hit else 'none'
    else:
        sys_cpu = foreign = 'not sampled'
    print(f"| {tag} | {o['frames']} | {fps:.0f} | {o['build_p50']:.2f}/{o['build_p99']:.2f} | "
          f"{o['raster_p50']:.2f}/{o['raster_p90']:.2f}/{o['raster_p99']:.2f}/{o['raster_max']:.1f} | "
          f"{o['over_16ms']} ({100 * o['over_16ms'] / o['frames']:.1f}%) | "
          f"{avg(col('cpu_pct')):.1f}/{max(col('cpu_pct')):.1f} | "
          f"{avg(col('gpu3d_pct')):.1f}/{max(col('gpu3d_pct')):.1f} | "
          f"{avg(col('adapter3d_pct')):.1f} | "
          f"{avg(col('dedicated_mb')):.0f}/{max(col('dedicated_mb')):.0f} | "
          f"{rss[0]['rss'] / 2**20:.0f}/{rss[-1]['rss'] / 2**20:.0f} | {sys_cpu} | {foreign} |")
if invalid:
    print()
    print('Excluded (measured while a resident Brain would be slowed): ' + '; '.join(invalid))
