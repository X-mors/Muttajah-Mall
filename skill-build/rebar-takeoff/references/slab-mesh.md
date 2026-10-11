# Main slab mesh takeoff — الفرش والغطاء (bottom + top mesh)

This is the SECOND mode of the skill, distinct from the additional-reinforcement takeoff. It quantifies
the **continuous two-way slab mesh**: the bottom layer (فرش / farsh) and the top layer (غطاء / ghitaa).
Run it with `scripts/slab_mesh.py "<CEILING NAME>"`.

## Never confuse it with the additional reinforcement

Two independent discriminators (either one is enough):
- **Notation:** main mesh notes read `TOP=T##@### C/C` and `BOT.=T##@### C/C` (an `=`, an `@`, and
  `C/C`). Additional bars read `T##-###-T|B` (hyphens, `-T`/`-B`). 
- **A small grid/mesh symbol** sits next to the main-mesh note (layer `st_cir_mesh`), whereas additional
  bars carry the orange crossing-circle.

The mesh notes are stored as **block ATTRIBUTES** (`insert.attribs`, tag `LINE_1`, block `00_block1010`,
layer `S-TEXT-1`), NOT as plain TEXT/MTEXT — a normal text query misses them. There is normally **one
`TOP=` + one `BOT.=` per plan**: a single TYPICAL spec for the whole slab, not per-panel.

## The method (area / supply method — the user's convention)

```
Net area  A (m²) = gross slab area − openings − stair voids
Steel length per m² for a two-way mesh at spacing s (mm), per layer = 2000 / s   (= 1000/s per direction)
Total length (per Ø) = A × Σ(2000/s)   over the TOP and BOT meshes of that diameter
Multiply by a lap-splice factor (real overlap, per Ø) → No. of 12 m stock bars = (total_length × factor) / 12
```

**Lap splices, not a flat +10%.** A mesh bar runs the full slab side (~45–54 m), so it is spliced from
several 12 m stock bars with an overlap `lap = lap_mult × Ø` (default **60×Ø** tension, ECP 203) with a
**1 m practical minimum** (the engineer's floor). The old blanket +10% is replaced by a real, per-Ø
factor computed from the slab dimensions and the lap — `slab_mesh.lap_factor(gx, gy, Ø, lap_mult, reuse)`:
- **Optimized (default, `reuse=True`)** — offcut of each run reused to start the next parallel run, so
  only the laps count: factor = 12/(12 − lap). This is the engineer's chosen method.
- **Conservative (`--conservative`)** — each run buys whole 12 m bars, the last bar's offcut is waste.
- With run length ≤ 12 m (small slab) the factor → 1 automatically (no splice needed).

Tune with `--lap <mult>` (60 tension / 40 compression). The lap portion is intentional steel, not waste;
a separate purchase margin (5–10 %) is the engineer's to add at ordering.

Worked check (Lower Basement, `TOP=BOT=T10@200`, lap 60×Ø but floored at 1 m): gross 53.87×44.96 = 2422 m²,
− openings ~212 m² = net **2210 m²** → 20 m/m² → 44,197 m → ×**1.091** (lap factor) = 48,211 m → /12 ≈
**4,018 Ø10 bars**.

Output is **counts + lengths per diameter** (no weight, per the user), procurement-style.

## Where each input comes from

- **Gross slab dimensions** = the **bounding box of the `ST-RFT-*` rebar lines** in the plan (matches the
  measured slab — Lower Basement gave 53.87 × 44.96 m vs the engineer's 53.9 × 45). Do NOT use the `SLAB`
  layer (small panel markers, ~7× too small) or a single overall DIMENSION (only the width has one; the
  length is a sum of grid bays). Override with `--gx <width_m> --gy <length_m>` or `--area <m²>` when
  needed.
- **Mesh spec** (Ø, spacing, TOP/BOT) = the `TOP=`/`BOT.=` block attributes inside the plan box.
- **Openings = X-crossed boxes on layer `S - dot`** (auto-detected). Each opening is a rectangle with an
  X (two crossing diagonals); all such symbols live on layer `S - dot`. `detect_openings()` collects the
  `S - dot` diagonal segments (both |Δx| and |Δy| > 400 mm), then treats **each opening as one X = a pair
  of crossing diagonals of opposite slope sign** (`_seg_cross` returns the interior intersection point,
  0.05 ≤ t,u ≤ 0.95). The opening's box is the bounding box of the pair's four endpoints; it **dedupes by
  centre only when within 0.8 m** (so the same X detected via several diagonal pairs collapses to one).
  This deliberately **does NOT merge adjacent openings** — an earlier connected-components version fused
  two X-boxes ~2 m apart into one oversized rectangle (over-deducting). The crossing method keeps them
  separate: e.g. the OP3 cluster splits correctly into a 6.0 m² and a 5.3 m² void. Lower Basement result:
  a 95 m² and a 71 m² edge void plus ~11 smaller ones → **13 openings, ~212 m² total** (vs the useless
  0.7 m² from the `S-OPENING` layer, which is just tiny symbols — do NOT use it). Openings are ~9% of this
  slab, so getting them right matters.
- **Stairs are folded INTO the openings** here (their voids are `S - dot` X-boxes too, and the engineer
  treats the stair as a deducted opening with its own SEPARATE reinforcement takeoff done elsewhere) — so
  do NOT also deduct `A-STAIR` or you double-count.
- Override the auto opening total with `--openings <m²>` when the engineer wants to set it by hand. If a
  drawing hides some openings the detector misses, confirm the rendered set with the engineer (opening
  symbols are not fully standardised — the same caveat every takeoff tool hits).

## Usage

```
python slab_mesh.py "LOWER BASEMENT CEILING"                      # auto dims + spec + stairs
python slab_mesh.py "LOWER BASEMENT CEILING" --openings 24        # deduct 24 m² of openings the engineer identified
python slab_mesh.py "GROUND CEILING" --gx 53.9 --gy 45.0          # override the auto dimensions
```

Possible future refinement: use **Shapely** to compute the net area as (slab polygon − opening polygons)
for irregular slabs, instead of gross-rectangle minus areas.
