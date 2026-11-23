# -*- coding: utf-8 -*-
"""
البند 2: حصر العزل بالدهان (م²) — Muttajah Mall، البدروم السفلي. كله لحد منسوب الردم بالظبط. (v3 — ترقيم موحّد)

دهان → مفيش ركوب ومفيش خصم سُمك من الردم. نفس النموذج والعناصر اللي في حصر الردم.
  أفقي: ظهر المات + القواعد + السملات − بصمات الأعمدة/الأكوار/الخزان/البادئ − قاع الحفر (بند لوحده).
  جوانب القواعد والسملات المكشوفة؛ رقاب الأعمدة؛ الأكوار من كل الجوانب؛ الوش الداخلي للجدار المحيط؛
  الخزان من برّه بس؛ بادئا الرامب؛ قاع بلاطة رامب 03 تحت الردم؛ الحفر (3 صرف + 2 أسانسير): قاع + جوانب بعمق 0.50م مفترض.
  أبواب كوري السلالم تبدأ ‑7.25 (فوق الردم) → خصم صفر.
الإكسل عربي بالكامل؛ عمود «رقم على اللوحة» = الرقم المكتوب على صورتي المراجعة (عربي/إنجليزي) والـDXF.
الاستخدام: python insulation_takeoff.py [--no-review] [--pit-depth 0.50]
"""
import sys, os, argparse, logging
import ezdxf
import concrete_columns_takeoff as cc
import substructure_model as SM, substructure_calc as SC, substructure_xl as X
import foundation_review as FR

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "output")
WASTE = 1.05
T_AR = [('h_mat', "أفقي: ظهر المات العام ‑8.45"), ('h_foot', "أفقي: ظهر القواعد المُثخّنة"),
        ('h_beam', "أفقي: ظهر السملات"), ('s_foot', "جوانب القواعد"), ('s_beam', "جوانب السملات"),
        ('col', "رقاب الأعمدة"), ('core', "الأكوار (برّه وجوّه)"), ('perim', "الوش الداخلي للجدار المحيط"),
        ('tank', "الخزان (الوش الخارجي بس)"), ('starter', "بادئا الرامب (كل الأوجه المكشوفة)"),
        ('wedge', "قاع بلاطة رامب 03 تحت منسوب الردم"),
        ('pit_bottom', "الحفر (3 صرف + 2 أسانسير): القاع الداخلي"), ('pit_sides', "الحفر: الجوانب الداخلية (عمق 0.50م مفترض)"),
        ('doors', "خصم أبواب كوري السلالم تحت منسوب الردم")]
KIND_AR = {'mat': 'منطقة لبشة', 'footing': 'قاعدة', 'beam': 'سمل', 'column': 'رقبة عمود', 'core': 'كور', 'tank': 'خزان',
           'starter': 'بادئ رامب', 'lift': 'حفرة أسانسير', 'sump': 'حفرة صرف', 'perim': 'الجدار المحيط', 'wedge': 'بلاطة رامب'}


def detail_rows(M, I, E):
    """(رقم، العنصر، النوع، أفقي، رأسي/جوانب، الإجمالي، الطول المكشوف، الارتفاع من–إلى، ملاحظة)"""
    h = {r['uid']: r for r in I['horiz']}; sd = {r['uid']: r for r in I['sides']}; v = {r['uid']: r for r in I['vert']}
    pe = {r['uid']: r for r in I['perim']}; pt = {r['uid']: r for r in I['pits']}
    rng = lambda r: f"{r['rng'][0]:.2f} – {r['rng'][1]:.2f}" if r['rng'][1] > 0 else "—"
    rows = []
    for e in E:
        u = e['uid']; nm = e['ar']; kd = KIND_AR[e['kind']]
        if u in h:
            hh = h[u]['Anet']; s = sd.get(u)
            vv = s['A'] if s else 0.0
            note = "ظهر − بصمات العناصر فوقه" + (f" − قاع الحفر" if e['kind'] in ('mat', 'footing') else '')
            rows.append((e['no'], nm, kd, hh, vv, hh + vv, s['L'] if s else None, rng(s) if s else "—", note))
        elif u in v:
            r = v[u]
            note = {'column': "محيط العمود المكشوف", 'core': "برّه + جوّه", 'tank': "الوش الخارجي بس",
                    'starter': "الأوجه المكشوفة"}.get(e['kind'], '')
            rows.append((e['no'], nm, kd, 0.0, r['A'], r['A'], r['P'], rng(r), note))
        elif u in pt:
            q = pt[u]
            rows.append((e['no'], nm, kd, q['A_bot'], q['A_side'], q['A_bot'] + q['A_side'], q['P'],
                         f"عمق {q['depth']:.2f}", f"داخلي {q['w']:.2f}×{q['l']:.2f}، القاع {q['bottom']:+.2f} (عمق مفترض)"))
        elif u in pe:
            r = pe[u]
            rows.append((e['no'], nm, kd, 0.0, r['A'], r['A'], r['L'], rng(r), "من وش اللبشة جنبه لحد منسوب الردم"))
        elif e['kind'] == 'wedge':
            V, A, Lw = I['wedge']['RAMP 03']
            rows.append((e['no'], nm, kd, A, 0.0, A, Lw, "—", "قاع مائل 7.5٪ تحت منسوب الردم"))
    return rows


