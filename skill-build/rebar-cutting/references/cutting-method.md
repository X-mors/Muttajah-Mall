# Cutting method — size-cascade (تفريد حسب المقاس)

The optimizer cuts required rebar pieces from 12 m stock bars, one **diameter at a time** (pieces of
different Ø never share a bar). It reproduces the foreman's hand method **size by size**, so every row of
the output is a check he can make on the steel.

## Algorithm (as implemented in `scripts/cutlist.py`, `cascade_cut()`)

Constant: `STOCK = 12000 mm`.

**STEP 0 — Clean.** Drop rows with length ≤ 0 or count ≤ 0. Pieces counted with no `L=` arrive as
`length_mm = 0`; set them aside as an `unknown_length` warning and NEVER cut them.

**STEP 1 — Pre-split long pieces (L > 12 m).** See `lap-rules.md`. Each long run becomes whole 12 m bars
plus a remainder pushed back into the demand. After this every remaining length ≤ 12 m. (A normal slab
additional plan has none.)

**STEP 2 — Cascade, largest size first, disposing every offcut.** Process sizes **descending**. For each
size `L`, its `need` has already been reduced by offcuts disposed into it from bigger sizes. Cut
`per_bar = ⌊STOCK/L⌋` pieces per bar, `bars = ⌈need/per_bar⌉`. Every bar produces an offcut
(`STOCK − pieces_on_that_bar × L`); **`dispose()`** cuts that offcut down to the nearest smaller demanded
sizes, largest-first (least waste), decrementing their demand and recording the cut. A leftover ≥ the
smallest size is banked as **surplus** (reusable); a shorter tail is **waste**.

**STEP 3 — Report.** Per size: `need`, `received` (pieces got from bigger offcuts), `per_bar`, `bars`, and
the offcut's fate (what it is cut into + surplus + waste). Per Ø: `stock_bars`, surplus, waste, and
`weight = stock_bars × 12 × Ø²/162`. Loss % = (surplus + waste) / (stock_bars × 12).

## Worked example — the engineer's own case (Ø16, real Lower-Basement data)

Demand: `6 m ×600, 4.5 m ×220, 4 m ×84, 3 m ×251, 2.4 m ×51`.

| size | pieces | per bar | from bigger offcut | bars | the offcut → what to cut from it |
|---|---|---|---|---|---|
| 6 m | 600 | 2 | — | 300 | — (6+6 = 12 exact) |
| 4.5 m | 220 | 2 | — | 110 | **110 × 3 m → 110 to the 3 m size** |
| 4 m | 84 | 3 | — | 28 | — |
| 3 m | 251 | 4 | **110** (from the 4.5 offcuts) | 36 | 1 × 9 m → 3 to the 2.4 m size + 1.8 m waste |
| 2.4 m | 51 | 5 | 3 | 10 | 1 × 4.8 m → surplus |

**Ø16 = 484 bars.** The 3 m row cut only 36 bars instead of ⌈251/4⌉ = 63, because 110 of its pieces came
free from the 4.5 m offcuts — exactly *"نضعها بالحسبان حتى لا نقطع المزيد من الـ3م"* — and the odd 9 m
offcut is itself cut into three 2.4 m pieces, leaving only 1.8 m waste.

Whole ceiling: Ø10 = 407, Ø12 = 370, Ø16 = 484 → **1261 bars, 16.1 t** (true waste ≈ 40 m, plus ≈ 199 m
of reusable 3 m surplus). A pattern-mixing ILP would shave a couple of bars off Ø12's 5 m→2 m offcuts, at
the cost of the by-size clarity the engineer requires.

## Why cascade, not pattern-mixing

A true 1-D cutting-stock optimum (ILP / column generation, or a greedy that mixes three sizes on one bar
like `5+4+3`) would save ~5 bars across this whole ceiling (~0.4 %). It is rejected here because its bars
carry mixed-size combos that a foreman cannot re-derive at the bench, whereas the size-cascade gives a
table he cuts straight from: *this size, this many per bar, this leftover.* The engineer asked for that
clarity explicitly. Waste stays under the 5 % field target on real data because the dominant saving —
feeding each size's offcut to the next smaller size — is exactly what the cascade does.

## Edge cases

- **Odd count** (e.g. 375 × 6 m): `⌈375/2⌉ = 188` bars; the last bar yields one spare 6 m piece, banked
  (and, if no 6 m demand remains, reported as surplus).
- **Leftover with no matching smaller size** (e.g. 5 m → 2 m offcut when there is no 2 m demand): stays in
  the bank and is reported as surplus/waste, never silently dropped.
- **Size that divides 12 exactly** (6, 4, 3, 2.4): zero leftover on full bars.
- **Demand fully covered by the bank:** `bars = 0` for that size (shown highlighted), the clearest proof
  the leftovers were reused.
