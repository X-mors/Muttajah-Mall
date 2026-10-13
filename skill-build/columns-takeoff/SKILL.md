---
name: columns-takeoff
description: >-
  Automated column COUNT takeoff from an AutoCAD structural COLUMNS & AXES plan (.dwg/.dxf).
  Reads the per-column mark labels (C, C1..Cn) and the cores (CORE 1..n) off the layout, counts how
  many columns of each mark, cross-references the COLUMN SCHEDULE for each mark's section size and
  vertical reinforcement, and outputs a clean formatted Excel table (mark, count, section, rebar).
  Use this whenever the user has a columns/axes layout or column-schedule drawing and wants to tally
  or count the columns — عدّ الأعمدة / حصر الأعمدة / جدول بأرقام الأعمدة (C1 C2 C3 …) بعددهم /
  كام عمود من كل نوع / columns schedule quantities — or points at a COLUMNS & AXES sheet and asks for
  an organized table of column marks by count, even without saying 'takeoff'. Specifically about
  COUNTING/quantifying columns from a plan: do NOT use it for rebar/slab takeoff (that is rebar-takeoff),
  wall/block takeoff, concrete volume, or structural design of columns.
compatibility: Requires Python 3 with ezdxf and openpyxl (matplotlib only for the optional --debug-render check). Convert DWG→DXF first with the ODA File Converter.
---

# Column takeoff from a COLUMNS & AXES plan

This skill counts the columns on a structural column-layout sheet and produces a tidy Excel table of
**mark → count → section → vertical rebar**. It was built against a real consultant drawing and encodes
that drawing's conventions. **Prefer running `scripts/columns_takeoff.py` over counting by hand** — the
labels are easy to miscount by eye (many are white-on-white, see the gotchas) and the script also joins
the counts to the schedule automatically.

> ⚠️ **نطاق العمل:** هذه المهارة مُعايَرة على **أعراف لوحات هذا المكتب (مشروع Muttajah Mall)** — أسماء
> الطبقات، صيغة الماركات `C/C1..Cn`، وتخطيط جدول الأعمدة. **قد لا تعمل كما هي على مشروع إنشائي آخر بأعراف
> مختلفة** دون ضبط الطبقات/الصِّيَغ.

## The core idea

On a "COLUMNS & AXES" sheet every column carries a **mark** — a short text like `C`, `C1`, `C2` … — and
each core (shear wall) is marked `CORE 1`, `CORE 2` … The count of each mark **is** the number of
columns of that type. So the whole job is: read every mark label inside the plan area, tally by mark,
and look up each mark's section/rebar in the **COLUMN SCHEDULE** table that sits elsewhere on the same
sheet. The script does exactly this.

```
number of columns of mark X = number of "X" mark labels inside the plan area
```

## Usage

```
python scripts/columns_takeoff.py --dxf "<file.dxf>"
python scripts/columns_takeoff.py --dxf "<file.dxf>" --out "<out.xlsx>"
python scripts/columns_takeoff.py --dxf "<file.dxf>" --debug-render   # + a review PNG
```

It prints the per-mark counts and writes `output/حصر الأعمدة - COLUMNS & AXES.xlsx`: a right-to-left
table with mark, count, section (mm) and vertical reinforcement, a columns total, a separate **cores**
block, and a note. `--debug-render` also writes a review PNG (see below).

The plan area and the schedule area are found automatically from their titles (`COLUMNS&AXES` and
`COLUMN SCHEDULE`). If a sheet is laid out unusually and detection misses, pass the regions explicitly
with `--plan-bbox XMIN XMAX YMIN YMAX` and/or `--sched-bbox …`.

## How to work with the user

1. **Confirm the file and the sheet.** Which `.dxf`, and is the target the COLUMNS & AXES layout? If it's
   a `.dwg`, convert to `.dxf` first (ODA File Converter; use a plain-ASCII temp name — the batch filter
   fails on Arabic names).
2. **Run the script** and relay the per-mark counts and the total. Reading the big DXF takes ~1 minute —
   run it once, not repeatedly.
3. **Offer a visual check.** Run with `--debug-render` and hand over the review PNG so the user can eyeball
   that every column got exactly one mark. This matters because the marks are invisible in a normal render
   (see gotchas) — the review PNG forces them black so they can be read.
4. **Surface the judgement calls, don't bury them.** In particular: is `C` really meant as its own mark
   (it is, in the reference drawing), and is a mark that appears twice (e.g. `CORE 3`) two elements or one
   element tagged twice? Ask rather than guess.

## Conventions the script relies on (quick reference)

Full detail and the reasoning in `references/drawing-conventions.md`. The essentials:

- **Mark labels** are `TEXT` matching `^C\d{0,3}$` (so `C` on its own **and** `C1`..`Cn`) and
  `^CORE\s*\d+$`, drawn at a uniform height on layer `0`.
- **`C` (bare) is a distinct, separate mark** — a small column — **not** shorthand for `C1`. The COLUMN
  SCHEDULE lists `C` and `C1` on separate rows with different sections. **Never merge them.**
- **Perimeter columns sit inside a colour-coded bubble** (a circle of radius ≈ 610). The **colour encodes
  the column's top level, not its type**: e.g. red = "To Landing Slab", yellow = "To Ramp Level",
  green = "To Lower Basement Slab". Counting bubbles (perimeter only) is a useful cross-check on the
  perimeter `C`+`C1` total, but the labels are the source of truth, not the bubbles.
- **Interior columns** are floating mark labels with **no** bubble.
- **The COLUMN SCHEDULE** is a separate table on the sheet. Its mark column is on its far left; each mark's
  section (`SIZE = W x H`) and `VERTICAL = n T d` sit **below** the mark, roughly one row-height down, with
  one column per construction stage (foundation→upper-basement, →1st, →3rd, →5th, →roof). The script takes
  the **left-most (first-stage)** section, which is the largest/base size.

## Important gotchas (learned the hard way)

- **Mark labels are ACI colour 7 (white).** On a white render background they are **invisible** — a normal
  plot shows empty bubbles and a bare plan, which is why counting by eye fails and why an early look at the
  drawing is misleading. The script reads them from the entity text regardless; `--debug-render` forces the
  text black so a human can verify. If you render for any reason, recolour text to black first
  (`e.rgb = (0,0,0)`).
- **Separate the plan from the schedule before counting.** Both contain `C1`..`Cn` texts; if you count over
  the whole modelspace you double-count (plan columns + one schedule header per mark). The script isolates
  the plan area and the schedule area by their titles.
- **Schedule row window is asymmetric.** The section/rebar text sits ~1000 units *below* its mark header and
  the next mark is ~1700 below, so match a mark's row with a window like `head_y-1450 < y < head_y+250`, not
  a symmetric band — a symmetric ±900 silently drops the lower rows (seen with C9/C10).
- **Reading the DXF is slow (~60–90 s) and memory-heavy.** Read the file once per run; don't launch several
  parsing passes in parallel, and prefer the printed summary over re-rendering.
- **A mark that appears N times = N columns**, *unless* it's a single element tagged twice. Watch cores
  especially; flag duplicates to the user instead of assuming.
- **Section sizes are per stage** and shrink up the building. The Excel reports the first (base) stage; if
  the user needs upper-stage sizes, all stages are in the schedule — read the other columns of that row.
