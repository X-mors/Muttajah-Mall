---
name: rebar-cutting
description: >-
  1-D rebar cutting optimization (تفريد الحديد). Takes a per-diameter piece list — (cut length, count),
  e.g. from rebar-takeoff — and cuts it from standard 12 m stock bars the way a foreman does: largest
  size first, as many pieces per bar as fit, and each bar's leftover carried forward to cover the exact
  smaller size so it is not cut again (e.g. 4.5+4.5 leaves 3 m → used for the 3 m demand). Splices bars
  over 12 m by a code lap (1 m minimum). Outputs an Excel جدول تفريد, size by size: pieces,
  pieces-per-bar, bars needed, leftovers reused, and remainder — plus stock bars, waste %, and weight.
  Use when the user has a rebar quantity / piece list and wants a cutting schedule / تفريد الحديد /
  عدد الأسياخ / المتبقّي / كم قطعة من كل مقاس. Composes after rebar-takeoff (reads its pieces.json). Do
  NOT use it to COUNT bars off a CAD plan (that is rebar-takeoff), for concrete volume, or structural design.
compatibility: Requires Python 3 with openpyxl. No CAD libraries needed — the input is a piece list, not a drawing.
---

# Rebar cutting optimization (تفريد الحديد)

This skill is a pure **1-D rebar cutting optimizer**: it takes a list of required bar pieces (by
diameter, each a cut length and a count) and works out how to cut them from standard **12 m stock
bars**. It is cleanly SEPARATE from the geometry takeoff — the seam between them is the piece list, not
the drawing.

**GOLDEN RULE:** it reproduces the foreman's hand method, **size by size**, so every row of the output
is checkable by eye on the steel (this size: so many pieces, so many per bar, so many bars, this
leftover), never a black-box optimum. **Prefer running the bundled `scripts/cutlist.py` over hand work.**

## What it does / does NOT do

- **Does:** cut same-Ø pieces from 12 m stock largest-size-first, carrying each bar's leftover forward to
  the smaller sizes; pre-split pieces >12 m with lap splices; report bars, remainder, waste %, and weight
  per diameter; write an Excel جدول تفريد.
- **Does NOT:** read drawings or count bars (that is the **rebar-takeoff** skill), compute concrete
  volume, or do structural design. Different input, different expertise. They compose: `takeoff → cut list`.

## The engineer's method (the law this encodes)

Stated verbatim (worked example): *لو كان عندنا ٢٠٠ قطعة Ø16 طول ٤.٥ — كل سيخ نقطع منه قطعتين ويتبقّى ٣م،
فنحتاج ١٠٠ سيخ ويتبقّى ١٠٠ قطعة ٣م نضعها بالحسبان حتى لا نقطع المزيد من الـ٣م.*

The **size-cascade with explicit leftover disposal**:
1. **Largest size first, as many per bar as fit.** For each size L, `pieces_per_bar = ⌊12 / L⌋`; every
   bar leaves an offcut of `12 − pieces_per_bar × L` (e.g. 4.5 → 2 per bar, offcut 3 m).
2. **Each offcut is cut down to the nearest smaller demanded size(s), largest-first = least waste**, and
   those pieces are counted toward that size's demand — so the 3 m offcuts of the 4.5 m bars cover the
   3 m demand and few/no 3 m bars are cut. A big odd-bar offcut (say 9 m) is cut e.g. into 3×2.4 m + a
   1.8 m scrap. The table SHOWS this for every size: "N قطعة بطول Lم → يُقطع M لمقاس Sم + …".
3. **What's left is split honestly:** a whole unused piece ≥ the smallest size is **فائض** (surplus —
   usable on another ceiling); a bit smaller than the smallest size is **هدر** (true waste).

