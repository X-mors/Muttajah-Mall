# -*- coding: utf-8 -*-
"""
حصر خرسانة السقف (ceiling/slab CONCRETE volume takeoff) — مشروع Muttajah Mall.

خرسانة السقف = بلاطة + كمرات + (رامبات مائلة ولها كمرات)، بلا ازدواج حساب:
  • البلاطة = (مساحة − فتحات) × سُمك البلاطة t.
  • كل كمرة = العرض W × (العمق D − t) × الطول L   ← الظاهر أسفل البلاطة فقط
    (الجزء داخل سُمك البلاطة محسوب ضمن البلاطة، فلا يُضاف مرتين). المقطع من ليبل MARK(WxD)،
    الطول من زوج حواف الكمرة على طبقة S -Beams (نعيد استخدام beams_rebar.extract_beams).
  • الرامب: بلاطة وكمرات مثل أعلاه لكن على ميل → تُضرب أطوال/مساحات الرامب في معامل الميل
    factor = sqrt(1 + ميل²). الميل يُمرَّر بـ --ramp-slope-pct (يعرفه المهندس من اللوحة).

الاستخدام:
    python ceiling_concrete_takeoff.py "LOWER BASEMENT CEILING" [--slab 220] [--with-ramp]
           [--ramp-slope-pct 12] [--dwg]
"""
import argparse, os, math, collections, re
import ezdxf
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import takeoff, slab_mesh, beams_rebar as br

WASTE = 1.05           # هدر خرسانة ≈ 5٪

def beam_volume(beams, t_slab_mm, slope=1.0):
    """حجم الكمرات = Σ W×(D−t)×L (الظاهر أسفل البلاطة). المقلوبة نفس الصيغة. العمق المتغيّر = متوسط."""
    tot=0.0; rows=[]; nomatch=0
    for bm in beams:
        L=bm.get("length")
        if not L: nomatch+=1; continue
        D=bm["D"] if not bm.get("D2") else (bm["D"]+bm["D2"])/2.0
        stem=max(0.0, D - t_slab_mm)
        v=(bm["W"]/1000.0)*(stem/1000.0)*(L/1000.0)*slope
        tot+=v; rows.append((bm,D,stem,L*slope,v))
    return tot, rows, nomatch

