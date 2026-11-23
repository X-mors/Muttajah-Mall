# -*- coding: utf-8 -*-
"""
لوحة الحصر الكاملة لجميع العناصر الرأسية — البدروم السفلي (لِفت 1):
أعمدة (مرقّمة بارتفاع+حجم) + حوائط محيطة (W1 شمالي 1.70م + W4 ×3) + أكوار (CORE1/2/3)
+ خزان T1 + بادئ الرمب. مع لوحة ملخّص جانبية بالأحجام. تُخرَج PNG عالية الوضوح.
"""
import sys, os
import ezdxf, columns_takeoff as ct, concrete_columns_takeoff as cc, column_base_levels as cbl
import column_query as cq

OUT=os.path.join(os.path.dirname(__file__), "..", "output")
CEIL=-3.85; SLAB=0.22; SOFFIT=round(CEIL-SLAB,2)

def arabic(s):
    try:
        import arabic_reshaper; from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(s))
    except Exception:
        return s

def build(msp):
    rows=cq.compute(msp)                         # الأعمدة
    plan,_=ct.collect(msp)
    cores=[(m,x,y) for sn,m,x,y in cc.columns_list(plan) if m.startswith("CORE")]
    cx=[c["x"] for c in rows]; cy=[c["y"] for c in rows]
    x0,x1,y0,y1=min(cx),max(cx),min(cy),max(cy)
    # أحجام العناصر = **نفس حساب main_elements_concrete** (تُقرأ من output/vertical_totals.json، بلا أرقام ثابتة)
    import json
    tp=os.path.join(OUT,"vertical_totals.json")
    if not os.path.exists(tp):
        raise SystemExit("شغّل main_elements_concrete.py أولاً لتوليد vertical_totals.json")
    tj=json.load(open(tp,encoding="utf-8"))
    cols_ex=tj["columns"]; walls_ex=tj["walls"]; cores_ex=tj["cores"]; tank_ex=tj["tank"]; start_ex=tj["starter"]; total=tj["total"]
    # تفصيل الجدران للعرض فقط (الإجمالي من الملف)
    T=0.30
    seg=[("W1 شمالي 1.70م",48.835,-8.45,-6.75),("W2 غربي",45.0,-8.45,SOFFIT),("W3 جنوبي",53.335,-8.45,SOFFIT),
         ("W4 شرقي",14.1,-8.45,SOFFIT),("W4 شرقي",6.0,-8.15,SOFFIT),("W4 شرقي",4.85,-8.45,SOFFIT),
         ("W4 شرقي",6.0,-8.15,SOFFIT),("W4 شرقي",14.05,-8.45,SOFFIT)]
    wv={}
    for nm,L,b,t in seg: wv[nm]=wv.get(nm,0)+L*T*(t-b)
    walls=[(k,round(v,1)) for k,v in wv.items()]
    v_cols=round(cols_ex,1); v_walls=round(walls_ex,1); v_cores=round(cores_ex,1); v_tank=round(tank_ex,1); v_start=round(start_ex,2)
    return rows,cores,(x0,x1,y0,y1),dict(cols=v_cols,walls=walls,v_walls=v_walls,
            cores=v_cores,tank=v_tank,start=v_start,total=round(total,2),
            waste=round(tj["waste"],2), ncols=tj.get("n_cols",len(rows)))