On the Lower-Basement data: Ø10 = 407 bars, Ø12 = 370, Ø16 = 484; total **1261 bars, 16.1 t**, true waste
≈ 40 m (Ø12's 5 m bars leave an unusable 2 m each) plus ≈ 199 m of reusable 3 m surplus.

## How it works (algorithm)

Solve **one diameter at a time** (pieces of different Ø never share a bar). Per diameter:

1. **Clean** — drop zero/negative; set aside pieces with no length (`L=` missing) as a warning, never cut.
2. **Pre-split long pieces (>12 m)** — splice with a lap; each run = whole 12 m bars + a remainder
   pushed back into the demand (see `references/lap-rules.md`).
3. **Cascade by size (descending).** For each size: cut `⌈need/⌊12/L⌋⌉` bars (its `need` is already
   reduced by offcuts disposed into it from bigger sizes); dispose each new offcut into the nearest
   smaller demanded sizes (`dispose()` in `cutlist.py`), decrementing their demand.
4. **Report** — per size: pieces, per-bar, received-from-bigger-offcuts, bars, and the offcut's fate
   (what it is cut into + surplus + waste); per Ø: stock bars, surplus, waste, weight.

Full method and a worked example: `references/cutting-method.md`.

## Lap / splice rule (طول التزويد)

Only matters for pieces longer than one 12 m bar (long edge / continuity bars). ECP 203 field rule:
lap ≈ **60×Ø** in tension (شد), 40×Ø in compression (ضغط), **1 m minimum** (engineer's floor); **no lap splice for Ø>32**
(weld/mechanical — flagged, not cut as a normal lap). **Safe default = 60×Ø** (conservative tension),
editable with `--lap <multiplier>`. Details: `references/lap-rules.md`.

## Input

A per-diameter piece list. Two accepted forms:

1. **Sidecar JSON** (the normal hand-off from rebar-takeoff), written next to its `… - FULL.xlsx` as
   `… - pieces.json`:
   ```json
   { "ceiling": "...", "stock_length_mm": 12000, "unit": "mm",
     "pieces": [ {"diameter":12,"length_mm":4500,"count":163}, {"diameter":12,"length_mm":3000,"count":96} ],
     "unknown_length": [ {"diameter":12,"count":0} ],
     "mesh": [ {"diameter":10,"full_bars_12m":4052,"spec":"TOP=T10@200 ، BOT T10@200"} ] }
   ```
2. **In-process dict** `{diameter: {length_mm: count}}` (== rebar-takeoff's `add_piv`) via `optimize()`.

**Only the ADDITIONAL discrete pieces are cut here.** The main mesh (الفرش والغطاء) is already
quantified by rebar-takeoff as whole 12 m stock bars (its lap factor covers the overlaps) and yields no
offcut, so it is EXCLUDED and only shown separately (with `--include-mesh`) so the bar tally reconciles.

## Usage

```
python cutlist.py "<… - pieces.json>"
python cutlist.py "<… - pieces.json>" --lap 60 --include-mesh --out "<file.xlsx>"
```

Outputs `… - CUTLIST.xlsx` (RTL) with **ملخص التفريد** (per-Ø: pieces, stock bars, reusable surplus,
true waste, loss %, weight, grand total); **جدول التفريد** — the by-size table: one row per cut size with
`عدد القطع`, `قطع لكل سيخ`, `مأخوذ من متبقٍّ أكبر`, `عدد أسياخ 12م`, and `المتبقّي وما يُقطع منه` (the
offcut and exactly what to cut from it), plus a per-Ø total; and **تفاصيل الفائض والهدر** — every leftover
by Ø with its length, count, total metres and weight, split into فائض (usable) vs هدر (scrap). A
**الوصلات** sheet appears only if a piece exceeds 12 m. It also prints the cut list to stdout.

**One-shot from the takeoff:** `rebar-takeoff`'s `full_takeoff.py` accepts `--cut` (plus `--lap`,
`--include-mesh`); it writes the `pieces.json` sidecar and, if `cutlist.py` is importable, the CUTLIST
workbook in the same run.

## How to work with the user

1. **Confirm** the stock length (12 m) and the lap multiplier (default 60×Ø) — laps only bite when a
   piece exceeds 12 m, of which a normal slab plan has none.
2. **Run**, then relay per-Ø **stock bars + waste %** and the grand total (bars + tonnes).
3. **Hand over the جدول التفريد** so the foreman can verify each size row by eye (pieces, per-bar, bars,
   leftover) — this is the by-size layout the engineer asked for.
4. **Flag, never hide:** pieces counted with no `L=` (in `unknown_length`) and any Ø>32 lap are review
   items. Report residual surplus honestly — target < 5% (the field purchase allowance of 5–10% for
   laps/waste/error is a separate line, not part of this KPI).

## Parameters (editable inputs)

`stock_mm` (default 12000; 6 m half-bars exist in Egypt as a secondary option), `lap_mult` per Ø
(default 60, floored at 1 m), `include_mesh` (default off).

## Reference files

- `references/cutting-method.md` — the algorithm in full, a worked `4.5/4.5/3` example, edge cases, the ILP note.
- `references/lap-rules.md` — the ECP 203 lap/splice table and how over-length bars are split.
