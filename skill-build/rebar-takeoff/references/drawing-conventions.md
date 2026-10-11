# Drawing conventions — how these structural DXFs encode reinforcement

These are the entity/layer conventions the scripts depend on. If a new drawing set differs, this is the
first file to re-verify (a quick `ezdxf` probe of layers and entity types near a known callout is enough).

## Sheet layout

- One DXF holds **many plan drawings tiled in a grid** in modelspace. Rows differ by Y (~100000 units
  apart), columns by X. A typical set: for each floor level, an "ADDITIONAL TOP REINFORCEMENT PLAN FOR
  <level>", a "CONCRETE DIMENSION & ADDITIONAL BOTTOM REINFORCEMENT PLAN FOR <level>", and sometimes a
  "RAMPS REINFORCEMENT PLAN".
- **Titles** are `MTEXT`/`TEXT` on layer `A-ANNO-TEXT-25`, text containing `PLAN FOR` / `REINFORCEMENT
  PLAN`. The title sits at the **bottom** of its plan; the plan drawing is **above** it. `takeoff.py`'s
  `plan_bbox()` derives a plan's bounding box from its title plus the grid of neighbouring titles.

## Bars (the steel itself)

- Bar lines are `LWPOLYLINE`/`LINE` on layers whose name contains **`RFT`**:
  - `ST-RFT-TOP` — top-face reinforcement (drawn blue in the sample set)
  - `ST-RFT-BOT` — bottom-face reinforcement (drawn yellow)
- **Detect rebar by layer name (`RFT`), not by colour** — colour differs between top and bottom plans and
  can't be relied on. The count of RFT lines in a plan region equals the number of bar callouts (1:1).
- Map a callout's face letter to the layer: `-T` → `ST-RFT-TOP`, `-B` → `ST-RFT-BOT`. A "top
  reinforcement" plan still contains a few `-B` bars (and vice-versa), so always map by the callout, not
  by the plan.

## Callouts (diameter / spacing / face)

- `TEXT` (often on `ST-203-SLAB-TXT`) matching `^T(\d{1,2})-(\d{2,4})-([TB])(?:-ADD)?$`, e.g.
  `T16-200-T`, `T12-400-B`, `T16-250-B-add`.
  - group 1 = **diameter** mm, group 2 = **spacing** mm (centre-to-centre), group 3 = **T/B face**,
    optional `-add` = "additional".
- `T` denotes high-tensile steel; the number after is the diameter.
- **Text rotation encodes bar direction**: rotation 0 → the bar runs **horizontally** (distribution is
  vertical); rotation 90 → the bar runs **vertically** (distribution is horizontal).

## Bar length

- A separate `TEXT` `L=####` sits next to each callout (~a few hundred units away). Match it 1-to-1 to the
  nearest callout. This is the cut length of the bar in mm.

## Distribution width (the number that drives the count)

- `DIMENSION` entities, often on `ST-206-SLAB-DIM`, drawn **perpendicular to the bar**. The measured value
  (`get_measurement()`, or the distance between defpoint2/defpoint3) is the width over which the parallel
  bars are distributed.
- Measured values carry small drawing imprecision (e.g. 5500.9); round to the nearest 100.
- Ignore near-zero dimensions and absurdly large ones — but keep the cap generous (≤ ~60000) because
  **edge bars** legitimately use the full-width overall dimension (~50000+).

## Crossing markers (orange circles)

- Small `CIRCLE` entities, **ACI colour 30 (orange), radius ≈ 75**, placed exactly where a bar crosses
  its own distribution dimension. Their count equals the number of slab callouts.
- Purpose: when one dimension line visually crosses a **group** of parallel bars, the circle marks which
  specific bar that measurement belongs to. Authoritative when readable.
- **Caveat:** they are not always usable. In some plans the circles are absent from the readable
  modelspace, or stored at **mirrored/orphaned coordinates** (e.g. a cluster at +X with no geometry, while
  the plan is at −X) with no recoverable 1-to-1 mapping. The bar-line method (see `method.md`) is the
  fallback that does not need them.

## Stairs

- A stairwell carries a **`with stair`** text label, a nearby `SLAB=###mm` note, and a run of closely
  spaced parallel step lines. The stair rebar callouts are `T##-200-T` / `T##-200-B` pairs clustered in a
  narrow strip **without** an `L=` label. These are excluded from the slab takeoff.

## Other text seen in the plans (not bars)

- `SLAB=220mm` (slab thickness), a lone `320` (slab-thickness marker), `CAMBER`, beam tags like
  `B2(200X700)`, level notes. None of these match the callout regex, so they are ignored automatically.
