# -*- coding: utf-8 -*-
"""
حساب البندين على النموذج الهندسي (substructure_model.Substructure):
  backfill(M)      → الردم الداخلي م³ (المناطق + الخصومات عنصر عنصر)
  insulation(M)    → العزل بالدهان م² حتى منسوب الردم بالظبط (كل نوع سطح + تفصيل كل عنصر)
  pending_items(M) → عناصر مرسومة لكن ناقص قطاعها/منسوبها (بتتعرض، مش بتتفترض)

الأسطح الرأسية بتتحسب بتقسيم كل حافة كل 20مم وفحص الجنب اللي برّه بـ5مم: الوش موجود لو الجنب ده منطقة ردم
(جوه حدود الردم ومش جوه عنصر رأسي/الخزان)، وارتفاعه من وش اللبشة/القاعدة/السمل في الجنب ده لحد منسوب الردم.
"""
import math, collections
import numpy as np
import shapely
from substructure_model import MAT_TOP, PROBE, DOOR_W, DOOR_SILL_ABOVE


def _loc(g):
    """موقع مختصر: مركز الشكل بالمتر من تقاطع المحورين 01/A."""
    c = g.centroid
    return f"({c.x/1000:.2f}, {c.y/1000:.2f})"


def _segments(X, Y, NX, NY, W, ok, h, gap=60.0):
    """يجمع نقاط الحافة المتتالية الصالحة في قطع مستقيمة للرسم: [(x0,y0,x1,y1,nx,ny,متوسط الارتفاع)]."""
    segs = []; cur = None
    for i in range(len(X)):
        if not ok[i]:
            if cur: segs.append(cur); cur = None
            continue
        if cur and abs(NX[i] - cur[4]) < 1e-6 and abs(NY[i] - cur[5]) < 1e-6 \
                and math.hypot(X[i] - cur[2], Y[i] - cur[3]) <= W[i] + gap:
            cur = [cur[0], cur[1], X[i], Y[i], NX[i], NY[i], cur[6] + W[i] * h[i], cur[7] + W[i]]
        else:
            if cur: segs.append(cur)
            cur = [X[i], Y[i], X[i], Y[i], NX[i], NY[i], W[i] * h[i], W[i]]
    if cur: segs.append(cur)
    return [(s[0], s[1], s[2], s[3], s[4], s[5], s[6] / s[7]) for s in segs]


def _rng(h, ok):
    return (float(h[ok].min()), float(h[ok].max())) if ok.any() else (0.0, 0.0)


