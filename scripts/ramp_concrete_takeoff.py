# -*- coding: utf-8 -*-
"""
حصر خرسانة رامب 3 و رامب 4 (البدروم السفلي) — من اللوحات، شامل الكمرات، غير شامل البادئ.
مطابق لطريقة الحصر الدقيق (مراجعة البروجكت):
  • البلاطة على الميل = 3 أجزاء لكل رمب (7.5٪ أول/آخر 3م، ~15٪ النص) من مناسيب القطاع × 0.16م.
  • الكمرات المقلوبة INV = كمرات طولية على حواف الرمب (تجري بطول الميل)، الجزء الطالع فوق البلاطة = 0.54م.
      RAMP04: حافة واحدة (K1)؛ الحافة الأخرى حائط محيطي. RAMP03: حافتان (K2–K11).
  • يُخصَم من بلاطة RAMP03 الأعمدة المستمرة التي تعبر البلاطة (D1–D11).
  • البادئ غير داخل (محسوب في العناصر الرأسية).
"""
import sys, os, math
import ezdxf, takeoff as tk, beams_rebar as br, concrete_columns_takeoff as cc

OUT=os.path.join(os.path.dirname(__file__), "..", "output")
SLAB=0.16; BEAM_D=0.70; STEM=round(BEAM_D-SLAB,3)   # جذع الكمرة فوق البلاطة = 0.54م

# معطيات مُستخرَجة من مسقط الرمب + القطاع (لوحة البدروم السفلي)
RAMPS=[
  dict(name="رامب 04", width=3.9,
       # (من محطة، إلى محطة، منسوب الوش بداية، منسوب الوش نهاية)
       parts=[("S1 أول 3م (7.5٪)",0,3,-7.2,-6.975),
              ("S2 الأوسط (~15٪)",3,22,-6.975,-4.075),
              ("S3 آخر 3م (7.5٪)",22,25,-4.075,-3.85)],
       # كمرات الحواف الطولية: (وصف، الطول الأفقي م، العرض م)
       beams=[("K1 الحافة الشرقية B2(250×700)", 23.9, 0.25)],
       col_deduct=0.000),   # أعمدة RAMP04 تقف تحت الرمب → لا خصم
  dict(name="رامب 03", width=4.2,
       parts=[("S4 أول 3م (7.5٪)",0,3,-7.35,-7.125),
              ("S5 الأوسط (~15٪)",3,23.3,-7.125,-4.075),
              ("S6 آخر 3م (7.5٪)",23.3,26.3,-4.075,-3.85)],
       beams=[("الحافة الغربية K2–K6 B2(250×700)", 21.3, 0.25),
              ("الحافة الشرقية K8–K11 B2/B3(250×700)", 16.5, 0.25),
              ("الحافة الشرقية K7 B2(200×700)", 4.2, 0.20)],
       col_deduct=0.417),   # 11 عمود مستمر يعبر بلاطة RAMP03 (D1–D11) × 0.16
]

def slope_factor(run, rise):
    return math.sqrt(1+(rise/run)**2) if run else 1.0

def takeoff(ramp):
    rows_s=[]; v_slab=0.0
    for nm,a,b,z0,z1 in ramp["parts"]:
        run=b-a; rise=abs(z1-z0); f=round(slope_factor(run,rise),4)
        slen=round(run*f,2); area=round(slen*ramp["width"],2); v=round(area*SLAB,3)
        rows_s.append((nm,run,round(rise,3),f,area,v)); v_slab+=v
    rows_b=[]; v_beam=0.0
    # معامل ميل تقريبي للكمرات = متوسط ميل الرمب
    totrun=ramp["parts"][-1][2]-ramp["parts"][0][1]; totrise=abs(ramp["parts"][-1][4]-ramp["parts"][0][3])
    bf=round(slope_factor(totrun,totrise),4)
    for nm,L,w in ramp["beams"]:
        v=round(L*bf*w*STEM,3); rows_b.append((nm,L,w,bf,v)); v_beam+=v
    net=round(v_slab+v_beam-ramp["col_deduct"],3)
    return rows_s, rows_b, round(v_slab,3), round(v_beam,3), ramp["col_deduct"], net