def draw(rows,cores,box,summ,path):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle, FancyBboxPatch
    x0,x1,y0,y1=[v/1000.0 for v in box]
    fig=plt.figure(figsize=(26,17)); ax=fig.add_axes([0.03,0.04,0.66,0.92])
    # الحوائط المحيطة
    ax.add_patch(Rectangle((x0,y0),x1-x0,y1-y0,fill=False,ec="#c2185b",lw=6))           # W4 ×3 وردي
    ax.plot([x0,x1],[y1,y1],color="#6a1b9a",lw=10,solid_capstyle="butt")                # W1 شمالي بنفسجي 1.70م
    ax.annotate(arabic("W1 جدار شمالي 1.70م (عليه أعمدة C)"),((x0+x1)/2,y1),color="#6a1b9a",
                fontsize=12,ha="center",va="bottom",weight="bold")
    for sx,sy,lbl in [((x0+x1)/2,y0,"W4 جنوبي"),(x0,(y0+y1)/2,"W4 غربي"),(x1,(y0+y1)/2,"W4 شرقي")]:
        ax.annotate(arabic(lbl),(sx,sy),color="#c2185b",fontsize=11,ha="center",va="center",weight="bold")
    # الأعمدة
    for r in rows:
        xx,yy=r["x"]/1000.0,r["y"]/1000.0
        col="#c62828" if "الرمب" in r["note"] else ("#6a1b9a" if r["mark"]=="C" else "#1565c0")
        ax.plot(xx,yy,"s",ms=7,color=col)
        ax.annotate(f"{r['no']} {r['mark']}\n{r['height']}m|{r['volume']}",(xx,yy),fontsize=6,
                    ha="center",va="bottom",color=col,xytext=(0,3),textcoords="offset points")
    # الأكوار + الخزان
    core_lbl={"CORE3":"كور سلالم","CORE2":"كور أسانسير","CORE1":"كور T2"}
    for m,x,y in cores:
        xx,yy=x/1000.0,y/1000.0
        ax.add_patch(Rectangle((xx-1.6,yy-1.6),3.2,3.2,fill=True,fc="#e2efda",ec="#2e7d32",lw=2.5,alpha=0.8))
        ax.annotate(arabic(f"{m}\n{core_lbl.get(m,'')}"),(xx,yy),fontsize=9,ha="center",va="center",
                    color="#1b5e20",weight="bold")
        if m=="CORE1":   # الخزان ملتصق بـCORE1
            ax.add_patch(Rectangle((xx+1.7,yy-2.6),5.0,5.2,fill=True,fc="#d4e6f7",ec="#0d47a1",lw=2.5,alpha=0.8))
            ax.annotate(arabic("الخزان T1\n(ملتصق بـCORE1)"),(xx+4.2,yy),fontsize=9,ha="center",va="center",color="#0d47a1",weight="bold")
    # بادئ الرمب (شمال غرب، أعلى شريط الرمب)
    ax.annotate(arabic("بادئ الرمب ↓"),((x0+ (x0)) /2 if False else x0+0.5, y1-0.4),fontsize=10,color="#e65100",weight="bold",ha="left")
    ax.set_aspect("equal"); ax.grid(True,ls=":",alpha=0.35)
    ax.set_title(arabic("لوحة حصر خرسانة جميع العناصر الرأسية — البدروم السفلي (لِفت 1: اللبشة → ‑3.85)"),fontsize=16,weight="bold")
    ax.set_xlabel("X (m)"); ax.set_ylabel("Y (m)")
    # لوحة الملخّص الجانبية
    axs=fig.add_axes([0.71,0.04,0.27,0.92]); axs.axis("off")
    lines=[("حصر العناصر الرأسية — م³","hdr"),("",""),
           (f"الأعمدة ({summ['ncols']} عمود)        {summ['cols']}","it"),
           ("الحوائط المحيطة:","sub")]
    for nm,v in summ["walls"]: lines.append((f"   {nm}      {v}","sm"))
    lines+=[(f"   مجموع الحوائط       {summ['v_walls']}","it"),
            (f"الأكوار (CORE3×2+CORE2)  {summ['cores']}","it"),
            (f"الخزان T1 (ارتفاع 3.68م)  {summ['tank']}","it"),
            (f"بادئ الرمب (حائط 250مم)   {summ['start']}","it"),
            ("",""),(f"الإجمالي                {summ['total']}","tot"),
            (f"+ هدر 5٪               {summ['waste']}","tot"),("",""),
            ("دليل الألوان:","sub"),
            ("■ أزرق: عمود يكمل للسقف","leg"),
            ("■ بنفسجي: عمود جدار C / W1","legp"),
            ("■ أحمر: عمود يقف عند الرمب","legr"),
            ("▭ أخضر: أكوار | ▭ سماوي: خزان","legg"),
            ("▭ وردي: W4 | ▬ بنفسجي: W1","legw")]
    yy=0.98
    for t,kind in lines:
        if not t: yy-=0.018; continue
        fs,col,wt=11,"#222","normal"
        if kind=="hdr": fs,col,wt=15,"#1F3864","bold"
        elif kind=="tot": fs,col,wt=14,"#1b5e20","bold"
        elif kind=="sub": fs,col,wt=12,"#1F3864","bold"
        elif kind=="sm": fs,col=9,"#555"
        elif kind=="legp": col="#6a1b9a"
        elif kind=="legr": col="#c62828"
        elif kind=="legg": col="#2e7d32"
        elif kind=="legw": col="#c2185b"
        axs.text(0.02,yy,arabic(t),fontsize=fs,color=col,weight=wt,va="top",transform=axs.transAxes,family="monospace" if kind in("it","sm","tot") else None)
        yy-=0.030 if kind in("hdr","tot","sub") else 0.024
    fig.savefig(path,dpi=120,facecolor="white"); plt.close(fig); return True

def main():
    doc=ezdxf.readfile(cc.DEFAULT_DXF); msp=doc.modelspace()
    rows,cores,box,summ=build(msp)
    os.makedirs(OUT,exist_ok=True)
    p=os.path.join(OUT,"لوحة حصر العناصر الرأسية - البدروم السفلي.png")
    draw(rows,cores,box,summ,p); print("SAVED:",p)
    print(f"الإجمالي {summ['total']} م³ (+هدر {summ['waste']})")

if __name__=="__main__":
    sys.stdout.reconfigure(encoding="utf-8",errors="replace"); main()
