# -*- coding: utf-8 -*-
"""
حصر خرسانة العناصر الرئيسية الرأسية — Muttajah Mall (جدول موحّد في Excel):
  • الأعمدة (بأرقام الماركات C..C10) — مقطع كل مرحلة × العدد × الارتفاع الصافي.
  • الأكوار (CORE1/2/3 — سلالم/أسانسير) — مقطع (مساحة) × ارتفاع. [مساحة المقطع تُؤكّد]
  • الخزان — [أبعاد/مناسيب من المهندس].

الارتفاع لكل عنصر = منسوب السقف (أو قاع الكمرة/الهابط) − منسوب القاعدة. المناسيب (مؤكّدة):
  قاعدة البدروم (قواعد عالية) = -7.35 | سقف بدروم علوي = -0.10 | سقف أرضي = +5.70.
  المراحل 3-5 (متكرر/روف) تنتظر مناسيبها. خصم البلاطة 0.22 (الهابط 0.32 حيث يوجد — مبدئياً بلاطة).

⚠️ أساس الحصر (شفافية): مناسيب القاعدة بالمنطقة (‑7.35 للقواعد العالية)، وسقف البدروم العلوي مُدرَّج
  (‑0.10/+1.10) أُخذ ‑0.10؛ الأعمدة على ظهر الجدار (1.70م)/الرمب بدايتها أعلى (تُصحَّح لاحقاً).
"""
import argparse, os, collections
import ezdxf
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import columns_takeoff as ct
import concrete_columns_takeoff as cc

