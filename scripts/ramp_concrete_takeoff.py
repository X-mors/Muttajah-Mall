# -*- coding: utf-8 -*-
"""
حصر خرسانة رامب 3 و رامب 4 (البدروم السفلي) — من اللوحات، شامل الكمرات، غير شامل البادئ.
= بلاطة الرمب على الميل (سُمك 16سم) + الكمرات العرضية (250×700) — البادئ محسوب في العناصر الرأسية.

البلاطة: المساحة المسقطية من measure_ramps × معامل الميل × 0.16.
الكمرات: 5 كمرات عرضية لكل رمب (من ليبلات B2/B3 250×700)، جذع = العمق − البلاطة = 0.54م.
"""
import sys, os, math
import ezdxf, takeoff as tk, beams_rebar as br, concrete_columns_takeoff as cc

OUT=os.path.join(os.path.dirname(__file__), "..", "output")
SLAB=0.16          # سُمك بلاطة رمب البدروم السفلي (م) — من المهندس/اللوحة
BEAM_W=0.25; BEAM_D=0.70
STEM=round(BEAM_D-SLAB,3)   # جذع الكمرة تحت البلاطة (م) = 0.54
RISE=3.40          # ارتفاع الرمب ‑7.25→‑3.85

def ramp_data(msp):
    tt=tk.all_titles(msp); rt=[x for x in tt if "RAMPS REINFORCEMENT PLAN FOR LOWER" in x[2].upper()][0]
    bbox=tk.plan_bbox(tt, rt[0], rt[1]); xmid=(bbox[0]+bbox[1])/2
    strips=br.measure_ramps(msp, bbox)   # [(اسم, عرض, طول, مساحة)]
    # عدّ الكمرات لكل رمب من ليبلات B#(250x700) (كمرات عرضية، تُلبَل عند طرف/طرفين)
    import re, collections
    lab=collections.defaultdict(list)
    for e in msp.query("TEXT MTEXT"):
        try: t=" ".join((e.plain_text() if e.dxftype()=="MTEXT" else e.dxf.text).split())
        except: continue
        x,y=e.dxf.insert.x,e.dxf.insert.y
        if bbox[0]<=x<=bbox[1] and bbox[2]<=y<=bbox[3] and re.search(r"B\d\s*\(?\s*\d{3}\s*[xX×]\s*\d{3}", t):
            lab["RAMP04" if x<xmid else "RAMP03"].append(round(y))
    # كمرات متميّزة = مناسيب y مميّزة (ضمن 800مم) لكل رمب
    def nbeams(ys):
        ys=sorted(set(ys)); c=[]
        for y in ys:
            if c and y-c[-1][-1]<800: c[-1].append(y)
            else: c.append([y])
        return len(c)
    out=[]
    for nm,w,L,area in strips:
        n=nbeams(lab.get(nm,[]))
        out.append(dict(name=nm, width=round(w,2), plan_len=round(L,2), plan_area=round(area,2), n_beams=n))
    return out

