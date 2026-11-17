# How a ceiling's concrete is read & computed (slab + beams + drops)

Exact encoding on this office's drawings (Muttajah Mall, drawing 2026-11-08), so the extraction never has
to be re-derived. Companion to the column method in `skill-build/concrete-takeoff/references/concrete-method.md`.

## The volume (no double-count)

```
V(ceiling) = V(slab) + V(beams) + V(drops)                                   (م³)

V(slab)  = (slab_area − openings) × t_slab
V(beam)  = (W/1000) × ((D − t_slab)/1000) × L        per beam, below-slab stem only
V(drop)  = drop_area × (t_drop − t_slab)             extra thickening over the slab
```

`t_slab` = `SLAB=###mm` read per ceiling (0.22 here). The beam's **(D − t_slab)** is the stem hanging below
the slab soffit; the part inside the slab thickness already lives in `V(slab)`, so counting the full D would
double-count. Totals: per ceiling + grand total × 1.05 (concrete waste ≈ 5 %).

## BEAMS — section per label (layers `BEAMS`, `ST-203-SLAB-TXT`)

- Section is in each beam's **own plan label**: `MARK(W X D)` → width × depth (mm), e.g. `B2(300X600)`.
  There is **no dimensions schedule**; the "Beams Reinforcement Table" (layer `00-EG-Text`) holds
  reinforcement only. **The same mark carries several sections**, so read W×D per label, not per mark.
- Variable depth `MARK(W X D1/D2)` (e.g. `B5(300X600/1350)`, `B3(300X400/850)`) — two depths (haunch/step);
  the two bare numbers are drawn on `BEAMS` at each depth location. Use `((D1+D2)/2 − t_slab)` or split.
- `INVERTED` / `INV.` (prefix or suffix) = upstand beam (projects above the slab). Same added volume
  `W×(D−t_slab)×L`; it only matters to the column below (which then stops at the slab soffit, not the beam).
- **Exclude `S -Beams` (`S(WxD)`)** — those are foundation tie beams (handled by `raft_footings.py`).
- Marks on plan: B1 B2 B3 B4 B5 CA2 CA3 CA4. 423 beam labels total in the drawing (all ceilings stacked
  in Y bands ≈ 380k / 480k / 580k / 680k / 780k / 880k / 980k).
- **Length L**: measured from the beam's drawn centerline/polyline on `BEAMS` (LINE/LWPOLYLINE), associated
  to each label by nearest position. This is the open implementation task (parsing the section is proven).

### Sections seen per mark (from plan labels, mm)
| Mark | Sections (W×D) |
|---|---|
| B1 | 120×600 |
| B2 | 300×600, 200×700, 250×700, 250×600, 300×500, 300×700 |
| B3 | 300×600, 250×600, 250×700, 300×400/850, 300×700 |
| B4 | 300×800, 300×600, 200×700, 250×1400, 300×700 |
| B5 | 300×600/1350 |
| CA2 | 300×600, 300×500, 300×700 |
| CA3 | 300×1400 |
| CA4 | 300×900 |

Width 120–300 mm, depth 400–1400 mm (+ variable). 48 INVERTED labels.

## SLAB — area × thickness

- **Thickness**: text `SLAB=###mm` on layer `ST-203-SLAB-TXT` (take the mode per ceiling; 220 mm here —
  but READ it, it can change per zone/ceiling). Same read as the column skill's `detect_slab()`.
- **Area**: from the slab outline / panel polygons on the ceiling plan, minus openings/voids (openings on
  the `S - dot` layer per the office convention). Stepped slabs can carry more than one S.S.L — area is by
  the drawn boundary regardless of level; the level only affects beam/column heights, not slab volume.

## DROP PANELS — the extra over the slab

- A standalone number `320` (also `350`/`400`) on layer `S-TEXT` inside a diamond at a column head
  (same source as the column skill's `count_drops()`). The drop adds `drop_area × (t_drop − t_slab)` of
  concrete above the slab plane. If drop areas aren't dimensioned, use the diamond polygon's area.

## Serial numbering (review drawing)

Beams (and slab zones) of the requested ceiling are numbered 1..N (top→bottom, left→right); a circle + that
number is drawn on each on a `CHECK-CONCRETE-CEILING` layer, matching the Excel rows one-to-one — so the
engineer verifies any element by eye against its circle, exactly like the columns review.
