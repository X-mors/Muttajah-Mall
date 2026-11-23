# -*- coding: utf-8 -*-
"""
البند 1: حصر الردم الداخلي (م³) — Muttajah Mall، البدروم السفلي. (v3 — ترقيم موحّد مع صور المراجعة)

النموذج: substructure_model.Substructure (الشبكة الموحّدة column_exact.PLAN_ORIGIN، نقطة 01/A).
• منسوب الردم = بطاقة المنسوب المرسومة جوه القاعدة اللي سمكها 1500 (‑7.35) = ‑8.85 + 1.50.
• حدود الردم = الوش الداخلي للجدار المحيط (3 أضلاع عالية + جدار الجار 1.70م) — الجدار نفسه برّه الحدود.
• الحجم القائم = Σ مساحة كل منطقة وش لبشة جوه الحدود × (منسوب الردم − وشّها).
• يُخصَم (كل عنصر من حدوده المرسومة، وارتفاعه من الوش اللي تحته بالظبط): السملات (الظاهر فوق المات)، رقاب الأعمدة،
  الأكوار (الحائط تحت باب السلالم مصمت)، الخزان كله (جوّه مياه)، بادئا الرامب، داخل كوري الأسانسير (مش بيتردم)،
  بلاطة رامب 03 اللي قاعها تحت منسوب الردم. كوري السلالم بيتردموا من جوّه.
الإكسل عربي بالكامل؛ عمود «رقم على اللوحة» = الرقم المكتوب على صورتي المراجعة (عربي/إنجليزي) والـDXF.
الاستخدام: python backfill_takeoff.py [--no-review]
"""
import sys, os, argparse, logging
import ezdxf
import concrete_columns_takeoff as cc
import substructure_model as SM, substructure_calc as SC, substructure_xl as X
import foundation_review as FR

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "output")
WASTE = 1.05
KIND_AR = {'mat': 'منطقة لبشة', 'footing': 'قاعدة', 'beam': 'سمل', 'column': 'رقبة عمود', 'core': 'كور', 'tank': 'خزان',
           'starter': 'بادئ رامب', 'lift': 'كور أسانسير من جوّه', 'sump': 'حفرة صرف', 'wedge': 'بلاطة رامب'}
DED_AR = [('beam', "السملات (الجزء الظاهر فوق المات)"), ('column', "رقاب الأعمدة"), ('core', "حوائط الأكوار"),
          ('tank', "الخزان (حوائطه + داخله)"), ('starter', "بادئا الرامب"),
          ('lift', "داخل كوري الأسانسير (مش بيتردم)"), ('sump', "حفر الصرف التلاتة (مش بتتردم)"), ('wedge', "بلاطة رامب 03 تحت منسوب الردم")]


def detail_rows(M, B, E):
    """صفوف التفصيل بنفس أرقام اللوحة: (رقم، العنصر، النوع، الوش، المساحة، الارتفاع، الحجم ±، الموقع)."""
    g = {r['uid']: r for r in B['gross_rows']}; b = {r['uid']: r for r in B['beams']}; o = {r['uid']: r for r in B['obs']}
    rows = []
    for e in E:
        u = e['uid']
        if u in g:
            r = g[u]
            nm = e['ar'] + (" — شامل مكان السملات" if u == 'MAT' else '')
            rows.append((e['no'], nm, KIND_AR[e['kind']], r['top'], r['A'], r['h'], r['V'], SC._loc(r['region'])))
        elif u in b:
            r = b[u]
            rows.append((e['no'], e['ar'] + f" — طول {r['L']:.2f}م", KIND_AR['beam'], r['top'], r['A'], r['h'], -r['V'], SC._loc(e['poly'])))
        elif u in o:
            r = o[u]
            rows.append((e['no'], e['ar'], KIND_AR[e['kind']], r['base'], r['A'], r['h'], -r['V'], SC._loc(e['poly'])))
        elif e['kind'] == 'wedge':
            V, A, Lw = B['wedge']['RAMP 03']
            rows.append((e['no'], e['ar'], KIND_AR['wedge'], None, None, None, -V, SC._loc(e['poly'])))
    return rows