def main():
    doc=ezdxf.readfile(cc.DEFAULT_DXF); msp=doc.modelspace()
    rds=ramp_data(msp)
    # معامل الميل للبلاطة: الرمب يرتفع 3.40م على طول مسقطي ≈ (طول الرمب) → sec(θ)
    rows=[]; v_slab_t=0.0; v_beam_t=0.0
    for r in rds:
        run=r["plan_len"]
        slope_factor=round(math.sqrt(1+(RISE/run)**2),4) if run else 1.0
        area_slope=round(r["plan_area"]*slope_factor,2)
        v_slab=round(area_slope*SLAB,2)
        # الكمرات العرضية: n × عرض الرمب (+ ارتكاز) × 0.25 × جذع 0.54
        beam_len=round(r["width"]+0.30,2)   # طول الكمرة ≈ عرض الرمب + ارتكاز
        v_beam=round(r["n_beams"]*beam_len*BEAM_W*STEM,2)
        rows.append(dict(**r, slope_factor=slope_factor, area_slope=area_slope,
                         v_slab=v_slab, beam_len=beam_len, v_beam=v_beam, v_total=round(v_slab+v_beam,2)))
        v_slab_t+=v_slab; v_beam_t+=v_beam
    total=round(v_slab_t+v_beam_t,2)
    # طباعة
    print("حصر خرسانة الرمبات (البدروم السفلي) — بلاطة على الميل 16سم + كمرات 250×700، بدون البادئ")
    for r in rows:
        print(f"\n{r['name']}: عرض {r['width']}م، طول مسقطي {r['plan_len']}م، مساحة مسقطية {r['plan_area']}م²")
        print(f"  البلاطة: {r['plan_area']} × ميل {r['slope_factor']} × {SLAB} = {r['v_slab']} م³")
        print(f"  الكمرات: {r['n_beams']} كمرة × {r['beam_len']}م × {BEAM_W} × جذع {STEM} = {r['v_beam']} م³")
        print(f"  إجمالي {r['name']} = {r['v_total']} م³")
    print(f"\nإجمالي البلاطات {round(v_slab_t,2)} + الكمرات {round(v_beam_t,2)} = {total} م³ | +هدر 5٪ = {round(total*1.05,2)} م³")
    # Excel
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
        NAVY,LT,GRN,GREY="1F3864","D9E1F2","E2EFDA","F2F2F2"
        bd=Border(*[Side(style="thin",color="BFBFBF")]*4)
        wb=Workbook(); ws=wb.active; ws.title="حصر الرمبات"; ws.sheet_view.rightToLeft=True
        def st(c,*,b=False,sz=11,color="000000",fill=None,ha="center",wrap=False):
            c.font=Font(bold=b,size=sz,color=color); c.alignment=Alignment(ha,"center",wrap_text=wrap)
            if fill:c.fill=PatternFill("solid",fgColor=fill)
            c.border=bd
        ws.merge_cells("A1:H1"); st(ws["A1"],b=True,sz=13,color="FFFFFF",fill=NAVY)
        ws["A1"]="حصر خرسانة رامب 3 و رامب 4 — البدروم السفلي (بلاطة على الميل + كمرات، بدون البادئ)"
        ws.merge_cells("A2:H2"); st(ws.cell(2,1,f"سُمك بلاطة الرمب {SLAB}م؛ الكمرات العرضية {int(BEAM_W*1000)}×{int(BEAM_D*1000)} جذع {STEM}م (العمق−البلاطة)؛ معامل الميل=√(1+(3.40/الطول)²). البادئ محسوب في العناصر الرأسية."),sz=9,fill=GRN,ha="right",wrap=True); ws.row_dimensions[2].height=30
        hdr=["الرمب","العرض م","الطول المسقطي م","مساحة مسقطية م²","معامل الميل","بلاطة م³","كمرات (عدد×طول) م³","إجمالي م³"]
        for j,h in enumerate(hdr,1): st(ws.cell(3,j,h),b=True,fill=NAVY,color="FFFFFF")
        r=4
        for d in rows:
            st(ws.cell(r,1,d["name"]),b=True,fill=LT); st(ws.cell(r,2,d["width"])); st(ws.cell(r,3,d["plan_len"]))
            st(ws.cell(r,4,d["plan_area"])); st(ws.cell(r,5,d["slope_factor"])); st(ws.cell(r,6,d["v_slab"]))
            st(ws.cell(r,7,f"{d['n_beams']}×{d['beam_len']} = {d['v_beam']}")); st(ws.cell(r,8,d["v_total"]),b=True); r+=1
        st(ws.cell(r,1,"الإجمالي"),b=True,fill=GRN); ws.merge_cells(f"A{r}:E{r}")
        st(ws.cell(r,6,round(v_slab_t,2)),b=True,fill=GRN); st(ws.cell(r,7,round(v_beam_t,2)),b=True,fill=GRN); st(ws.cell(r,8,total),b=True,fill=GRN); r+=1
        st(ws.cell(r,1,"+ هدر 5٪"),b=True,fill=GREY); ws.merge_cells(f"A{r}:G{r}"); st(ws.cell(r,8,round(total*1.05,2)),b=True,fill=GREY)
        for j,w in enumerate([12,8,14,14,10,10,18,10],1): ws.column_dimensions[get_column_letter(j)].width=w
        os.makedirs(OUT,exist_ok=True); p=os.path.join(OUT,"حصر خرسانة الرمبات - البدروم السفلي.xlsx")
        wb.save(p); print("SAVED:", p)
    except Exception as e:
        print("Excel skip:", e)

if __name__=="__main__":
    sys.stdout.reconfigure(encoding="utf-8",errors="replace"); main()
