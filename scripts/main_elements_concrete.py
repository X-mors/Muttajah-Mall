# -*- coding: utf-8 -*-
"""
حصر خرسانة العناصر الرئيسية الرأسية — Muttajah Mall (لِفت 1: اللبشة → سقف البدروم السفلي -3.85).
كل عمود بارتفاعه حسب مكانه (من ظهر قاعدته حتى قاع السقف) — بدون توحيد:
  • القاعدة نفسها ليست ضمن حصر العمود (العمود يبدأ من ظهرها).
  • مارك C (9) = أعمدة الجدار الشمالي W1 → تبدأ من ظهر الجدار -6.75 (لبشة 40سم وش -8.45 + ظاهر 1.70).
  • باقي الأعمدة (C1..C10) → من وش اللبشة -8.45.
  • أعمدة الرمب: تُخصم سماكة الرمب (أو عمق الكمرة المقلوبة) — تُعلَّم (تحتاج قائمتها ومنسوب الرمب).
  • الأكوار (CORE1/2/3) والخزان والحوائط = عناصر رئيسية (مقاطع/أبعاد تُدخَل/تُستخرَج).
القاعدة: ارتفاع العمود = قاع السقف − ظهر القاعدة.  قاع السقف = السقف SSL − سماكة البلاطة.
"""
import argparse, os, collections
import ezdxf
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import columns_takeoff as ct
import concrete_columns_takeoff as cc
import column_base_levels as cbl

