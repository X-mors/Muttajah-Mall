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
WALL_TOP  = -8.45     # قاعدة أعمدة الجدار الشمالي (مارك C): العمود الخرساني ينزل للمات ‑8.45
                      # (الجدار الظاهر 1.70م = حائط W1 بين الأعمدة، يُحصَر منفصلاً). مطابق للـproject.
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

HEAVY_MARKS = ("C3","C6","C7","C8","C9","C10")   # مقاطع كبيرة → يجب أن تقع داخل قواعد مُثخّنة

def drop_tank_c3(colcols, all_cols):
    """يشيل عمود C3 الواقع داخل الخزان (العمود/الجدار الفاصل T3، محسوب ضمن حوائط الخزان 0.65م²)
    حتى لا يُحصَر مرتين. يُحدَّد كأقرب C3 لمركز CORE1 (الخزان ملاصق له) ضمن 7م."""
    import math
    core1=[(x,y) for sn,m,x,y in all_cols if m=="CORE1"]
    if not core1: return colcols
    cx,cy=core1[0]
    c3=[c for c in colcols if c[1]=="C3"]
    if not c3: return colcols
    nearest=min(c3, key=lambda c: math.hypot(c[2]-cx, c[3]-cy))
    if math.hypot(nearest[2]-cx, nearest[3]-cy) < 7000:
        return [c for c in colcols if c is not nearest]
    return colcols

def _align_footings(cols, foot):
    """إزاحة (dx,dy) تحوّل إحداثي العمود إلى إطار اللبشة بمطابقة مراكز القواعد على الأعمدة.
    لوحة القواعد تغطّي النطاق الأوسط فقط، فمحاذاة مركز‑الـbbox تنحرف؛ بدلاً منها نصوّت على
    فرق (مركز القاعدة − موضع العمود) لكل الأزواج → أكثف عنقود = الإزاحة، ثم نُحسّنها بدقة
    لتعظيم عدد الأعمدة التقيلة الواقعة داخل قواعدها (ثم إجمالي الأعمدة داخل القواعد)."""
    if not foot: return (0.0, 0.0)
    cxy=[(c[2],c[3]) for c in cols]
    votes=collections.Counter()
    for f in foot:
        for x,y in cxy:
            votes[(round((f["cx"]-x)/500)*500, round((f["cy"]-y)/500)*500)]+=1
    bx,by=votes.most_common(1)[0][0]
    heavy=[c for c in cols if c[1] in HEAVY_MARKS]
    def score(dx,dy):
        h=sum(1 for c in heavy if any(_pt_in_poly(c[2]+dx,c[3]+dy,f["poly"]) for f in foot))
        t=sum(1 for c in cols  if any(_pt_in_poly(c[2]+dx,c[3]+dy,f["poly"]) for f in foot))
        return (h,t)
    best=None
    for dx in range(bx-1500, bx+1500, 100):
        for dy in range(by-1500, by+1500, 100):
            s=score(dx,dy)
            if best is None or s>best[0]: best=(s,dx,dy)
    return (float(best[1]), float(best[2]))

def column_bases(msp, verbose=False):
    """يعيد list أعمدة: dict(mark,x,y,base,zone). base = منسوب وش القاعدة."""
    plan,sched=ct.collect(msp)
    cols=[c for c in cc.columns_list(plan) if not c[1].startswith("CORE")]
    foot=footing_polys(msp)
    dx,dy=_align_footings(cols, foot)   # محاذاة بالتصويت: تطابق مراكز القواعد على الأعمدة
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
        heavy=[o for o in out if o["mark"] in HEAVY_MARKS]
        onf=sum(1 for o in heavy if o["base"]>MAT_TOP+0.01)
        print(f"تحقق: أعمدة تقيلة على قواعد مُثخّنة = {onf}/{len(heavy)}")
    return out

RAMP_FFL   = -7.25         # أرضية الرمب (F.F.L) عند البادئ — من اللوحة (A-SYMB-LEVL '-7.25 F.F.L')
RAMP_SSL   = -3.85         # قمة الرمب (S.S.L) حيث يلتقي السقف — من اللوحة
RAMP_THK_S = 0.16          # سماكة بلاطة الرمب → قاع البلاطة = SSL − 0.16
RAMP_PROJ_BASE = -8.45     # نشوز أعمدة الرمب: تنزل للمات المنخفض 40سم (وش ‑8.45)