def hand_checks(M, B, E):
    """مراجعة يدوية من أبعاد مرسومة مباشرة (مش من خوارزمية السكريبت)."""
    F = M.FILL; out = []; num = {e['uid']: e['no'] for e in E}
    o = {r['uid']: r for r in B['obs']}
    W, H = M.D_dims
    out.append(("حدود الردم (الوش الداخلي للجدار)", f"{W:.3f} × {H:.3f}", W * H, sum(z['A'] for z in B['zones'])))
    c = [x for x in M.obs if x['kind'] == 'column' and x['ref']['no'] == 44][0]
    x0, y0, x1, y1 = c['poly'].bounds; w, h = (x1 - x0) / 1000, (y1 - y0) / 1000
    out.append((f"رقم {num[c['uid']]}: رقبة عمود C8 (على وش ‑7.75)", f"{w:.2f} × {h:.2f} × ({F:+.2f} − (‑7.75))", w * h * (F + 7.75), o[c['uid']]['V']))
    k = [x for x in M.obs if x['kind'] == 'core' and 'شمالي' in x['name']][0]
    x0, y0, x1, y1 = k['poly'].bounds; a, bb = (x1 - x0) / 1000, (y1 - y0) / 1000
    out.append((f"رقم {num[k['uid']]}: كور 3 شمالي (صندوق حوائط 300، الباب مقفول تحت ‑7.25)",
                f"[{a:.1f}×{bb:.1f} − {a-0.6:.1f}×{bb-0.6:.1f}] × 0.40", (a * bb - (a - 0.6) * (bb - 0.6)) * 0.40, o[k['uid']]['V']))
    s = [x for x in M.bz if x['d'] == 1500][0]; r = [x for x in B['beams'] if x['uid'] == s['uid']][0]
    out.append((f"رقم {num[s['uid']]}: سمل 300×1500", f"0.30 × {s['L']:.2f} × (‑7.35 − (‑8.45))", 0.30 * s['L'] * 1.10, r['V']))
    l = [x for x in M.lifts if 'CORE2' in x['ref']['label']][0]
    x0, y0, x1, y1 = l['poly'].bounds; w, h = (x1 - x0) / 1000, (y1 - y0) / 1000
    out.append((f"رقم {num[l['uid']]}: داخل كور 2 (أسانسير — مش بيتردم)", f"{w:.2f} × {h:.2f} × 0.40", w * h * 0.40, o[l['uid']]['V']))
    q = [x for x in M.sumps if x['uid'] == 'PIT3'][0]
    x0, y0, x1, y1 = q['poly'].bounds; w, h = (x1 - x0) / 1000, (y1 - y0) / 1000
    out.append((f"رقم {num['PIT3']}: حفرة صرف 3 (على المات ‑8.45 — مش بتتردم)", f"{w:.2f} × {h:.2f} × 1.10", w * h * 1.10, o['PIT3']['V']))
    return out