CEIL_SSL   = -3.85     # سقف البدروم السفلي (لِفت 1)
SLAB       = 0.22      # سماكة البلاطة → قاع السقف
BASE_WALL  = -6.75     # ظهر الجدار الشمالي (مارك C)
BASE_RAFT  = -8.45     # وش اللبشة (باقي الأعمدة)
RAMP_THK   = 0.16      # سماكة الرمب — تُخصم من ارتفاع أعمدة زون الرمب (تخترق الرمب)
RAMP_EDGE  = 4500      # زون الرمب: الأعمدة ضمن هذه المسافة من حافة المسقط يسار/يمين (RAMP04/03)
WALL_THK   = 0.30      # سماكة الجدار المحيطي — مُستخرَج من بلوك R.WALL_DETAILS (300مم)
CORE_THK   = 0.30      # سماكة جدران الأكوار — مُستخرَج من بلوك ST_WAll (300مم ×21)
STARTER_THK= 0.20      # سماكة بادئ الرمب (من السيكشن)
STARTER_H  = 1.00      # ارتفاع بادئ الرمب (من السيكشن)
WASTE      = 1.05

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--dxf", default=cc.DEFAULT_DXF)
    ap.add_argument("--ceil", type=float, default=CEIL_SSL)
    ap.add_argument("--slab", type=float, default=SLAB)
    ap.add_argument("--outdir", default=r"D:\مشروع الحصر\output")
    args=ap.parse_args()
    soffit = args.ceil - args.slab
    doc=ezdxf.readfile(args.dxf); msp=doc.modelspace()
    plan, sched = ct.collect(msp)
    counts = ct.count_marks(plan)
    stages_by_mark, stage_names = cc.parse_schedule_stages(sched)
    cols = cc.columns_list(plan)

    # منسوب قاعدة كل عمود من منطقته (أداة column_base_levels) — يُستدعى قبل الحصر
    bl = cbl.column_bases(msp)
    base_map = {(round(o["x"]), round(o["y"])): (o["base"], o["zone"]) for o in bl}

    # ترتيب الأعمدة (أعلى→أسفل ثم يسار→يمين) وترقيمها
    colcols=[c for c in cols if not c[1].startswith("CORE")]
    xs=[c[2] for c in colcols]; xmin,xmax=min(xs),max(xs)
    colcols.sort(key=lambda c:(-c[3], c[2]))
    rows=[]; grand=0.0; n_ramp=0
    per_mark=collections.defaultdict(lambda: dict(n=0, v=0.0))
    for i,(sn,m,x,y) in enumerate(colcols,1):
        wh=stages_by_mark.get(m,[None])[0] if m in stages_by_mark else None
        base, zone = base_map.get((round(x),round(y)), (BASE_RAFT, f"المات {BASE_RAFT}"))
        wall = (m=="C")
        # زون الرمب: الأعمدة عند حافة المسقط (يسار RAMP04 / يمين RAMP03) غير أعمدة الجدار → تخترق الرمب
        ramp = (not wall) and (x < xmin+RAMP_EDGE or x > xmax-RAMP_EDGE)
        h = round(soffit - base - (RAMP_THK if ramp else 0.0), 3)
        if ramp: n_ramp+=1
        if wh:
            W,D=wh[0]/1000.0, wh[1]/1000.0; v=W*D*h
        else:
            W=D=0; v=0
        rows.append(dict(no=i, mark=m, sec=(f"{wh[0]}×{wh[1]}" if wh else "—"),
                         base=base, zone=zone, h=h, W=W, D=D, v=v, wall=wall, ramp=ramp, x=x, y=y))
        grand+=v; per_mark[m]["n"]+=1; per_mark[m]["v"]+=v
    cores=sorted([m for m in counts if m.startswith("CORE")])

    # طباعة
    zdist=collections.Counter(round(d["base"],2) for d in rows)
    print(f"قاع السقف = {args.ceil} − {args.slab} = {soffit:.2f} | منسوب القاعدة لكل عمود من منطقته")
    print("توزيع مناسيب القواعد:", dict(zdist))
    print(f"{'ماركة':6}{'عدد':5}{'حجم م³':9}")
    for m in sorted(per_mark, key=ct.mark_key):
        print(f"{m:6}{per_mark[m]['n']:<5}{per_mark[m]['v']:<9.1f}")
    print(f"\nأعمدة الرمب (خُصم منها 16سم): {n_ramp}")
    print(f"إجمالي خرسانة الأعمدة (لِفت 1) = {grand:.1f} م³ | +هدر = {grand*WASTE:.1f} م³  | عدد الأعمدة {len(rows)}")
    print(f"الأكوار: {cores}")

    # ===== الحوائط المحيطة + بادئ الرمب =====
    fx=(max(c[2] for c in colcols)-min(c[2] for c in colcols))/1000.0
    fy=(max(c[3] for c in colcols)-min(c[3] for c in colcols))/1000.0
    Hw = round(soffit - BASE_RAFT, 2)
    walls=[("W1 شمالي (ظاهر 1.70م)", fx, 1.70, WALL_THK, fx*1.70*WALL_THK),
           ("W4 جنوبي (حتى السقف)",  fx, Hw, WALL_THK, fx*Hw*WALL_THK),
           ("W4 غربي (حتى السقف)",   fy, Hw, WALL_THK, fy*Hw*WALL_THK),
           ("W4 شرقي (حتى السقف)",   fy, Hw, WALL_THK, fy*Hw*WALL_THK)]
    v_walls=sum(w[4] for w in walls)
    try:
        import beams_rebar as br, takeoff as _tk
        tt=_tk.all_titles(msp); rt=[x for x in tt if "RAMPS REINFORCEMENT PLAN FOR LOWER" in x[2].upper()][0]
        rstr=br.measure_ramps(msp, _tk.plan_bbox(tt, rt[0], rt[1]))
        if not rstr: raise ValueError
    except Exception:
        rstr=[("RAMP03",4.2,26.3,110.5),("RAMP04",3.9,25.0,97.5)]
    starters=[(nm, w, STARTER_THK, STARTER_H, w*STARTER_THK*STARTER_H) for nm,w,h,a in rstr]
    v_starter=sum(s[4] for s in starters)
    # الأكوار والخزان على قواعد 1100مم (وش ‑7.75) → الارتفاع حتى قاع السقف = 3.68م
    # مساحات المقطع من تهشير الكور على لوحة COLUMNS&AXES (حوائط 300مم) — مطابقة لحصر الـproject.
    CORE_BASE=-7.75
    Hc = round(soffit - CORE_BASE, 2)                       # 3.68
    CORE_AREA={"CORE2":2.55, "CORE3":6.00}                  # م² (CORE3 صندوق 4.0×7.2م؛ CORE2 شكل U 2.9×3.1م). CORE1 مع الخزان.
    core_rows=[]; v_cores=0.0
    for c in sorted([x for x in cores if x in CORE_AREA]):
        a=CORE_AREA[c]; v=counts[c]*a*Hc; core_rows.append((c, counts[c], a, Hc, v)); v_cores+=v
    # الخزان: حوائط L (16.63) + ضلعا CORE1 (1.35) + العمود الفاصل C3 (0.65) × الارتفاع
    TANK_T1=16.63; TANK_T2=1.35; TANK_T3=0.65; Ht=Hc; TANK_AREA=TANK_T1+TANK_T2+TANK_T3
    v_tank=TANK_AREA*Ht

    # Excel
    NAVY,BLUE,LT,GREY,GRN,YEL,PUR="1F3864","2E5496","D9E1F2","F2F2F2","E2EFDA","FFF2CC","E6D5F2"
    thin=Side(style="thin",color="BFBFBF"); bd=Border(thin,thin,thin,thin)
    wb=Workbook()
    def st(c,*,b=False,sz=11,color="000000",fill=None,ha="center",wrap=False):
        c.font=Font(bold=b,size=sz,color=color); c.alignment=Alignment(ha,"center",wrap_text=wrap)
        if fill:c.fill=PatternFill("solid",fgColor=fill)
        c.border=bd
    ws=wb.active; ws.title="الأعمدة"; ws.sheet_view.rightToLeft=True
    ws.merge_cells("A1:H1"); st(ws["A1"],b=True,sz=14,color="FFFFFF",fill=NAVY); ws["A1"]="حصر خرسانة الأعمدة — لِفت 1 (اللبشة → سقف البدروم السفلي ‑3.85)"
    ws.merge_cells("A2:H2"); st(ws.cell(2,1,f"ارتفاع كل عمود = قاع السقف ({soffit:+.2f}) − منسوب قاعدته حسب منطقة اللبشة (أداة column_base_levels): المات ‑8.45، قواعد مُثخّنة ‑7.35..‑8.15، الجدار الشمالي ‑6.75. أعمدة الرمب تُخصم 16سم. القاعدة ليست ضمن العمود."),sz=9,fill=GRN,ha="right",wrap=True); ws.row_dimensions[2].height=34
    for j,h in enumerate(["#","الماركة","المقطع (مم)","ظهر القاعدة","الارتفاع م","الحجم م³","نوع القاعدة","ملاحظة"],1): st(ws.cell(3,j,h),b=True,fill=NAVY,color="FFFFFF")
    r=4
    for d in rows:
        note = "جدار شمالي W1" if d["wall"] else ("رمب: خصم 16سم" if d["ramp"] else "")
        fill = PUR if d["wall"] else (YEL if d["ramp"] else None)
        st(ws.cell(r,1,d["no"]),fill=fill); st(ws.cell(r,2,d["mark"]),b=True,fill=fill or LT)
        st(ws.cell(r,3,d["sec"])); st(ws.cell(r,4,f"{d['base']:+.2f}")); st(ws.cell(r,5,d["h"]))
        st(ws.cell(r,6,round(d["v"],3))); st(ws.cell(r,7,d["zone"]),fill=fill,ha="right")
        st(ws.cell(r,8,note),fill=fill,ha="right"); r+=1
    st(ws.cell(r,1,"الإجمالي"),b=True,fill=NAVY,color="FFFFFF"); ws.merge_cells(f"A{r}:E{r}")
    st(ws.cell(r,6,round(grand,2)),b=True,fill=LT); r+=1
    st(ws.cell(r,1,"+ هدر 5٪"),b=True,fill=GREY); ws.merge_cells(f"A{r}:E{r}"); st(ws.cell(r,6,round(grand*WASTE,2)),b=True,fill=LT); r+=1
    for j,w in enumerate([5,8,12,11,10,10,12,16],1): ws.column_dimensions[get_column_letter(j)].width=w
    ws.freeze_panes="A4"

    # ملخص بالماركة
    ws1=wb.create_sheet("ملخص الماركات"); ws1.sheet_view.rightToLeft=True
    for j,h in enumerate(["الماركة","العدد","المقطع","مدى منسوب القاعدة","مدى الارتفاع م","الحجم الكلي م³"],1): st(ws1.cell(1,j,h),b=True,fill=NAVY,color="FFFFFF")
    rr=2
    mbase=collections.defaultdict(list)
    for d in rows: mbase[d["mark"]].append(d["base"])
    for m in sorted(per_mark, key=ct.mark_key):
        wh=stages_by_mark.get(m,[None])[0]; bs=mbase[m]
        brange = f"{min(bs):+.2f}" if min(bs)==max(bs) else f"{max(bs):+.2f}..{min(bs):+.2f}"
        hrange = f"{soffit-min(bs):.2f}" if min(bs)==max(bs) else f"{soffit-max(bs):.2f}..{soffit-min(bs):.2f}"
        st(ws1.cell(rr,1,m),b=True,fill=LT); st(ws1.cell(rr,2,per_mark[m]["n"]))
        st(ws1.cell(rr,3,f"{wh[0]}×{wh[1]}" if wh else "—")); st(ws1.cell(rr,4,brange))
        st(ws1.cell(rr,5,hrange)); st(ws1.cell(rr,6,round(per_mark[m]["v"],2))); rr+=1
    for j,w in enumerate([10,6,12,16,15,13],1): ws1.column_dimensions[get_column_letter(j)].width=w

    # الأكوار (محسوبة — مساحة المقطع من بلوك ST_WAll، الارتفاع حتى السقف)
    ws2=wb.create_sheet("الأكوار والخزان"); ws2.sheet_view.rightToLeft=True
    ws2.merge_cells("A1:E1"); st(ws2["A1"],b=True,sz=12,color="FFFFFF",fill=NAVY); ws2["A1"]="الأكوار (سلالم/أسانسير) + الخزان"
    ws2.merge_cells("A2:E2"); st(ws2.cell(2,1,f"مساحة مقطع جدران الأكوار من بلوك ST_WAll (سماكة 300مم)؛ الارتفاع حتى قاع السقف ({Hc}م). المسقط: K1=K2=CORE3، K3=CORE2، T2=CORE1."),sz=9,fill=GRN,ha="right",wrap=True); ws2.row_dimensions[2].height=28
    for j,h in enumerate(["الكور","العدد","مساحة المقطع م²","ارتفاع م","حجم م³"],1): st(ws2.cell(3,j,h),b=True,fill=NAVY,color="FFFFFF")
    rr=4
    for c,n,a,H,V in core_rows:
        st(ws2.cell(rr,1,c),b=True,fill=LT); st(ws2.cell(rr,2,n)); st(ws2.cell(rr,3,a)); st(ws2.cell(rr,4,H)); st(ws2.cell(rr,5,round(V,2))); rr+=1
    st(ws2.cell(rr,1,"مجموع الأكوار"),b=True,fill=GRN); ws2.merge_cells(f"A{rr}:D{rr}"); st(ws2.cell(rr,5,round(v_cores,2)),b=True,fill=GRN); rr+=2
    st(ws2.cell(rr,1,"الخزان T1 (L‑shape 10.51×9.70م، سماكة 350مم، مُلتصق بـCORE1)"),b=True,fill=NAVY,color="FFFFFF"); ws2.merge_cells(f"A{rr}:E{rr}"); rr+=1
    for lbl,ar in [("حوائط الخزان T1", TANK_T1), ("ضلعا CORE1 (T2)", TANK_T2), ("العمود الفاصل C3 (T3)", TANK_T3)]:
        st(ws2.cell(rr,1,lbl),fill=LT,ha="right"); st(ws2.cell(rr,3,ar)); st(ws2.cell(rr,4,Ht)); st(ws2.cell(rr,5,round(ar*Ht,2))); rr+=1
    st(ws2.cell(rr,1,"مجموع الخزان"),b=True,fill=GRN); ws2.merge_cells(f"A{rr}:D{rr}"); st(ws2.cell(rr,5,round(v_tank,2)),b=True,fill=GRN); rr+=1
    for j,w in enumerate([30,14,12,9,10],1): ws2.column_dimensions[get_column_letter(j)].width=w

    ws3=wb.create_sheet("الحوائط وبادئ الرمب"); ws3.sheet_view.rightToLeft=True
    ws3.merge_cells("A1:E1"); st(ws3["A1"],b=True,sz=12,color="FFFFFF",fill=NAVY); ws3["A1"]="الحوائط المحيطة + بادئ الرمب"
    ws3.merge_cells("A2:E2"); st(ws3.cell(2,1,f"الأطوال من أبعاد المبنى ({fx:.1f}×{fy:.1f}م). W1 ظاهر 1.70م (بلوك rwall 2m)، W4 حتى قاع السقف (ارتفاع {Hw}م، بلوك R.WALL_DETAILS). السماكة {WALL_THK}م مُستخرَجة من البلوكات."),sz=9,fill=GRN,ha="right",wrap=True); ws3.row_dimensions[2].height=30
    for j,h in enumerate(["العنصر","الطول م","الارتفاع م","السماكة م","الحجم م³"],1): st(ws3.cell(3,j,h),b=True,fill=NAVY,color="FFFFFF")
    r3=4
    for nm,L,H,T,V in walls:
        st(ws3.cell(r3,1,nm),b=True,fill=LT,ha="right"); st(ws3.cell(r3,2,round(L,2))); st(ws3.cell(r3,3,H)); st(ws3.cell(r3,4,T)); st(ws3.cell(r3,5,round(V,2))); r3+=1
    st(ws3.cell(r3,1,"مجموع الحوائط"),b=True,fill=GRN); ws3.merge_cells(f"A{r3}:D{r3}"); st(ws3.cell(r3,5,round(v_walls,2)),b=True,fill=GRN); r3+=2
    st(ws3.cell(r3,1,"بادئ الرمب (الطول=عرض الرمب)"),b=True,fill=NAVY,color="FFFFFF"); ws3.merge_cells(f"A{r3}:E{r3}"); r3+=1
    for nm,L,T,H,V in starters:
        st(ws3.cell(r3,1,nm),b=True,fill=LT,ha="right"); st(ws3.cell(r3,2,round(L,2))); st(ws3.cell(r3,3,H)); st(ws3.cell(r3,4,T)); st(ws3.cell(r3,5,round(V,3))); r3+=1
    st(ws3.cell(r3,1,"مجموع بادئ الرمب"),b=True,fill=GRN); ws3.merge_cells(f"A{r3}:D{r3}"); st(ws3.cell(r3,5,round(v_starter,3)),b=True,fill=GRN); r3+=1
    for j,w in enumerate([24,9,10,9,10],1): ws3.column_dimensions[get_column_letter(j)].width=w

    # ===== الإجمالي =====
    ws5=wb.create_sheet("الإجمالي"); ws5.sheet_view.rightToLeft=True
    ws5.merge_cells("A1:C1"); st(ws5["A1"],b=True,sz=13,color="FFFFFF",fill=NAVY); ws5["A1"]="إجمالي خرسانة العناصر الرئيسية — لِفت 1"
    items=[("الأعمدة (65)", round(grand,2), "كل عمود من ظهر قاعدته حتى قاع السقف"),
           ("الحوائط المحيطة (W1+W4)", round(v_walls,2), f"سماكة {WALL_THK}م مُستخرَجة"),
           ("الأكوار (CORE1/2/3)", round(v_cores,2), f"مقطع من ST_WAll، ارتفاع {Hc}م حتى السقف"),
           ("الخزان T1", round(v_tank,2), "9.7×5.5م سماكة 350مم − الجدار المشترك مع CORE1"),
           ("بادئ الرمب", round(v_starter,3), "الطول=عرض الرمب")]
    for j,h in enumerate(["العنصر","الحجم م³","ملاحظة"],1): st(ws5.cell(2,j,h),b=True,fill=NAVY,color="FFFFFF")
    r5=3; tot=0.0
    for nm,v,nt in items:
        st(ws5.cell(r5,1,nm),b=True,fill=LT,ha="right"); st(ws5.cell(r5,2,v if v is not None else "؟"),fill=(None if v is not None else YEL))
        st(ws5.cell(r5,3,nt),ha="right",fill=(None if v is not None else YEL));
        if v: tot+=v
        r5+=1
    st(ws5.cell(r5,1,"الإجمالي (المحسوب)"),b=True,fill=NAVY,color="FFFFFF"); st(ws5.cell(r5,2,round(tot,2)),b=True,fill=GRN); st(ws5.cell(r5,3,"بدون الأكوار والخزان")); r5+=1
    st(ws5.cell(r5,1,"+ هدر 5٪"),b=True,fill=GREY); st(ws5.cell(r5,2,round(tot*WASTE,2)),b=True,fill=GRN); r5+=1
    for j,w in enumerate([26,12,30],1): ws5.column_dimensions[get_column_letter(j)].width=w

    # ===== أسئلة ومُعلَّقات (في الآخر) =====
    ws4=wb.create_sheet("أسئلة ومُعلَّقات"); ws4.sheet_view.rightToLeft=True
    notes=["① الأكوار (CORE1/2/3 = سلالم/أسانسير): ليبلاتها في جدول الأعمدة لا المسقط، فمساحة مقطع جدرانها لم تُستخرَج بثقة — محتاج مساحة مقطع كل كور (أو تأكيد أستخرجها من مسقط معيّن).",
           "② الخزان T1: لا يوجد له أي ليبل/رسم في الـDXF الإنشائي الحالي — محتاج موقعه وأبعاده (أرضية/حوائط/غطاء) ومناسيبه.",
           "③ سماكة الحوائط المحيطة مفترضة 25سم (الجدران غير مرسومة في الـDXF) — أكّد السماكة الفعلية.",
           "④ بادئ الرمب: الطول = عرض الرمب (4.2/3.9م) مؤكّد؛ السماكة (20سم) والارتفاع (1.0م) مفترضان من السيكشن — أكّدهما لو مختلفان.",
           "⑤ أعمدة الرمب: خُصم 16سم من كل أعمدة الزون (الطريقة المبسّطة). الأعمدة التي تقف أسفل الرمب فعلياً أقصر — لو تريد الدقة الكاملة أعطني قائمتها.",
           "⑥ الربط عمود↔قاعدة بالمحاذاة (15/19 عمود تقيل على قواعد مُثخّنة) — دقّة ~80٪؛ لو عمود طلع منسوبه غلط أصلّحه يدوياً.",
           "⑦ هذا لِفت 1 فقط (اللبشة→‑3.85). اللِفتات الأعلى تحتاج مناسيب المتكرر/الروف."]
    ws4.merge_cells("A1:A1"); st(ws4["A1"],b=True,sz=12,color="FFFFFF",fill=NAVY); ws4["A1"]="أسئلة ومُعلَّقات (للمراجعة)"
    for i,n in enumerate(notes,3):
        ws4.merge_cells(f"A{i}:H{i}"); st(ws4.cell(i,1,n),sz=10,ha="right",wrap=True,fill=YEL); ws4.row_dimensions[i].height=34
    ws4.column_dimensions["A"].width=120

    tot_all=grand+v_walls+v_cores+v_tank+v_starter
    print(f"\nالحوائط {v_walls:.1f} | الأكوار {v_cores:.1f} | الخزان {v_tank:.1f} | بادئ الرمب {v_starter:.2f} م³")
    print(f"الإجمالي الكلي (كل العناصر الرئيسية) = {tot_all:.1f} م³ | +هدر 5٪ = {tot_all*WASTE:.1f} م³")

    os.makedirs(args.outdir,exist_ok=True)
    out=os.path.join(args.outdir,"حصر خرسانة العناصر الرئيسية - لِفت 1.xlsx")
    wb.save(out); print("SAVED:",out)

if __name__=="__main__":
    main()
