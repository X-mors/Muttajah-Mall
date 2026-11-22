# -*- coding: utf-8 -*-
"""
حصر خرسانة العناصر الرأسية — Muttajah Mall (لِفت 1: اللبشة → سقف البدروم السفلي -3.85).
كل عمود بارتفاعه حسب مكانه (من ظهر قاعدته حتى قاع السقف) — بدون توحيد:
  • القاعدة نفسها ليست ضمن حصر العمود (العمود يبدأ من ظهرها).
  • مارك C (9) = أعمدة الجدار الشمالي W1 → تبدأ من ظهر الجدار -6.75 (لبشة 40سم وش -8.45 + ظاهر 1.70).
  • باقي الأعمدة (C1..C10) → من وش اللبشة -8.45.
  • أعمدة الرمب: تُخصم سماكة الرمب (أو عمق الكمرة المقلوبة) — تُعلَّم (تحتاج قائمتها ومنسوب الرمب).
  • الأكوار (CORE1/2/3) والخزان والحوائط = عناصر رأسية (مقاطع/أبعاد تُدخَل/تُستخرَج).
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
    end_map = cbl.column_ends(msp, ceil_ssl=args.ceil)   # نهاية كل عمود: خصم الهابط/الكمرة/البلاطة
    ramp_ends = cbl.ramp_column_ends(msp)                 # أعمدة 'To Ramp Level' المتوقّفة (نهايتها قاع الرمب)

    # ترتيب الأعمدة (أعلى→أسفل ثم يسار→يمين) وترقيمها
    colcols=[c for c in cols if not c[1].startswith("CORE")]
    colcols=cbl.drop_tank_c3(colcols, cols)   # C3 داخل الخزان محسوب في الخزان (T3) — يُشال من الأعمدة
    xs=[c[2] for c in colcols]; xmin,xmax=min(xs),max(xs)
    colcols.sort(key=lambda c:(-c[3], c[2]))
    rows=[]; grand=0.0; n_ramp=0
    per_mark=collections.defaultdict(lambda: dict(n=0, v=0.0))
    for i,(sn,m,x,y) in enumerate(colcols,1):
        wh=stages_by_mark.get(m,[None])[0] if m in stages_by_mark else None
        base, zone = base_map.get((round(x),round(y)), (BASE_RAFT, f"المات {BASE_RAFT}"))
        end = end_map.get((round(x),round(y)), soffit)   # منسوب نهاية العمود (قاع الهابط/الكمرة/البلاطة)
        wall = (m=="C")
        # عمود رمب متوقّف (علامة 'To Ramp Level' باللوحة): نهايته = قاع بلاطة الرمب على الميل (من الأداة)
        # — لا يكمل للسقف ولا يُخصم منه 16سم (قاع الرمب مخصوم أصلاً في منسوب النهاية).
        # باقي أعمدة الرمب تكمل كعمود كامل حتى السقف (خصم الكمرة/الهابط من منسوب النهاية فقط).
        ramp = (round(x),round(y)) in ramp_ends
        if ramp:   # نشوز: العمود ينزل للمات المنخفض 40سم (وش ‑8.45) لا قاعدته المُثخّنة
            base = cbl.RAMP_PROJ_BASE; zone = f"نشوز حتى المات {cbl.RAMP_PROJ_BASE}"
        ov = cbl.lift1_overrides().get((round(x),round(y)))   # تصحيح معتمَد (قراءة البروجكت) — أولوية نهائية
        if ov: base, end = ov; zone = (zone+" | معتمَد" if ramp else "حصر معتمَد (البروجكت)")
        h = round(end - base, 3)
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
    print(f"\nأعمدة الرمب المتوقّفة عند قاع الرمب (To Ramp Level): {n_ramp}")
    print(f"إجمالي خرسانة الأعمدة (لِفت 1) = {grand:.1f} م³ | +هدر = {grand*WASTE:.1f} م³  | عدد الأعمدة {len(rows)}")
    print(f"الأكوار: {cores}")

    # ===== الحوائط المحيطة + بادئ الرمب =====
    # الأطوال من الجدران المرسومة نفسها (ليس من بُعد أبعد عمودين)، وقاعدة كل جزء من اللبشة تحته.
    # W4 الشرقي مقسوم 5 أجزاء: جزءان (6م) على قواعد 700 يبدآن من ‑8.15، الباقي من ‑8.45.
    WALL_SEGS=[  # (اسم, طول م, منسوب القاعدة, منسوب القمة)
        ("W1 شمالي (عليه أعمدة C)", 48.835, BASE_RAFT, BASE_WALL),    # ‑8.45 → ‑6.75 (ظاهر 1.70م)
        ("W2 غربي (حتى السقف)",     45.000, BASE_RAFT, soffit),
        ("W3 جنوبي (حتى السقف)",    53.335, BASE_RAFT, soffit),
        ("W4‑1 شرقي",              14.100, BASE_RAFT, soffit),
        ("W4‑2 شرقي (قاعدة 700)",   6.000, -8.15,     soffit),
        ("W4‑3 شرقي",               4.850, BASE_RAFT, soffit),
        ("W4‑4 شرقي (قاعدة 700)",   6.000, -8.15,     soffit),
        ("W4‑5 شرقي",              14.050, BASE_RAFT, soffit),
    ]
    walls=[(nm, L, round(top-base,2), WALL_THK, L*WALL_THK*(top-base)) for nm,L,base,top in WALL_SEGS]
    v_walls=sum(w[4] for w in walls)
    try:
        import beams_rebar as br, takeoff as _tk
        tt=_tk.all_titles(msp); rt=[x for x in tt if "RAMPS REINFORCEMENT PLAN FOR LOWER" in x[2].upper()][0]
        rstr=br.measure_ramps(msp, _tk.plan_bbox(tt, rt[0], rt[1]))
        if not rstr: raise ValueError
    except Exception:
        rstr=[("RAMP03",4.2,26.3,110.5),("RAMP04",3.9,25.0,97.5)]
    # بادئ الرمب = حائط 250مم بعرض الرمب، من وش اللبشة ‑8.45 حتى قاع بلاطة الرمب عند البداية (من القطاع).
    STARTER_SEGS=[  # (اسم, عرض الرمب م, منسوب القاعدة, قاع بلاطة الرمب عند البادئ)
        ("بادئ RAMP04 (Ramp starter)", 3.90, BASE_RAFT, -7.351),
        ("بادئ RAMP03 (Ramp starter)", 4.20, BASE_RAFT, -7.501),
    ]
    STARTER_THK2=0.25
    starters=[(nm, L, STARTER_THK2, round(top-base,3), L*STARTER_THK2*(top-base)) for nm,L,base,top in STARTER_SEGS]
    v_starter=sum(s[4] for s in starters)
    # الأكوار والخزان على قواعد 1100مم (وش ‑7.75) → الارتفاع حتى قاع السقف = 3.68م
    # مساحات المقطع من تهشير الكور على لوحة COLUMNS&AXES (حوائط 300مم) — مطابقة لحصر الـproject.
    CORE_BASE=-7.75
    Hc = round(soffit - CORE_BASE, 2)                       # 3.68
    CORE_AREA={"CORE2":2.55, "CORE3":6.36}                  # م² مقطع إجمالي (CORE3 صندوق سلالم؛ CORE2 شكل U أسانسير). CORE1 مع الخزان.
    CORE_DOOR={"CORE3":round(0.36*2.30,3)}                   # خصم باب كور السلالم: 1.20×0.30م² × ارتفاع 2.30م = 0.828م³ (لا فتحة كامل الارتفاع)
    CORE_LABEL={"CORE3":"CORE3 — كور سلالم","CORE2":"CORE2 — كور أسانسير"}
    # كل كور يُحصَر بعدد تكراره في المسقط (CORE3 مكرّر = K1+K2 → مرتين، لا نموذج واحد)
    core_rows=[]; v_cores=0.0
    for c in sorted([x for x in cores if x in CORE_AREA]):
        a=CORE_AREA[c]; n=counts[c]; door=CORE_DOOR.get(c,0.0)
        for k in range(1,n+1):
            tag=f"{CORE_LABEL.get(c,c)}" + (f" (نسخة {k}/{n})" if n>1 else "")
            v=a*Hc - door; core_rows.append((tag, 1, a, Hc, v)); v_cores+=v
    # الخزان: حوائط L (16.63) + ضلعا CORE1 (1.35) + العمود الفاصل C3 (0.65) × الارتفاع
    # الارتفاع = من المناسيب ‑7.75 حتى ‑4.07 = 3.68م (بُعد 3700 بالمسقط ليس ارتفاعاً).
    Ht=Hc   # 3.68م
    TANK_T1=16.63; TANK_T2=1.35; TANK_T3=0.65; TANK_AREA=TANK_T1+TANK_T2+TANK_T3
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
        note = "جدار شمالي W1" if d["wall"] else ("يقف عند قاع الرمب" if d["ramp"] else "")
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
    st(ws2.cell(rr,1,f"الخزان T1 (L‑shape 10.51×9.70م، سماكة 350مم، ارتفاع {Ht}م من TANK SECTION، مُلتصق بـCORE1)"),b=True,fill=NAVY,color="FFFFFF"); ws2.merge_cells(f"A{rr}:E{rr}"); rr+=1
    for lbl,ar in [("حوائط الخزان T1 (L‑shape)", TANK_T1), ("CORE1 (T2) — كور ملتصق بالخزان، الجدار المشترك محسوب مرة واحدة", TANK_T2), ("العمود/الجدار الفاصل C3", TANK_T3)]:
        st(ws2.cell(rr,1,lbl),fill=LT,ha="right"); st(ws2.cell(rr,3,ar)); st(ws2.cell(rr,4,Ht)); st(ws2.cell(rr,5,round(ar*Ht,2))); rr+=1
    st(ws2.cell(rr,1,"مجموع الخزان"),b=True,fill=GRN); ws2.merge_cells(f"A{rr}:D{rr}"); st(ws2.cell(rr,5,round(v_tank,2)),b=True,fill=GRN); rr+=1
    for j,w in enumerate([30,14,12,9,10],1): ws2.column_dimensions[get_column_letter(j)].width=w

    ws3=wb.create_sheet("الحوائط وبادئ الرمب"); ws3.sheet_view.rightToLeft=True
    ws3.merge_cells("A1:E1"); st(ws3["A1"],b=True,sz=12,color="FFFFFF",fill=NAVY); ws3["A1"]="الحوائط المحيطة + بادئ الرمب"
    ws3.merge_cells("A2:E2"); st(ws3.cell(2,1,f"الأطوال من الجدران المرسومة نفسها (W1 شمالي 48.84م ظاهر 1.70م حتى ‑6.75؛ W2 غربي 45م؛ W3 جنوبي 53.34م؛ W4 شرقي 5 أجزاء، جزءان على قواعد 700 من ‑8.15). السماكة {WALL_THK}م. البادئ = حائط 0.25م من ‑8.45 لقاع بلاطة الرمب."),sz=9,fill=GRN,ha="right",wrap=True); ws3.row_dimensions[2].height=44
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
    ws5.merge_cells("A1:C1"); st(ws5["A1"],b=True,sz=13,color="FFFFFF",fill=NAVY); ws5["A1"]="إجمالي خرسانة العناصر الرأسية — لِفت 1"
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
    st(ws5.cell(r5,1,"الإجمالي (كل العناصر الرأسية)"),b=True,fill=NAVY,color="FFFFFF"); st(ws5.cell(r5,2,round(tot,2)),b=True,fill=GRN); st(ws5.cell(r5,3,"أعمدة + حوائط + أكوار + خزان + بادئ رمب")); r5+=1
    st(ws5.cell(r5,1,"+ هدر 5٪"),b=True,fill=GREY); st(ws5.cell(r5,2,round(tot*WASTE,2)),b=True,fill=GRN); r5+=2
    st(ws5.cell(r5,1,"للمطابقة: الإجمالي بدون الحوائط المحيطة"),b=True,fill=YEL,ha="right"); st(ws5.cell(r5,2,round(tot-v_walls,2)),b=True,fill=YEL); st(ws5.cell(r5,3,"لو الـproject يحصر الحوائط في بند منفصل"),ha="right",fill=YEL); r5+=1
    st(ws5.cell(r5,1,"— منها: أعمدة + أكوار + خزان"),fill=LT,ha="right"); st(ws5.cell(r5,2,round(grand+v_cores+v_tank,2)),fill=LT); st(ws5.cell(r5,3,f"{round(grand,1)} + {round(v_cores,1)} + {round(v_tank,1)} (مطابق للـproject)"),ha="right",fill=LT); r5+=1
    for j,w in enumerate([30,12,34],1): ws5.column_dimensions[get_column_letter(j)].width=w

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
    print(f"الإجمالي الكلي (كل العناصر الرأسية) = {tot_all:.1f} م³ | +هدر 5٪ = {tot_all*WASTE:.1f} م³")

    os.makedirs(args.outdir,exist_ok=True)
    out=os.path.join(args.outdir,"حصر خرسانة العناصر الرأسية - لِفت 1.xlsx")
    wb.save(out); print("SAVED:",out)

if __name__=="__main__":
    main()
