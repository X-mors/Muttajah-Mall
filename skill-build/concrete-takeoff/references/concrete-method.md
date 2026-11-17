# How the column schedule & ceiling plans are read (concrete takeoff)

Exact encoding on this office's drawings, so the extraction never has to be re-derived.

## COLUMN SCHEDULE — per-stage sections (layer `ST-TEXT`)

- The schedule has **5 construction stages**, each its own X-band. Stage HEADERS (one per stage, X ascending
  = stage 1→5): `FROM FOUNDATION TO UPPER BASEMENT CEILING`, `FROM UPPER BASEMENT CEILING TO 1ST CEILING`,
  `FROM 1ST CEILING TO 3RD CEILING`, `FROM 3RD CEILING TO 5TH CEILING`, `FROM 5TH CEILING TO ROOF OR TOP ROOF`.
- Each mark's row (marks column at far left, `^C\s*\.?\s*(\d{0,3})$`) holds up to 5 `SIZE = W x H` cells —
  one per stage band. Assign each `SIZE` to the nearest stage-header X. A missing cell / `----` = the column
  **terminated** (not present in that stage → zero volume there).
- The section **shrinks going up** (e.g. C3: 500×1300 → 450×1300 → 400×1200 → 400×1100 → 400×1000).
- `VERTICAL = n T d` and `HORIZONTAL = T d - s` are also per stage (kept for an optional rebar tally later).
- C and C1 exist in **stage 1 only** (basement columns); C2…C10 run all 5 stages.
- `collect()` splits plan (x < −480000) from schedule (−460000 < x < −330000, 440000 < y < 490000).

## Ceiling plans — the three new reads

Each ceiling is a title tile on layer `A-ANNO-TEXT-25`: `ADDITIONAL TOP REINFORCEMENT PLAN FOR <NAME>`
(LOWER/UPPER BASEMENT, GROUND, TYPICAL, ROOF). Associate any entity to a ceiling by nearest title Y.

1. **Slab thickness** — plain text `SLAB=220mm` on layer `ST-203-SLAB-TXT`. Take the mode per ceiling.
   (All ceilings = 220 mm here, but READ it — it may change.)
2. **Drop panel** — a standalone number `320` (also `350`, `400`) on layer `S-TEXT`, inside a diamond, at
   the column head. ~40–49 per ceiling. A column deducts the drop thickness (0.32) instead of the slab
   (0.22) when a drop number sits over it. Associate by position (column ↔ nearest drop number).
3. **Ceiling S.S.L levels** — NOT plain text; they live in the block `XREF-…-A-LVL_FFL-SSL` as the
   attribute **`FLOOR-LEVEL-FFL`** (value like `-3.30m`, `+1.10m`, `+5.70m`). Filter noise (|level| > 12 m
   is a tank/retaining/absolute survey value, not a ceiling). **Several floors carry more than one level**
   (stepped slab: e.g. Upper Basement ceiling has both −0.10 and +1.10), so a column's top level is the
   NEAREST S.S.L, not a single per-floor number.

Levels found so far: Lower Basement ceiling −3.30 · Upper Basement ceiling −0.10 / +1.10 · Ground ceiling
+5.70 (+ stepped values). **Typical/Roof levels are on a sheet the engineer will send.**

## Volume

`V(column) = (W/1000) × (H/1000) × net_height`, `net_height = storey_height − top_deduction`,
`storey_height = upper ceiling S.S.L − lower ceiling S.S.L` (per column, because levels step within a floor).
`top_deduction` = **قاع العنصر الذي يعلو العمود** (engineer's rule: count the column up to the soffit of
whatever sits over it — slab OR beam):
- slab only → `0.22` (SLAB) or `0.32` (drop panel).
- **a normal (downstand) beam over the column → the FULL beam depth `D`** (the column stops at the beam
  soffit, which is `D − t_slab` lower than the slab soffit). So `net_height = storey_height − D_beam`.
- an **inverted** beam over the column → back to the slab soffit (`0.22`): the beam projects UP, not down.

Totals: per floor, grand total, and grand × 1.05 (concrete waste ≈ 5 %, unlike steel which is cut-exact).
Cores (shear walls) are a separate block (section area from the drawn polygon, not W×H).

## BEAMS — ceiling-beam concrete (submodule, planned)

**Beam sections are NOT in a schedule** — the W×D section is written in **each beam's own label on the
plan** as `MARK(W X D)` (e.g. `B2(300X600)`). The *reinforcement* table ("Beams Reinforcement Table",
layer `00-EG-Text`: B1–B5 / CA1–CA4, Top/Bottom RFT + `5Ø8` stirrups) groups **reinforcement** by mark
only — it carries no dimensions. **The same mark appears with several sections** (B2 = 300×600, 200×700,
250×700, 250×600, 300×500, 300×700…), so the section is read **per label from the plan**, and the mark is
used only to look up reinforcement later.

Label encoding (423 labels):
- Layers `ST-203-SLAB-TXT` (ceiling plans) + `BEAMS` (ramp / basement zone). **`S -Beams` = foundation
  tie beams `S(WxD)` — a different element, excluded (handled by `raft_footings.py`).**
- `MARK(W X D)` → width×depth (mm). Variable depth `MARK(W X D1/D2)` (e.g. `B5(300X600/1350)`,
  `B3(300X400/850)`) = two depths (haunch/step); the two bare numbers are drawn on `BEAMS` at each depth.
- `INVERTED` / `INV.` prefix-or-suffix = upstand beam (projects above the slab). 48 labels.
- Marks seen on plan: B1 B2 B3 B4 B5 CA2 CA3 CA4 (CA1 = reinforcement table only, no plan label).

**Concrete rule (engineer):** a beam is cast monolithic with the slab, overlapping it by the slab
thickness, so the **beam takeoff counts only the stem BELOW the slab** — the part within the slab
thickness already belongs to the slab area, and counting it again would double-count.

```
exposed stem depth = D − t_slab          (e.g. slab 200, beam 300×700 → 500 mm exposed)
V(beam) = (W/1000) × ((D − t_slab)/1000) × L        (م³)      t_slab = SLAB=220mm (read per ceiling)
```

- **L (length)** = measured from the beam's drawn centerline/polyline on `BEAMS` (LINE/LWPOLYLINE),
  associated to its label by position. This is the one part still to implement/verify.
- **Variable depth:** use `((D1+D2)/2 − t_slab)`, or split into two runs if the break point is dimensioned.
- **Inverted:** same added volume `W × (D − t_slab) × L` (it just projects up instead of down).
- Per-ceiling totals + grand total × 1.05 (5 % concrete waste), same as columns.

Status: **documented, not yet coded.** Build `beams_takeoff.py` when the user requests a ceiling takeoff —
label+section parsing is proven here; label↔geometry length association is the open task.

## Serial numbering (review drawing)

Columns of the requested floor are sorted top→bottom then left→right and numbered 1..N; a green circle +
that number is drawn on each on layer `CHECK-CONCRETE-COLUMNS`, matching the Excel rows one-to-one.
