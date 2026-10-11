---
name: concrete-takeoff
description: >-
  Column concrete-VOLUME takeoff (حصر خرسانة الأعمدة) from an AutoCAD structural COLUMNS & AXES plan +
  COLUMN SCHEDULE (.dwg/.dxf). Builds on the columns-takeoff skill: reads each column's position & count
  and its section W×H for each of the 5 schedule stages (the section shrinks going up), then computes
  every column's concrete volume = length × width × net height (m³). Net height = the ceiling-to-ceiling
  storey height minus the top slab (SLAB=220mm) or the drop panel (320mm) where one sits over the column;
  S.S.L ceiling levels, SLAB thickness and the drop-panel number are read from the ceiling plans. Outputs
  a per-column Excel (serial, mark, section, height, volume + total) and a review drawing with a numbered
  circle on every column matching the Excel rows. Use for حصر خرسانة الأعمدة / كمية أو حجم خرسانة الأعمدة
  (م³) / concrete volume of columns per floor. Do NOT use it to COUNT columns (that is columns-takeoff),
  for slab/ceiling concrete (a later submodule), or for rebar.
compatibility: Requires Python 3 with ezdxf and openpyxl. DWG⇄DXF conversion needs the ODA File Converter.
---

# حصر خرسانة الأعمدة — concrete-takeoff (COLUMNS mode)

Computes **column concrete volume** from the structural drawing. It is the volume sibling of the
**columns-takeoff** skill (which only counts columns): it reuses that skill's reading of the
COLUMNS & AXES plan and the COLUMN SCHEDULE, and adds per-stage sections + storey heights → m³.

**Prefer running `scripts/concrete_columns_takeoff.py` over re-deriving the geometry** — the schedule
reading is subtle and already encoded.

## The method

For a floor (= one of the schedule's 5 stages), each column's concrete:

```
volume = length × width × net_height           (م³)
net_height = storey_height(ceiling→ceiling) − top deduction
top deduction = 0.22 m (slab)   OR   0.32 m (drop panel, where one sits over that column)
```

- **length × width** = the column's section **for that stage**, read from the COLUMN SCHEDULE. The
  section SHRINKS going up, so each stage has its own W×H; `----` means the column terminated (not in
  that stage). `parse_schedule_stages()` returns the 5-stage section list per mark.
- **storey_height** follows the engineer's rule: from the ceiling of the floor below to that floor's
  ceiling (سقف↔سقف). **Levels can differ column-to-column within one floor** (stepped slab), so each
  column takes the nearest S.S.L to it — not one height per floor.
- **Cores** (CORE1/2/3, shear walls) are NOT W×H rectangles — handled separately, excluded from the
  column table.

## What the drawing gives (auto-extracted) — `references/concrete-method.md` for the exact encoding

- **Per-stage sections**: COLUMN SCHEDULE, 5 stage columns on layer `ST-TEXT` (`SIZE = W x H`).
  Stage headers: `FROM FOUNDATION TO UPPER BASEMENT CEILING` / `…TO 1ST / 3RD / 5TH CEILING` / `…TO ROOF`.
- **Slab thickness**: text `SLAB=220mm` on layer `ST-203-SLAB-TXT` (per ceiling plan). → `detect_slab()`.
- **Drop panel**: a standalone number `320` (also `350`/`400`) on layer `S-TEXT` inside a diamond at the
  column. ~40–49 per ceiling. → `count_drops()` (per-column association: a column deducts 0.32 if a drop
  number sits over it).
- **Ceiling levels**: block `XREF-…-A-LVL_FFL-SSL`, attribute `FLOOR-LEVEL-FFL` holds the value
  (e.g. −3.30, +1.10, +5.70). Several floors have MORE THAN ONE level (stepped slab). → `detect_levels()`.

## Output (the deliverable)

1. **Review drawing** (`… - review.dwg`): a green circle + a serial number on **every column of the
   requested floor**, numbered 1..N to match the Excel.
2. **Excel** (`… - <stage>.xlsx`, RTL): one row per column — `رقم العمود | الماركة | الطول | العرض |
   الارتفاع | الحجم (م³) | ملاحظة` — then the total and total + waste (5 %). Each volume = L×W×height, so
   the engineer can verify any column by eye against its circle.

## Usage

```
python concrete_columns_takeoff.py --debug                       # مقاطع المراحل + استخراج آلي (مناسيب/بلاطة/هوابط)
python concrete_columns_takeoff.py --stage 2 --height 4.60 --dwg  # حصر أعمدة المرحلة 2 (دور)، لوحة + إكسل
```

`--stage N` picks the floor (1..5 of the schedule). `--height` is the storey height (temporary single
value until per-column S.S.L levels are wired). `--drop-serials 3,7,11` marks the columns that have a
drop panel (deduct 0.32 instead of 0.22). `--mode gross` keeps the full ceiling-to-ceiling height.

## How to work with the user

1. Confirm which **floor/ceiling** to take off (maps to a schedule stage).
2. Run; relay per-column volumes + the floor total.
3. Hand over the **review drawing** so the serial-numbered circles can be checked against the Excel.
4. Heights are the main input: read the S.S.L levels per column (stepped floors differ), confirm the
   drop-panel columns, then compute. Report net vs any waste separately.

## Status / pending

Per-stage section reading, column numbering, the review drawing and the per-column Excel all work.
**Pending:** the repeated-floor / roof S.S.L levels (the engineer is sending a sheet with them) to finish
the storey heights, and wiring the per-column level + drop-panel association from `detect_levels()` /
`count_drops()`. Reference drawing for this project: `drawings/2026-09-27-STR-MOTTAGAH.dxf` in the repo.