def _ramp_text_pts(msp, needle):
    import re
    out=[]
    for e in msp.query("TEXT MTEXT"):
        try: t=" ".join((e.plain_text() if e.dxftype()=="MTEXT" else e.dxf.text).split())
        except: continue
        if re.search(needle, t, re.I): out.append((e.dxf.insert.x, e.dxf.insert.y, t))
    return out

def ramp_column_ends(msp):
    """أعمدة الرمب المتوقّفة (علامة 'To Ramp Level' على طبقة 00-EG-Text) تنتهي عند
    قاع بلاطة الرمب على الميل — لا تكمل للسقف. **الاتجاه يُعيَّر من موضع بادئ الرمب**
    (Ramp starter = أوطى نقطة ‑7.25): العمود الأقرب للبادئ = قاع الرمب (‑7.41)،
    وكل ما ابتعدنا عن البادئ يرتفع قاع الرمب. يعيد {(round(x),round(y)): end_level}."""
    import re, math
    plan,_=ct.collect(msp); cols=[c for c in cc.columns_list(plan) if not c[1].startswith("CORE")]
    colx=[c[2] for c in cols]; coly=[c[3] for c in cols]
    rx0,rx1,ry0,ry1=min(colx)-8000,max(colx)+8000,min(coly)-8000,max(coly)+8000
    labels=[(x,y) for x,y,t in _ramp_text_pts(msp,r"To Ramp Level") if rx0<=x<=rx1 and ry0<=y<=ry1]
    if not labels: return {}
    # كل علامة → أقرب عمود واحد
    chosen={}
    for lx,ly in labels:
        best=None; bd=9e9
        for sn,m,x,y in cols:
            d=math.hypot(lx-x,ly-y)
            if d<bd: bd=d; best=(m,x,y)
        if best and bd<4000: chosen[(round(best[1]),round(best[2]))]=best
    ramp_cols=list(chosen.values())
    xmid=(min(colx)+max(colx))/2
    # بادئا الرمب (إطار لوحة الرمب) → تحويل لإطار الأعمدة بإزاحة مطابقة ليبل RAMP04 لعنقود اليسار
    starters=[(x,y) for x,y,t in _ramp_text_pts(msp,r"Ramp\s*starter")]
    r04=[p for p in _ramp_text_pts(msp,r"RAMP\s*0?4")];
    left=[c for c in ramp_cols if c[1] < xmid]; right=[c for c in ramp_cols if c[1] >= xmid]
    # إزاحة إطار الرمب→الأعمدة من مركز عنقود اليسار مقابل ليبل RAMP04
    dxv=dyv=0.0
    if r04 and left:
        lcx=sum(c[1] for c in left)/len(left); lcy=sum(c[2] for c in left)/len(left)
        dxv=lcx-r04[0][0]; dyv=lcy-r04[0][1]
    def starter_in_cols(group):
        if not starters or not group: return None
        gcx=sum(c[1] for c in group)/len(group)
        cand=[(sx+dxv, sy+dyv) for sx,sy in starters]
        return min(cand, key=lambda p: abs(p[0]-gcx))   # البادئ الأقرب لعنقود المجموعة بالـx
    # قاع بلاطة الرمب: من ‑7.41 عند البادئ (أرضية ‑7.25) إلى ‑5.23 عند أبعد عمود واقف (قراءة الـproject،
    # متوسط ميل ~9.4% لأن النص 15% والطرفان 7.5%). الاتجاه يُعيَّر من البادئ (العمود الأقرب = قاع الرمب).
    soffit_bottom=round(RAMP_FFL-RAMP_THK_S,2)   # ‑7.41
    RAMP_FAR=-5.23
    out={}
    for group in (left, right):
        if not group: continue
        st=starter_in_cols(group)
        if st is None:   # fallback: البادئ شمال (أعلى y)
            st=(sum(c[1] for c in group)/len(group), max(c[2] for c in group)+1)
        dists=[(c, math.hypot(c[1]-st[0], c[2]-st[1])) for c in group]
        dmin=min(d for _,d in dists); dmax=max(d for _,d in dists)
        for (m,x,y),d in dists:
            frac=(d-dmin)/(dmax-dmin) if dmax>dmin else 0.0
            end=round(soffit_bottom+frac*(RAMP_FAR-soffit_bottom),3)
            out[(round(x),round(y))]=end
    return out

