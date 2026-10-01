# Report C: Comparative performance on equivalent workloads

All configurations run on the same 138 holdout cases and are scored on the first repeat. They are composed from the recorded per-arm outputs by `compose.py`; the routing rules are in that file. End-to-end latency is the sum of the measured wall times of the stages a configuration invokes, which includes model loading as it happened in the run, agent builds, validation and fallback. Specialists are `needle_P1` and `granite_json_P1`; the Main Brain is `qwen3.5:9b`. The assignments used by the selective configurations were chosen on the development split and frozen before the holdout (`battery/assignment_by_kind_from_dev.json`, `battery/assignment_from_dev.json`).

## 1. Results

| Configuration | success | incorrect | safe fail | Brain share | calls / case | p50 / p95 ms |
|---|---|---|---|---|---|---|
| C0 deterministic only | 14 (fix1: 24) | 13 (fix1: 3) | 111 | 0 | 0 | 0 / 0 |
| C1 Needle alone | 47 | 39 | 52 | 0 | 0.88 | 671 / 955 |
| C2 Granite alone | 56 | 34 | 48 | 0 | 0.88 | 179 / 491 |
| C3 pair, selective by request kind (implementable) | 56 | 34 | 48 | 0 | 0.88 | 179 / 491 |
| C3o pair, selective by family (oracle; URI cannot know the family) | 59 | 39 | 40 | 0 | 0.88 | 267 / 790 |
| C4 pair, Needle then Granite on rejection | 59 | 51 | 28 | 0 | 1.17 | 680 / 1338 |
| C4b pair, Granite then Needle on rejection | 69 | 41 | 28 | 0 | 1.14 | 279 / 1124 |
| C5 Main Brain alone | **109** | 17 | 12 | 1.00 | 1.00 | 908 / 1794 |
| C6 URI hybrid: M36 gate, rules, Granite, Brain on rejection | 86 (fix1: 96) | 45 (35) | 7 | 0.32 | 1.04 | 273 / 1493 |
| C6o hybrid with family-oracle selection | 85 (95) | 50 (40) | 3 | 0.25 | 0.97 | 286 / 1619 |
| C6c hybrid with Needle as the Edge model | 82 (92) | 54 (44) | 2 | 0.33 | 1.04 | 703 / 2074 |
| C7 M36 gate and rules, then Brain (no Edge model) | 100 (fix1: 110) | 27 (17) | 11 | 0.80 | 0.80 | 743 / 1621 |

"fix1" is the post-holdout correction of the experimental deterministic rules (report E). It is shown beside the original, never instead of it.

## 2. Paired comparisons (one-sided 95% lower bound of the success difference, Wald on paired discordance)

| Comparison | wins / losses (cases) | difference | lower bound | Reading against the pre-registered rule |
|---|---|---|---|---|
| C6 hybrid vs C5 Brain | 6 / 29 | −16.7 pts | −23.3 | **fails non-inferiority** (needs > −2) |
| C6 hybrid (fix1) vs C5 | 6 / 19 | −9.4 | −15.2 | fails |
| C6c Needle hybrid vs C5 | 9 / 36 | −19.6 | −27.1 | fails |
| C7 rules then Brain vs C5 | 2 / 11 | −6.5 | −10.7 | fails |
| C7 (fix1) vs C5 | 2 / 1 | +0.7 | −1.3 | non-inferior. Brain share 80% (19.6 points avoided, threshold 20); p95 −9.6% (threshold −25%). **No material advantage**, and the fix came after the holdout |
| C4b pair vs C2 Granite alone | 13 / 0 | +9.4 | +5.3 | better completion, but incorrect 41 vs 34 and p95 +129% (threshold +10%): **regression** |
| C6c Needle hybrid vs C6b Granite hybrid | 14 / 18 | −2.9 | −9.6 | Needle as the Edge model is not non-inferior to Granite |

## 3. What the comparison shows

1. **No Edge-model configuration is worthwhile against the Main Brain alone.** Every hybrid with Needle or Granite loses 9 to 20 points of verified success and returns 2 to 3 times as many incorrect results. That outweighs its gains: Brain calls fall from 100% to 25–33% of turns and p50 latency from 908 to 273–703 ms.
2. **The pairing adds measurable completion over Granite alone (+13 cases, none lost), but no qualifying value.** It adds 7 more incorrect results and more than doubles p95 latency, because the second model runs only after the first is rejected, and that happens on 26–29% of turns (calls per case 1.14–1.17 against 0.88).
3. **Selective routing gives nothing that URI can implement.** By request kind, Granite won every kind on development, so C3 equals C2. By family it adds 3 cases, but that needs an oracle URI does not have.
4. **Calling both models on every turn was not tested.** Per the brief, a model is invoked only when the configuration's routing reaches it; calls per case stay at 0.88–1.17.
5. **The deterministic layer, not an Edge model, is the only thing that reduced Brain calls without losing success**, and only after the post-holdout rule fix (C7 fix1). It is experimental and not a URI component, and its advantage is below the material-advantage thresholds.
6. **Latency comparisons need the placement caveat.** On the same CPU placement, Granite JSON's p50 (745 ms) equals Needle's (734 ms). The idle-machine rerun (report B §5) reproduces the specialist latencies within 5%. The Main Brain idle rerun was cut off after 3 calls. Its holdout figures may include contention from another session; its warm p50 on an idle machine with a fixed prompt is 554–581 ms (cold-start script).

## 4. Limits

- n = 138, one repeat for composition; bounds are wide.
- The Brain is local `qwen3.5:9b`; no cloud Brain was used (no metered spend).
- The configurations are composed from recorded outputs, not run as one live process. The 7 live workflows in report D show the same routing behaviour on single turns.
- Selection and argument handling use the typed catalogue. Under the real URI schemas (R1), incorrect executions are higher (report B, interim 2 §3), so these comparisons are, if anything, favourable to Edge.
