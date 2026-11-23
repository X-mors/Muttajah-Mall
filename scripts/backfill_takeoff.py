# -*- coding: utf-8 -*-
"""
البند 1: حصر الردم الداخلي (م³) — Muttajah Mall، البدروم السفلي.
يقرأ من اللوحة (DXF) على الشبكة الموحّدة (column_exact.PLAN_ORIGIN) ويستخدم مستطيلات الأعمدة من column_exact.

=================  المناسيب والفرضيات (مقروءة من اللوحة)  =================
• منسوب الردم (FILL) = أعلى قاعدة سمكها 1.50م = ‑7.35 (= قاع التأسيس ‑8.85 + 1.50).
• قاع التأسيس (formation) = ‑8.85. وش المات العام = ‑8.45 (مات 40سم).
• مناطق وش اللبشة (مقروءة من R.C. footing + بابلات السماكة):
    المات ‑8.45 | قواعد مُثخّنة وشّها ‑8.15/‑7.85/‑7.75/‑7.55/‑7.35 (سماكة 700/1000/1100/1300/1500).
• الحدود: الوش الداخلي للجدار المحيط (3 أضلاع عالية + ضلع جدار الجار 1.70م). الردم يملأ من وش اللبشة
  في كل منطقة حتى ‑7.35، ويُخصَم منه كل الخرسانة الواقعة في هذا المدى (قواعد/رقاب أعمدة/حوائط/أكوار/خزان/بادئ رمب).

الحجم = Σ (مساحة المنطقة × (‑7.35 − وش اللبشة فيها)) − خرسانة العناصر الرأسية في مدى الردم.
المدموك = هذا الحجم. التوريد = × معامل انضغاط (COMPACTION، افتراضي 1.20 — يُعدَّل من المهندس).

⚠️ قيد الإكمال (تُضاف لاحقاً بعد تأكيد موقعها في اللوحة): السملات (tie beams)، حفر الأسانسير، الهوابط السفلية، سمك العزل.
"""
import sys, os, collections
import ezdxf, raft_footings as RF, concrete_columns_takeoff as cc, columns_takeoff as ct, column_exact as CX

OUT=os.path.join(os.path.dirname(__file__), "..", "output")
FILL=-7.35; MAT_TOP=-8.45; WALL_THK=0.30; CORE_THK=0.30
COMPACTION=1.20; WASTE=1.05

def poly_area(pts):
    a=0.0
    for i in range(len(pts)):
        x1,y1=pts[i]; x2,y2=pts[(i+1)%len(pts)]; a+=x1*y2-x2*y1
    return abs(a)/2/1e6

def raft_zones(msp):
    """مناطق وش اللبشة: {وش: مساحة م²}. المات = اللبشة الكلية − القواعد المُثخّنة."""
    RX,RY=CX.PLAN_ORIGIN['RAFT']
    fts=RF.assign_thickness(RF.collect_footings(msp), RF.collect_thickness_bubbles(msp))
    zt=collections.defaultdict(float)
    for f in fts: zt[round(f['top'],2)]+=poly_area([(x-RX,y-RY) for x,y in f['pts']])
    allp=[]
    for e in msp.query('LWPOLYLINE'):
        if e.dxf.layer!='R.C. footing': continue
        try: pts=[(p[0]-RX,p[1]-RY) for p in e.get_points('xy')]
        except: continue
        if len(pts)>=4 and -15000<min(p[0] for p in pts)<60000: allp.append(poly_area(pts))
    raft=max(allp) if allp else 0.0
    zt[MAT_TOP]+=raft-sum(zt.values())   # المات = الكلية − المُثخّنة
    return raft, dict(sorted(zt.items()))

def column_necks(msp):
    """حجم رقاب الأعمدة في مدى الردم (من وش قاعدة كل عمود حتى ‑7.35)."""
    L=CX.LiftOne(msp); plan,sched=ct.collect(msp); stages,_=cc.parse_schedule_stages(sched)
    cols=[c for c in cc.columns_list(plan) if not c[1].startswith('CORE')]
    sz={m:stages[m][0] for m in stages}
    match=L.match([(sn,m,x,y) for sn,m,x,y in cols], sz)
    v=0.0; n=0
    for i,(sn,m,x,y) in enumerate(cols):
        if i not in match: continue
        r=match[i]; base=L.levels(r)['base']
        if base<FILL-1e-6:
            A=(r['x1']-r['x0'])*(r['y1']-r['y0'])/1e6; v+=A*(FILL-base); n+=1
    return round(v,2), n

