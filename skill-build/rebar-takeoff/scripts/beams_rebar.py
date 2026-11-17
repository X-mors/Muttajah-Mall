# -*- coding: utf-8 -*-
"""
حصر حديد كمرات السقف (ceiling BEAM rebar takeoff) — جزء من حصر حديد السقف.

المصدر من اللوحة (مُثبَت على مشروع Muttajah Mall):
  • مقطع كل كمرة من ليبلها على المسقط: MARK(W X D)  (طبقتا BEAMS / ST-203-SLAB-TXT).
  • طول كل كمرة من جيومتريها: الكمرة مرسومة كزوج خطوط متوازية على طبقة `S -Beams`،
    المسافة بين الخطين = العرض W، وطول الزوج = طول الكمرة L. (نبني strips ونربطها بالليبلات.)
  • التسليح لكل ماركة من جدول "Beams Reinforcement Table":
    references beam-reinforcement.md  →  BEAM_RFT أدناه (Top L/C/R، Bottom، كانات 5Ø8/م).

ملاحظة أمانة: أطوال الأسياخ تعتمد افتراضات تفصيل قياسية (أدناه، قابلة للتعديل) — الأطوال من اللوحة،
وترتيب/عدد الأسياخ من الجدول، أما طول الإرساء/أسياخ الشدّ فمن الافتراضات. راجعها مع المهندس.
"""
import re, math, collections

# ═══ جدول تسليح الكمرات (من اللوحة 2026-11-08) ═══
# mark: (top_left, top_center, top_right, bottom, [stirrup_dia, stirrups_per_m])
BEAM_RFT = {
    "B1":  ((3,16),(2,12),(3,16),(2,16),(8,5)),
    "B2":  ((4,16),(3,12),(4,16),(3,16),(8,5)),
    "B3":  ((5,16),(2,16),(5,16),(4,16),(8,5)),
    "B4":  ((7,16),(3,16),(7,16),(5,16),(8,5)),
    "B5":  ((7,16),(3,16),(7,16),(6,16),(8,5)),
    "CA1": ((2,16),(2,16),(2,16),(2,12),(8,5)),
    "CA2": ((4,16),(4,16),(4,16),(2,16),(8,5)),
    "CA3": ((5,16),(5,16),(5,16),(3,16),(8,5)),
    "CA4": ((6,16),(6,16),(6,16),(4,16),(8,5)),
}

# ═══ افتراضات التفصيل (قابلة للتعديل — راجعها مع المهندس) ═══
ANCHOR_MM     = 500    # إرساء السيخ الطولي داخل كل ركيزة (يُضاف طرفَي الكمرة)
SUPPORT_FRAC  = 0.30   # طول سيخ الشدّ العلوي الإضافي عند الركيزة = نسبة × طول الكمرة
COVER_MM      = 25     # الغطاء الخرساني للكانة
HOOK_MULT     = 10     # طول خطّاف الكانة = HOOK_MULT × قطر الكانة (لكل خطّاف، وعددهما 2)
LAP_MULT      = 60     # وصلة تراكب (×القطر) للأطوال > 12م

BEAM_RE = re.compile(
    r"(INV\.?\s*)?([A-Z]{1,3}\d{0,2})\s*\(\s*(\d{2,4})\s*[xX×]\s*(\d{2,4})(?:\s*/\s*(\d{2,4}))?\s*\)\s*(INVERTED)?",
    re.I)

def _text(e):
    try:
        if e.dxftype()=="MTEXT": return e.plain_text()
        if e.dxftype() in ("TEXT","ATTRIB"): return e.dxf.text
    except Exception: pass
    return ""

# ═══ الرامبات (مشترك بين حصر الحديد والخرسانة) ═══
RAMP_LBL = re.compile(r"^RAMP\s*0?\d$", re.I)
RAMP_MESH_RE = re.compile(r"T(\d+)\s*-\s*(\d+)\s*-\s*(T|B)\b", re.I)   # كولّ شبكة الرامب: T12-200-B

def measure_ramps(msp, rbox):
    """يجد ليبلات 'RAMP 0N' داخل لوحة الرامبات ويقيس bbox شريط كل رامب →
    [(اسم, عرض_م, طول_م, مساحة_م²)]. (الرامب شريط ضيّق، فالقياس = امتداد جيومتريه الفعلي.)"""
    xmin,xmax,ymin,ymax=rbox; labs=[]
    for e in msp.query("TEXT MTEXT"):
        t=" ".join(_text(e).split())
        if RAMP_LBL.match(t) and xmin<=e.dxf.insert.x<=xmax and ymin<=e.dxf.insert.y<=ymax:
            labs.append((t.upper().replace(" ",""), e.dxf.insert.x, e.dxf.insert.y))
    out=[]
    for nm,lx,ly in labs:
        xs=[];ys=[]
        for e in msp.query("LINE LWPOLYLINE"):
            if e.dxf.layer not in ("S -Beams","SLAB","ST-RFT-TOP","ST-RFT-BOT","S-OPENING"): continue
            pp=[(e.dxf.start.x,e.dxf.start.y),(e.dxf.end.x,e.dxf.end.y)] if e.dxftype()=="LINE" else list(e.get_points("xy"))
            for x,y in pp:
                if abs(x-lx)<6000 and abs(y-ly)<22000: xs.append(x);ys.append(y)
        if xs:
            w=max(xs)-min(xs); h=max(ys)-min(ys)
            out.append((nm, w/1000.0, h/1000.0, w*h/1e6))
    return out