def main():
    results=[]; grand=0.0
    for r in RAMPS:
        rs,rb,vs,vb,cd,net=takeoff(r); results.append((r,rs,rb,vs,vb,cd,net)); grand+=net
        print(f"\n=== {r['name']} === بلاطة {vs} + كمرات {vb} − أعمدة {cd} = {net} م³")
        for nm,run,rise,f,area,v in rs: print(f"  بلاطة {nm}: طول {run}م رفع {rise}م ميل×{f} مساحة {area}م² = {v}م³")
        for nm,L,w,f,v in rb: print(f"  كمرة {nm}: طول {L}م × ميل {f} × {w} × جذع {STEM} = {v}م³")
    grand=round(grand,2)
    print(f"\nالإجمالي الصافي = {grand} م³ | +هدر 5٪ = {round(grand*1.05,2)} م³")
    # Excel
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
        NAVY,LT,GRN,GREY,ORG="1F3864","D9E1F2","E2EFDA","F2F2F2","FCE4D6"
        bd=Border(*[Side(style="thin",color="BFBFBF")]*4)
        def st(c,*,b=False,sz=11,color="000000",fill=None,ha="center",wrap=False):
            c.font=Font(bold=b,size=sz,color=color); c.alignment=Alignment(ha,"center",wrap_text=wrap)
            if fill:c.fill=PatternFill("solid",fgColor=fill)
            c.border=bd
        wb=Workbook(); ws=wb.active; ws.title="حصر الرمبات"; ws.sheet_view.rightToLeft=True
        ws.merge_cells("A1:F1"); st(ws["A1"],b=True,sz=13,color="FFFFFF",fill=NAVY)
        ws["A1"]="حصر خرسانة رامب 3 و رامب 4 — البدروم السفلي (بلاطة على الميل + كمرات حافة طولية، بدون البادئ)"
        ws.merge_cells("A2:F2"); st(ws.cell(2,1,f"بلاطة {SLAB}م (3 أجزاء بميل متغيّر من القطاع)؛ كمرات مقلوبة طولية على الحواف، جذع {STEM}م فوق البلاطة؛ خصم الأعمدة المستمرة في RAMP03؛ البادئ محسوب في العناصر الرأسية."),sz=9,fill=GRN,ha="right",wrap=True); ws.row_dimensions[2].height=32
        r=3
        for rmp,rs,rb,vs,vb,cd,net in results:
            ws.merge_cells(f"A{r}:F{r}"); st(ws.cell(r,1,rmp["name"]),b=True,fill=NAVY,color="FFFFFF"); r+=1
            for j,h in enumerate(["البند","الطول/الرفع م","الميل","المساحة/العرض","السُمك/الجذع م","الحجم م³"],1): st(ws.cell(r,j,h),b=True,fill=LT);
            r+=1
            for nm,run,rise,f,area,v in rs:
                st(ws.cell(r,1,nm),ha="right"); st(ws.cell(r,2,f"{run} / {rise}")); st(ws.cell(r,3,f)); st(ws.cell(r,4,f"{area} م²")); st(ws.cell(r,5,SLAB)); st(ws.cell(r,6,v)); r+=1
            for nm,L,w,f,v in rb:
                st(ws.cell(r,1,nm),ha="right",fill=ORG); st(ws.cell(r,2,L),fill=ORG); st(ws.cell(r,3,f),fill=ORG); st(ws.cell(r,4,f"{w}م عرض",),fill=ORG); st(ws.cell(r,5,STEM),fill=ORG); st(ws.cell(r,6,v),fill=ORG); r+=1
            if cd: st(ws.cell(r,1,"يُخصَم: أعمدة مستمرة تعبر البلاطة"),ha="right",fill=GREY); ws.merge_cells(f"A{r}:E{r}"); st(ws.cell(r,6,-cd),fill=GREY); r+=1
            st(ws.cell(r,1,f"صافي {rmp['name']}"),b=True,fill=GRN); ws.merge_cells(f"A{r}:E{r}"); st(ws.cell(r,6,net),b=True,fill=GRN); r+=2
        st(ws.cell(r,1,"الإجمالي الصافي"),b=True,fill=NAVY,color="FFFFFF"); ws.merge_cells(f"A{r}:E{r}"); st(ws.cell(r,6,grand),b=True,fill=GRN); r+=1
        st(ws.cell(r,1,"+ هدر 5٪"),b=True,fill=GREY); ws.merge_cells(f"A{r}:E{r}"); st(ws.cell(r,6,round(grand*1.05,2)),b=True,fill=GREY)
        for j,w in enumerate([34,14,8,13,13,10],1): ws.column_dimensions[get_column_letter(j)].width=w
        os.makedirs(OUT,exist_ok=True); p=os.path.join(OUT,"حصر خرسانة الرمبات - البدروم السفلي.xlsx")
        wb.save(p); print("SAVED:", p)
    except Exception as e:
        import traceback; print("Excel skip:", e); traceback.print_exc()

if __name__=="__main__":
    sys.stdout.reconfigure(encoding="utf-8",errors="replace"); main()
