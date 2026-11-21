# -*- coding: utf-8 -*-
"""
ربط كل عمود بمنطقة اللبشة التي يقف عليها → منسوب قاعدته (وش القاعدة) تلقائياً.
أساس حصر خرسانة العناصر الرئيسية (يُستدعى قبل الحصر).

المنطق:
  • لوحة اللبشة (قواعد R.C. footing) ولوحة الأعمدة لوحتان منفصلتان بإطارين مختلفين (إزاحة) —
    نحاذيهما بإزاحة مراكز الـbbox (نفس المقياس)، ثم اختبار نقطة-داخل-مضلّع:
       عمود داخل قاعدة مُثخّنة → منسوبها (وش = قاع التأسيس -8.85 + السماكة).
       عمود خارجها → المات العام -8.45 (أوطى جزء).
  • أعمدة الجدار الشمالي (مارك C) → ظهر الجدار -6.75 (لا تتبع اللبشة).
التحقق: الأعمدة التقيلة (مقاطع كبيرة) يجب أن تقع داخل القواعد المُثخّنة.
"""
import sys, math, collections
import ezdxf, takeoff, raft_footings as rf, columns_takeoff as ct, concrete_columns_takeoff as cc

MAT_TOP   = -8.45     # وش المات العام (أوطى جزء)
WALL_TOP  = -6.75     # ظهر الجدار الشمالي (مارك C)
WALL_MARK = "C"

def _poly_of(f):
    for k in ("pts","poly","points","verts"):
        if k in f: return [(p[0],p[1]) for p in f[k]]
    return None

def _pt_in_poly(x,y,poly):
    inside=False; n=len(poly); j=n-1
    for i in range(n):
        xi,yi=poly[i]; xj,yj=poly[j]
        if ((yi>y)!=(yj>y)) and (x < (xj-xi)*(y-yi)/((yj-yi) or 1e-9)+xi): inside=not inside
        j=i
    return inside

def footing_polys(msp):
    """قواعد مُثخّنة بمضلّعاتها الحقيقية + منسوب الوش."""
    foot=rf.assign_thickness(rf.collect_footings(msp), rf.collect_thickness_bubbles(msp))
    out=[]
    for f in foot:
        poly=_poly_of(f)
        if poly and f.get("top") is not None:
            xs=[p[0] for p in poly]; ys=[p[1] for p in poly]
            out.append(dict(poly=poly, top=f["top"], th=f.get("th"),
                            cx=sum(xs)/len(xs), cy=sum(ys)/len(ys),
                            bbox=(min(xs),max(xs),min(ys),max(ys))))
    return out

def column_bases(msp, verbose=False):
    """يعيد list أعمدة: dict(mark,x,y,base,zone). base = منسوب وش القاعدة."""
    plan,sched=ct.collect(msp)
    cols=[c for c in cc.columns_list(plan) if not c[1].startswith("CORE")]
    foot=footing_polys(msp)
    # محاذاة: إزاحة مركز bbox القواعد → مركز bbox الأعمدة (نفس المقياس)
    cxs=[c[2] for c in cols]; cys=[c[3] for c in cols]
    fxs=[f["cx"] for f in foot]; fys=[f["cy"] for f in foot]
    fallxs=[v for f in foot for v in (f["bbox"][0],f["bbox"][1])]
    fallys=[v for f in foot for v in (f["bbox"][2],f["bbox"][3])]
    ccx=(min(cxs)+max(cxs))/2; ccy=(min(cys)+max(cys))/2
    fcx=(min(fallxs)+max(fallxs))/2; fcy=(min(fallys)+max(fallys))/2
    dx,dy=fcx-ccx, fcy-ccy          # لتحويل إحداثي العمود إلى إطار اللبشة
    out=[]; zc=collections.Counter()
    for sn,m,x,y in cols:
        if m==WALL_MARK:
            out.append(dict(mark=m,x=x,y=y,base=WALL_TOP,zone="الجدار الشمالي")); zc["جدار"]+=1; continue
        tx,ty=x+dx, y+dy
        base=MAT_TOP; zone=f"المات {MAT_TOP}"
        for f in foot:
            bx0,bx1,by0,by1=f["bbox"]
            if bx0-200<=tx<=bx1+200 and by0-200<=ty<=by1+200 and _pt_in_poly(tx,ty,f["poly"]):
                base=f["top"]; zone=f"قاعدة t={f['th']} وش {f['top']}"; break
        out.append(dict(mark=m,x=x,y=y,base=base,zone=zone)); zc[round(base,2)]+=1
    if verbose:
        print(f"أعمدة={len(out)} | قواعد مُثخّنة={len(foot)} | إزاحة المحاذاة Δ=({dx:.0f},{dy:.0f})")
        print("توزيع المناسيب:", dict(zc))
        # تحقق: الأعمدة التقيلة (مقاطع كبيرة) على قواعد مُثخّنة؟
        heavy=[o for o in out if o["mark"] in ("C3","C6","C7","C8","C9","C10")]
        onf=sum(1 for o in heavy if o["base"]>MAT_TOP+0.01)
        print(f"تحقق: أعمدة تقيلة على قواعد مُثخّنة = {onf}/{len(heavy)}")
    return out

