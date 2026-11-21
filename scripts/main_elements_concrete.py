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

CEIL_SSL   = -3.85     # سقف البدروم السفلي (لِفت 1)
SLAB       = 0.22      # سماكة البلاطة → قاع السقف
BASE_WALL  = -6.75     # ظهر الجدار الشمالي (مارك C)
BASE_RAFT  = -8.45     # وش اللبشة (باقي الأعمدة)
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

    # ترتيب الأعمدة (أعلى→أسفل ثم يسار→يمين) وترقيمها
    colcols=[c for c in cols if not c[1].startswith("CORE")]
    colcols.sort(key=lambda c:(-c[3], c[2]))
    rows=[]; grand=0.0
    per_mark=collections.defaultdict(lambda: dict(n=0, v=0.0))
    for i,(sn,m,x,y) in enumerate(colcols,1):
        wh=stages_by_mark.get(m,[None])[0] if m in stages_by_mark else None
        base = BASE_WALL if m=="C" else BASE_RAFT
        h = round(soffit - base, 3)
        if wh:
            W,D=wh[0]/1000.0, wh[1]/1000.0; v=W*D*h
        else:
            W=D=0; v=0
        wall = (m=="C")
        rows.append(dict(no=i, mark=m, sec=(f"{wh[0]}×{wh[1]}" if wh else "—"),
                         base=base, h=h, W=W, D=D, v=v, wall=wall, x=x, y=y))
        grand+=v; per_mark[m]["n"]+=1; per_mark[m]["v"]+=v
    cores=sorted([m for m in counts if m.startswith("CORE")])

    # طباعة
    print(f"قاع السقف = {args.ceil} − {args.slab} = {soffit:.2f} | جدار C: ظهر {BASE_WALL} (ارتفاع {soffit-BASE_WALL:.2f}) | لبشة {BASE_RAFT} (ارتفاع {soffit-BASE_RAFT:.2f})")
    print(f"{'ماركة':6}{'عدد':5}{'ارتفاع':8}{'حجم م³':9}")
    for m in sorted(per_mark, key=ct.mark_key):
        hh = soffit-(BASE_WALL if m=="C" else BASE_RAFT)
        print(f"{m:6}{per_mark[m]['n']:<5}{hh:<8.2f}{per_mark[m]['v']:<9.1f}")
    print(f"\nإجمالي خرسانة الأعمدة (لِفت 1) = {grand:.1f} م³ | +هدر = {grand*WASTE:.1f} م³  | عدد الأعمدة {len(rows)}")
    print(f"الأكوار: {cores}")

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
    ws.merge_cells("A2:H2"); st(ws.cell(2,1,f"ارتفاع كل عمود = قاع السقف ({soffit:+.2f}) − ظهر قاعدته. أعمدة الجدار C من ‑6.75 (ارتفاع {soffit-BASE_WALL:.2f}م)؛ الباقي من اللبشة ‑8.45 (ارتفاع {soffit-BASE_RAFT:.2f}م). القاعدة ليست ضمن العمود."),sz=9,fill=GRN,ha="right",wrap=True); ws.row_dimensions[2].height=30
    for j,h in enumerate(["#","الماركة","المقطع (مم)","ظهر القاعدة","الارتفاع م","الحجم م³","نوع القاعدة","ملاحظة"],1): st(ws.cell(3,j,h),b=True,fill=NAVY,color="FFFFFF")
    r=4
    for d in rows:
        note = "جدار شمالي W1" if d["wall"] else ""
        fill = PUR if d["wall"] else None
        st(ws.cell(r,1,d["no"]),fill=fill); st(ws.cell(r,2,d["mark"]),b=True,fill=fill or LT)
        st(ws.cell(r,3,d["sec"])); st(ws.cell(r,4,f"{d['base']:+.2f}")); st(ws.cell(r,5,d["h"]))
        st(ws.cell(r,6,round(d["v"],3))); st(ws.cell(r,7,"ظهر الجدار" if d["wall"] else "وش اللبشة"),fill=fill)
        st(ws.cell(r,8,note),fill=fill,ha="right"); r+=1
    st(ws.cell(r,1,"الإجمالي"),b=True,fill=NAVY,color="FFFFFF"); ws.merge_cells(f"A{r}:E{r}")
    st(ws.cell(r,6,round(grand,2)),b=True,fill=LT); r+=1
    st(ws.cell(r,1,"+ هدر 5٪"),b=True,fill=GREY); ws.merge_cells(f"A{r}:E{r}"); st(ws.cell(r,6,round(grand*WASTE,2)),b=True,fill=LT); r+=1
    for j,w in enumerate([5,8,12,11,10,10,12,16],1): ws.column_dimensions[get_column_letter(j)].width=w
    ws.freeze_panes="A4"

    # ملخص بالماركة
    ws1=wb.create_sheet("ملخص الماركات"); ws1.sheet_view.rightToLeft=True
    for j,h in enumerate(["الماركة","العدد","المقطع","ظهر القاعدة","الارتفاع م","الحجم الكلي م³"],1): st(ws1.cell(1,j,h),b=True,fill=NAVY,color="FFFFFF")
    rr=2
    for m in sorted(per_mark, key=ct.mark_key):
        wh=stages_by_mark.get(m,[None])[0]; base=BASE_WALL if m=="C" else BASE_RAFT
        st(ws1.cell(rr,1,m),b=True,fill=LT); st(ws1.cell(rr,2,per_mark[m]["n"]))
        st(ws1.cell(rr,3,f"{wh[0]}×{wh[1]}" if wh else "—")); st(ws1.cell(rr,4,f"{base:+.2f}"))
        st(ws1.cell(rr,5,round(soffit-base,2))); st(ws1.cell(rr,6,round(per_mark[m]["v"],2))); rr+=1
    for j,w in enumerate([10,6,12,11,10,13],1): ws1.column_dimensions[get_column_letter(j)].width=w

    # الأكوار
    ws2=wb.create_sheet("الأكوار"); ws2.sheet_view.rightToLeft=True
    ws2.merge_cells("A1:E1"); st(ws2["A1"],b=True,sz=12,color="FFFFFF",fill=NAVY); ws2["A1"]="الأكوار (سلالم/أسانسير) CORE"
    for j,h in enumerate(["الكور","العدد","مساحة المقطع م²","ارتفاع م","حجم م³"],1): st(ws2.cell(2,j,h),b=True,fill=NAVY,color="FFFFFF")
    rr=3
    for c in cores:
        st(ws2.cell(rr,1,c),b=True,fill=LT); st(ws2.cell(rr,2,counts[c])); st(ws2.cell(rr,3,"؟ (مساحة مقطع الجدران — تُستخرَج)"),fill=YEL,ha="right"); st(ws2.cell(rr,4,round(soffit-BASE_RAFT,2))); st(ws2.cell(rr,5,"؟"),fill=YEL); rr+=1
    for j,w in enumerate([10,6,28,10,10],1): ws2.column_dimensions[get_column_letter(j)].width=w

    # الخزان والحوائط
    ws3=wb.create_sheet("الخزان والحوائط"); ws3.sheet_view.rightToLeft=True
    ws3.merge_cells("A1:D1"); st(ws3["A1"],b=True,sz=12,color="FFFFFF",fill=NAVY); ws3["A1"]="الخزان + الحوائط المحيطة"
    msgs=["الخزان T1: أرضية + حوائط + غطاء — أبعاد/مناسيب تُدخَل.",
          "الجدار الشمالي W1 (البنفسجي): ظاهر 1.70م على لبشة 40سم — الطول×1.70×السماكة. (أعمدته محسوبة أعلاه من ‑6.75.)",
          "الحوائط المحيطة W4 (غرب/جنوب/شرق): ارتفاع كامل حتى السقف — أطوال/سماكة/ارتفاع تُدخَل.",
          "الجدران غير مرسومة في الـDXF الإنشائي الحالي — تُدخَل أبعادها."]
    for i,msg in enumerate(msgs,3):
        ws3.merge_cells(f"A{i}:D{i}"); st(ws3.cell(i,1,msg),sz=10,fill=YEL,ha="right",wrap=True); ws3.row_dimensions[i].height=26
    for j,w in enumerate([30,20,20,20],1): ws3.column_dimensions[get_column_letter(j)].width=w

    # ملاحظات/مُعلَّقات
    ws4=wb.create_sheet("مُعلَّقات"); ws4.sheet_view.rightToLeft=True
    notes=["لِفت 1 فقط (اللبشة → ‑3.85). اللِفتات الأعلى تحتاج مناسيب الأدوار (متكرر/روف لم تصل).",
           "أعمدة الرمب: لم تُخصم سماكة الرمب بعد — محتاج قائمة الأعمدة التي تخترق الرمب + منسوب الرمب (أو الكمرة المقلوبة) لخصمها.",
           "10 قواعد مُثخّنة (وش ‑7.35..‑8.15) تحت بعض الأعمدة التقيلة → ارتفاعها أقل قليلاً؛ الربط الآلي عمود↔قاعدة غير نظيف (اللوحتان منفصلتان) — يُدقَّق لاحقاً.",
           "الأكوار: مساحة مقطع الجدران تُستخرَج/تُدخَل. الخزان والحوائط: أبعاد تُدخَل.",
           "الخصم العلوي: بلاطة 0.22. حيث توجد كمرة فوق العمود يُخصَم عمقها الكامل (لم يُضَف بعد)."]
    ws4.merge_cells("A1:A1"); st(ws4["A1"],b=True,sz=12,color="FFFFFF",fill=NAVY); ws4["A1"]="مُعلَّقات لرفع الدقة"
    for i,n in enumerate(notes,3):
        ws4.merge_cells(f"A{i}:H{i}"); st(ws4.cell(i,1,n),sz=10,ha="right",wrap=True,fill=YEL); ws4.row_dimensions[i].height=30
    ws4.column_dimensions["A"].width=120

    os.makedirs(args.outdir,exist_ok=True)
    out=os.path.join(args.outdir,"حصر خرسانة العناصر الرئيسية - لِفت 1.xlsx")
    wb.save(out); print("SAVED:",out)

if __name__=="__main__":
    main()
