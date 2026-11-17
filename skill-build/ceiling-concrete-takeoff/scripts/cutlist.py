# -*- coding: utf-8 -*-
"""
تفريد الحديد (rebar cutting) — منهج التتالي حسب المقاس (طريقة الحدّاد):
  • رتّب المقاسات تنازلياً. لكل مقاس: نقطع من السيخ (12م) أكبر عدد ممكن (12÷المقاس)،
    فيتبقّى طول قصير من كل سيخ.
  • هذا المتبقّي يُحسب لصالح المقاس الأصغر المساوي له، فلا نقطع منه سيخاً جديداً.
    مثال: 200 قطعة Ø16 طول 4.5 → قطعتان/سيخ = 100 سيخ، ويتبقّى 100 قطعة 3م
    تُستعمَل لتغطية طلب الـ3م.

خالٍ من مكتبات CAD — يحتاج openpyxl فقط.

الاستخدام:
  python cutlist.py "<pieces.json>"
  python cutlist.py "<pieces.json>" --lap 60 --include-mesh
"""
import argparse, os, json, math, collections

DEF_STOCK = 12000     # مم — طول السيخ القياسي في مصر
LAP_MIN = 1000        # مم — أدنى طول وصلة (حدّ عملي حدّده المهندس: ١ متر)


def unit_weight(d_mm):
    """الوزن النوعي كجم/م = قطر²/162."""
    return d_mm * d_mm / 162.0


def _normalize(pieces):
    """يقبل {قطر:{طول:عدد}} أو قائمة [{diameter,length_mm,count}] → {قطر:{طول:عدد}}."""
    if isinstance(pieces, dict):
        return {int(d): {int(L): int(c) for L, c in v.items()} for d, v in pieces.items()}
    norm = collections.defaultdict(lambda: collections.defaultdict(int))
    for p in pieces:
        norm[int(p["diameter"])][int(p["length_mm"])] += int(p["count"])
    return {d: dict(v) for d, v in norm.items()}


def presplit_long(demand, stock, lap_mm):
    """يقسّم كل قطعية طولها > stock إلى (m-1) سيخ كامل + بقية تُعاد للطلب.
    يعيد (بقية_الطلب، أسياخ_كاملة، سجل_الوصلات)."""
    residual = collections.defaultdict(int); full_bars = 0; log = []
    for L, cnt in demand.items():
        L = int(L); cnt = int(cnt)
        if L <= stock:
            residual[L] += cnt; continue
        m = math.ceil((L - lap_mm) / (stock - lap_mm))
        r = L - (m - 1) * (stock - lap_mm)
        full_bars += (m - 1) * cnt
        if r > 0:
            residual[int(round(r))] += cnt
        log.append(dict(L=L, cnt=cnt, bars=m, splices=m - 1, remainder=int(round(r)), lap=int(lap_mm)))
    return dict(residual), full_bars, log