def wall_necks():
    """حوائط محيطة في مدى الردم: الطول × 0.30 × (‑7.35 − القاعدة). (أطوال/قواعد من حصر العناصر الرأسية)."""
    segs=[("W1 شمالي",48.835,-8.45),("W2 غربي",45.0,-8.45),("W3 جنوبي",53.335,-8.45),
          ("W4‑1 شرقي",14.1,-8.45),("W4‑2 شرقي(700)",6.0,-8.15),("W4‑3 شرقي",4.85,-8.45),
          ("W4‑4 شرقي(700)",6.0,-8.15),("W4‑5 شرقي",14.05,-8.45)]
    rows=[(nm, round(L*WALL_THK*(FILL-b),2)) for nm,L,b in segs]
    return round(sum(v for _,v in rows),2), rows

def core_tank_starter_necks(msp):
    """أكوار + خزان + بادئ رمب في مدى الردم (مقطعها × (‑7.35 − قاعدتها))."""
    plan,_=ct.collect(msp); counts=collections.Counter(c[1] for c in cc.columns_list(plan))
    CORE_AREA={"CORE2":2.55,"CORE3":6.36}; CORE_BASE=-7.75
    rows=[]; v=0.0
    for c in sorted(x for x in counts if x in CORE_AREA):
        a=CORE_AREA[c]; n=counts[c]; vv=n*a*(FILL-CORE_BASE)
        rows.append((f"{c}×{n}", round(vv,2))); v+=vv
    TANK_AREA=16.6334+1.35+0.65; vt=TANK_AREA*(FILL-CORE_BASE); rows.append(("الخزان T1", round(vt,2))); v+=vt
    # بادئ الرمب: حائط 250مم بعرض الرمب من ‑8.45 حتى ‑7.35 (ضمن مدى الردم)
    vs=(3.9+4.2)*0.25*(FILL-MAT_TOP); rows.append(("بادئ الرمب", round(vs,2))); v+=vs
    return round(v,2), rows