# ═══════════════════════════════════════════════════════════════════ البند 1: الردم
def backfill(M):
    F = M.FILL
    zones = M.zone_regions()
    zone_rows = []
    for name, kind, reg, top in zones:
        h = max(0.0, F - top); A = reg.area / 1e6
        Ao = reg.intersection(M.O_fill).area / 1e6
        zone_rows.append(dict(name=name, kind=kind, top=top, A=A, Aobs=Ao, Anet=A - Ao, h=h,
                              Vg=A * h, Vnet=(A - Ao) * h, loc=_loc(reg), region=reg))
    # الحجم القائم: المات (شامل شرائح السملات) + كل قاعدة بوشّها
    gross_rows = [dict(name="المات العام ‑ شامل مكان السملات", top=MAT_TOP, A=M.mat_with_beams.area / 1e6,
                       h=F - MAT_TOP, loc="كل المساحة خارج القواعد", region=M.mat_with_beams)]
    for f in M.fz:
        gross_rows.append(dict(name=f['name'], top=f['top'], A=f['region'].area / 1e6, h=max(0.0, F - f['top']),
                               loc=_loc(f['region']), region=f['region']))
    for g in gross_rows:
        g['V'] = g['A'] * g['h']
    gross = sum(g['V'] for g in gross_rows)
    # السملات: الجزء الظاهر فوق المات. (اللي تحت عنصر رأسي بيتخصم مع العنصر بارتفاعه فوق ظهر السمل → مفيش تكرار)
    beam_rows = []
    for b in M.bz:
        A = b['region'].area / 1e6; hb = b['top'] - MAT_TOP
        beam_rows.append(dict(name=b['name'], top=b['top'], L=b['L'], w=b['w'] / 1000.0, A=A, h=hb, V=A * hb,
                              loc=_loc(b['region'])))
    # العناصر الرأسية: Σ مساحة العنصر في كل منطقة وش × ارتفاع الردم فوقها
    obs_rows = []
    for o in M.obs + M.lifts:
        V = 0.0; Aw = 0.0; zs = []
        for name, kind, reg, top in zones:
            a = o['poly'].intersection(reg).area / 1e6
            if a > 1e-9:
                V += a * max(0.0, F - top); Aw += a; zs.append((top, a))
        base = sum(t * a for t, a in zs) / Aw if Aw else MAT_TOP
        obs_rows.append(dict(kind=o['kind'], name=o['name'], A=o['poly'].area / 1e6, base=base, h=F - base, V=V,
                             ref=o['ref'], poly=o['poly'], loc=_loc(o['poly'])))
    tank_split = []
    for nm, g in (("حوائط الخزان 350مم + العمود الفاصل C3", M.tank_walls), ("داخل الخزان (مياه — مفيش ردم)", M.tank_in)):
        V = sum(g.intersection(reg).area / 1e6 * max(0.0, F - top) for _, _, reg, top in zones)
        tank_split.append(dict(name=nm, A=g.area / 1e6, V=V))
    wedge = M.ramp03_wedge()
    wedge_V = sum(v[0] for v in wedge.values())
    by_kind = collections.OrderedDict()
    by_kind['tie_beams'] = sum(r['V'] for r in beam_rows)
    for k in ('column', 'core', 'tank', 'starter', 'lift'):
        by_kind[k] = sum(r['V'] for r in obs_rows if r['kind'] == k)
    by_kind['ramp_slab'] = wedge_V
    deduct = sum(by_kind.values())
    net = gross - deduct
    check = sum(z['Vnet'] for z in zone_rows) - wedge_V          # نفس الصافي بطريقة المناطق (تحقق داخلي)
    return dict(F=F, zones=zone_rows, gross_rows=gross_rows, gross=gross, beams=beam_rows, obs=obs_rows,
                tank_split=tank_split, wedge=wedge, by_kind=by_kind, deduct=deduct, net=net, check=check)