def cascade_cut(demand, stock):
    """التتالي حسب المقاس مع إظهار مصير كل متبقٍّ. demand = {طول:عدد}.
    الأكبر أولاً؛ متبقّي كل سيخ يُقطع لأقرب مقاسات أصغر (الأكبر أولاً = أقل هدر) وتُحسب تلك
    القطع مع طلب تلك المقاسات؛ ما تبقّى قطعةً كاملة قابلة للاستخدام = فائض، والكسر الصغير = هدر.
    يعيد (صفوف، إجمالي_الأسياخ، الفائض_الكلي{طول:عدد}، الهدر_مم).
    كل صف: {L, need, received, per_bar, bars, offcuts{طول:عدد}, placed{مقاس:عدد}, surplus{طول:عدد}, waste_mm}."""
    demand = {int(L): int(c) for L, c in demand.items() if int(L) > 0 and int(c) > 0}
    if not demand:
        return [], 0, {}, 0
    sizes = sorted(demand, reverse=True)     # تنازلي
    min_size = sizes[-1]
    need = dict(demand)                      # المتبقّي المطلوب توفيره لكل مقاس
    received = collections.defaultdict(int)  # كم قطعة تلقّاها مقاسٌ من متبقّي الأكبر
    tot_surplus = collections.defaultdict(int); tot_waste = collections.defaultdict(int)

    def dispose(length, cur):
        """يقطع من قطعة متبقّية طولها length قطعاً لمقاسات أصغر من cur (الأكبر أولاً = أقل هدر).
        يعيد (placed{مقاس:عدد}, surplus{طول:عدد قطع كاملة}, waste{طول الكسر:عدد})."""
        placed = collections.defaultdict(int); rem = length
        while True:
            s = next((x for x in sizes if x < cur and x <= rem and need.get(x, 0) > 0), None)
            if s is None: break
            need[s] -= 1; received[s] += 1; placed[s] += 1; rem -= s
        if rem >= min_size:                  # بقيت قطعة كاملة قابلة للاستخدام (لا طلب لها الآن)
            return dict(placed), {rem: 1}, {}
        if rem > 0:
            return dict(placed), {}, {rem: 1}  # كسر أصغر من أصغر مقاس = هدر
        return dict(placed), {}, {}

    rows = []
    for L in sizes:
        n = need[L]                           # بعد ما استُهلك من متبقّي الأكبر
        per_bar = stock // L if L <= stock else 0
        bars = math.ceil(n / per_bar) if (n > 0 and per_bar >= 1) else 0
        offcuts = collections.defaultdict(int); placed = collections.defaultdict(int)
        row_surplus = collections.defaultdict(int); row_waste = collections.defaultdict(int)
        if bars > 0:
            full = n // per_bar; rem_p = n - full * per_bar
            lo_full = stock - per_bar * L
            pieces = ([lo_full] * full if lo_full > 0 else []) \
                     + ([stock - rem_p * L] if (rem_p > 0 and (stock - rem_p * L) > 0) else [])
            for lo in pieces:
                offcuts[lo] += 1
                pl, sp, w = dispose(lo, L)
                for s, c in pl.items(): placed[s] += c
                for l, c in sp.items(): row_surplus[l] += c; tot_surplus[l] += c
                for l, c in w.items(): row_waste[l] += c; tot_waste[l] += c
        rows.append(dict(L=L, need=demand[L], received=received[L], per_bar=per_bar, bars=bars,
                         offcuts=dict(offcuts), placed=dict(placed),
                         surplus=dict(row_surplus), waste=dict(row_waste),
                         waste_mm=sum(l * c for l, c in row_waste.items())))
    total_bars = sum(r["bars"] for r in rows)
    return rows, total_bars, dict(tot_surplus), dict(tot_waste)


def optimize(pieces, stock_mm=DEF_STOCK, lap_by_dia=None, lap_mult=60, prio_w=None):
    """المدخل الأعلى. pieces = {قطر:{طول:عدد}} أو قائمة. يعيد {قطر: نتائج}."""
    norm = _normalize(pieces)
    out = {}
    for d in sorted(norm):
        demand = {int(L): int(c) for L, c in norm[d].items() if L and c}
        if not demand:
            continue
        lap = int((lap_by_dia or {}).get(d, lap_mult * d)); lap = max(lap, LAP_MIN)
        residual, full_bars, splice_log = presplit_long(demand, stock_mm, lap)
        rows, cascade_bars, surplus, waste = cascade_cut(residual, stock_mm)
        stock_bars = full_bars + cascade_bars
        total_len_m = sum(L * c for L, c in demand.items()) / 1000.0
        surplus_mm = sum(l * c for l, c in surplus.items())
        waste_mm = sum(l * c for l, c in waste.items())
        total_splices = sum(s["splices"] * s["cnt"] for s in splice_log)
        weight_kg = stock_bars * (stock_mm / 1000.0) * unit_weight(d)
        # الفاقد = فائض قابل للاستخدام + هدر فعلي؛ النسبة على الفاقد الكلي
        loss_mm = surplus_mm + waste_mm
        waste_pct = (loss_mm / (stock_bars * stock_mm) * 100.0) if stock_bars else 0.0
        out[d] = dict(rows=rows, surplus=surplus, waste=waste, surplus_mm=surplus_mm, waste_mm=waste_mm,
                      loss_mm=loss_mm, splice_log=splice_log,
                      stock_bars=stock_bars, full_bars=full_bars, cascade_bars=cascade_bars,
                      total_splices=total_splices, total_len_m=total_len_m, n_pieces=sum(demand.values()),
                      waste_pct=waste_pct, weight_kg=weight_kg, lap_mm=lap, no_lap_flag=(d > 32),
                      demand=dict(demand))
    return out