def main():
    doc=ezdxf.readfile(cc.DEFAULT_DXF); msp=doc.modelspace()
    raft, zones = raft_zones(msp)
    # الحجم القائم (قبل خصم الخرسانة)
    gross_rows=[]; gross=0.0
    for top,A in zones.items():
        h=round(FILL-top,2); v=round(A*h,2); gross_rows.append((top,round(A,1),h,v)); gross+=v
    nc,ncn=column_necks(msp); nw,wrows=wall_necks(); no,orows=core_tank_starter_necks(msp)
    deduct=round(nc+nw+no,2); net=round(gross-deduct,2); supply=round(net*COMPACTION,2)
    print("البند 1: حصر الردم الداخلي — البدروم السفلي (منسوب الردم ‑7.35)")
    print(f"اللبشة الكلية = {raft:.1f} م²")
    print("\nالحجم القائم حسب مناطق وش اللبشة:")
    for top,A,h,v in gross_rows: print(f"  وش {top}: مساحة {A}م² × ارتفاع {h}م = {v} م³")
    print(f"  الحجم القائم = {round(gross,1)} م³")
    print(f"\nيُخصَم خرسانة في مدى الردم: رقاب أعمدة {nc} ({ncn} عمود) + حوائط {nw} + (أكوار/خزان/بادئ) {no} = {deduct} م³")
    print(f"\nالردم المدموك (صافي) = {net} م³")
    print(f"الردم المطلوب توريده (× معامل انضغاط {COMPACTION}) = {supply} م³ | +هدر 5٪ = {round(supply*WASTE,2)} م³")
    # Excel
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
        NAVY,LT,GRN,GREY,YEL="1F3864","D9E1F2","E2EFDA","F2F2F2","FFF2CC"
        bd=Border(*[Side(style="thin",color="BFBFBF")]*4)
        def st(c,*,b=False,sz=11,color="000000",fill=None,ha="center",wrap=False):
            c.font=Font(bold=b,size=sz,color=color); c.alignment=Alignment(ha,"center",wrap_text=wrap)
            if fill:c.fill=PatternFill("solid",fgColor=fill)
            c.border=bd
        wb=Workbook(); ws=wb.active; ws.title="الردم"; ws.sheet_view.rightToLeft=True
        ws.merge_cells("A1:D1"); st(ws["A1"],b=True,sz=13,color="FFFFFF",fill=NAVY); ws["A1"]="البند 1: حصر الردم الداخلي — البدروم السفلي"
        ws.merge_cells("A2:D2"); st(ws.cell(2,1,f"منسوب الردم ‑7.35 (أعلى قاعدة 1500مم). الحجم = Σ(مساحة المنطقة × (‑7.35 − وش اللبشة)) − خرسانة العناصر الرأسية في مدى الردم. المدموك ثم ×معامل انضغاط {COMPACTION} للتوريد."),sz=9,fill=GRN,ha="right",wrap=True); ws.row_dimensions[2].height=40
        r=3; st(ws.cell(r,1,"الحجم القائم حسب مناطق وش اللبشة"),b=True,fill=NAVY,color="FFFFFF"); ws.merge_cells(f"A{r}:D{r}"); r+=1
        for h in ["وش اللبشة","المساحة م²","ارتفاع الردم م","الحجم م³"]: pass
        for j,h in enumerate(["وش اللبشة","المساحة م²","ارتفاع الردم م","الحجم م³"],1): st(ws.cell(r,j,h),b=True,fill=LT)
        r+=1
        for top,A,h,v in gross_rows:
            st(ws.cell(r,1,top)); st(ws.cell(r,2,A)); st(ws.cell(r,3,h)); st(ws.cell(r,4,v)); r+=1
        st(ws.cell(r,1,"الحجم القائم"),b=True,fill=GRN); ws.merge_cells(f"A{r}:C{r}"); st(ws.cell(r,4,round(gross,2)),b=True,fill=GRN); r+=2
        st(ws.cell(r,1,"يُخصَم: خرسانة في مدى الردم"),b=True,fill=NAVY,color="FFFFFF"); ws.merge_cells(f"A{r}:D{r}"); r+=1
        st(ws.cell(r,1,f"رقاب الأعمدة ({ncn} عمود)"),ha="right",fill=LT); ws.merge_cells(f"A{r}:C{r}"); st(ws.cell(r,4,-nc),fill=LT); r+=1
        for nm,v in wrows: st(ws.cell(r,1,f"حائط {nm}"),ha="right",fill=LT); ws.merge_cells(f"A{r}:C{r}"); st(ws.cell(r,4,-v),fill=LT); r+=1
        for nm,v in orows: st(ws.cell(r,1,nm),ha="right",fill=LT); ws.merge_cells(f"A{r}:C{r}"); st(ws.cell(r,4,-v),fill=LT); r+=1
        st(ws.cell(r,1,"مجموع الخصم"),b=True,fill=GREY); ws.merge_cells(f"A{r}:C{r}"); st(ws.cell(r,4,-deduct),b=True,fill=GREY); r+=2
        st(ws.cell(r,1,"الردم المدموك (صافي)"),b=True,fill=GRN); ws.merge_cells(f"A{r}:C{r}"); st(ws.cell(r,4,net),b=True,fill=GRN); r+=1
        st(ws.cell(r,1,f"الردم المطلوب توريده (×{COMPACTION})"),b=True,fill=GRN); ws.merge_cells(f"A{r}:C{r}"); st(ws.cell(r,4,supply),b=True,fill=GRN); r+=1
        st(ws.cell(r,1,"+ هدر 5٪ على التوريد"),b=True,fill=GREY); ws.merge_cells(f"A{r}:C{r}"); st(ws.cell(r,4,round(supply*WASTE,2)),b=True,fill=GREY); r+=2
        st(ws.cell(r,1,"⚠️ قيد الإكمال (تُخصَم لاحقاً): السملات، حفر الأسانسير، الهوابط السفلية، سمك العزل."),ha="right",fill=YEL); ws.merge_cells(f"A{r}:D{r}")
        for j,w in enumerate([30,14,14,12],1): ws.column_dimensions[get_column_letter(j)].width=w
        os.makedirs(OUT,exist_ok=True); p=os.path.join(OUT,"حصر الردم الداخلي - البدروم السفلي.xlsx")
        wb.save(p); print("SAVED:",p)
    except Exception as e:
        import traceback; print("Excel skip:",e); traceback.print_exc()

if __name__=="__main__":
    sys.stdout.reconfigure(encoding="utf-8",errors="replace"); main()