def hand_checks(M, I, E):
    F = M.FILL; out = []; num = {e['uid']: e['no'] for e in E}
    v = {r['uid']: r for r in I['vert']}
    k = [x for x in M.obs if x['kind'] == 'core' and 'شمالي' in x['name']][0]
    x0, y0, x1, y1 = k['poly'].bounds; W, H = (x1 - x0) / 1000, (y1 - y0) / 1000
    out.append((f"رقم {num[k['uid']]}: كور 3 شمالي — برّه وجوّه", f"[2×({W:.1f}+{H:.1f}) + 2×({W-0.6:.1f}+{H-0.6:.1f})] × 0.40",
                (2 * (W + H) + 2 * (W - 0.6 + H - 0.6)) * (F + 7.75), v[k['uid']]['A']))
    e = [p for p in I['perim'] if p['uid'] == 'PER:E'][0]
    L700 = sum((f['poly'].bounds[3] - f['poly'].bounds[1]) / 1000 for f in M.footings if f['th'] == 700)
    Le = M.D_dims[1]
    out.append((f"رقم {num['PER:E']}: الحائط الشرقي — الوش الداخلي", f"({Le:.2f} − {L700:.1f}) × 1.10 + {L700:.1f} × 0.80",
                (Le - L700) * 1.10 + L700 * 0.80, e['A']))
    c = [x for x in M.obs if x['kind'] == 'column' and x['ref']['no'] == 44][0]
    x0, y0, x1, y1 = c['poly'].bounds; w, h = (x1 - x0) / 1000, (y1 - y0) / 1000
    out.append((f"رقم {num[c['uid']]}: رقبة عمود C8", f"2×({w:.2f}+{h:.2f}) × 0.40", 2 * (w + h) * 0.40, v[c['uid']]['A']))
    s = [x for x in M.beams if x['d'] == 1500][0]; r = [x for x in I['sides'] if x['uid'] == s['uid']][0]
    out.append((f"رقم {num[s['uid']]}: جوانب سمل 300×1500", f"2 × {s['L']:.2f} × 1.10", 2 * s['L'] * 1.10, r['A']))
    q = [x for x in I['pits'] if x['kind'] == 'lift' and 'CORE2' in x['uid']][0]
    out.append((f"رقم {num[q['uid']]}: حفرة أسانسير كور 2 (قاع + جوانب)", f"{q['w']:.2f}×{q['l']:.2f} + 2×({q['w']:.2f}+{q['l']:.2f})×{q['depth']:.2f}",
                q['w'] * q['l'] + 2 * (q['w'] + q['l']) * q['depth'], q['A_bot'] + q['A_side']))
    return out