def column_ends(msp, ceil_ssl=-3.85):
    """منسوب نهاية كل عمود = ceil_ssl ناقص (بلاطة 0.22 / هابط 0.32 / عمق الكمرة فوقه).
    يحاذي لوحة سقف البدروم السفلي (هوابط S-TEXT + كمرات S -Beams) بالأعمدة ويربط كل عمود بما فوقه.
    يعيد {(round(x),round(y)): end_level}."""
    import takeoff, beams_rebar as br, re, math
    titles=takeoff.all_titles(msp)
    th=takeoff.find_title(titles,"LOWER BASEMENT CEILING","TOP")
    plan,_=ct.collect(msp); cols=[c for c in cc.columns_list(plan) if not c[1].startswith("CORE")]
    if not th: return {(round(c[2]),round(c[3])): ceil_ssl-0.22 for c in cols}
    cbox=takeoff.plan_bbox(titles,th[0][0],th[0][1]); cx0,cx1,cy0,cy1=cbox
    drops=[]
    for e in msp.query("TEXT MTEXT"):
        if e.dxf.layer!="S-TEXT": continue
        t=" ".join((e.plain_text() if e.dxftype()=="MTEXT" else e.dxf.text).split())
        if re.fullmatch(r"3[25]0|400", t) and cx0<=e.dxf.insert.x<=cx1 and cy0<=e.dxf.insert.y<=cy1:
            drops.append((e.dxf.insert.x,e.dxf.insert.y,int(t)))
    beams,_,_=br.extract_beams(msp,cbox)
    colx=[c[2] for c in cols]; coly=[c[3] for c in cols]
    dxs=[d[0] for d in drops]+[b['cx'] for b in beams]; dys=[d[1] for d in drops]+[b['cy'] for b in beams]
    if not dxs: return {(round(c[2]),round(c[3])): ceil_ssl-0.22 for c in cols}
    ccx=(min(colx)+max(colx))/2; ccy=(min(coly)+max(coly))/2
    dcx=(min(dxs)+max(dxs))/2; dcy=(min(dys)+max(dys))/2
    sx=(max(dxs)-min(dxs))/(max(colx)-min(colx)); sy=(max(dys)-min(dys))/(max(coly)-min(coly))
    def toC(x,y): return (dcx+(x-ccx)*sx, dcy+(y-ccy)*sy)
    out={}
    for sn,m,x,y in cols:
        tx2,ty2=toC(x,y)
        dd=min(((math.hypot(d[0]-tx2,d[1]-ty2),d[2]) for d in drops), default=(9e9,0))
        best_bd=9e9; beamD=None
        for b in beams:
            if b.get('orient')=='H' and b['lo']-500<=tx2<=b['hi']+500: pd=abs(ty2-b['pos'])
            elif b.get('orient')=='V' and b['lo']-500<=ty2<=b['hi']+500: pd=abs(tx2-b['pos'])
            else: pd=9e9
            if pd<best_bd: best_bd=pd; beamD=b['D']
        if dd[0]<1600: end=ceil_ssl-(0.32 if dd[1]==320 else (0.35 if dd[1]==350 else 0.40))
        elif best_bd<400 and beamD: end=ceil_ssl-beamD/1000.0
        else: end=ceil_ssl-0.22
        out[(round(x),round(y))]=round(end,3)
    return out

if __name__=="__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    doc=ezdxf.readfile(cc.DEFAULT_DXF); msp=doc.modelspace()
    column_bases(msp, verbose=True)
    ends=column_ends(msp); import collections as _c
    print("توزيع منسوب النهاية:", dict(sorted(_c.Counter(ends.values()).items())))
