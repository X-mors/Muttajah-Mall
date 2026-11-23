# -*- coding: utf-8 -*-
"""
البند 2: حصر العزل بالدهان (م²) — Muttajah Mall، البدروم السفلي. كله حتى منسوب الردم ‑7.35 بالظبط.
يقرأ من اللوحة (DXF) على الشبكة الموحّدة (column_exact.PLAN_ORIGIN) ومستطيلات الأعمدة من column_exact.

=================  المناسيب والفرضيات (مقروءة من اللوحة)  =================
• منسوب الردم (نهاية العزل) = ‑7.35. وش المات ‑8.45. قواعد مُثخّنة وشّها ‑8.15/‑7.85/‑7.75/‑7.55/‑7.35.
• أنواع الأسطح (كل نوع منفصل):
  1) أفقي: ظهر اللبشة والقواعد (= مساحة اللبشة − بصمات العناصر الرأسية؛ لا عزل تحت عنصر رأسي).
  2) رقاب الأعمدة: محيط كل عمود × (‑7.35 − وش قاعدته).
  3) الأكوار: جدرانها من كل الجوانب (الوجهان) × الارتفاع في مدى الردم.
  4) الجدار المحيط: الوش الداخلي فقط × الارتفاع (الخارجي ملاصق للأرض).
  5) الخزان: الوش الخارجي فقط × الارتفاع (من الداخل لا يُعزَل).
  6) بادئ الرمب: وجهاه × الارتفاع.
• الخزان من الداخل لا يُعزَل. تُخصَم بصمات الأعمدة/الحوائط من ظهر اللبشة (لا عزل تحتها).

⚠️ قيد الإكمال (تحتاج مخططات القطاع/التفصيل): جوانب القواعد والسملات والهوابط وحفر الأسانسير (أفقي رأسي)،
   وفتحات أبواب الأكوار أسفل منسوب الردم. ومحيطات الأكوار/الخزان هنا تقريبية (مساحة المقطع ÷ السماكة) لحين استخراج الحدود المرسومة.
"""
import sys, os, collections
import ezdxf, raft_footings as RF, concrete_columns_takeoff as cc, columns_takeoff as ct, column_exact as CX
import backfill_takeoff as BF

OUT=os.path.join(os.path.dirname(__file__), "..", "output")
FILL=-7.35; MAT_TOP=-8.45; WALL_THK=0.30; CORE_THK=0.30; TANK_THK=0.35; WASTE=1.05

def columns_surf(msp):
    """بصمة الأعمدة (تُخصَم من الأفقي) + رقاب الأعمدة الرأسية (محيط × ارتفاع)."""
    L=CX.LiftOne(msp); plan,sched=ct.collect(msp); stages,_=cc.parse_schedule_stages(sched)
    cols=[c for c in cc.columns_list(plan) if not c[1].startswith('CORE')]
    sz={m:stages[m][0] for m in stages}
    match=L.match([(sn,m,x,y) for sn,m,x,y in cols], sz)
    foot=0.0; vert=0.0; n=0
    for i,(sn,m,x,y) in enumerate(cols):
        if i not in match: continue
        r=match[i]; base=L.levels(r)['base']
        w=(r['x1']-r['x0'])/1000.0; h=(r['y1']-r['y0'])/1000.0; foot+=w*h
        if base<FILL-1e-6: vert+=2*(w+h)*(FILL-base); n+=1
    return round(foot,2), round(vert,2), n

