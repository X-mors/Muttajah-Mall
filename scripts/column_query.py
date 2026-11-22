# -*- coding: utf-8 -*-
"""
استعلام ارتفاع/خرسانة أي عمود في لِفت 1 — جاهز للإجابة فوراً عند الإشارة لعمود بسكرين شوت.

يحسب كل عمود من هندسة اللوحة (نفس أدوات الحصر): القاعدة من منطقته (محاذاة التصويت)،
والنهاية من الهوابط/الكمرات/علامات الرمب. يُخرج:
  • output/column_heights.json  — قائمة كل عمود: رقم، مقطع، موضع، قاعدة، نهاية، ارتفاع، حجم، ملاحظة.
  • output/column_heights_map.png — خريطة مرقّمة بنفس تخطيط المسقط (رقم + مقطع + ارتفاع على كل عمود)
    → أطابق عليها السكرين شوت لأحدّد العمود.

الاستعلام:
  python column_query.py                 # يبني الـJSON والخريطة ويطبع الإجمالي
  python column_query.py --num 56         # عمود برقمه
  python column_query.py --mark C8        # كل أعمدة مقطع معيّن
  python column_query.py --near X Y       # أقرب عمود لموضع (إحداثي اللوحة)
"""
import sys, os, json, argparse, math
import ezdxf, columns_takeoff as ct, concrete_columns_takeoff as cc, column_base_levels as cbl

CEIL=-3.85; SLAB=0.22; SOFFIT=round(CEIL-SLAB,2)
OUT=os.path.join(os.path.dirname(__file__), "..", "output")

def compute(msp):
    """يعيد قائمة أعمدة لِفت 1 مرقّمة (نفس ترتيب حصر main_elements: أعلى→أسفل ثم يسار→يمين)."""
    plan,sched=ct.collect(msp); stages,_=cc.parse_schedule_stages(sched)
    bl=cbl.column_bases(msp); base_map={(round(o["x"]),round(o["y"])):(o["base"],o["zone"]) for o in bl}
    ends=cbl.column_ends(msp, ceil_ssl=CEIL); rs=cbl.ramp_column_ends(msp)
    allc=cc.columns_list(plan)
    cols=[c for c in allc if not c[1].startswith("CORE")]
    cols=cbl.drop_tank_c3(cols, allc)          # C3 داخل الخزان محسوب في الخزان — يُشال من الأعمدة
    cols.sort(key=lambda c:(-c[3], c[2]))
    rows=[]
    for i,(sn,m,x,y) in enumerate(cols,1):
        wh=stages.get(m,[None])[0] if m in stages else None
        base,zone=base_map.get((round(x),round(y)),(cbl.MAT_TOP,f"المات {cbl.MAT_TOP}"))
        end=ends.get((round(x),round(y)),SOFFIT)
        if (round(x),round(y)) in rs:   # نشوز أعمدة الرمب: تنزل للمات المنخفض ‑8.45
            base=cbl.RAMP_PROJ_BASE; zone=f"نشوز حتى المات {cbl.RAMP_PROJ_BASE}"
        ov=cbl.lift1_overrides().get((round(x),round(y)))   # تصحيح معتمَد (قراءة البروجكت)
        if ov: base,end=ov; zone="حصر معتمَد (البروجكت)"
        h=round(end-base,3)
        if wh: W,D=wh[0]/1000.0,wh[1]/1000.0; v=round(W*D*h,3)
        else: W=D=0; v=0.0
        key=(round(x),round(y))
        note=("يقف عند قاع الرمب (To Ramp Level)" if key in rs
              else ("جدار شمالي W1 — ينتهي عند قاع الكمرة" if m=="C" else ""))
        rows.append(dict(no=i, mark=m, sec=(f"{wh[0]}x{wh[1]}" if wh else "-"),
                         x=round(x), y=round(y), base=base, end=round(end,3),
                         height=round(h,2), volume=v, zone=zone, note=note))
    return rows

def save_json(rows, path):
    with open(path,"w",encoding="utf-8") as f:
        json.dump(dict(level="Lift 1 (raft -> -3.85)", ceil=CEIL, slab=SLAB, soffit=SOFFIT,
                       total_volume=round(sum(r["volume"] for r in rows),2), columns=rows),
                  f, ensure_ascii=False, indent=1)

def save_map(rows, path):
    """خريطة مرقّمة بنفس تخطيط المسقط (CAD: y لأعلى). كل عمود: رقم + مقطع + ارتفاع."""
    try:
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        print("matplotlib غير متاح، تخطّي الخريطة:", e); return False
    fig,ax=plt.subplots(figsize=(22,18))
    for r in rows:
        xx,yy=r["x"]/1000.0, r["y"]/1000.0
        col="#c62828" if "الرمب" in r["note"] else ("#6a1b9a" if r["mark"]=="C" else "#1565c0")
        ax.plot(xx,yy,"o",ms=6,color=col)
        ax.annotate(f"{r['no']} {r['mark']}\nh={r['height']}",(xx,yy),fontsize=6.5,
                    ha="center",va="bottom",color=col,xytext=(0,3),textcoords="offset points")
    ax.set_aspect("equal"); ax.set_title("Lift 1 columns — No. Mark / height(m)  [red=stops at ramp, purple=wall C]")
    ax.grid(True,ls=":",alpha=0.4)
    fig.tight_layout(); fig.savefig(path,dpi=130); plt.close(fig); return True

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--dxf",default=cc.DEFAULT_DXF); ap.add_argument("--num",type=int)
    ap.add_argument("--mark"); ap.add_argument("--near",nargs=2,type=float)
    a=ap.parse_args()
    doc=ezdxf.readfile(a.dxf); msp=doc.modelspace()
    rows=compute(msp)
    if a.num:
        r=next((x for x in rows if x["no"]==a.num),None)
        print(json.dumps(r,ensure_ascii=False,indent=1) if r else "لا يوجد"); return
    if a.mark:
        for r in [x for x in rows if x["mark"].upper()==a.mark.upper()]:
            print(f"#{r['no']:>3} {r['mark']:4} {r['sec']:10} قاعدة {r['base']} نهاية {r['end']} ارتفاع {r['height']}م حجم {r['volume']}م³  {r['note']}")
        return
    if a.near:
        x,y=a.near; r=min(rows,key=lambda t:math.hypot(t["x"]-x,t["y"]-y))
        print(json.dumps(r,ensure_ascii=False,indent=1)); return
    os.makedirs(OUT,exist_ok=True)
    jp=os.path.join(OUT,"column_heights.json"); save_json(rows,jp); print("SAVED:",jp)
    mp=os.path.join(OUT,"column_heights_map.png")
    if save_map(rows,mp): print("SAVED:",mp)
    print(f"عدد الأعمدة {len(rows)} | إجمالي خرسانة الأعمدة {round(sum(r['volume'] for r in rows),1)} م³")

if __name__=="__main__":
    sys.stdout.reconfigure(encoding="utf-8",errors="replace"); main()