def write_excel(M, B, E, hc, path):
    wb = X.Workbook()
    # ---- الملخص
    s = X.Sheet(wb, "الملخص", [50, 16, 22], first=True)
    s.title("البند 1: حصر الردم الداخلي — البدروم السفلي")
    s.note(f"منسوب الردم {M.FILL:+.2f} = وش القاعدة اللي سمكها 1.50م (مقروء من بطاقة المنسوب المرسومة جوه القاعدة)، ومطابق لقاع التأسيس ‑8.85 + 1.50.")
    s.note(f"حدود الردم = الوش الداخلي للجدار المحيط: {M.D_dims[0]:.3f} × {M.D_dims[1]:.3f} م = {M.D.area/1e6:.2f} م². "
           "الجدار نفسه برّه الحدود فمفيش خصم ليه.")
    s.head(["البند", "م³", "التفصيل"])
    s.row(["الحجم القائم (كل مناطق وش اللبشة × ارتفاع الردم فوقها)", B['gross'], "ورقة التفصيل بالأرقام"], b=True)
    for k, nm in DED_AR:
        s.row([f"يُخصَم: {nm}", -B['by_kind'][k], "ورقة التفصيل بالأرقام"])
    s.total("الردم الصافي (مدموك في مكانه)", B['net'], col=2)
    s.total("بالهالك 5٪", B['net'] * WASTE, col=2, fill=X.GREY)
    s.gap()
    s.note(f"تحقق داخلي: نفس الصافي محسوب بطريقة المناطق (مساحة كل منطقة بعد الخصم × ارتفاعها) = {B['check']:.2f} م³.", fill=X.GREY)
    s.note("الأرقام في ورقة «التفصيل بالأرقام» هي نفس الأرقام المكتوبة على صورتي المراجعة (العربي والإنجليزي).", fill=X.YEL)
    # ---- التفصيل بالأرقام
    s = X.Sheet(wb, "التفصيل بالأرقام", [9, 52, 18, 11, 12, 11, 13, 20])
    s.title("الردم عنصر عنصر — الرقم = الرقم المكتوب على صورة المراجعة")
    s.note("الموجب = حجم قائم (المنطقة × ارتفاع الردم فوق وشّها). السالب = خصم (بصمة العنصر × ارتفاع الردم فوق الوش اللي تحته). "
           "السمل: الشريحة المرسومة × ظهره فوق المات ‑8.45. المجموع = الردم الصافي.")
    s.head(["رقم على اللوحة", "العنصر", "النوع", "الوش م", "المساحة م²", "الارتفاع م", "الحجم م³", "الموقع (م من 01 / A)"])
    rows = detail_rows(M, B, E)
    for r in rows:
        s.row(list(r), fill=(X.GRN if r[6] > 0 else None))
    s.total("الردم الصافي", sum(r[6] for r in rows), col=7)
    s.total("بالهالك 5٪", sum(r[6] for r in rows) * WASTE, col=7, fill=X.GREY)
    s.gap()
    s.head(["", "تفصيل الخزان", "", "", "المساحة م²", "", "الحجم م³", ""])
    for t in B['tank_split']:
        s.row(["", t['name'], "", "", t['A'], "", -t['V'], ""])
    # ---- حسب مناسيب اللبشة
    s = X.Sheet(wb, "حسب مناسيب اللبشة", [36, 11, 14, 16, 13, 12, 14])
    s.title("الردم مقسّم حسب منسوب وش اللبشة (بعد الخصم)")
    s.head(["المنطقة", "الوش م", "المساحة م²", "بصمات مخصومة م²", "الصافي م²", "الارتفاع م", "الردم م³"])
    agg = {}
    for z in B['zones']:
        k = round(z['top'], 2); a = agg.setdefault(k, [0, 0, 0, 0, z['h']])
        a[0] += z['A']; a[1] += z['Aobs']; a[2] += z['Anet']; a[3] += z['Vnet']
    names = {-8.45: "المات العام", -8.15: "قواعد 700 + سملات 700", -7.85: "قواعد 1000 + سملات 1000",
             -7.75: "قواعد 1100 + سملات 1100", -7.55: "قواعد 1300 + سملات 1300", -7.35: "قواعد 1500 + سمل 1500"}
    for k in sorted(agg):
        a = agg[k]; s.row([names.get(k, ''), k, a[0], a[1], a[2], a[4], a[3]])
    s.row(["يُخصَم: بلاطة رامب 03 تحت منسوب الردم", None, None, None, None, None, -B['wedge_V']])
    s.total("الردم الصافي", B['check'], col=7)
    # ---- مراجعة يدوية
    s = X.Sheet(wb, "مراجعة يدوية", [50, 40, 13, 13, 11])
    s.title("مراجعة يدوية — حساب مستقل من الأبعاد المرسومة مقابل السكريبت")
    s.head(["العنصر", "الحساب اليدوي", "يدوي", "السكريبت", "الفرق"])
    for nm, f, a, b in hc:
        s.row([nm, f, a, b, a - b])
    # ---- الفرضيات
    s = X.Sheet(wb, "الفرضيات والملاحظات", [28, 100])
    s.title("الفرضيات والملاحظات (من اللوحة وتعليمات المهندس)")
    for k, v in SC.notes(M):
        s.row([k, v])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    wb.save(path)
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--no-review", action="store_true")
    a = ap.parse_args(argv)
    logging.disable(logging.WARNING)
    doc = ezdxf.readfile(cc.DEFAULT_DXF)
    M = SM.Substructure(doc.modelspace())
    E = SC.elements(M); B = SC.backfill(M); hc = hand_checks(M, B, E)
    print(f"البند 1: الردم الداخلي — منسوب الردم {M.FILL:+.2f}")
    print(f"حدود الردم {M.D_dims[0]:.3f} × {M.D_dims[1]:.3f} = {M.D.area/1e6:.2f} م² | القائم {B['gross']:.2f} م³")
    for k, nm in DED_AR: print(f"  − {nm}: {B['by_kind'][k]:.2f}")
    print(f"الصافي {B['net']:.2f} م³ (تحقق بالمناطق {B['check']:.2f}) | بالهالك 5٪ = {B['net']*WASTE:.2f}")
    for nm, f, x, y in hc: print(f"  يدوي: {nm}: {x:.3f} | سكريبت {y:.3f}")
    p = write_excel(M, B, E, hc, os.path.join(OUT, "حصر الردم الداخلي - البدروم السفلي.xlsx")); print("SAVED:", p)
    if not a.no_review:
        print("SAVED:", FR.backfill_png(M, B, E, 'ar', os.path.join(OUT, "مراجعة الردم - البدروم السفلي (عربي).png")))
        print("SAVED:", FR.backfill_png(M, B, E, 'en', os.path.join(OUT, "Backfill review - Lower basement (English).png")))
        for f in FR.review_dxf(doc, M, E, 'fill', B, os.path.join(OUT, "مراجعة الردم - البدروم السفلي.dxf")): print("SAVED:", f)
    return M, B


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace"); main()