def main():
    doc=ezdxf.readfile(cc.DEFAULT_DXF); msp=doc.modelspace()
    raft,_=BF.raft_zones(msp)
    col_foot, col_vert, ncn = columns_surf(msp)
    # بصمات العناصر الرأسية (تُخصَم من الأفقي)
    wall_segs=[("W1",48.835,-8.45),("W2",45.0,-8.45),("W3",53.335,-8.45),
               ("W4‑1",14.1,-8.45),("W4‑2",6.0,-8.15),("W4‑3",4.85,-8.45),("W4‑4",6.0,-8.15),("W4‑5",14.05,-8.45)]
    wall_foot=sum(L*WALL_THK for _,L,_ in wall_segs)
    core_foot=6.36*2+2.55; tank_foot=16.6334+1.35+0.65; start_foot=(3.9+4.2)*0.25
    horiz=round(raft-(col_foot+wall_foot+core_foot+tank_foot+start_foot),2)
    # رأسي
    perim_wall=round(sum(L*(FILL-b) for _,L,b in wall_segs),2)                 # الوش الداخلي للجدار المحيط
    cores_v=round((2*(6.36/CORE_THK)*(FILL-(-7.75)))*2 + 2*(2.55/CORE_THK)*(FILL-(-7.75)),2)  # الأكوار الوجهان
    tank_outer=round(40.4*(FILL-(-7.75)),2)                                    # محيط خارجي ≈40.4م (L 10.51×9.70) × الارتفاع
    starter_v=round(2*(3.9+4.2)*(FILL-MAT_TOP),2)                              # بادئ الرمب وجهاه
    surfaces=[("أفقي: ظهر اللبشة والقواعد (− بصمات العناصر)", horiz),
              ("رأسي: رقاب الأعمدة", col_vert),
              ("رأسي: الأكوار (الوجهان)", cores_v),
              ("رأسي: الجدار المحيط (الوش الداخلي)", perim_wall),
              ("رأسي: الخزان (الوش الخارجي)", tank_outer),
              ("رأسي: بادئ الرمب (الوجهان)", starter_v)]
    total=round(sum(v for _,v in surfaces),2)
    print("البند 2: حصر العزل بالدهان — البدروم السفلي (حتى منسوب الردم ‑7.35)")
    print(f"اللبشة الكلية {raft:.1f} م² − بصمات (أعمدة {col_foot} + حوائط {round(wall_foot,1)} + أكوار {round(core_foot,1)} + خزان {round(tank_foot,1)} + بادئ {round(start_foot,2)})")
    for nm,v in surfaces: print(f"  {nm}: {v} م²")
    print(f"\nإجمالي العزل = {total} م² | +هدر 5٪ = {round(total*WASTE,2)} م²")
    print("⚠️ لم تُضَف بعد: جوانب القواعد/السملات/الهوابط/حفر الأسانسير، وفتحات الأبواب.")
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
        wb=Workbook(); ws=wb.active; ws.title="العزل"; ws.sheet_view.rightToLeft=True
        ws.merge_cells("A1:C1"); st(ws["A1"],b=True,sz=13,color="FFFFFF",fill=NAVY); ws["A1"]="البند 2: حصر العزل بالدهان — البدروم السفلي"
        ws.merge_cells("A2:C2"); st(ws.cell(2,1,"كله حتى منسوب الردم ‑7.35. الأفقي = ظهر اللبشة − بصمات العناصر الرأسية. الرأسي = محيط كل عنصر × الارتفاع. الخزان من الخارج فقط. (محيطات الأكوار/الخزان تقريبية لحين استخراج الحدود المرسومة.)"),sz=9,fill=GRN,ha="right",wrap=True); ws.row_dimensions[2].height=40
        for j,h in enumerate(["نوع السطح","المساحة م²",""],1): st(ws.cell(3,j,h),b=True,fill=LT)
        r=4
        for nm,v in surfaces: st(ws.cell(r,1,nm),ha="right",fill=LT); ws.merge_cells(f"A{r}:A{r}"); st(ws.cell(r,2,v)); r+=1
        st(ws.cell(r,1,"إجمالي العزل (صافي)"),b=True,fill=GRN); st(ws.cell(r,2,total),b=True,fill=GRN); r+=1
        st(ws.cell(r,1,"+ هدر 5٪"),b=True,fill=GREY); st(ws.cell(r,2,round(total*WASTE,2)),b=True,fill=GREY); r+=2
        st(ws.cell(r,1,"⚠️ قيد الإكمال: جوانب القواعد/السملات/الهوابط/حفر الأسانسير، وفتحات الأبواب."),ha="right",fill=YEL); ws.merge_cells(f"A{r}:C{r}")
        for j,w in enumerate([44,14,4],1): ws.column_dimensions[get_column_letter(j)].width=w
        os.makedirs(OUT,exist_ok=True); p=os.path.join(OUT,"حصر العزل بالدهان - البدروم السفلي.xlsx")
        wb.save(p); print("SAVED:",p)
    except Exception as e:
        import traceback; print("Excel skip:",e); traceback.print_exc()

if __name__=="__main__":
    sys.stdout.reconfigure(encoding="utf-8",errors="replace"); main()
