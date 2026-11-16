# -*- coding: utf-8 -*-
"""
حصر/مراجعة قواعد اللبشة (RAFT) — استخراج أشكال القواعد الحقيقية + سماكاتها + مناسيبها.

المعرفة المُثبتة (أعراف هذا المكتب، مشروع Muttajah Mall) — راجع reference/raft-findings.md:
  • القواعد = مضلّعات مغلقة على طبقة  "R.C. footing"  (قد تكون غير منتظمة، ليست مستطيلات).
  • السماكة = رقم مجرّد (مثل 1500) نصّه على طبقة  "S -Beams"  داخل دائرة صغيرة (r≈366 مم).
  • السملات = نصوص  "S(العرض X العمق)"  مثل  S(300X1500)  على طبقة  "S -Beams".
  • مناسيب S.S.L للّبشة ليست على بلان اللبشة (موجودة على قطاعات الرامب كـ A-SYMB-LEVL).
  • منسوب وجه القاعدة = قاع التأسيس + السماكة.  القاع ≈ -8.85 م (ثابت تقريباً).
      مُعاير على نقطتين أكّدهما المهندس:  t=400→-8.45 (الجزء المنخفض) ، t=1500→-7.35 (أعلى قاعدة).
  • تنبيه: قد يكون المهندس عدّل رقم سماكة في لوحته — عند الاختلاف تُعتمد قيمة المهندس.

الاستخدام:
  python scripts/raft_footings.py --list            # جدول القواعد (سماكة/منسوب/شكل)
  python scripts/raft_footings.py --png             # صورة بالأشكال الحقيقية والأبعاد
  python scripts/raft_footings.py --review --dwg    # لوحة مراجعة: تحويط أعلى قاعدة + DWG
  python scripts/raft_footings.py --beams           # قائمة السملات (طول×عرض) ومواقعها
"""
import argparse, os, re, sys, glob, math, collections
import ezdxf

try:  # اطبع عربي على أي كونسول (Windows cp1252 وغيره)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "scripts"))

FORMATION_LEVEL = -8.85   # م — قاع التأسيس (ثابت تقريباً، مُعاير على نقطتَي المهندس)
LOW_RAFT_THK_MM = 400     # سماكة الجزء المنخفض العام (0.40م، وجهه -8.45) — مرجع الارتفاع الظاهر للسملات
FOOTING_LAYER   = "R.C. footing"
BUBBLE_LAYER    = "S -Beams"
OUTDIR          = os.path.join(_ROOT, "output")

def _default_dxf():
    for p in sorted(glob.glob(os.path.join(_ROOT, "drawings", "*.dxf"))):
        return p
    return os.path.join(_ROOT, "drawings", "STR-MOTTAGAH.dxf")

def text_of(e):
    try:
        if e.dxftype() == "MTEXT": return " ".join(e.plain_text().split())
        return " ".join((e.dxf.text or "").split())
    except Exception:
        return ""

def tpos(e):
    try: return float(e.dxf.insert.x), float(e.dxf.insert.y)
    except Exception:
        try: return float(e.dxf.align_point.x), float(e.dxf.align_point.y)
        except Exception: return None

def top_level(th_mm):
    return round(FORMATION_LEVEL + th_mm / 1000.0, 2) if th_mm else None

# ----------------------------------------------------------------------------
def collect_footings(msp):
    """كل مضلّع على طبقة R.C. footing بنقاطه الحقيقية + مركزه + bbox."""
    out = []
    for pl in msp.query("LWPOLYLINE POLYLINE"):
        if pl.dxf.layer != FOOTING_LAYER:
            continue
        try:
            if pl.dxftype() == "LWPOLYLINE":
                pts = [(float(x), float(y)) for x, y, *_ in pl.get_points()]
            else:
                pts = [(float(v.dxf.location.x), float(v.dxf.location.y)) for v in pl.vertices]
        except Exception:
            continue
        if len(pts) < 3:
            continue
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        bb = (min(xs), min(ys), max(xs), max(ys))
        out.append({"pts": pts, "bb": bb, "n": len(pts),
                    "c": (sum(xs) / len(xs), sum(ys) / len(ys)), "th": None})
    return out

