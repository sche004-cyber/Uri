"""Summarises a directory of companion_perf runs (JSON + samples CSV).

    python rnd/companions/settings/summarize.py <dir> [<dir> ...]

Prints one markdown row per run. Columns: the requested setting, the display
rate, frames the engine produced per second, frames the companion clock
delivered per second, build and raster percentiles, frames over 16.7 ms,
process CPU, the process's own share of the GPU 3D engine, the whole
adapter's 3D utilisation (so other GPU users are visible), dedicated VRAM, RSS
and Dart heap at start and end, and the largest other process in VRAM.

For a run with a minimise window (tag starting "hidden"), also prints frames
per second and GPU share before, during and after the window.
"""
import csv
import glob
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")


def avg(v):
    return sum(v) / len(v) if v else 0.0


def rows_of(csv_path):
    if not os.path.exists(csv_path):
        return []
    with open(csv_path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def col(rows, k):
    out = []
    for r in rows:
        try:
            out.append(float(r[k]))
        except (KeyError, TypeError, ValueError):
            pass
    return out


def advisory(d, tag):
    """The P-GOV-1 verdict run_companion_perf.ps1 recorded for this run (None for runs made before it existed)."""
    try:
        return json.load(open(os.path.join(d, tag + '.gpu_advise.json'), encoding='utf-8-sig')).get('verdict')
    except (OSError, ValueError):
        return None


def main(dirs):
    print('| run | display Hz | engine fps | companion fps | build p90 | raster p50 / p90 / p99 ms '
          '| frames > 16.7 ms | CPU % | own GPU 3D % | adapter 3D % | VRAM MB | RSS MB start→end '
          '| Dart heap MB start→end | other >1 GB VRAM |')
    print('|---|---|---|---|---|---|---|---|---|---|---|---|---|---|')
    hidden = []
    for d in dirs:
        for jf in sorted(glob.glob(os.path.join(d, '*.json'))):
            if jf.endswith('.gpu_advise.json'):
                continue                      # the P-GOV-1 advisory record of a run, not a run
            tag = os.path.basename(jf)[:-5]
            j = json.load(open(jf, encoding='utf-8'))
            if not isinstance(j, dict) or 'overall' not in j:
                continue                      # another result file (e.g. brain_contention.json), not a perf run
            adv = advisory(d, tag)
            # WILL_DEGRADE_BRAIN is what a contention run measures on purpose; the row says so. The file tag stays
            # unchanged for the samples CSV.
            label = tag if adv in (None, 'GO') else f"{tag} [gpu advisory {adv}]"
            o = j['overall']
            rows = rows_of(os.path.join(d, tag + '.samples.csv'))
            ps = j['per_second'][3:]  # skip start-up
            eng = avg([p['frames'] for p in ps])
            comp = avg([p['companion_frames'] for p in ps])
            rss = j['rss']
            heap = j['heap']
            fv = col(rows, 'foreign_vram_gb')
            foreign = f"max {max(fv):.1f} GB ({sum(1 for v in fv if v > 0)}/{len(fv)})" if fv and max(fv) > 0 else 'none'
            print(f"| {label} | {j['display_hz']:.0f} | {eng:.1f} | {comp:.1f} | {o['build_p90']:.2f} | "
                  f"{o['raster_p50']:.2f} / {o['raster_p90']:.2f} / {o['raster_p99']:.2f} | "
                  f"{o['over_16ms']} ({100 * o['over_16ms'] / max(1, o['frames']):.2f} %) | "
                  f"{avg(col(rows, 'cpu_pct')):.1f} | {avg(col(rows, 'gpu3d_pct')):.1f} | "
                  f"{avg(col(rows, 'adapter3d_pct')):.1f} | {avg(col(rows, 'dedicated_mb')):.0f} | "
                  f"{rss[0]['rss'] / 2**20:.0f}→{rss[-1]['rss'] / 2**20:.0f} | "
                  + (f"{heap[0]['heap_used'] / 2**20:.1f}→{heap[-1]['heap_used'] / 2**20:.1f}" if heap else 'n/a')
                  + f" | {foreign} |")
            if tag.startswith('hidden'):
                hidden.append((tag, j, rows))
    for tag, j, rows in hidden:
        ps = j['per_second']
        print(f'\n{tag}: engine frames per second, by second:')
        print(' '.join(str(p['frames']) for p in ps))
        g = col(rows, 'gpu3d_pct')
        print('own GPU 3D % per sample (1 s, from second 4):')
        print(' '.join(f'{v:.1f}' for v in g))


if __name__ == '__main__':
    main(sys.argv[1:])
