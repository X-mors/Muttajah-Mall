# -*- coding: utf-8 -*-
"""
البند 1: حصر الردم الداخلي (م³) — Muttajah Mall، البدروم السفلي. (v2 — كل الجيومتري من اللوحة)

=================  المصدر والطريقة  =================
النموذج: substructure_model.Substructure (الشبكة الموحّدة column_exact.PLAN_ORIGIN، نقطة 01/A).
• منسوب الردم = بطاقة المنسوب المرسومة جوه القاعدة اللي سمكها 1500 (‑7.35m S.S.L) = ‑8.85 + 1.50.
• حدود الردم = الوش الداخلي للجدار المحيط (3 أضلاع عالية + جدار الجار 1.70م وأعمدة C فيه) — الجدار نفسه برّه الحدود.
• الحجم القائم = Σ مساحة كل منطقة وش لبشة جوه الحدود × (منسوب الردم − وشّها)
      المات ‑8.45 (شامل مكان السملات) | قواعد 700/1000/1100/1300/1500 → ‑8.15/‑7.85/‑7.75/‑7.55/‑7.35
• يُخصَم (كل عنصر من حدوده المرسومة، وارتفاعه من الوش اللي تحته بالظبط):
      السملات 17 (الظاهر فوق المات) | رقاب الأعمدة | الأكوار (الحائط تحت باب السلالم مصمت تحت ‑7.25)
      | الخزان (الحوائط + الداخل: مياه، مفيش ردم) | بادئا الرمب | بلاطة رمب 03 اللي قاعها تحت منسوب الردم.
• الجدار المحيط مفيش منه خصم (الحدود هي وشّه الداخلي).
• عناصر مرسومة من غير قطاع (حفر الصرف) أو مش مرسومة (حفر الأسانسير، هوابط سفلية) → ورقة "بنود ناقصة" بأثرها، مش داخلة في الرقم.
الصافي = الردم المدموك في مكانه. + هدر 5٪. (سطر مرجعي للتوريد بمعامل انضغاط 1.20 — يتعدّل من المهندس.)
الاستخدام: python backfill_takeoff.py [--no-review]
"""
import sys, os, argparse, logging, shutil
import ezdxf
import concrete_columns_takeoff as cc
import substructure_model as SM, substructure_calc as SC, substructure_xl as X
import foundation_review as FR

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "output")
WASTE = 1.05; COMPACTION = 1.20
KIND_AR = {'tie_beams': "السملات (الظاهر فوق المات)", 'column': "رقاب الأعمدة", 'core': "الأكوار",
           'tank': "الخزان T1 (الحوائط + الداخل)", 'starter': "بادئا الرمب", 'ramp_slab': "بلاطة رمب 03 تحت منسوب الردم"}


def hand_checks(M, B):
    """مراجعة يدوية من أبعاد مرسومة مباشرة (مش من خوارزمية السكريبت)."""
    F = M.FILL; out = []
    W, H = M.D_dims
    out.append(("مساحة حدود الردم", f"{W:.3f} × {H:.3f} (الوش الداخلي للجدار)", W * H,
                sum(z['A'] for z in B['zones'])))
    col = [o for o in B['obs'] if o['name'].startswith('C8 #44')][0]
    x0, y0, x1, y1 = col['poly'].bounds
    w, h = (x1 - x0) / 1000, (y1 - y0) / 1000
    out.append(("رقبة العمود C8 #44 (على الزون الأوسط ‑7.75)", f"{w:.2f} × {h:.2f} × ({F:+.2f} − (‑7.75))", w * h * (F + 7.75), col['V']))
    core = [o for o in B['obs'] if o['name'] == 'CORE3 (شمالي)'][0]
    x0, y0, x1, y1 = core['poly'].bounds
    a = (x1 - x0) / 1000 * (y1 - y0) / 1000 - ((x1 - x0) / 1000 - 0.6) * ((y1 - y0) / 1000 - 0.6)
    out.append(("CORE3 الشمالي (صندوق حوائط 300، الباب مقفول تحت ‑7.25)",
                f"[{(x1-x0)/1000:.1f}×{(y1-y0)/1000:.1f} − {(x1-x0)/1000-0.6:.1f}×{(y1-y0)/1000-0.6:.1f}] × 0.40", a * 0.40, core['V']))
    b = [r for r in B['beams'] if r['name'] == 'S(300×1500)'][0]
    out.append(("السمل S(300×1500)", f"0.30 × {b['L']:.2f} × (‑7.35 − (‑8.45))", 0.30 * b['L'] * 1.10, b['V']))
    return out