def ramp_mesh_specs(msp, rbox):
    """كولّات شبكة بلاطة الرامب 'T##-###-T|B' (مسافة) → [(dia, spacing_mm, face)] مميّزة."""
    xmin,xmax,ymin,ymax=rbox; seen=set(); out=[]
    for e in msp.query("TEXT MTEXT"):
        x,y=e.dxf.insert.x,e.dxf.insert.y
        if not (xmin<=x<=xmax and ymin<=y<=ymax): continue
        m=RAMP_MESH_RE.search(" ".join(_text(e).split()))
        if m:
            key=(int(m.group(1)),int(m.group(2)),m.group(3).upper())
            if key not in seen: seen.add(key); out.append(key)
    return out

def ramp_slab_mesh_len(msp, rbox, slope=1.0):
    """طول شبكة بلاطة الرامب لكل قطر (م) = مساحة الرامب × ميل × (1000/المسافة) لكل كولّ اتجاه.
    يعيد (dict dia->متر، مساحة م², قائمة الشرائط، قائمة المواصفات)."""
    strips=measure_ramps(msp, rbox); area=sum(s[3] for s in strips)
    specs=ramp_mesh_specs(msp, rbox)
    out=collections.defaultdict(float)
    for dia,sp,face in specs:
        out[dia]+= area*slope*(1000.0/sp)
    return dict(out), area, strips, specs

def extract_labels(msp, box):
    xmin,xmax,ymin,ymax = box
    out=[]
    for e in msp.query("TEXT MTEXT"):
        if e.dxf.layer not in ("BEAMS","ST-203-SLAB-TXT"): continue
        t=" ".join(_text(e).split()); m=BEAM_RE.search(t)
        if not m or m.group(2).upper()=="S": continue     # S = سملات أساس، مستبعدة
        try: x,y=float(e.dxf.insert.x),float(e.dxf.insert.y)
        except Exception: continue
        if xmin<=x<=xmax and ymin<=y<=ymax:
            out.append(dict(mk=m.group(2).upper(), W=int(m.group(3)), D=int(m.group(4)),
                            D2=int(m.group(5)) if m.group(5) else None,
                            inv=bool(m.group(1)) or bool(m.group(6)), x=x, y=y))
    return out

def _segments(msp, box):
    xmin,xmax,ymin,ymax=box; Hs=[]; Vs=[]
    for e in msp.query("LINE"):
        if e.dxf.layer!="S -Beams": continue
        a,b=e.dxf.start,e.dxf.end
        if not (xmin<=a.x<=xmax and ymin<=a.y<=ymax) and not (xmin<=b.x<=xmax and ymin<=b.y<=ymax): continue
        dx,dy=b.x-a.x,b.y-a.y; L=math.hypot(dx,dy)
        if L<250: continue
        if abs(dy)<=2 and abs(dx)>2: Hs.append([min(a.x,b.x),max(a.x,b.x),(a.y+b.y)/2])
        elif abs(dx)<=2 and abs(dy)>2: Vs.append([min(a.y,b.y),max(a.y,b.y),(a.x+b.x)/2])
    return Hs,Vs

def _strips(segs, orient):
    """زاوِج خطين متوازيين فجوتهما [100,320] (=العرض) وتداخل مدى >500 → شريحة كمرة."""
    strips=[]; used=[False]*len(segs)
    order=sorted(range(len(segs)), key=lambda i:segs[i][2])
    for ii in range(len(order)):
        i=order[ii]
        if used[i]: continue
        for jj in range(ii+1,len(order)):
            j=order[jj]
            if used[j]: continue
            gap=segs[j][2]-segs[i][2]
            if gap>320: break
            if gap<100: continue
            lo=max(segs[i][0],segs[j][0]); hi=min(segs[i][1],segs[j][1])
            if hi-lo>500:
                pos=(segs[i][2]+segs[j][2])/2
                strips.append(dict(orient=orient, pos=pos, width=round(gap),
                                   lo=lo, hi=hi, length=hi-lo))
                used[i]=used[j]=True; break
    return strips

