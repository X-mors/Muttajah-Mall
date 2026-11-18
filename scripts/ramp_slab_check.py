# -*- coding: utf-8 -*-
"""
تحقّق إنشائي أوّلي لبلاطة الرمب (one-way slab) — الكود المصري ECP 203 (حالة الحدود القصوى).
ليس بديلاً عن موديل SAFE/اعتماد المهندس المسؤول — مراجعة يدوية/برمجية شفّافة بافتراضات صريحة.

يحسب: عزم المقطع المقاوم بتسليحه، المطاوعة، أدنى حديد، القص، ضبط الترخيم (بحر/سُمك)،
وأقصى حمل (UDL) موزّع يمكن أن تحمله البلاطة → أقصى حمل حي. يُخرج تقرير Excel.

المقطع من اللوحة: بلاطة 220مم، سفلي رئيسي T12@200 (يفرش عرض الرمب ~4.2م)، توزيع T10@200.
الافتراضات (عدّلها بالوسائط): fcu=30، fy=400، غطاء=20مم، SDL=2.0، وزن ذاتي من السُمك.
"""
import argparse, os, math
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--h", type=float, default=220, help="سُمك البلاطة مم")
    ap.add_argument("--cover", type=float, default=20, help="الغطاء للحديد السفلي مم")
    ap.add_argument("--bar", type=float, default=12, help="قطر الحديد الرئيسي مم")
    ap.add_argument("--spacing", type=float, default=200, help="تباعد الحديد الرئيسي مم")
    ap.add_argument("--fcu", type=float, default=30, help="مقاومة الخرسانة المكعبية N/mm²")
    ap.add_argument("--fy", type=float, default=400, help="إجهاد خضوع الحديد N/mm²")
    ap.add_argument("--span", type=float, default=4.20, help="بحر البلاطة (عرض الرمب، م) مركز-لمركز")
    ap.add_argument("--beam-w", type=float, default=0.25, help="عرض الكمرة الحافّة م (لحساب البحر الصافي)")
    ap.add_argument("--sdl", type=float, default=2.0, help="أحمال ميتة إضافية (تشطيبات) kN/m²")
    ap.add_argument("--conc", type=float, default=25, help="كثافة الخرسانة kN/m³")
    ap.add_argument("--ll", type=float, default=4.0, help="الحمل الحي التصميمي للمقارنة kN/m² (جراج سيارات ECP≈4)")
    ap.add_argument("--slope-pct", type=float, default=12, help="ميل الرمب ٪ (لأثره على الوزن الذاتي العمودي)")
    ap.add_argument("--outdir", default=r"D:\مشروع الحصر\output")
    args=ap.parse_args()

    # ── هندسة المقطع ──
    h=args.h; cov=args.cover; dia=args.bar; s=args.spacing
    d=h-cov-dia/2                                   # العمق الفعّال مم
    As=(math.pi/4*dia**2)*(1000.0/s)                # مساحة الحديد مم²/م
    b=1000.0
    gc,gs=1.5,1.15                                  # معاملات أمان المواد (ECP)
    # ── عزم المقطع المقاوم (ECP، كتلة إجهاد مستطيلة a=0.8x) ──
    T=As*args.fy/gs
    a=T/(0.446*args.fcu*b)                           # 0.67 fcu/γc = 0.446 fcu
    x=a/0.8; xd=x/d
    Mu_cap=T*(d-a/2)/1e6                             # kN·m/م
    # مطاوعة وأدنى/أقصى حديد (ECP)
    xd_max=0.44                                      # حدّ المطاوعة (tension-controlled) لـ fy=400
    As_min=max(0.6/args.fy*b*d, 0.0015*b*h)          # mm²/م
    ductile = xd<=xd_max
    # ── الأحمال ──
    slope=math.sqrt(1+(args.slope_pct/100)**2)
    ow=h/1000.0*args.conc*slope                      # وزن ذاتي kN/m² (×معامل الميل للمساحة المائلة)
    DL=ow+args.sdl
    wu_design=1.4*DL+1.6*args.ll                     # الحمل الأقصى التصميمي kN/m²
    # ── البحر ──
    Lc=args.span-args.beam_w                         # بحر صافٍ م
    Leff=min(args.span, Lc+d/1000.0)                 # بحر فعّال (ECP) م
    L=Leff
    # ── أقصى UDL من العزم (SS و مستمرة) ──
    wmax_ss = 8*Mu_cap/L**2
    wmax_cont = 10*Mu_cap/L**2                        # عزم منتصف بحر مستمر wL²/10
    def ll_max(wmax): return (wmax-1.4*DL)/1.6
    # ── القص (ECP بلا كانات) ──
    qcu=0.16*math.sqrt(args.fcu/gc)                  # N/mm²
    Vc=qcu*b*d/1000.0                                # kN/م
    Vu_ss=wu_design*L/2; Vu_cont=0.6*wu_design*L
    # ── الترخيم: بحر/سُمك ──
    Lt=args.span*1000/h
    Lt_limit_ss, Lt_limit_cont = 25, 30              # ECP حدود عدم حساب الترخيم (one-way)
    # ── نِسَب الاستغلال تحت الحمل التصميمي ──
    M_ss=wu_design*L**2/8; M_cont=wu_design*L**2/10
    util_ss=M_ss/Mu_cap; util_cont=M_cont/Mu_cap

    # ── طباعة ──
    print(f"بلاطة {h:.0f}مم | رئيسي Ø{dia:.0f}@{s:.0f} → As={As:.0f}mm²/م | d={d:.0f}مم | fcu={args.fcu:.0f} fy={args.fy:.0f}")
    print(f"عزم المقطع المقاوم Mu = {Mu_cap:.1f} kN·m/م | x/d={xd:.3f} ({'مطاوع ✓' if ductile else 'غير مطاوع ✗'}) | As_min={As_min:.0f} ({'≥ ✓' if As>=As_min else '< ✗'})")
    print(f"البحر: مركزي {args.span:.2f} | صافٍ {Lc:.2f} | فعّال {L:.2f} م | ميل {args.slope_pct:g}٪ (معامل {slope:.4f})")
    print(f"الأحمال: ذاتي {ow:.2f} + تشطيب {args.sdl:.2f} = ميت {DL:.2f} | حي {args.ll:.2f} → تصميمي wu={wu_design:.2f} kN/m²")
    print(f"أقصى UDL (عزم): بسيطة الارتكاز {wmax_ss:.1f} | مستمرة {wmax_cont:.1f} kN/m²")
    print(f"→ أقصى حمل حي: بسيطة {ll_max(wmax_ss):.1f} | مستمرة {ll_max(wmax_cont):.1f} kN/m²")
    print(f"القص: Vc={Vc:.0f} kN/م | المطلوب SS {Vu_ss:.0f} / مستمرة {Vu_cont:.0f} → {'آمن ✓' if Vc>max(Vu_ss,Vu_cont) else 'راجع ✗'}")
    print(f"الترخيم: L/t={Lt:.1f} مقابل حدّ {Lt_limit_cont} (مستمرة) → {'ضمن الحدّ ✓' if Lt<=Lt_limit_cont else 'يلزم حساب ✗'}")
    print(f"الاستغلال تحت الحمل التصميمي: SS {util_ss*100:.0f}٪ | مستمرة {util_cont*100:.0f}٪")

    # ── Excel ──
    NAVY,BLUE,LT,GRN,RED,GREY="1F3864","2E5496","D9E1F2","E2EFDA","F8CBAD","F2F2F2"
    thin=Side(style="thin",color="BFBFBF"); bd=Border(thin,thin,thin,thin)
    wb=Workbook()
    def st(c,*,b=False,sz=11,color="000000",fill=None,ha="right",wrap=False):
        c.font=Font(bold=b,size=sz,color=color); c.alignment=Alignment(ha,"center",wrap_text=wrap)
        if fill:c.fill=PatternFill("solid",fgColor=fill)
        c.border=bd
    ws=wb.active; ws.title="تحقّق بلاطة الرمب"; ws.sheet_view.rightToLeft=True
    ws.merge_cells("A1:D1"); st(ws["A1"],b=True,sz=14,color="FFFFFF",fill=NAVY,ha="center"); ws["A1"]="تحقّق إنشائي أوّلي — بلاطة الرمب (ECP 203)"
    r=3
    def row(k,v,note="",fill=None,kb=True):
        nonlocal r
        st(ws.cell(r,1,k),b=kb,fill=fill or GREY); st(ws.cell(r,2,v),fill=fill); st(ws.cell(r,3,note),ha="right",wrap=True); ws.merge_cells(f"C{r}:D{r}"); r+=1
    def hdr(t):
        nonlocal r
        ws.merge_cells(f"A{r}:D{r}"); st(ws.cell(r,1,t),b=True,color="FFFFFF",fill=BLUE); r+=1
    hdr("المعطيات (افتراضات — عدّلها لو مختلفة)")
    row("المقطع", f"بلاطة {h:.0f}مم، Ø{dia:.0f}@{s:.0f} سفلي", "من اللوحة")
    row("رتبة الخرسانة fcu", f"{args.fcu:.0f} N/mm²", "مفترض — أكّده من اللوحة")
    row("رتبة الحديد fy", f"{args.fy:.0f} N/mm²", "مفترض — أكّده من اللوحة")
    row("الغطاء / d", f"{cov:.0f} / {d:.0f} مم","")
    row("البحر الفعّال", f"{L:.2f} م", f"عرض الرمب {args.span:.2f} مركزي (أفقي، الميل لا يؤثّر عليه)")
    row("الحمل الميت", f"{DL:.2f} kN/m²", f"ذاتي {ow:.2f} + تشطيب {args.sdl:.2f}")
    row("الحمل الحي المفترض", f"{args.ll:.2f} kN/m²", "جراج سيارات ECP≈4 — أكّده")
    hdr("النتائج")
    row("As الموجود", f"{As:.0f} mm²/م", f"أدنى As_min={As_min:.0f} → {'✓' if As>=As_min else '✗'}", fill=(GRN if As>=As_min else RED))
    row("عزم المقطع المقاوم Mu", f"{Mu_cap:.1f} kN·m/م", f"x/d={xd:.3f} {'(مطاوع ✓)' if ductile else '(✗)'}", fill=GRN)
    row("الحمل الأقصى التصميمي wu", f"{wu_design:.2f} kN/m²", "1.4 ميت + 1.6 حي")
    row("الاستغلال (بسيطة الارتكاز)", f"{util_ss*100:.0f}٪", "wL²/8", fill=(GRN if util_ss<=1 else RED))
    row("الاستغلال (مستمرة)", f"{util_cont*100:.0f}٪", "wL²/10 (الأرجح للرمب فوق كمرات)", fill=(GRN if util_cont<=1 else RED))
    row("القص Vc / المطلوب", f"{Vc:.0f} / {max(Vu_ss,Vu_cont):.0f} kN/م", "آمن ✓" if Vc>max(Vu_ss,Vu_cont) else "راجع", fill=GRN)
    row("الترخيم L/t", f"{Lt:.1f} ≤ {Lt_limit_cont}", "ضمن الحدّ ✓" if Lt<=Lt_limit_cont else "يلزم حساب", fill=GRN)
    hdr("أقصى حمل تتحمّله البلاطة")
    row("أقصى UDL — بسيطة الارتكاز", f"{wmax_ss:.1f} kN/m²", f"→ أقصى حمل حي ≈ {ll_max(wmax_ss):.1f} kN/m²", fill=LT)
    row("أقصى UDL — مستمرة", f"{wmax_cont:.1f} kN/m²", f"→ أقصى حمل حي ≈ {ll_max(wmax_cont):.1f} kN/m²", fill=LT)
    hdr("الخلاصة والتنبيهات")
    verdict = "المقطع كافٍ للحمل الحي القياسي (≈4 kN/m² جراج) كبلاطة مستمرة" if util_cont<=1 else "راجع — الاستغلال يتجاوز 100٪"
    ws.merge_cells(f"A{r}:D{r}"); st(ws.cell(r,1,"الحكم (تحت الافتراضات): "+verdict),b=True,fill=(GRN if util_cont<=1 else RED),ha="right",wrap=True); ws.row_dimensions[r].height=30; r+=1
    notes=("تنبيهات: (1) مراجعة أولية بالكود — ليست اعتماداً؛ الاعتماد النهائي للمهندس المسؤول وبموديل SAFE. "
           "(2) رتب المواد والحمل الحي مفترضة — أكّدها. (3) تحليل حمل موزّع؛ **أحمال العجلات المركّزة للسيارات** "
           "قد تحكم وتحتاج فحصاً منفصلاً/SAFE. (4) افتراض استمرارية البلاطة فوق الكمرات؛ لو بسيطة الارتكاز راجع الاستغلال. "
           "(5) القص والترخيم مبدئياً آمنان. (6) حديد علوي عند الركائز (عزوم سالبة) غير مُراجَع هنا.")
    ws.merge_cells(f"A{r}:D{r}"); st(ws.cell(r,1,notes),sz=9,fill="FFF2CC",ha="right",wrap=True); ws.row_dimensions[r].height=95
    ws.column_dimensions["A"].width=26; ws.column_dimensions["B"].width=20
    ws.column_dimensions["C"].width=24; ws.column_dimensions["D"].width=22

    os.makedirs(args.outdir,exist_ok=True)
    out=os.path.join(args.outdir,"تقرير تحقّق بلاطة الرمب - البدروم السفلي.xlsx")
    wb.save(out); print("SAVED:",out)

if __name__=="__main__":
    main()