# ═══════════════════════════════════════════════════════════════════ البند 2: العزل
def insulation(M):
    F = M.FILL
    # 1) أفقي: ظهر كل منطقة − بصمات العناصر الرأسية والخزان (مفيش عزل تحت عنصر رأسي ولا جوه الخزان)
    horiz = []
    for name, kind, reg, top in M.zone_regions():
        net = reg.difference(M.O)
        horiz.append(dict(name=name, kind=kind, top=top, A=reg.area / 1e6, A_obs=reg.intersection(M.O).area / 1e6,
                          Anet=net.area / 1e6, loc=_loc(reg), region=net))
    # 2) جوانب القواعد والسملات: من وش المنطقة الأوطى جنبها لحد ظهرها (بيتحسب من العنصر الأعلى بس → مفيش تكرار)
    sides = []
    for kind, items in (('footing', M.footings), ('beam', M.beams)):
        for it in items:
            X, Y, NX, NY, W = M.samples(it['poly'])
            ix, iy = X - NX * PROBE, Y - NY * PROBE; ox, oy = X + NX * PROBE, Y + NY * PROBE
            zin = M.z(ix, iy); zout = M.z(ox, oy)
            ok = (np.abs(zin - it['top']) < 1e-6) & (zout < it['top'] - 1e-6) & M.free(ox, oy) \
                 & shapely.contains_xy(M.D, ix, iy)
            h = np.minimum(it['top'], F) - zout
            sides.append(dict(kind=kind, name=it['name'], top=it['top'], A=float(np.sum(W[ok] * h[ok])) / 1e3,
                              L=float(np.sum(W[ok])) / 1000.0, loc=_loc(it['poly']), rng=_rng(h, ok),
                              segs=_segments(X, Y, NX, NY, W, ok, h)))
    # 3) العناصر الرأسية: رقاب الأعمدة / الأكوار (كل الجوانب) / الخزان (الخارجي) / بادئ الرمب
    vert = []
    for o in M.obs:
        X, Y, NX, NY, W = M.samples(o['poly'])
        px, py = X + NX * PROBE, Y + NY * PROBE
        top = np.full(X.shape, F)
        if o['kind'] == 'starter':     # الوش ناحية الرمب: لحد قاع بلاطة الرمب لو تحت منسوب الردم
            R = o['ref']['R']
            top = np.where(py < R['y_start'] - R['wall_t'], min(F, o['ref']['top']), F)
        h = np.maximum(0.0, top - M.z(px, py))
        ok = M.free(px, py) & (h > 1e-6)
        vert.append(dict(kind=o['kind'], name=o['name'], A=float(np.sum(W[ok] * h[ok])) / 1e3,
                         P=float(np.sum(W[ok])) / 1000.0, rng=_rng(h, ok), ref=o['ref'], loc=_loc(o['poly']),
                         segs=_segments(X, Y, NX, NY, W, ok, h)))
    # 4) الوش الداخلي للجدار المحيط (من وش اللبشة جنبه لحد منسوب الردم)
    X, Y, NX, NY, W = M.samples(M.D)
    px, py = X - NX * PROBE, Y - NY * PROBE
    ok = ~shapely.contains_xy(M.O, px, py)
    h = np.maximum(0.0, F - M.z(px, py))
    N_, CN = 'W1 شمالي — جدار الجار 1.70م', 'W1 — الوش الداخلي لأعمدة C التسعة'
    side = np.where(NX < -0.5, 'W2 غربي', np.where(NX > 0.5, 'W4 شرقي', np.where(NY < -0.5, 'W3 جنوبي', N_)))
    incol = np.zeros(X.shape, bool)
    for c in M.north_cols:
        x0, _, x1, _ = c.bounds
        incol |= (side == N_) & (X >= x0) & (X <= x1)
    side = np.where(incol, CN, side)
    perim = []
    for s_ in (N_, CN, 'W2 غربي', 'W3 جنوبي', 'W4 شرقي'):
        m = ok & (side == s_)
        perim.append(dict(name=s_, L=float(np.sum(W[m])) / 1000.0, A=float(np.sum(W[m] * h[m])) / 1e3,
                          rng=_rng(h, m), segs=_segments(X, Y, -NX, -NY, W, m, h)))
    # 5) قاع بلاطة رمب 03 اللي تحت منسوب الردم (أول ~1.9م بعد البادئ)
    wedge = M.ramp03_wedge()
    # 6) أبواب أكوار السلالم: الباب بيبدأ 10سم فوق وش قاعدة الـ1500 → الجزء تحت منسوب الردم
    sill = round(F + DOOR_SILL_ABOVE, 3)
    doors = []
    for c in M.cores:
        for d in c['doors']:
            hd = max(0.0, F - sill)
            doors.append(dict(core=c['label'], w=DOOR_W, sill=sill, h=hd, A=2 * DOOR_W * hd, loc=_loc(d)))
    t = collections.OrderedDict()
    t['h_mat'] = sum(r['Anet'] for r in horiz if r['kind'] == 'mat')
    t['h_foot'] = sum(r['Anet'] for r in horiz if r['kind'] == 'footing')
    t['h_beam'] = sum(r['Anet'] for r in horiz if r['kind'] == 'beam')
    t['s_foot'] = sum(r['A'] for r in sides if r['kind'] == 'footing')
    t['s_beam'] = sum(r['A'] for r in sides if r['kind'] == 'beam')
    t['col'] = sum(r['A'] for r in vert if r['kind'] == 'column')
    t['core'] = sum(r['A'] for r in vert if r['kind'] == 'core')
    t['perim'] = sum(r['A'] for r in perim)
    t['tank'] = sum(r['A'] for r in vert if r['kind'] == 'tank')
    t['starter'] = sum(r['A'] for r in vert if r['kind'] == 'starter')
    t['ramp_soffit'] = sum(v[1] for v in wedge.values())
    t['doors'] = -sum(d['A'] for d in doors)
    return dict(F=F, horiz=horiz, sides=sides, vert=vert, perim=perim, wedge=wedge, doors=doors, sill=sill,
                totals=t, total=sum(t.values()))