def extract_beams(msp, box):
    """كل شريحة geometry (زوج خطوط = جزء كمرة حقيقي) → أقرب ليبل عرضه = عرض الشريحة،
    فيؤخذ الطول من اللوحة. ثم الليبلات التي لم تطالبها أي شريحة (كمرات polyline غير ملتقَطة)
    تُضاف بطول None للمراجعة اليدوية. هكذا نغطّي كل الأطوال المرسومة ونعلّم الناقص."""
    labels=extract_labels(msp, box)
    Hs,Vs=_segments(msp, box)
    strips=_strips(Hs,"H")+_strips(Vs,"V")
    beams=[]; claimed_lab=set()
    for s in strips:
        best=None; bd=1e9
        for li,lab in enumerate(labels):
            along = lab["x"] if s["orient"]=="H" else lab["y"]
            perp  = abs(lab["y"]-s["pos"]) if s["orient"]=="H" else abs(lab["x"]-s["pos"])
            if s["lo"]-2500<=along<=s["hi"]+2500 and perp<3500 and abs(s["width"]-lab["W"])<=60:
                if perp<bd: bd=perp; best=li
        if best is None:
            # شريحة بلا ليبل مطابق العرض — جرّب أقرب ليبل أياً كان عرضه
            for li,lab in enumerate(labels):
                along = lab["x"] if s["orient"]=="H" else lab["y"]
                perp  = abs(lab["y"]-s["pos"]) if s["orient"]=="H" else abs(lab["x"]-s["pos"])
                if s["lo"]-2500<=along<=s["hi"]+2500 and perp<bd: bd=perp; best=li
        if best is None: continue
        lab=labels[best]; claimed_lab.add(best)
        cx=(s["lo"]+s["hi"])/2 if s["orient"]=="H" else s["pos"]
        cy=s["pos"] if s["orient"]=="H" else (s["lo"]+s["hi"])/2
        beams.append(dict(mk=lab["mk"],W=lab["W"],D=lab["D"],D2=lab.get("D2"),inv=lab["inv"],
                          length=s["length"],width=s["width"],orient=s["orient"],
                          cx=cx,cy=cy,lo=s["lo"],hi=s["hi"],pos=s["pos"],matched=True))
    # ليبلات لم تطالبها أي شريحة: غالباً ليبل مكرّر لنفس الكمرة (per-bay) أو كمرة polyline.
    # لا تُضاف ككمرات مستقلة (تفادي الـphantom)؛ تُرجَع للتقرير فقط.
    unclaimed=[labels[li] for li in range(len(labels)) if li not in claimed_lab]
    return beams, labels, unclaimed

# ═══ حساب الحديد ═══
def _pcs(piv, dia, length_mm, n):
    if n<=0 or length_mm<=0: return
    piv[dia][round(length_mm)] += n

def beam_rebar(beams):
    """يعيد: piv[dia][length_mm]=count ، وتفاصيل لكل كمرة، وملخص لكل ماركة."""
    piv=collections.defaultdict(lambda: collections.defaultdict(int))
    details=[]; permark=collections.defaultdict(lambda: dict(n=0, L=0.0))
    for bm in beams:
        rft=BEAM_RFT.get(bm["mk"])
        permark[bm["mk"]]["n"]+=1; permark[bm["mk"]]["L"]+=(bm["length"] or 0)
        if not rft or not bm.get("length"):
            details.append((bm, None)); continue
        (tl,tld),(tc,tcd),(tr,trd),(bo,bod),(sd,spm)=rft
        L=bm["length"]; full=L+2*ANCHOR_MM
        # سفلي (مستمر) + علوي مستمر (الوسط)
        _pcs(piv, bod, full, bo)
        _pcs(piv, tcd, full, tc)
        # علوي إضافي عند الركيزتين = (الركيزة − المستمر) على كل جانب
        ex_l=max(0, tl-tc); ex_r=max(0, tr-tc)
        _pcs(piv, tld, SUPPORT_FRAC*L+ANCHOR_MM, ex_l)
        _pcs(piv, trd, SUPPORT_FRAC*L+ANCHOR_MM, ex_r)
        # كانات: عدد = per_m × الطول(م)، طول الواحدة = محيط صافٍ + خطّافان
        nst=math.ceil(spm*(L/1000.0))
        stlen=2*((bm["W"]-2*COVER_MM)+(bm["D"]-2*COVER_MM))+2*HOOK_MULT*sd
        _pcs(piv, sd, stlen, nst)
        details.append((bm, dict(full=full, bottom=(bo,bod), topc=(tc,tcd),
                                 topl=(ex_l,tld), topr=(ex_r,trd),
                                 stirrups=(nst,sd,round(stlen)))))
    return piv, details, permark

def weight_kg(piv):
    tot=0.0; byd={}
    for d in piv:
        m=sum(L*n for L,n in piv[d].items())/1000.0
        byd[d]=m*d*d/162.0; tot+=byd[d]
    return byd, tot
