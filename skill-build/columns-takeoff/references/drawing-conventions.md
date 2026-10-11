# COLUMNS & AXES — drawing conventions & method

Detail behind `SKILL.md`. Read this when a count looks wrong, when adapting the script to a new sheet, or
when deciding how to treat an ambiguous mark. Everything here was verified against the reference drawing
`2026-09-22-STR-MOTTAGAH.dxf` (sheet title `COLUMNS&AXES`).

## Table of contents
1. What is on the sheet
2. Column marks (the count source)
3. The level bubbles (colour ≠ type)
4. The COLUMN SCHEDULE
5. Plan vs schedule separation
6. Why the marks are invisible in a render
7. The reference tally (for regression)

---

## 1. What is on the sheet
A COLUMNS & AXES sheet holds the column layout: grid axes, every column drawn as a small cross-section
rectangle, a **mark** next to each column, the cores (shear walls) drawn as channel/box shapes, dimension
leaders that annotate each column's vertical extent, and — usually to one side — the **COLUMN SCHEDULE**
table giving each mark's section and reinforcement per construction stage.

## 2. Column marks (the count source)
- Marks are single-line `TEXT` (occasionally `MTEXT`), content `C`, `C1`, `C2` … and `CORE 1`, `CORE 2` …
- In the reference drawing they are on layer `0`, uniform height 225, ACI colour 7.
- Regexes used: marks `^C\s*\.?\s*(\d{0,3})$` (note `\d{0,3}` so bare `C` matches), cores `^CORE\s*\.?\s*(\d+)$`.
- **One label per column.** The per-mark tally is the column count. A mark appearing N times means N
  columns — *unless* a single element was tagged twice (watch cores; flag, don't assume).
- **`C` is its own mark, not a typo for `C1`.** The schedule lists them on separate rows with different
  sections (`C` = 300×500, 8T16; `C1` = 300×600, 10T16). Merging them corrupts both counts.

## 3. The level bubbles (colour ≠ type)
- Each **perimeter** column sits inside a circle of radius ≈ 610 ("bubble") with the mark text at its centre.
- **The bubble colour encodes the column's top level, not its type:**
  - red / ACI 11 → "From Foundations To Landing Slab"
  - yellow / ACI 2 → "From Foundations To Ramp Level"
  - green / ACI 3 → "From Foundations To Lower Basement Slab"
  - (top-row perimeter columns also carry a "To +1.70m" leader)
- **Interior** columns have no bubble — just the floating mark label.
- Useful cross-check: in the reference sheet there are exactly **40 bubbles = 9×`C` + 31×`C1`** (all
  perimeter). If your perimeter `C`+`C1` total doesn't equal the bubble count, something is off. But the
  labels are the source of truth; the bubble is just corroboration.

## 4. The COLUMN SCHEDULE
- A separate table, title `COLUMN SCHEDULE`. Mark column on the far left; one data column per stage:
  `FROM FOUNDATION TO UPPER BASEMENT CEILING`, `… TO 1ST CEILING`, `… TO 3RD CEILING`, `… TO 5TH CEILING`,
  `FROM 5TH CEILING TO ROOF OR TOP ROOF`, then `REMARKS`.
- Each cell holds `SIZE = W x H (mm)`, `VERTICAL = n T d`, `HORIZONTAL = T8-150`. Stages that don't exist
  for a mark show `----`.
- The section **shrinks going up** the building (e.g. C8: 550×1800 at base → 400×1700 at roof). The skill
  reports the **first (left-most, base) stage**; other stages are in the same row if the user needs them.
- Row geometry: the mark header sits at the **top** of its cell; `SIZE`/`VERTICAL` sit ~1000 units **below**
  it, and the next mark is ~1700 below. So match a row with an **asymmetric** window
  (`head_y-1450 < y < head_y+250`). A symmetric ±900 band silently drops the lower text (this bit C9/C10
  during development).

## 5. Plan vs schedule separation
Both the plan and the schedule contain `C1`..`Cn` texts. Counting over the whole modelspace double-counts
(every plan column **plus** one schedule header per mark). Isolate the two areas first. The script finds
them by title: the plan from the `COLUMNS&AXES` title (a box offset up/right of it), the schedule from the
`COLUMN SCHEDULE` title (a box down/right of it). Override with `--plan-bbox` / `--sched-bbox` if a sheet is
laid out differently. (In the reference sheet the split is simply x: plan at x ≲ −483000, schedule at
x ≳ −460000 — handy as a sanity check, but don't hard-code it for other sheets.)

## 6. Why the marks are invisible in a render
The mark text is ACI colour 7 = white. On a white plot background it renders white-on-white and disappears,
so a normal render shows empty bubbles and an unlabelled plan — misleading if you trust your eyes. The
extractor reads entity text directly, so this doesn't affect counts. For a human-checkable image, recolour
text to black before plotting (`e.rgb = (0,0,0)`); that is exactly what `--debug-render` does.

## 7. The reference tally (for regression)
`2026-09-22-STR-MOTTAGAH.dxf`, sheet `COLUMNS&AXES`:

| mark | count | base section | vertical |
|------|------:|--------------|----------|
| C  | 9  | 300×500  | 8 T 16  |
| C1 | 31 | 300×600  | 10 T 16 |
| C2 | 2  | 400×600  | 14 T 16 |
| C3 | 3  | 500×1300 | 22 T 22 |
| C4 | 2  | 600×750  | 18 T 22 |
| C5 | 2  | 400×1000 | 20 T 18 |
| C6 | 7  | 500×1200 | 18 T 22 |
| C7 | 2  | 500×1600 | 24 T 22 |
| C8 | 4  | 550×1800 | 30 T 22 |
| C9 | 2  | 500×1300 | 22 T 22 |
| C10| 1  | 500×1400 | 22 T 22 |
| **total columns** | **65** | | |

Cores: CORE 1 = 1, CORE 2 = 1, CORE 3 = 2 (CORE 3 appears twice — user confirmed these are two real cores,
so the tally is correct as counted).