def collect_thickness_bubbles(msp):
    """رقم السماكة المجرّد (300..2000) على طبقة S -Beams."""
    bubbles = []
    for e in msp.query("TEXT MTEXT"):
        if e.dxf.layer != BUBBLE_LAYER:
            continue
        t = text_of(e).strip()
        if re.fullmatch(r"\d{3,4}", t):
            v = int(t); p = tpos(e)
            if p and 300 <= v <= 2000:
                bubbles.append((v, p[0], p[1]))
    return bubbles

def assign_thickness(footings, bubbles):
    """ينسب كل فقاعة سماكة لأقرب قاعدة يحويها الـ bbox."""
    for (v, bx, by) in bubbles:
        best, bestd = None, 1e18
        for f in footings:
            bb = f["bb"]
            if bb[0]-300 <= bx <= bb[2]+300 and bb[1]-300 <= by <= bb[3]+300:
                d = math.hypot(bx - f["c"][0], by - f["c"][1])
                if d < bestd: bestd, best = d, f
        if best is not None:
            best["th"] = v if best["th"] is None else max(best["th"], v)
    for f in footings:
        f["top"] = top_level(f["th"])
    return [f for f in footings if f["th"] is not None]

def collect_beams(msp):
    """نصوص السملات S(العرض x العمق) ومواقعها + الارتفاع الظاهر فوق اللبشة المنخفضة + منسوب الظهر.

    قاع السملة = قاع التأسيس (FORMATION_LEVEL)؛ ظهرها = القاع + العمق.
    الارتفاع الظاهر فوق سطح اللبشة المنخفضة (0.40م) = العمق − 400مم.
    """
    beams = []
    rx = re.compile(r"S\s*\(\s*(\d+)\s*[xX]\s*(\d+)\s*\)")
    for e in msp.query("TEXT MTEXT"):
        if e.dxf.layer != BUBBLE_LAYER:
            continue
        m = rx.search(text_of(e))
        if m:
            w, d = int(m.group(1)), int(m.group(2))
            p = tpos(e) or (0.0, 0.0)
            beams.append({"w": w, "d": d, "x": p[0], "y": p[1],
                          "exposed_mm": max(d - LOW_RAFT_THK_MM, 0),
                          "back": round(FORMATION_LEVEL + d / 1000.0, 2)})
    return beams

def render_beams(footings, beams, out_png):
    """صورة: القواعد كسياق + كل سمل مُعلّم بالارتفاع الظاهر منه."""
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon as MplPoly
    fig, ax = plt.subplots(figsize=(12, 10), dpi=170)
    for f in footings:                      # القواعد كسياق خفيف
        ax.add_patch(MplPoly(f["pts"], closed=True, fill=False,
                     edgecolor="#adb5bd", linewidth=0.9, zorder=1))
    xs = [b["x"] for b in beams]; ys = [b["y"] for b in beams]
    for b in beams:
        ax.plot(b["x"], b["y"], "s", ms=5, color="#1864ab", zorder=4)
        ax.annotate(f"S{b['w']}x{b['d']}\n^ {b['exposed_mm']/1000:.2f} m",
                    (b["x"], b["y"]), fontsize=6.6, ha="center", va="center",
                    color="#c00000", fontweight="bold", zorder=6,
                    bbox=dict(boxstyle="round,pad=0.18", fc="white", ec="#c00000", lw=0.6, alpha=0.9))
    allx = xs + [p[0] for f in footings for p in f["pts"]]
    ally = ys + [p[1] for f in footings for p in f["pts"]]
    mx = (max(allx)-min(allx))*0.06; my = (max(ally)-min(ally))*0.05
    ax.set_xlim(min(allx)-mx, max(allx)+mx); ax.set_ylim(min(ally)-my, max(ally)+my)
    ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values(): s.set_visible(False)
    ax.set_title("RAFT tie-beams (السملات) — exposed height above low raft\n"
                 "'^ X.XX m' = depth - 0.40m  (exposed above low raft top -8.45)", fontsize=10)
    fig.tight_layout(); os.makedirs(os.path.dirname(out_png), exist_ok=True)
    fig.savefig(out_png, bbox_inches="tight")
    return out_png