def slab_area(msp, box, args):
    gx = slab_mesh.rebar_extent(msp, box)[0]
    gy = slab_mesh.rebar_extent(msp, box)[1]
    gross = gx*gy
    ops = slab_mesh.detect_openings(msp, box)[1]
    openings = sum(o[0] for o in ops)
    return gx, gy, gross, openings, gross-openings

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("ceiling"); ap.add_argument("--dxf", default=takeoff.DEFAULT_DXF)
    ap.add_argument("--outdir", default=takeoff.DEFAULT_OUT); ap.add_argument("--dwg", action="store_true")
    ap.add_argument("--slab", type=float, default=None, help="سُمك البلاطة مم (افتراضي: يُقرأ من SLAB= أو 220)")
    ap.add_argument("--with-ramp", action="store_true", help="أضِف كمرات رامبات البدروم (لوحة RAMPS) على ميل")
    ap.add_argument("--ramp-slope-pct", type=float, default=0.0, help="ميل الرامب ٪ (rise/run). المعامل=sqrt(1+(p/100)^2)")
    ap.add_argument("--ramp-area", type=float, default=None, help="مساحة بلاطة الرامب المسقطية م² (من المهندس/اللوحة) — لا تُقاس آلياً بثقة")
    ap.add_argument("--ramp-slab", type=float, default=None, help="سُمك بلاطة الرمب مم (افتراضي: السفلي 160 / العلوي 220 تلقائياً من اسم السقف)")
    args=ap.parse_args()
    doc=ezdxf.readfile(args.dxf); msp=doc.modelspace(); titles=takeoff.all_titles(msp)
    th=takeoff.find_title(titles, args.ceiling, "TOP")
    if not th: print("لا توجد لوحة TOP لهذا السقف."); return
    tx,ty,ttl=th[0]; tbox=takeoff.plan_bbox(titles,tx,ty)

    # سُمك البلاطة
    t_slab = args.slab
    if t_slab is None:
        try:
            import concrete_columns_takeoff as cc
            sb=cc.detect_slab(msp,[(tx,ty,ttl)]); t_slab=float(next(iter(sb.values()))) if sb else 220.0
        except Exception: t_slab=220.0
    t_slab=float(t_slab)

    # ---------- البلاطة المسطّحة ----------
    gx,gy,gross,openings,net = slab_area(msp,tbox,args)
    v_slab = net*(t_slab/1000.0)

    # ---------- الكمرات المسطّحة ----------
    beams,_,unclaimed = br.extract_beams(msp,tbox)
    v_beams, brows, bno = beam_volume(beams, t_slab, 1.0)

    # ---------- الرامبات (اختياري) ----------
    ramp=None
    if args.with_ramp:
        base=args.ceiling.upper().replace("CEILING","").strip()   # "LOWER BASEMENT"/"UPPER BASEMENT"
        rt=[x for x in titles if "RAMPS REINFORCEMENT PLAN" in x[2].upper() and base in x[2].upper()]
        if rt:
            rtx,rty,rttl=rt[0]; rbox=takeoff.plan_bbox(titles,rtx,rty)
            slope=math.sqrt(1+(args.ramp_slope_pct/100.0)**2)
            # سُمك بلاطة الرمب: السفلي 160 / العلوي 220 (مؤكّد من المهندس) — أو --ramp-slab للتجاوز
            if args.ramp_slab is not None: t_ramp=float(args.ramp_slab)
            elif "LOWER" in base: t_ramp=160.0
            elif "UPPER" in base: t_ramp=220.0
            else: t_ramp=t_slab
            rbeams,_,runcl = br.extract_beams(msp,rbox)
            rv_beams, rbrows, rbno = beam_volume(rbeams, t_ramp, slope)
            # مساحة بلاطة الرامب: تُقاس آلياً من شرائط RAMP 0N (أو --ramp-area للتجاوز)
            strips = br.measure_ramps(msp, rbox)
            auto_area = sum(s[3] for s in strips) if strips else None
            rnet = args.ramp_area if args.ramp_area is not None else auto_area
            rv_slab = (rnet*slope*(t_ramp/1000.0)) if rnet else None
            ramp=dict(title=rttl, slope_pct=args.ramp_slope_pct, slope=slope, t_ramp=t_ramp,
                      net=rnet, auto_area=auto_area, strips=strips, v_slab=rv_slab,
                      beams=rbeams, v_beams=rv_beams, rbrows=rbrows, box=rbox)
        else:
            print(f"تحذير: لم أجد لوحة رامبات لـ '{base}'")

    # ---------- الطباعة ----------
    print(f"السقف: {ttl}  | سُمك البلاطة {t_slab:.0f}مم")
    print(f"البلاطة: {gx:.2f}×{gy:.2f}={gross:.0f} − فتحات {openings:.0f} = صافي {net:.0f} م² → خرسانة {v_slab:.1f} م³")
    print(f"الكمرات: {len(beams)} جزء، طول {sum((b['length'] or 0) for b in beams)/1000:.1f}م → خرسانة {v_beams:.1f} م³ (ظاهر أسفل البلاطة)")
    sub = v_slab+v_beams
    if ramp:
        for nm,w,h,a in ramp.get("strips",[]):
            print(f"   {nm}: {w:.1f}×{h:.1f}م = {a:.1f} م² (مسقطي)")
        rslab = f"{ramp['v_slab']:.1f} م³ (مساحة {ramp['net']:.0f}م² × سُمك {ramp['t_ramp']:.0f}مم)" if ramp['v_slab'] is not None else "— (لا مساحة)"
        print(f"الرامب (ميل {ramp['slope_pct']:g}٪، معامل {ramp['slope']:.4f}، سُمك بلاطة {ramp['t_ramp']:.0f}مم): بلاطة {rslab} | كمرات {len(ramp['beams'])} جزء → {ramp['v_beams']:.1f} م³")
        sub += (ramp['v_slab'] or 0)+ramp['v_beams']
    print(f"الإجمالي{'(بدون بلاطة الرامب)' if (ramp and ramp['v_slab'] is None) else ''}: {sub:.1f} م³  | + هدر 5٪ = {sub*WASTE:.1f} م³")

    # ---------- EXCEL ----------
    NAVY,BLUE,LT,GREY,GRN="1F3864","2E5496","D9E1F2","F2F2F2","E2EFDA"
    thin=Side(style="thin",color="BFBFBF"); bd=Border(thin,thin,thin,thin)
    wb=Workbook()
    def st(c,*,b=False,sz=11,color="000000",fill=None,ha="center",wrap=False):
        c.font=Font(bold=b,size=sz,color=color); c.alignment=Alignment(ha,"center",wrap_text=wrap)
        if fill:c.fill=PatternFill("solid",fgColor=fill)
        c.border=bd
    ws=wb.active; ws.title="خرسانة السقف"; ws.sheet_view.rightToLeft=True
    ws.merge_cells("A1:F1"); st(ws["A1"],b=True,sz=15,color="FFFFFF",fill=NAVY); ws["A1"]=f"حصر خرسانة — {ttl}"
    r=3
    ws.merge_cells(f"A{r}:F{r}"); st(ws.cell(r,1,f"سُمك البلاطة {t_slab:.0f}مم | الكمرة تُحصَر بالظاهر أسفل البلاطة فقط (D−t) منعاً للازدواج | هدر 5٪"),sz=9,fill=GRN,ha="right"); r+=2
    # slab
    ws.merge_cells(f"A{r}:F{r}"); st(ws.cell(r,1,"◄ البلاطة المسطّحة"),b=True,color="FFFFFF",fill=BLUE,ha="right"); r+=1
    for h,c in [("الإجمالي (م²)",1),("الفتحات (م²)",2),("الصافي (م²)",3),("السُمك (م)",4),("الحجم (م³)",5)]:
        st(ws.cell(r,c,h),b=True,fill=NAVY,color="FFFFFF")
    r+=1
    for j,v in enumerate([round(gross),round(openings),round(net),round(t_slab/1000,3),round(v_slab,2)],1):
        st(ws.cell(r,j,v),b=(j==5),fill=(LT if j==5 else None)); r+=0
    r+=1
    # beams
    ws.merge_cells(f"A{r}:F{r}"); st(ws.cell(r,1,"◄ الكمرات المسطّحة (الظاهر أسفل البلاطة)"),b=True,color="FFFFFF",fill=BLUE,ha="right"); r+=1
    for h,c in [("الماركة",1),("المقطع WxD",2),("عدد الأجزاء",3),("إجمالي الطول (م)",4),("الحجم (م³)",5)]:
        st(ws.cell(r,c,h),b=True,fill=NAVY,color="FFFFFF")
    r+=1
    agg=collections.defaultdict(lambda:dict(n=0,L=0.0,v=0.0,sec=set()))
    for bm,D,stem,L,v in brows:
        k=bm["mk"]; agg[k]["n"]+=1; agg[k]["L"]+=L; agg[k]["v"]+=v; agg[k]["sec"].add(f"{bm['W']}×{bm['D']}")
    for mk in sorted(agg):
        st(ws.cell(r,1,mk),b=True,fill=LT); st(ws.cell(r,2," ، ".join(sorted(agg[mk]["sec"])))); st(ws.cell(r,3,agg[mk]["n"]))
        st(ws.cell(r,4,round(agg[mk]["L"]/1000,1))); st(ws.cell(r,5,round(agg[mk]["v"],2)),b=True); r+=1
    st(ws.cell(r,1,"مجموع الكمرات"),b=True,fill=GREY); ws.merge_cells(f"B{r}:D{r}")
    st(ws.cell(r,5,round(v_beams,2)),b=True,fill=LT); r+=1
    if bno: st(ws.cell(r,1,f"كمرات بلا طول مُلتقَط: {bno} (راجع اللوحة)"),sz=9,fill="FFF2CC",ha="right"); ws.merge_cells(f"A{r}:F{r}"); r+=1
    r+=1
    # ramp
    if ramp:
        ws.merge_cells(f"A{r}:F{r}"); st(ws.cell(r,1,f"◄ الرامبات (سُمك بلاطة {ramp['t_ramp']:.0f}مم | ميل {ramp['slope_pct']:g}٪ → معامل {ramp['slope']:.4f})"),b=True,color="FFFFFF",fill=BLUE,ha="right"); r+=1
        for nm,w,h,a in ramp.get("strips",[]):
            st(ws.cell(r,1,nm),fill=GREY); st(ws.cell(r,2,f"{w:.1f}×{h:.1f}م"),ha="center"); st(ws.cell(r,3,f"{a:.1f} م² مسقطي"),ha="center"); ws.merge_cells(f"C{r}:D{r}"); r+=1
        if ramp['v_slab'] is not None:
            src="مقاس آلياً" if (args.ramp_area is None) else "مُدخَل يدوياً"
            st(ws.cell(r,1,"بلاطة الرامب (م³)"),b=True,fill=LT); st(ws.cell(r,2,f"{ramp['net']:.0f}م² ({src}) × ميل × {ramp['t_ramp']/1000:.3f}"),ha="right"); ws.merge_cells(f"B{r}:D{r}"); st(ws.cell(r,5,round(ramp['v_slab'],2)),b=True,fill=LT); r+=1
        else:
            st(ws.cell(r,1,"بلاطة الرامب (م³)"),b=True,fill="FFF2CC"); st(ws.cell(r,2,"لم أجد شرائط رامب — مرّر --ramp-area"),ha="right",fill="FFF2CC"); ws.merge_cells(f"B{r}:E{r}"); r+=1
        st(ws.cell(r,1,"كمرات الرامب (م³)"),b=True,fill=LT); st(ws.cell(r,2,f"{len(ramp['beams'])} جزء × ميل"),ha="right"); ws.merge_cells(f"B{r}:D{r}"); st(ws.cell(r,5,round(ramp['v_beams'],2)),b=True,fill=LT); r+=1
        if ramp['slope_pct']==0: st(ws.cell(r,1,"⚠ الميل=0 (قيم مسقطية). مرّر --ramp-slope-pct بقيمة اللوحة لتطبيق الميل."),sz=9,fill="FFF2CC",ha="right"); ws.merge_cells(f"A{r}:F{r}"); r+=1
        r+=1
    # totals
    ws.merge_cells(f"A{r}:F{r}"); st(ws.cell(r,1,"◄ الإجمالي"),b=True,color="FFFFFF",fill=NAVY,ha="right"); r+=1
    st(ws.cell(r,1,"صافي خرسانة السقف (م³)"),b=True,fill=GREY); ws.merge_cells(f"B{r}:D{r}"); st(ws.cell(r,5,round(sub,2)),b=True,fill=LT); r+=1
    st(ws.cell(r,1,"مع هدر 5٪ (م³)"),b=True,fill=NAVY,color="FFFFFF"); ws.merge_cells(f"B{r}:D{r}"); st(ws.cell(r,5,round(sub*WASTE,2)),b=True,fill=LT); r+=1
    ws.column_dimensions["A"].width=22
    for cc in range(2,7): ws.column_dimensions[get_column_letter(cc)].width=14

    # beams detail sheet
    ws2=wb.create_sheet("تفاصيل الكمرات"); ws2.sheet_view.rightToLeft=True
    for j,h in enumerate(["#","الموقع","الماركة","W","D","الظاهر(D−t)","الطول(م)","الحجم(م³)"],1): st(ws2.cell(1,j,h),b=True,fill=NAVY,color="FFFFFF")
    i=0
    allrows=[("سقف",row) for row in brows]+([("رامب",row) for row in ramp['rbrows']] if ramp else [])
    for loc,(bm,D,stem,L,v) in allrows:
        i+=1
        for j,val in enumerate([i,loc,bm["mk"],bm["W"],bm["D"],round(stem),round(L/1000,2),round(v,3)],1): st(ws2.cell(i+1,j,val))
    for j,wd in enumerate([5,8,8,7,7,11,9,10],1): ws2.column_dimensions[get_column_letter(j)].width=wd
    ws2.freeze_panes="A2"

    os.makedirs(args.outdir,exist_ok=True)
    base=os.path.join(args.outdir, takeoff.safe(ttl)+" - خرسانة")
    xlsx=base+".xlsx"; wb.save(xlsx); print("SAVED:",xlsx)

    # review drawing: beam strips + serial
    doc2=ezdxf.readfile(args.dxf); msp2=doc2.modelspace(); LAY="CHECK-CONC-BEAMS"
    if LAY not in doc2.layers: doc2.layers.add(LAY,color=30)
    allb=list(beams)+(ramp['beams'] if ramp else [])
    for k,bm in enumerate(allb,1):
        if bm.get("orient")=="H": p0,p1=(bm["lo"],bm["pos"]),(bm["hi"],bm["pos"])
        elif bm.get("orient")=="V": p0,p1=(bm["pos"],bm["lo"]),(bm["pos"],bm["hi"])
        else: p0=None
        if p0: msp2.add_line(p0,p1,dxfattribs={"layer":LAY,"color":30})
        tt=msp2.add_text(f"{k}:{bm['mk']}",height=300,dxfattribs={"layer":LAY,"color":30}); tt.dxf.insert=(bm["cx"],bm["cy"]-450)
    review=base+" - review.dxf"; doc2.saveas(review); print("SAVED:",review)
    if args.dwg:
        d=takeoff.to_dwg(review); print("DWG:",d or "فشل")

if __name__=="__main__":
    main()
