# Lap / splice length (طول التزويد / وصلة التراكب) — ECP 203

Laps only matter for a required piece **longer than one 12 m stock bar** (long edge / continuity bars).
A normal slab additional-reinforcement plan usually has none; the main mesh already folds laps into its
+10 %. When a long bar does appear, the optimizer pre-splits it (STEP 1 of the method) using a lap length.

## The rule

The lap (overlap) length equals the development/bond length `Ld`:

| Condition | Lap length | Notes |
|---|---|---|
| Tension (شد) | **≈ 60 × Ø** | conservative blanket default |
| Compression (ضغط) | ≈ 40 × Ø | only if the bar is confirmed compression |
| Practical band | 40 – 65 × Ø | varies with concrete grade `Fcu` and bar type |
| Practical minimum | **≥ 1000 mm (1 m)** | the engineer's floor — overrides the ECP 300 mm code minimum |
| **Ø > 32 mm** | **no lap splice** | must be welded / mechanical — the tool flags it |

Default multiplier per diameter (tension, 60 × Ø):

| Ø (mm) | 10 | 12 | 16 | 20 | 25 | 32 |
|---|---|---|---|---|---|---|
| lap (mm) | 600 | 720 | 960 | 1200 | 1500 | 1920 |

Code conditions the length alone does not capture (design-side, not the takeoff's job): laps must be
**staggered**, no more than 50 % of a section's bar area spliced at one location, and adjacent splice
centres ≥ 1.3 · Ld apart.

## How the optimizer uses it

For a run of length `L > STOCK` (= 12000 mm) with lap `p`:

```
m       = ceil((L − p) / (STOCK − p))     # number of 12 m bars in the run
splices = m − 1
remainder r = L − (m − 1)·(STOCK − p)     # < STOCK, pushed back into the piece pool
```

Each run consumes `m − 1` whole 12 m bars (their lap ends overlap, so no reusable offcut) plus one short
remainder that the normal packer nests with everything else. Total steel = `L + splices·p` — the extra is
exactly the intentional lap steel at each joint, not waste. Example: an `L = 53335 mm` Ø12 bar at 40×Ø
(lap 480) → `m = 5`, 4 splices, remainder 7255 mm; steel = 4·12000 + 7255 = 55255 = 53335 + 4·480. ✓

## Setting it

- Default: `lap_mult = 60` (tension), with a **1 m minimum** (`LAP_MIN = 1000`). Override the multiplier
  on the CLI with `--lap 40` (compression) or another value.
- Per-diameter overrides: pass `lap_by_dia = {12: 1000, 16: 1000, ...}` to `optimize()` (values below 1 m
  are raised to the 1 m floor).
- The **acceptable cutting-waste target is < 5 %** (ideally 2–3 %). The separate field purchase allowance
  of 5–10 % (for laps, bending elongation, execution error) is added by the engineer at ordering, not by
  this cutting KPI.