def build_beams_review(src_dxf, beams, out_dxf, want_dwg=False):
    """لوحة DXF: جنب كل سمل الارتفاع الظاهر منه ومنسوب ظهره (عربي)."""
    doc = ezdxf.readfile(src_dxf); msp = doc.modelspace()
    LAY = "CHECK-RAFT-BEAMS"
    if LAY not in doc.layers: doc.layers.add(LAY, color=1)
    for b in beams:
        txt = f"ظاهر {b['exposed_mm']/1000:.2f}م (ظهر {b['back']})"
        t = msp.add_text(txt, height=350, dxfattribs={"layer": LAY, "color": 1})
        t.dxf.insert = (b["x"] + 400, b["y"] + 400)
    os.makedirs(os.path.dirname(out_dxf), exist_ok=True)
    doc.saveas(out_dxf)
    dwg = None
    if want_dwg:
        try:
            import takeoff; dwg = takeoff.to_dwg(out_dxf)
        except Exception as e:
            print("تعذّر DWG:", e)
    return out_dxf, dwg

# ----------------------------------------------------------------------------
def render_png(footings, out_png):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon as MplPoly
    maxth = max((f["th"] for f in footings), default=None)
    COL = {700:"#9ec5fe",1000:"#74c0fc",1100:"#ffa94d",1300:"#b197fc",1500:"#ff6b6b"}
    fig, ax = plt.subplots(figsize=(10, 11), dpi=160)
    for f in footings:
        th = f["th"]; irr = f["n"] > 4
        ax.add_patch(MplPoly(f["pts"], closed=True, fill=True,
            facecolor=COL.get(th, "#ced4da"), alpha=0.35,
            edgecolor=("#d6336c" if irr else "#1864ab"),
            linewidth=(2.6 if irr else 1.4), zorder=2))
        ax.text(f["c"][0], f["c"][1], f"t={th}\n({f['top']})",
                ha="center", va="center", fontsize=8, fontweight="bold", zorder=5)
        if irr:
            pts = f["pts"]
            for i in range(len(pts)):
                a, b = pts[i], pts[(i+1) % len(pts)]
                L = math.hypot(b[0]-a[0], b[1]-a[1])
                if L < 300: continue
                ax.text((a[0]+b[0])/2, (a[1]+b[1])/2, f"{L:.0f}", fontsize=6.5,
                        color="#d6336c", ha="center", va="center", zorder=6,
                        bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.7))
                ax.plot(a[0], a[1], "o", ms=3, color="#d6336c", zorder=7)
    allx = [p[0] for f in footings for p in f["pts"]]
    ally = [p[1] for f in footings for p in f["pts"]]
    mx = (max(allx)-min(allx))*0.08; my = (max(ally)-min(ally))*0.05
    ax.set_xlim(min(allx)-mx, max(allx)+mx); ax.set_ylim(min(ally)-my, max(ally)+my)
    ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values(): s.set_visible(False)
    ax.set_title(f"RAFT footings — TRUE shapes & dims (mm)\nHighest footing t={maxth} -> top {top_level(maxth)}", fontsize=10)
    fig.tight_layout(); os.makedirs(os.path.dirname(out_png), exist_ok=True)
    fig.savefig(out_png, bbox_inches="tight")
    return out_png