def write_excel(M, B, pend, hc, path):
    wb = X.Workbook()
    # ---- الملخص
    s = X.Sheet(wb, "الملخص", [46, 16, 16], first=True)
    s.title("البند 1: حصر الردم الداخلي — البدروم السفلي (Muttajah Mall)")
    s.note(f"منسوب الردم {M.FILL:+.2f} — {M.fill_src}؛ مطابق لـ ‑8.85 + 1.50 = {M.fill_check[0]:+.2f}.")
    s.note(f"حدود الردم = الوش الداخلي للجدار المحيط: {M.D_dims[0]:.3f} × {M.D_dims[1]:.3f} م = {M.D.area/1e6:.2f} م² "
           f"(الأضلاع الغربي/الجنوبي/الشرقي + جدار الجار الشمالي 1.70م). الجدار نفسه برّه الحدود فمفيش خصم ليه.")
    s.head(["البند", "م³", "ملاحظة"])
    s.row(["الحجم القائم (كل مناطق وش اللبشة × ارتفاع الردم فوقها)", B['gross'], "ورقة: القائم حسب المناطق"], b=True)
    for k, v in B['by_kind'].items():
        s.row([f"يُخصَم: {KIND_AR[k]}", -v, "ورقة: الخصومات"])
    s.row(["يُخصَم: الجدار المحيط", 0.0, "برّه حدود الردم"])
    s.total("الردم الصافي (مدموك في مكانه)", B['net'], col=2)
    s.total("+ هدر 5٪", B['net'] * WASTE, col=2, fill=X.GREY)
    s.gap()
    s.note(f"مرجعي: لو التوريد بمعامل انضغاط {COMPACTION:.2f} (يتعدّل من المهندس) = {B['net']*COMPACTION:.2f} م³، وبالهدر {B['net']*COMPACTION*WASTE:.2f} م³.", fill=X.GREY)
    s.note(f"تحقق داخلي: نفس الصافي محسوب بطريقة المناطق (مساحة كل منطقة بعد الخصم × ارتفاعها) = {B['check']:.3f} م³.", fill=X.GREY)
    s.note("بنود مش داخلة في الرقم لأن قطاعها/منسوبها مش في اللوحة — شوف ورقة «بنود ناقصة» وأثر كل واحد.", fill=X.YEL)
    # ---- حسب المناطق
    s = X.Sheet(wb, "حسب مناطق اللبشة", [6, 30, 10, 12, 12, 12, 10, 12, 18])
    s.title("الردم مقسّم حسب مناسيب وش اللبشة (القائم والصافي لكل منطقة)")
    s.note("الصافي = (مساحة المنطقة − بصمات العناصر الرأسية والخزان فوقها) × ارتفاع الردم. السملات منطقة لوحدها بوش ظهرها. "
           "بلاطة رمب 03 بتتخصم في الآخر (مش واقعة على منطقة واحدة).")
    s.head(["#", "المنطقة", "الوش م", "المساحة م²", "بصمات مخصومة م²", "الصافي م²", "ارتفاع الردم م", "الردم الصافي م³", "الموقع (م من 01/A)"])
    for i, z in enumerate(B['zones'], 1):
        s.row([i, z['name'], z['top'], z['A'], z['Aobs'], z['Anet'], z['h'], z['Vnet'], z['loc']])
    s.total("مجموع المناطق", sum(z['Vnet'] for z in B['zones']), col=8)
    s.row(["", "يُخصَم: بلاطة رمب 03 تحت منسوب الردم", "", "", "", "", "", -sum(v[0] for v in B['wedge'].values()), ""])
    s.total("الردم الصافي", B['check'], col=8)
    s.gap()
    s.head(["", "تجميع حسب الوش", "الوش م", "المساحة م²", "بصمات م²", "الصافي م²", "الارتفاع م", "م³", ""])
    agg = {}
    for z in B['zones']:
        k = round(z['top'], 2); a = agg.setdefault(k, [0, 0, 0, 0, z['h']])
        a[0] += z['A']; a[1] += z['Aobs']; a[2] += z['Anet']; a[3] += z['Vnet']
    for k in sorted(agg):
        a = agg[k]; s.row(["", f"كل المناطق على وش {k:+.2f}", k, a[0], a[1], a[2], a[4], a[3], ""])
    # ---- القائم
    s = X.Sheet(wb, "القائم حسب المناطق", [6, 34, 10, 12, 12, 12, 18])
    s.title("الحجم القائم: المساحة جوه حدود الردم × (منسوب الردم − وش اللبشة/القاعدة)")
    s.head(["#", "المنطقة", "الوش م", "المساحة م²", "ارتفاع الردم م", "الحجم م³", "الموقع (م من 01/A)"])
    for i, g in enumerate(B['gross_rows'], 1):
        s.row([i, g['name'], g['top'], g['A'], g['h'], g['V'], g['loc']])
    s.total("الحجم القائم", B['gross'], col=6)
    # ---- الخصومات
    s = X.Sheet(wb, "الخصومات", [6, 14, 30, 11, 11, 11, 12, 18])
    s.title("الخصومات عنصر عنصر (الأرقام = أرقام لوحة المراجعة)")
    s.note("العنصر الرأسي: Σ بصمته على كل منطقة × (منسوب الردم − وش المنطقة). الأعمدة بنفس ترقيم حصر العناصر الرأسية. "
           "السمل: الشريحة المرسومة × (ظهره − المات ‑8.45)؛ لو تحته عمود، العمود بيتخصم بارتفاعه فوق ظهر السمل (مفيش تكرار).")
    s.head(["#", "النوع", "العنصر", "البصمة م²", "الوش تحته م", "الارتفاع م", "الحجم م³", "الموقع (م من 01/A)"])
    kind_ar = {'column': 'عمود', 'core': 'كور', 'tank': 'خزان', 'starter': 'بادئ رمب'}
    for i, o in enumerate(B['obs'], 1):
        nm = o['name']
        if o['kind'] == 'column' and o['ref']:
            nm += f" ({o['ref']['w']}×{o['ref']['h']})"
        s.row([i, kind_ar[o['kind']], nm, o['A'], o['base'], o['h'], o['V'], o['loc']])
    for k in ('column', 'core', 'tank', 'starter'):
        s.total(f"مجموع {KIND_AR[k]}", B['by_kind'][k], col=7, fill=X.GREY)
    s.gap()
    s.head(["", "", "تفصيل الخزان", "البصمة م²", "", "", "الحجم م³", ""])
    for t in B['tank_split']:
        s.row(["", "", t['name'], t['A'], "", "", t['V'], ""])
    s.gap()
    s.head(["#", "النوع", "السمل", "الطول م", "العرض م", "فوق المات م", "الحجم م³", "الموقع (م من 01/A)"])
    for i, b in enumerate(B['beams'], 1):
        s.row([f"S{i}", "سمل", f"{b['name']} ظهره {b['top']:+.2f}", b['L'], b['w'], b['h'], b['V'], b['loc']])
    s.total("مجموع السملات", B['by_kind']['tie_beams'], col=7, fill=X.GREY)
    s.gap()
    for k, (V, A, L) in B['wedge'].items():
        if V > 0:
            s.row(["", "بلاطة رمب", f"{k}: قاعها تحت {M.FILL:+.2f} لمسافة {L:.2f}م بعد البادئ (ميل 7.5٪)", A, "", "", V, ""])
    # ---- مراجعة يدوية
    s = X.Sheet(wb, "مراجعة يدوية", [44, 40, 14, 14, 12])
    s.title("مراجعة يدوية — حساب مستقل من الأبعاد المرسومة مقابل السكريبت")
    s.head(["العنصر", "الحساب اليدوي", "يدوي", "السكريبت", "الفرق"])
    for nm, f, a, b in hc:
        s.row([nm, f, a, b, a - b])
    # ---- بنود ناقصة
    s = X.Sheet(wb, "بنود ناقصة", [24, 26, 40, 40, 30, 30])
    s.title("بنود مرسومة من غير قطاع أو مش مرسومة — مش داخلة في الرقم (ما افترضتش)")
    s.head(["البند", "المكان", "الموجود في اللوحة", "الناقص", "الأثر على الردم لو اتأكد", "الأثر على العزل"])
    for p in pend:
        s.row([p['item'], p['where'], p['known'], p['missing'], p['fill'], p['ins']])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    wb.save(path)
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--no-review", action="store_true")
    a = ap.parse_args(argv)
    logging.disable(logging.WARNING)
    doc = ezdxf.readfile(cc.DEFAULT_DXF)
    M = SM.Substructure(doc.modelspace())
    B = SC.backfill(M); pend = SC.pending_items(M); hc = hand_checks(M, B)
    print(f"البند 1: الردم الداخلي — منسوب الردم {M.FILL:+.2f} ({M.fill_src})")
    print(f"حدود الردم {M.D_dims[0]:.3f} × {M.D_dims[1]:.3f} = {M.D.area/1e6:.2f} م²")
    print(f"القائم {B['gross']:.2f} م³")
    for k, v in B['by_kind'].items(): print(f"  − {KIND_AR[k]}: {v:.2f}")
    print(f"الصافي {B['net']:.2f} م³ (تحقق بالمناطق {B['check']:.2f}) | +هدر 5٪ = {B['net']*WASTE:.2f}")
    for nm, f, x, y in hc: print(f"  يدوي: {nm}: {x:.3f} | سكريبت {y:.3f}")
    p = write_excel(M, B, pend, hc, os.path.join(OUT, "حصر الردم الداخلي - البدروم السفلي.xlsx")); print("SAVED:", p)
    if not a.no_review:
        print("SAVED:", FR.backfill_png(M, B, os.path.join(OUT, "مراجعة الردم - البدروم السفلي.png")))
        for f in FR.backfill_dxf(doc, M, B, pend, os.path.join(OUT, "مراجعة الردم - البدروم السفلي.dxf")): print("SAVED:", f)
    return M, B


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace"); main()