# مناسيب المراحل (قاعدة، سقف) بالمتر — مؤكّدة من اللوحة/المهندس
STAGES = [
    ("مرحلة 1: البدروم (قاعدة → سقف بدروم علوي)", -7.35, -0.10),
    ("مرحلة 2: الأرضي (سقف بدروم علوي → سقف أرضي)", -0.10, 5.70),
]
SLAB_DED = 0.22      # خصم البلاطة م (الهابط 0.32 حيث يوجد — يُضاف لاحقاً)
WASTE = 1.05

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--dxf", default=cc.DEFAULT_DXF)
    ap.add_argument("--slab", type=float, default=SLAB_DED)
    ap.add_argument("--outdir", default=r"D:\مشروع الحصر\output")
    args=ap.parse_args()
    doc=ezdxf.readfile(args.dxf); msp=doc.modelspace()
    plan, sched = ct.collect(msp)
    counts = ct.count_marks(plan)
    stages_by_mark, stage_names = cc.parse_schedule_stages(sched)
    marks = sorted([m for m in counts if not m.startswith("CORE")], key=ct.mark_key)
    cores = sorted([m for m in counts if m.startswith("CORE")])

    # ارتفاع صافٍ لكل مرحلة
    net_h=[round(top-base-args.slab,3) for (_,base,top) in STAGES]

    # ── حساب الأعمدة ──
    col_rows=[]      # (mark, count, [ (sec_str, area, vol_per, vol_total) per stage ], mark_total)
    grand=0.0
    for m in marks:
        secs=stages_by_mark.get(m, [None]*len(stage_names))
        n=counts[m]; per_stage=[]; mtot=0.0
        for si,(label,base,top) in enumerate(STAGES):
            wh=secs[si] if si<len(secs) else None
            if wh:
                a=cc.section_area_m2(wh); vper=a*net_h[si]; vtot=vper*n
                per_stage.append((f"{wh[0]}×{wh[1]}", a, vper, vtot)); mtot+=vtot
            else:
                per_stage.append(("—",0,0,0))
        col_rows.append((m,n,per_stage,mtot)); grand+=mtot

    # ── طباعة ملخص ──
    print("مرحلة | ارتفاع صافٍ م:", {f"S{i+1}":net_h[i] for i in range(len(STAGES))})
    print(f"\n{'ماركة':6}{'عدد':5}{'م1 مقطع':10}{'م1 حجم':9}{'م2 مقطع':10}{'م2 حجم':9}{'إجمالي م³':10}")
    for m,n,ps,mtot in col_rows:
        print(f"{m:6}{n:<5}{ps[0][0]:10}{ps[0][3]:<9.1f}{ps[1][0]:10}{ps[1][3]:<9.1f}{mtot:<10.1f}")
    print(f"\nإجمالي خرسانة الأعمدة (مرحلة 1+2) = {grand:.1f} م³ | + هدر 5٪ = {grand*WASTE:.1f} م³")
    print(f"الأكوار: {cores} (عدد {[counts[c] for c in cores]}) — مقطع يُؤكّد")

    # ── Excel ──
    NAVY,BLUE,LT,GREY,GRN,YEL="1F3864","2E5496","D9E1F2","F2F2F2","E2EFDA","FFF2CC"
    thin=Side(style="thin",color="BFBFBF"); bd=Border(thin,thin,thin,thin)
    wb=Workbook()
    def st(c,*,b=False,sz=11,color="000000",fill=None,ha="center",wrap=False):
        c.font=Font(bold=b,size=sz,color=color); c.alignment=Alignment(ha,"center",wrap_text=wrap)
        if fill:c.fill=PatternFill("solid",fgColor=fill)
        c.border=bd

    # Sheet 1: الأعمدة
    ws=wb.active; ws.title="الأعمدة"; ws.sheet_view.rightToLeft=True
    ws.merge_cells("A1:I1"); st(ws["A1"],b=True,sz=14,color="FFFFFF",fill=NAVY); ws["A1"]="حصر خرسانة الأعمدة — العناصر الرئيسية"
    ws.merge_cells("A2:I2"); st(ws.cell(2,1,f"الارتفاع الصافي: مرحلة1 {net_h[0]}م (قاعدة ‑7.35 → سقف بدروم علوي ‑0.10) | مرحلة2 {net_h[1]}م (‑0.10 → أرضي +5.70) | خصم بلاطة {args.slab}م"),sz=9,fill=GRN,ha="right",wrap=True); ws.row_dimensions[2].height=28
    hdr=["الماركة","العدد","م1: المقطع","م1: مساحة م²","م1: حجم م³","م2: المقطع","م2: مساحة م²","م2: حجم م³","إجمالي م³"]
    for j,h in enumerate(hdr,1): st(ws.cell(3,j,h),b=True,fill=NAVY,color="FFFFFF")
    r=4
    for m,n,ps,mtot in col_rows:
        term = " (ينتهي بالبدروم)" if ps[1][0]=="—" else ""
        st(ws.cell(r,1,m+term),b=True,fill=LT,ha="right"); st(ws.cell(r,2,n))
        st(ws.cell(r,3,ps[0][0])); st(ws.cell(r,4,round(ps[0][1],3))); st(ws.cell(r,5,round(ps[0][3],2)))
        st(ws.cell(r,6,ps[1][0])); st(ws.cell(r,7,round(ps[1][1],3) or "—")); st(ws.cell(r,8,round(ps[1][3],2) or "—"))
        st(ws.cell(r,9,round(mtot,2)),b=True,fill=GRN); r+=1
    st(ws.cell(r,1,"إجمالي الأعمدة"),b=True,fill=NAVY,color="FFFFFF"); ws.merge_cells(f"A{r}:H{r}")
    st(ws.cell(r,9,round(grand,2)),b=True,fill=LT); r+=1
    st(ws.cell(r,1,f"+ هدر 5٪"),b=True,fill=GREY); ws.merge_cells(f"A{r}:H{r}"); st(ws.cell(r,9,round(grand*WASTE,2)),b=True,fill=LT); r+=1
    for j,w in enumerate([16,6,11,11,10,11,11,10,11],1): ws.column_dimensions[get_column_letter(j)].width=w

    # Sheet 2: الأكوار
    ws2=wb.create_sheet("الأكوار"); ws2.sheet_view.rightToLeft=True
    ws2.merge_cells("A1:F1"); st(ws2["A1"],b=True,sz=13,color="FFFFFF",fill=NAVY); ws2["A1"]="الأكوار (سلالم/أسانسير) — CORE"
    for j,h in enumerate(["الكور","العدد","مساحة المقطع م²","ارتفاع م1","ارتفاع م2","حجم م³"],1): st(ws2.cell(2,j,h),b=True,fill=NAVY,color="FFFFFF")
    rr=3
    for c in cores:
        st(ws2.cell(rr,1,c),b=True,fill=LT); st(ws2.cell(rr,2,counts[c]))
        st(ws2.cell(rr,3,"؟ (مساحة مقطع جدار الكور — تُؤكّد)"),fill=YEL,ha="right"); ws2.merge_cells(f"C{rr}:F{rr}"); rr+=1
    ws2.merge_cells(f"A{rr}:F{rr}"); st(ws2.cell(rr,1,"الأكوار = جدران قص؛ الحجم = مساحة مقطع الجدران × الارتفاع (مثل الأعمدة). محتاج مساحة مقطع كل كور (من اللوحة أو منك)."),sz=9,fill=YEL,ha="right",wrap=True); ws2.row_dimensions[rr].height=30
    for j,w in enumerate([10,6,30,10,10,10],1): ws2.column_dimensions[get_column_letter(j)].width=w

    # Sheet 3: الخزان
    ws3=wb.create_sheet("الخزان"); ws3.sheet_view.rightToLeft=True
    ws3.merge_cells("A1:D1"); st(ws3["A1"],b=True,sz=13,color="FFFFFF",fill=NAVY); ws3["A1"]="الخزان (Tank)"
    ws3.merge_cells("A3:D3"); st(ws3.cell(3,1,"لم أجد ليبل «خزان/TANK» في اللوحة الحالية. محتاج موقعه وأبعاده (أرضية + حوائط + غطاء) ومناسيبه لحصره بدقة."),sz=10,fill=YEL,ha="right",wrap=True); ws3.row_dimensions[3].height=40
    for j,w in enumerate([20,20,20,20],1): ws3.column_dimensions[get_column_letter(j)].width=w

    # Sheet 4: ملاحظات
    ws4=wb.create_sheet("أساس الحصر"); ws4.sheet_view.rightToLeft=True
    notes=[
      "العناصر الرئيسية الرأسية فقط: أعمدة + أكوار + خزان.",
      "الارتفاع = منسوب السقف − منسوب القاعدة، ناقص خصم البلاطة (0.22) أو الهابط (0.32) أعلى العنصر.",
      "C و C1 ينتهيان في البدروم (مرحلة 1 فقط) = أعمدة لا تكمل. C2–C10 تكمل (مراحل أعلى).",
      "مناسيب مؤكّدة: قاعدة ‑7.35 (قواعد عالية) | سقف بدروم علوي ‑0.10 | سقف أرضي +5.70.",
      "⚠️ مُعلَّق لرفع الدقة: (1) مناسيب المتكرر/الروف (مراحل 3‑5). (2) مساحة مقطع الأكوار. (3) أبعاد/مناسيب الخزان.",
      "(4) الأعمدة على ظهر الجدار (1.70م) والرمب: بدايتها أعلى — ضمن العام الآن، تُصحَّح بتحديد أرقامها.",
      "(5) خصم عمق الكمرة الكامل للأعمدة تحت كمرات — مبدئياً بلاطة/هابط، يُضاف لاحقاً.",
      "(6) سقف البدروم العلوي مُدرَّج (‑0.10/+1.10)؛ أُخذ ‑0.10 — الأعمدة بزون +1.10 أطول ~1.2م.",
    ]
    ws4.merge_cells("A1:A1"); st(ws4["A1"],b=True,sz=12,color="FFFFFF",fill=NAVY); ws4["A1"]="أساس الحصر والمُعلَّقات"
    for i,n in enumerate(notes,3):
        ws4.merge_cells(f"A{i}:H{i}"); st(ws4.cell(i,1,n),sz=10,ha="right",wrap=True,fill=(YEL if "⚠️" in n or n.startswith("(") else None)); ws4.row_dimensions[i].height=24
    ws4.column_dimensions["A"].width=120

    os.makedirs(args.outdir,exist_ok=True)
    out=os.path.join(args.outdir,"حصر خرسانة العناصر الرئيسية - Muttajah Mall.xlsx")
    wb.save(out); print("SAVED:",out)

if __name__=="__main__":
    main()