def build_review(src_dxf, footings, out_dxf, want_dwg=False):
    maxth = max((f["th"] for f in footings), default=None)
    high = [f for f in footings if f["th"] == maxth]
    doc = ezdxf.readfile(src_dxf); msp = doc.modelspace()
    LAY = "CHECK-RAFT-HIGHEST"
    if LAY not in doc.layers: doc.layers.add(LAY, color=1)
    for f in high:
        cx, cy = f["c"]; bb = f["bb"]
        r = 0.5 * math.hypot(bb[2]-bb[0], bb[3]-bb[1]) + 800
        msp.add_circle((cx, cy), r, dxfattribs={"layer": LAY, "color": 1})
        t = msp.add_text(f"HIGHEST FOOTING {top_level(maxth)} (t={maxth})",
                         height=500, dxfattribs={"layer": LAY, "color": 1})
        t.dxf.insert = (cx - r, bb[3] + 900)
    os.makedirs(os.path.dirname(out_dxf), exist_ok=True)
    doc.saveas(out_dxf)
    dwg = None
    if want_dwg:
        try:
            import takeoff
            dwg = takeoff.to_dwg(out_dxf)
        except Exception as e:
            print("تعذّر DWG:", e)
    return out_dxf, dwg

# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="حصر/مراجعة قواعد اللبشة")
    ap.add_argument("--dxf", default=_default_dxf())
    ap.add_argument("--list", action="store_true", help="جدول القواعد")
    ap.add_argument("--png", action="store_true", help="صورة بالأشكال الحقيقية")
    ap.add_argument("--review", action="store_true", help="لوحة مراجعة تحويط أعلى قاعدة")
    ap.add_argument("--dwg", action="store_true", help="حوّل لوحة المراجعة إلى DWG")
    ap.add_argument("--beams", action="store_true", help="قائمة السملات")
    args = ap.parse_args()

    doc = ezdxf.readfile(args.dxf); msp = doc.modelspace()
    footings = assign_thickness(collect_footings(msp), collect_thickness_bubbles(msp))
    footings.sort(key=lambda f: (-(f["th"] or 0), -f["c"][1]))

    if args.list or not (args.png or args.review or args.beams):
        print(f"القاع المرجعي = {FORMATION_LEVEL} م | عدد القواعد ذات السماكة = {len(footings)}")
        hist = collections.Counter(f["th"] for f in footings)
        print("السماكات:", {k: hist[k] for k in sorted(hist)})
        print(f"{'#':>3} {'سماكة':>6} {'منسوب الوجه':>12} {'رؤوس':>5}  bbox")
        for i, f in enumerate(footings, 1):
            bb = f["bb"]
            print(f"{i:>3} {f['th']:>6} {str(f['top']):>12} {f['n']:>5}  "
                  f"x[{bb[0]:.0f},{bb[2]:.0f}] y[{bb[1]:.0f},{bb[3]:.0f}]")

    if args.beams:
        beams = collect_beams(msp)
        print(f"\nعدد السملات = {len(beams)} | الظاهر = العمق − {LOW_RAFT_THK_MM}مم (فوق اللبشة المنخفضة -8.45)")
        hb = collections.Counter(b["d"] for b in beams)
        print("الأعماق:", {k: hb[k] for k in sorted(hb)})
        print(f"  {'السمل':>12} {'ظاهر(م)':>9} {'منسوب الظهر':>12}  الموقع")
        for b in sorted(beams, key=lambda b: (-b["d"], b["x"])):
            print(f"  {'S%dx%d'%(b['w'],b['d']):>12} {b['exposed_mm']/1000:>9.2f} {b['back']:>12}  ({b['x']:.0f},{b['y']:.0f})")
        print("PNG:", render_beams(footings, beams, os.path.join(OUTDIR, "raft-beams-exposed.png")))
        dxf, dwg = build_beams_review(args.dxf, beams,
                                      os.path.join(OUTDIR, "raft-beams-exposed.dxf"), args.dwg)
        print("DXF:", dxf, "| DWG:", dwg or "—")

    if args.png:
        print("PNG:", render_png(footings, os.path.join(OUTDIR, "raft-footings-shapes.png")))
    if args.review:
        dxf, dwg = build_review(args.dxf, footings,
                                os.path.join(OUTDIR, "raft-review-highest.dxf"), args.dwg)
        print("DXF:", dxf); print("DWG:", dwg or "—")

if __name__ == "__main__":
    main()
