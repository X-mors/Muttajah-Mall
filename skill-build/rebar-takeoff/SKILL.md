---
name: rebar-takeoff
description: >-
  Automated steel-reinforcement (rebar) quantity takeoff from an AutoCAD structural reinforcement
  PLAN drawing (.dwg/.dxf). Two modes: (1) counts the individual ADDITIONAL top/bottom slab bars;
  (2) quantifies the MAIN two-way slab mesh (الفرش والغطاء, farsh/ghitaa) by area. Outputs a formatted
  Excel takeoff (bars by diameter and length) plus a marked-up review drawing. Use whenever the user
  has a structural reinforcement drawing or CAD file and wants to count or tally rebar / bars /
  أسياخ الحديد from it — additional reinforcement plans, main slab mesh (TOP=/BOT.=T##@### C/C) — asks
  حصر الحديد / حصر التسليح / عدد الأسياخ / الفرش والغطاء, points at callouts like T16-200-T or T12-400-B,
  or asks how many bars for a plan, even without saying 'takeoff'. Specifically about COUNTING bars on
  a plan: do NOT use it for concrete-volume takeoff, structural design or steel-per-m² ratios, rebar
  unit-weight facts, converting a DWG, or extracting a columns schedule.
compatibility: Requires Python 3 with ezdxf and openpyxl (matplotlib optional for diagnostics). Converting DWG⇄DXF needs the ODA File Converter.
---

# Rebar takeoff from structural DXF/DWG

This skill takes off slab reinforcement from AutoCAD structural plans and produces a clean Excel takeoff
plus a review drawing. It was built against real consultant drawings and encodes their conventions.
**Prefer running the bundled scripts over re-deriving the geometry by hand** — the logic is subtle and
already validated.

## Two modes — pick by what the user is counting

1. **Additional reinforcement** (extra local bars over supports): callouts like `T16-200-T` / `T12-400-B`.
   Use `scripts/takeoff.py` (one plan) or `scripts/ceiling_takeoff.py` (a ceiling's top+bottom together).
   Method + conventions: `references/method.md` and `references/drawing-conventions.md`.
2. **Main slab mesh** = الفرش والغطاء (the continuous two-way bottom+top mesh): notes like
   `TOP=T10@200 C/C` / `BOT.=T10@200 C/C`. Use `scripts/slab_mesh.py`. Method + conventions:
   `references/slab-mesh.md`. This is an AREA-based supply calc, not per-bar counting — read that file.

3. **Complete ceiling takeoff** (both of the above in one deliverable): `scripts/full_takeoff.py
   "<CEILING>" [--dwg]`. It runs the additional (top+bottom) AND the main mesh, and writes ONE Excel
   (`… - FULL.xlsx`) with a summary — additional counts by length×Ø, the mesh by Ø, and a grand total
   of linear metres per diameter — plus a `تفاصيل الإضافي` sheet and a `الفتحات` (openings) sheet, and a
   single review drawing that both circles/numbers the additional bars AND outlines every detected
   opening. Use this whenever the user asks for a **full / complete** steel takeoff of a ceiling.
   It also always writes a `… - pieces.json` sidecar (the clean per-Ø piece list) — the hand-off to the
   separate **rebar-cutting** skill (تفريد الحديد / cutting optimization).

**Bar cutting (تفريد) is a SEPARATE skill.** Counting bars is this skill; cutting the counted pieces from
12 m stock bars (by size, with leftover reuse) is `rebar-cutting`, which reads the `pieces.json` sidecar.
As a convenience, `full_takeoff.py --cut` (with `--lap`, `--include-mesh`) runs it in the same pass when
`cutlist.py` sits alongside. When the user wants a cutting schedule / تفريد الحديد / عدد أسياخ 12م /
المتبقّي, use the **rebar-cutting** skill.

The two mesh/additional modes are easy to tell apart: additional uses hyphen callouts (`T##-###-T|B`);
the main mesh uses `TOP=/BOT.= … @ … C/C` next to a small mesh symbol. If unsure which the user wants, ask.

## Prerequisites (one-time)

- Python 3 with `ezdxf` and `openpyxl`: `python -m pip install ezdxf openpyxl matplotlib`
- If the input is a `.dwg`, convert it to `.dxf` first with the **ODA File Converter**. The converter's
  batch filter fails on non-ASCII (e.g. Arabic) file names, so copy the file to a temp folder under a
  plain ASCII name (`conv.dwg`), convert, then rename the output back. `takeoff.py`'s `to_dwg()` shows the
  exact pattern for the reverse direction.

## The core idea (what the scripts do)

Each additional bar is drawn as a short line on a rebar layer, labelled with a callout like
`T16-200-T` (diameter 16 mm, spacing 200 mm, **T**op / **B**ottom face) and a length `L=6000`. A red
**dimension** perpendicular to the bar gives the **distribution width** — how far that set of parallel
bars extends. The count is simply:

```
number of bars = ceil( distribution_width / spacing )      # round up, no +1
```

So `T16-200` over a 5500 mm width → ceil(5500/200) = 28 bars, each `L` long. The whole problem is
**attributing the right dimension to each bar**, which `references/method.md` explains in full.

## Usage

Run from the skill's `scripts/` directory (they import each other).

**One plan** (by a fragment of its title; `--extra` disambiguates TOP vs BOTTOM):

```
python takeoff.py "<DXF path>" ... 
python takeoff.py "LOWER BASEMENT CEILING" --extra "TOP" --dxf "<file.dxf>" --dwg
```

Outputs to `output/<title>.xlsx` (counts by length × diameter, plus a numbered detail sheet) and
`output/<title> - review.dxf` (a copy of the drawing with a coloured circle on every counted bar).
`--dwg` also converts the review file to DWG. Pass `--bbox XMIN XMAX YMIN YMAX` to override the
auto-detected plan region if a plan is laid out unusually.

**A whole ceiling** (top + bottom in one workbook, one numbered review drawing):

```
python ceiling_takeoff.py "LOWER BASEMENT CEILING" --dxf "<file.dxf>" --dwg
```

This is the usual deliverable: `output/<ceiling> - TOP+BOTTOM.xlsx` with a **الملخص** (summary) sheet and
a **التفاصيل** (detail) sheet, plus one review drawing whose circle numbers match the detail rows.

## How to work with the user

1. **Confirm the file and the target.** Which `.dwg/.dxf`, and which ceiling/plan(s)? If it's a DWG,
   convert to DXF first.
2. **Run the script**, then read its printed summary (per-diameter totals, and how many callouts were
   flagged). Relay the totals.
3. **Hand over the review drawing for checking.** Circle colours: 🟢 green = counted confidently ·
   🔵 cyan = width came from the weaker fallback (worth a glance) · 🔴 red = could not be counted ·
   🟣 magenta = stair bar, excluded. Any callout in the plan **without** a circle is one the script did
   not see — ask the user to look for those; they are the main way misses surface.
4. **Iterate on flags.** For red/cyan cases, open the drawing near the printed coordinates, understand
   why, and fix the rule (see `references/method.md`) rather than hand-patching a number.

## Conventions the scripts rely on (quick reference)

Full detail in `references/drawing-conventions.md`. The essentials:

- **Callouts**: `TEXT` matching `^T(\d+)-(\d+)-([TB])(-add)?$`, usually on `ST-203-SLAB-TXT`.
- **Bar lines**: on layers whose name contains **`RFT`** — `ST-RFT-TOP` (top face) and `ST-RFT-BOT`
  (bottom face). **Find rebar by layer, not colour** (top is drawn blue, bottom yellow, but that varies).
- **Distribution dimensions**: `DIMENSION` entities (often `ST-206-SLAB-DIM`), perpendicular to the bar.
- **Crossing markers**: small orange circles (ACI colour 30, radius ≈ 75) sitting exactly where a bar
  crosses its own dimension. They pin down which bar in a group a shared dimension belongs to — use them
  where present, but never depend on them: in some plans they are absent or stored at mirrored/orphaned
  coordinates, and the bar-line method covers those.
- **Stairs are excluded** — see `references/method.md`.

## Important gotchas (learned the hard way)

- **A dimension must contain the crossing point within its span** (0 ≤ t ≤ 1), not merely lie on the
  same infinite line. Dimensions from other plans in the sheet share the same X/Y axis; without the
  in-span test you will grab a value from a completely different plan row.
- **One red dimension can cross a whole group of bars.** Picking the nearest dimension to the callout is
  not enough — the crossing circle (where readable) or the in-span bar∩dim test identifies the specific
  bar the measurement is for.
- **Edge bars span the full plan width** and are dimensioned by the long overall dimension (~50 m); keep
  the dimension-width cap high (~60000) or you will silently drop them.
- **Diameters are dynamic** — a plan may use Ø10, Ø12, Ø16, Ø18…; never hard-code the set.
- **Weight is intentionally out of scope** here (counts only) unless the user asks; if they do, unit
  weight is `d²/162` kg/m.