def write_excel(M, I, E, hc, path):
    wb = X.Workbook(); t = I['totals']
    s = X.Sheet(wb, "الملخص", [52, 16, 22], first=True)
    s.title("البند 2: حصر العزل بالدهان — البدروم السفلي")
    s.note(f"كله لحد منسوب الردم {M.FILL:+.2f} بالظبط (وش القاعدة اللي سمكها 1.50م). دهان: مفيش ركوب ولا خصم سُمك من الردم.")
    s.note("الخزان من جوّه مش بيتعزل (ومعاه العمودين اللي جوّاه). مفيش عزل تحت أي عنصر رأسي. كوري السلالم من برّه ومن جوّه.")
    s.head(["نوع السطح", "م²", "التفصيل"])
    for k, nm in T_AR:
        s.row([nm, t[k], "ورقة التفصيل بالأرقام"])
    s.total("إجمالي العزل (صافي)", I['total'], col=2)
    s.total("بالهالك 5٪", I['total'] * WASTE, col=2, fill=X.GREY)
    s.gap()
    s.head(["تجميع", "م²", ""])
    s.row(["أفقي (ظهر المات والقواعد والسملات + قاع الحفر + قاع رامب 03)", t['h_mat'] + t['h_foot'] + t['h_beam'] + t['pit_bottom'] + t['wedge'], ""])
    s.row(["جوانب القواعد والسملات", t['s_foot'] + t['s_beam'], ""])
    s.row(["رأسي (رقاب + أكوار + الجدار المحيط + الخزان + البادئين + جوانب الحفر)",
           t['col'] + t['core'] + t['perim'] + t['tank'] + t['starter'] + t['pit_sides'], ""])
    s.note("الأرقام في ورقة «التفصيل بالأرقام» هي نفس الأرقام المكتوبة على صورتي المراجعة (العربي والإنجليزي).", fill=X.YEL)
    # ---- التفصيل
    s = X.Sheet(wb, "التفصيل بالأرقام", [9, 50, 15, 12, 13, 13, 13, 14, 34])
    s.title("العزل عنصر عنصر — الرقم = الرقم المكتوب على صورة المراجعة")
    s.note("أفقي = الظهر المعزول (أو قاع الحفرة). رأسي = الجوانب/الأوجه من وش اللبشة جنبها لحد منسوب الردم. "
           "الطول المكشوف = طول الحافة اللي عليها عزل (من غير الملاصق لعنصر رأسي).")
    s.head(["رقم على اللوحة", "العنصر", "النوع", "أفقي م²", "رأسي / جوانب م²", "الإجمالي م²", "الطول المكشوف م", "الارتفاع م", "ملاحظة"])
    rows = detail_rows(M, I, E)
    for r in rows:
        s.row(list(r))
    s.row(["", "أبواب كوري السلالم (2)", "خصم", 0.0, t['doors'], t['doors'], None, "—",
           f"الباب يبدأ {I['sill']:+.2f} = فوق منسوب الردم → صفر"])
    s.total("إجمالي العزل", sum(r[5] for r in rows) + t['doors'], col=6)
    s.total("بالهالك 5٪", (sum(r[5] for r in rows) + t['doors']) * WASTE, col=6, fill=X.GREY)
    # ---- مراجعة يدوية
    s = X.Sheet(wb, "مراجعة يدوية", [48, 52, 12, 12, 10])
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
    ap.add_argument("--pit-depth", type=float, default=SC.PIT_DEPTH, help="عمق الحفر اللي عمقها مش مرسوم (م) — افتراضي 0.50")
    a = ap.parse_args(argv)
    logging.disable(logging.WARNING)
    doc = ezdxf.readfile(cc.DEFAULT_DXF)
    M = SM.Substructure(doc.modelspace())
    E = SC.elements(M); I = SC.insulation(M, a.pit_depth); hc = hand_checks(M, I, E)
    rows = detail_rows(M, I, E)
    print(f"البند 2: العزل بالدهان — لحد منسوب الردم {M.FILL:+.2f}")
    for k, nm in T_AR: print(f"  {nm}: {I['totals'][k]:.2f}")
    print(f"إجمالي العزل {I['total']:.2f} م² (مجموع التفصيل {sum(r[5] for r in rows) + I['totals']['doors']:.2f}) | بالهالك 5٪ = {I['total']*WASTE:.2f}")
    for nm, f, x, y in hc: print(f"  يدوي: {nm}: {x:.3f} | سكريبت {y:.3f}")
    p = write_excel(M, I, E, hc, os.path.join(OUT, "حصر العزل بالدهان - البدروم السفلي.xlsx")); print("SAVED:", p)
    if not a.no_review:
        print("SAVED:", FR.insulation_png(M, I, E, 'ar', os.path.join(OUT, "مراجعة العزل - البدروم السفلي (عربي).png")))
        print("SAVED:", FR.insulation_png(M, I, E, 'en', os.path.join(OUT, "Insulation review - Lower basement (English).png")))
        for f in FR.review_dxf(doc, M, E, 'ins', I, os.path.join(OUT, "مراجعة العزل - البدروم السفلي.dxf")): print("SAVED:", f)
    return M, I


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace"); main()