# ═══════════════════════════════════════════════════════════════════ البنود الناقصة
def pending_items(M):
    F = M.FILL; rows = []
    for i, p in enumerate(M.pits, 1):
        c = p['outer'].centroid
        z = float(M.z(np.array([c.x]), np.array([c.y]))[0])
        h = max(0.0, F - z); ai = p['inner'].area / 1e6 if p['inner'] else 0.0; ao = p['outer'].area / 1e6
        rows.append(dict(item=f"حفرة صرف (sump pit) {i}", where=f"{_loc(p['outer'])} على وش {z:+.2f}",
                         known=f"خارجي {math.sqrt(ao):.2f}×{math.sqrt(ao):.2f}م، داخلي {math.sqrt(ai):.2f}×{math.sqrt(ai):.2f}م (حائط 150مم) — بلوك 'sump pit' في لوحة RAFT RFT",
                         missing="العمق ومنسوب القاع، وهل الحفرة طالعة لحد الأرضية (مفيش قطاع لها في اللوحة)",
                         fill=f"لو مفتوحة لحد الأرضية: ‑{ao*h:.2f} م³ ({ao:.2f}م² × {h:.2f}م)",
                         ins=f"+{4*math.sqrt(ai):.2f} م² لكل 1م عمق (جوانب داخلية)" +
                             (f"، و+{4*math.sqrt(ao)*h:.2f} م² وش خارجي في مدى الردم لو طالعة" if h > 0 else ""),
                         dV=ao * h))
    for l in M.lifts:
        inner = l['poly']; a = inner.area / 1e6; cc_ = inner.centroid; c = l['ref']
        z = float(M.z(np.array([cc_.x]), np.array([cc_.y]))[0]); h = max(0.0, F - z)
        P = inner.length / 1000.0
        rows.append(dict(item=f"عمق حفرة الأسانسير — {c['label']}", where=f"{_loc(inner)} داخل الكور على وش {z:+.2f}",
                         known=f"داخل الكور {a:.2f} م² (من حدوده المرسومة) — مخصوم من الردم ({a*h:.2f} م³) وقاعه وجوانبه لحد {F:+.2f} معزولين",
                         missing="عمق الحفرة ومنسوب قاعها مش مرسومين على لوحتي اللبشة",
                         fill="مخصوم بالفعل (مش بيتردم)",
                         ins=f"لو الحفرة أعمق من وش اللبشة: + {P:.2f} م² لكل 1م عمق زيادة (جوانب)", dV=0.0))
    rows.append(dict(item="هوابط سفلية في اللبشة", where="—",
                     known="قاع اللبشة ثابت ‑8.85 في القطاعات، والقواعد مُثخّنة لفوق (محسوبة كمناطق)",
                     missing="مفيش هوابط لتحت مرسومة في لوحتي RAFT CONCRETE DIMENSIONS / RAFT RFT",
                     fill="لا شيء", ins="لا شيء", dV=0.0))
    return rows
