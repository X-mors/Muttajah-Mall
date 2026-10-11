# The takeoff method — attribution, edge cases, and why each rule exists

The count for a bar is `ceil(distribution_width / spacing)`. Everything hard is in finding the **right**
distribution width for each bar. This file explains the association pipeline the scripts implement and the
reasoning behind each rule, so you can adjust it intelligently instead of tuning magic numbers blindly.

## The counting rule

`number of bars = ceil(width / spacing)`, rounding **up**, with **no +1** for an end bar. This matches the
user's own hand method (5500 / 200 = 27.5 → 28). Bar length is the callout's `L=`. Do not change the +1
convention without the user asking — it is a deliberate choice, not an oversight.

## Attributing a dimension to a bar (in priority order)

For each callout, find its bar line (the nearest `ST-RFT-*` line of the matching face and orientation),
then determine the width:

1. **Crossing circle (authoritative, where readable).** Find the orange circle sitting on that bar, then
   take the perpendicular dimension the circle lies on. This is the ground truth when one dimension
   crosses a group of bars — the circle names the specific bar.
2. **Bar-line ∩ dimension (robust fallback).** Intersect the bar's axis with each perpendicular
   dimension; keep the dimension whose span contains the crossing and whose crossing is nearest the
   callout. Validated to agree with the circle method on 115/115 bars of a real top plan once the circle
   picks the group member — and it needs no circles, so it covers plans where the circles are missing or
   orphaned (e.g. bottom plans).
3. **Label-proximity (last resort).** Nearest perpendicular dimension to the callout label. Only used when
   1 and 2 both fail; flag these (cyan) for human review.

### The single most important rule: in-span, not on-line

A dimension defines a finite segment (between its two extension points). Many dimensions from **other
plans in the same sheet** happen to share the same X or Y axis, so their *infinite* line passes right
through a bar's crossing even though the real dimension is thousands of units away in another plan row.

**Always require the crossing point to project *within* the dimension's segment** (parameter `0 ≤ t ≤ 1`,
with a hair of tolerance), not merely to be close to the infinite line. This one test is what makes the
attribution correct; dropping it silently pulls widths from unrelated plans. It also disambiguates nested
dimensions (a 2800 sub-segment vs the 4500 that actually spans the bar): only the one whose segment
contains the bar qualifies.

### Why not just "nearest dimension to the label"?

Because a single red dimension can cross a whole group of parallel bars, and the callout label sits at the
bar's end — often closer to a neighbour's dimension than to its own. Nearest-to-label picks the wrong one
in exactly the group case. The circle (or the in-span bar∩dim crossing) is what resolves it.

## Stairs — exclude them

Stair reinforcement is **not** slab additional reinforcement and must be dropped. Detect a stair zone by
the **`with stair`** text marker, and exclude a callout only when it is **both** (a) near a stair marker
(≈ |Δx| < 4000, |Δy| < 9000) **and** (b) missing an `L=` label. The "+ missing L" condition matters: real
slab bars often pass near a stairwell and *do* carry `L=` — a zone-only rule wrongly removes them.

## Edge bars — full-width distribution

A bar running along the slab edge is distributed across the **entire plan width**, dimensioned by the long
overall dimension (~50000+ mm), whose line crosses the bar far from the bar's short callout. Keep the
dimension-width cap generous (≤ ~60000) so these are not filtered out, and rely on the in-span test to
attribute them correctly. In the sample set two Ø12-400 edge bars each spanned 53335 mm → 134 bars.

## Confidence / flags surfaced to the user

- `src = "circle"` or `"barline"` → counted confidently (green).
- `src = "heur"` → label-proximity fallback (cyan) — glance at it.
- no width found → red — investigate at the printed coordinates.
- Any callout **without** a circle in the review drawing was never seen by the script — the primary way a
  genuine miss shows up. Ask the user to scan for uncircled callouts.

## Diameters and output

- Diameter columns are built from whatever diameters actually appear (Ø10/12/16/18/20/25…). Never
  hard-code them.
- Review circles are numbered; those serial numbers are the detail-sheet row numbers, so the user can jump
  from a circle in the drawing to its full row in Excel.

## Validating a change

When you touch a threshold, re-run on a plan you already trust and compare totals to the previous result
(and, on a plan that has readable circles, compare the bar-line result to the circle-on-bar result). A
change that shifts totals should be explainable by a specific case you can point at in the drawing — never
accept a silent drift.