def _fmt_pieces(dct):
    """{3000:132} → '132 قطعة بطول 3م' (تنازلياً بالطول)."""
    if not dct: return "—"
    return " + ".join(f"{dct[L]} قطعة بطول {L/1000:g}م" for L in sorted(dct, reverse=True))

def _fate_str(x):
    """وصف مصير متبقّي مقاسٍ: 'ينتج N×Lم → M لمقاس Sم + فائض … + هدر …م'."""
    if not x["offcuts"]: return "—"
    tail = []
    if x["placed"]:
        tail.append("يُقطع " + " ، ".join(f"{c} لمقاس {s/1000:g}م"
                                          for s, c in sorted(x["placed"].items(), reverse=True)))
    if x["surplus"]:
        tail.append("فائض " + _fmt_pieces(x["surplus"]))
    if x.get("waste"):
        tail.append("هدر " + _fmt_pieces(x["waste"]))
    return _fmt_pieces(x["offcuts"]) + (" → " + " + ".join(tail) if tail else "")


def load_pieces(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    meta = dict(ceiling=data.get("ceiling", ""), stock_length_mm=data.get("stock_length_mm", DEF_STOCK),
                unknown_length=data.get("unknown_length", []), mesh=data.get("mesh", []))
    return data.get("pieces", []), meta


# ------------------------------- Excel -------------------------------
def write_cutlist_xlsx(result, meta, out_path, include_mesh=False):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    NAVY, BLUE, LT, GREY, GRN, RED = "1F3864", "2E5496", "D9E1F2", "F2F2F2", "E2EFDA", "F8CBAD"
    thin = Side(style="thin", color="BFBFBF"); bd = Border(thin, thin, thin, thin)
    wb = Workbook()

    def st(c, *, b=False, sz=11, color="000000", fill=None, ha="center", wrap=False):
        c.font = Font(bold=b, size=sz, color=color); c.alignment = Alignment(ha, "center", wrap_text=wrap)
        if fill: c.fill = PatternFill("solid", fgColor=fill)
        c.border = bd

    ttl = meta.get("ceiling", "") or "تفريد الحديد"
    stock = meta.get("stock_length_mm", DEF_STOCK)
    dias = sorted(result)

    # ---- Sheet 1: summary ----
    ws = wb.active; ws.title = "ملخص التفريد"; ws.sheet_view.rightToLeft = True
    ws.merge_cells("A1:H1"); st(ws["A1"], b=True, sz=14, color="FFFFFF", fill=NAVY)
    ws["A1"] = f"جدول تفريد الحديد — {ttl}"
    ws.merge_cells("A2:H2"); st(ws["A2"], sz=9, color="FFFFFF", fill=BLUE)
    ws["A2"] = (f"سيخ قياسي {stock/1000:g}م | التتالي حسب المقاس: متبقّي كل سيخ يُقطع لأقرب مقاس أصغر (أقل هدر) | "
                f"الفائض = قطع كاملة قابلة للاستخدام، الهدر = كسر أصغر من أصغر مقاس")
    hdr = ["القطر", "عدد القطع", "أسياخ 12م", "عدد الوصلات",
           "فائض قابل للاستخدام (م)", "هدر فعلي (م)", "نسبة الفاقد ٪", "الوزن الكلي (كجم)"]
    for j, h in enumerate(hdr, 1): st(ws.cell(4, j, h), b=True, fill=NAVY, color="FFFFFF")
    r = 5; tb = ts = twa = twt = tp = 0
    for d in dias:
        R = result[d]; wp = R["waste_pct"]
        wpfill = GRN if wp <= 3 else (RED if wp > 5 else None)
        st(ws.cell(r, 1, f"Ø{d}"), b=True, fill=LT)
        st(ws.cell(r, 2, R["n_pieces"])); st(ws.cell(r, 3, R["stock_bars"]), b=True)
        st(ws.cell(r, 4, R["total_splices"] or None))
        st(ws.cell(r, 5, round(R["surplus_mm"] / 1000.0, 1))); st(ws.cell(r, 6, round(R["waste_mm"] / 1000.0, 1)))
        st(ws.cell(r, 7, round(wp, 1)), b=True, fill=wpfill); st(ws.cell(r, 8, round(R["weight_kg"])))
        tb += R["stock_bars"]; ts += R["surplus_mm"]; twa += R["waste_mm"]; twt += R["weight_kg"]; tp += R["n_pieces"]; r += 1
    st(ws.cell(r, 1, "الإجمالي"), b=True, fill=NAVY, color="FFFFFF")
    st(ws.cell(r, 2, tp), b=True, fill=LT); st(ws.cell(r, 3, tb), b=True, fill=LT)
    st(ws.cell(r, 4, None), fill=LT); st(ws.cell(r, 5, round(ts / 1000.0, 1)), fill=LT); st(ws.cell(r, 6, round(twa / 1000.0, 1)), fill=LT)
    st(ws.cell(r, 7, None), fill=LT); st(ws.cell(r, 8, f"{round(twt)} ({round(twt/1000.0,2)} طن)"), b=True, fill=LT)
    r += 2
    if include_mesh and meta.get("mesh"):
        ws.merge_cells(f"A{r}:H{r}")
        st(ws.cell(r, 1, "◄ الشبكة (فرش وغطاء) — أسياخ 12م كاملة، خارج التفريد"), b=True, color="FFFFFF", fill=BLUE, ha="right"); r += 1
        for m in meta["mesh"]:
            st(ws.cell(r, 1, f"Ø{m['diameter']}"), b=True, fill=LT); st(ws.cell(r, 3, m.get("full_bars_12m")), b=True)
            ws.merge_cells(f"E{r}:H{r}"); st(ws.cell(r, 5, m.get("spec", "")), ha="right"); r += 1
    if meta.get("unknown_length"):
        ws.merge_cells(f"A{r}:H{r}")
        note = "، ".join(f"Ø{u['diameter']}: {u['count']}" for u in meta["unknown_length"])
        st(ws.cell(r, 1, f"⚠ قطع بلا طول L= (لم تُفرَّد، للمراجعة): {note}"), sz=9, fill=RED, ha="right")
    ws.column_dimensions["A"].width = 9
    for cc in "BCDEFGH": ws.column_dimensions[cc].width = 15

    # ---- Sheet 2: cut table by size (جدول التفريد) ----
    ws2 = wb.create_sheet("جدول التفريد"); ws2.sheet_view.rightToLeft = True
    ws2.merge_cells("A1:G1"); st(ws2["A1"], b=True, sz=13, color="FFFFFF", fill=NAVY)
    ws2["A1"] = "التفريد حسب المقاس — كل مقاس: كم قطعة، كم تُقطع من السيخ، كم سيخاً، وماذا يُفعل بالمتبقّي"
    h2 = ["القطر", "المقاس / الطول (م)", "عدد القطع", "قطع لكل سيخ 12م",
          "مأخوذ من متبقٍّ أكبر", "عدد أسياخ 12م", "المتبقّي وما يُقطع منه"]
    for j, h in enumerate(h2, 1): st(ws2.cell(3, j, h), b=True, fill=NAVY, color="FFFFFF")
    r = 4
    for d in dias:
        R = result[d]
        for x in R["rows"]:
            reused = (x["bars"] == 0 and x["received"] > 0)
            st(ws2.cell(r, 1, f"Ø{d}"), b=True, fill=LT)
            st(ws2.cell(r, 2, round(x["L"] / 1000.0, 2)))
            st(ws2.cell(r, 3, x["need"]))
            st(ws2.cell(r, 4, x["per_bar"] or None))
            st(ws2.cell(r, 5, x["received"] or None), fill=(GRN if x["received"] else None))
            st(ws2.cell(r, 6, x["bars"] or None), b=True, fill=(GRN if reused else None))
            st(ws2.cell(r, 7, _fate_str(x)), ha="right")
            r += 1
        st(ws2.cell(r, 1, f"مجموع Ø{d}"), b=True, fill=GREY); st(ws2.cell(r, 2, None), fill=GREY)
        st(ws2.cell(r, 3, R["n_pieces"]), fill=GREY); st(ws2.cell(r, 4, None), fill=GREY)
        st(ws2.cell(r, 5, None), fill=GREY); st(ws2.cell(r, 6, R["stock_bars"]), b=True, fill=GREY)
        tot_txt = f"فائض {round(R['surplus_mm']/1000.0,1)}م + هدر {round(R['waste_mm']/1000.0,1)}م"
        st(ws2.cell(r, 7, tot_txt), fill=GREY, sz=9, ha="right"); r += 1
    ws2.column_dimensions["A"].width = 9
    ws2.column_dimensions["B"].width = 14; ws2.column_dimensions["G"].width = 46
    for cc in "CDEF": ws2.column_dimensions[cc].width = 14
    ws2.freeze_panes = "A4"

    # ---- Sheet 3: waste / surplus details (تفاصيل الفائض والهدر) ----
    ws4 = wb.create_sheet("تفاصيل الفائض والهدر"); ws4.sheet_view.rightToLeft = True
    ws4.merge_cells("A1:F1"); st(ws4["A1"], b=True, sz=13, color="FFFFFF", fill=NAVY)
    ws4["A1"] = "تفاصيل الفائض والهدر — الأطوال والمقاسات والأوزان لكل قطر"
    for j, h in enumerate(["القطر", "النوع", "الطول (م)", "عدد القطع", "إجمالي الطول (م)", "الوزن (كجم)"], 1):
        st(ws4.cell(3, j, h), b=True, fill=NAVY, color="FFFFFF")
    r = 4; g_len = 0.0; g_wt = 0.0
    for d in dias:
        R = result[d]; uw = unit_weight(d); sub_len = 0.0; sub_wt = 0.0
        items = ([("فائض", L, c, GRN) for L, c in sorted(R["surplus"].items(), reverse=True)]
                 + [("هدر", L, c, RED) for L, c in sorted(R["waste"].items(), reverse=True)])
        if not items:
            st(ws4.cell(r, 1, f"Ø{d}"), b=True, fill=LT)
            ws4.merge_cells(f"B{r}:F{r}"); st(ws4.cell(r, 2, "بلا فائض أو هدر"), fill=GREY, sz=9); r += 1
            continue
        for typ, L, c, col in items:
            ln = L * c / 1000.0; wt = ln * uw
            st(ws4.cell(r, 1, f"Ø{d}"), b=True, fill=LT); st(ws4.cell(r, 2, typ), fill=col)
            st(ws4.cell(r, 3, round(L / 1000.0, 2))); st(ws4.cell(r, 4, c))
            st(ws4.cell(r, 5, round(ln, 1))); st(ws4.cell(r, 6, round(wt, 1)))
            sub_len += ln; sub_wt += wt; r += 1
        st(ws4.cell(r, 1, f"مجموع Ø{d}"), b=True, fill=GREY); st(ws4.cell(r, 2, None), fill=GREY)
        st(ws4.cell(r, 3, None), fill=GREY); st(ws4.cell(r, 4, None), fill=GREY)
        st(ws4.cell(r, 5, round(sub_len, 1)), b=True, fill=GREY); st(ws4.cell(r, 6, round(sub_wt, 1)), b=True, fill=GREY)
        g_len += sub_len; g_wt += sub_wt; r += 1
    st(ws4.cell(r, 1, "الإجمالي"), b=True, fill=NAVY, color="FFFFFF")
    for cc in (2, 3, 4): st(ws4.cell(r, cc, None), fill=LT)
    st(ws4.cell(r, 5, round(g_len, 1)), b=True, fill=LT); st(ws4.cell(r, 6, f"{round(g_wt)} كجم"), b=True, fill=LT)
    ws4.column_dimensions["A"].width = 9
    for cc in "BCDEF": ws4.column_dimensions[cc].width = 16
    ws4.freeze_panes = "A4"

    # ---- Sheet 4: splices (only if any) ----
    if any(result[d]["splice_log"] for d in dias):
        ws3 = wb.create_sheet("الوصلات"); ws3.sheet_view.rightToLeft = True
        h3 = ["القطر", "الطول المطلوب (م)", "العدد", "أسياخ 12م/سيخ", "عدد الوصلات",
              "طول الوصلة (مم)", "البقية (م)", "ملاحظة"]
        for j, h in enumerate(h3, 1): st(ws3.cell(1, j, h), b=True, fill=NAVY, color="FFFFFF")
        r = 2
        for d in dias:
            for s in result[d]["splice_log"]:
                flag = "لا يُسمح بوصلة تراكب — لحام/ميكانيكي" if d > 32 else ""
                for j, v in enumerate([f"Ø{d}", round(s["L"]/1000.0, 2), s["cnt"], s["bars"],
                                       s["splices"], s["lap"], round(s["remainder"]/1000.0, 2), flag], 1):
                    st(ws3.cell(r, j, v), fill=(RED if (j == 8 and flag) else None))
                r += 1
        ws3.column_dimensions["A"].width = 9
        for cc in "BCDEFG": ws3.column_dimensions[cc].width = 14
        ws3.column_dimensions["H"].width = 30

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    wb.save(out_path)
    return out_path


def cut_from_takeoff(add_piv, meta, out_path, stock_mm=DEF_STOCK, lap_mult=60,
                     prio_w=None, include_mesh=False, **_):
    result = optimize(add_piv, stock_mm=stock_mm, lap_mult=lap_mult)
    return result, write_cutlist_xlsx(result, meta, out_path, include_mesh=include_mesh)


def _print_summary(result):
    print("\n=== تفريد الحديد (تتالي حسب المقاس) ===")
    for d in sorted(result):
        R = result[d]
        print(f"  Ø{d}: {R['stock_bars']} سيخ 12م | فائض {R['surplus_mm']/1000.0:.1f}م "
              f"| هدر {R['waste_mm']/1000.0:.1f}م | وزن {round(R['weight_kg'])} كجم")
        for x in R["rows"]:
            recv = f" (منها {x['received']} من متبقٍّ أكبر)" if x["received"] else ""
            print(f"       {x['L']/1000:g}م: {x['need']} قطعة → {x['per_bar']}/سيخ → {x['bars']} سيخ"
                  f"{recv} | متبقٍّ: {_fate_str(x)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pieces_json")
    ap.add_argument("--stock", type=int, default=DEF_STOCK, help="طول السيخ القياسي (مم)")
    ap.add_argument("--lap", type=int, default=60, help="مضاعف طول الوصلة (×القطر) للأسياخ >12م")
    ap.add_argument("--include-mesh", action="store_true", help="أظهِر الشبكة في الملخص")
    ap.add_argument("--out", help="مسار ملف الإكسل (اختياري)")
    args = ap.parse_args()
    pieces, meta = load_pieces(args.pieces_json)
    meta["stock_length_mm"] = args.stock
    result = optimize(pieces, stock_mm=args.stock, lap_mult=args.lap)
    _print_summary(result)
    if args.out:
        out = args.out
    else:
        d = os.path.dirname(args.pieces_json)
        stem = os.path.basename(args.pieces_json).replace(" - pieces.json", "").replace(".json", "")
        out = os.path.join(d, stem + " - CUTLIST.xlsx")
    write_cutlist_xlsx(result, meta, out, include_mesh=args.include_mesh)
    print("\nSAVED:", out)


if __name__ == "__main__":
    main()