def column_ends(msp, ceil_ssl=-3.85):
    """منسوب نهاية كل عمود = ceil_ssl ناقص (بلاطة 0.22 / هابط 0.32 / عمق الكمرة فوقه).
    يحاذي لوحة سقف البدروم السفلي (هوابط S-TEXT + كمرات S -Beams) بالأعمدة ويربط كل عمود بما فوقه.
    أعمدة الرمب المتوقّفة (علامة 'To Ramp Level') تُستبدل بقاع بلاطة الرمب على الميل.
    يعيد {(round(x),round(y)): end_level}."""
    import takeoff, beams_rebar as br, re, math
    titles=takeoff.all_titles(msp)
    th=takeoff.find_title(titles,"LOWER BASEMENT CEILING","TOP")
    plan,sched=ct.collect(msp); cols=[c for c in cc.columns_list(plan) if not c[1].startswith("CORE")]
    stages,_=cc.parse_schedule_stages(sched)   # مقطع كل ماركة → للبحث بمستطيل العمود الحقيقي
    def half_mm(m):
        wh=stages.get(m,[None])[0] if m in stages else None
        return (max(wh)/2.0 if wh else 300.0)   # نصف أكبر بُعد للعمود (mm)
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
        hw=half_mm(m)                       # نصف أكبر بُعد للعمود (mm)
        # هابط فوق العمود (نطاق يغطّي مستطيل العمود؛ ليبل العمود قد يبعد عن المركز)
        dd=min(((math.hypot(d[0]-tx2,d[1]-ty2),d[2]) for d in drops), default=(9e9,0))
        drop_dep=(0.32 if dd[1]==320 else (0.35 if dd[1]==350 else 0.40)) if dd[0] < 1600 else 0.0
        # كمرة تلامس مستطيل العمود: المسافة العمودية < نصف بُعد العمود + هامش
        beam_dep=0.0; beam_w=250.0
        for b in beams:
            if b.get('orient')=='H' and b['lo']-500<=tx2<=b['hi']+500: pd=abs(ty2-b['pos'])
            elif b.get('orient')=='V' and b['lo']-500<=ty2<=b['hi']+500: pd=abs(tx2-b['pos'])
            else: continue
            if pd < hw + 150 and b['D']/1000.0 > beam_dep:   # نصف بُعد العمود بدل 400 ثابتة
                beam_dep=b['D']/1000.0; beam_w=b.get('W',250)
        # نهاية العمود = قاع أوطى عنصر فوقه (بلاطة 0.22 / هابط / كمرة)؛ الهابط له الأولوية إن وُجد
        if drop_dep:
            end=ceil_ssl - drop_dep
        elif beam_dep:
            # الكمرة تاخد جزءاً من العمود فقط (عرض الكمرة/أكبر بُعد للعمود)؛ الباقي يكمل لقاع البلاطة
            frac=min(1.0, beam_w/(2.0*hw))
            end=frac*(ceil_ssl-beam_dep) + (1.0-frac)*(ceil_ssl-0.22)
        else:
            end=ceil_ssl - 0.22
        out[(round(x),round(y))]=round(end,3)
    # أعمدة الرمب المتوقّفة: تُستبدَل نهايتها بقاع بلاطة الرمب على الميل (أوطى من السقف)
    out.update(ramp_column_ends(msp))
    return out

if __name__=="__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    doc=ezdxf.readfile(cc.DEFAULT_DXF); msp=doc.modelspace()
    column_bases(msp, verbose=True)
    ends=column_ends(msp); import collections as _c
    print("توزيع منسوب النهاية:", dict(sorted(_c.Counter(ends.values()).items())))
