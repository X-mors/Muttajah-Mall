# -*- coding: utf-8 -*-
"""
حساب البندين على النموذج الهندسي (substructure_model.Substructure):
  elements(M)      → ترقيم موحّد لكل العناصر (نفس الرقم في صور المراجعة عربي/إنجليزي وفي الإكسل)
  backfill(M)      → الردم الداخلي م³ (المناطق + الخصومات عنصر عنصر)
  insulation(M)    → العزل بالدهان م² حتى منسوب الردم بالظبط (كل نوع سطح + تفصيل كل عنصر)
  notes(M)         → الفرضيات والملاحظات

الأسطح الرأسية بتتحسب بتقسيم كل حافة كل 20مم وفحص الجنب اللي برّه بـ5مم: الوش موجود لو الجنب ده منطقة ردم
(جوه حدود الردم ومش جوه عنصر رأسي/الخزان)، وارتفاعه من وش اللبشة/القاعدة/السمل في الجنب ده لحد منسوب الردم.
"""
import math, collections
import numpy as np
import shapely
from shapely.geometry import LineString
from substructure_model import MAT_TOP, PROBE, DOOR_W, DOOR_SILL_ABOVE

PIT_DEPTH = 0.50   # م — عمق أي حفرة عمقها مش مرسوم (افتراض المهندس 2026-11-23)


def _loc(g):
    """موقع مختصر: مركز الشكل بالمتر من تقاطع المحورين 01/A."""
    c = g.centroid
    return f"({c.x/1000:.2f} ، {c.y/1000:.2f})"


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


def _core_names(label):
    n = label.replace('CORE', '').split()[0]
    side = 'شمالي' if 'شمالي' in label else ('جنوبي' if 'جنوبي' in label else '')
    use_ar = {'1': 'أسانسير جنب الخزان', '2': 'أسانسير', '3': 'سلالم'}.get(n, '')
    use_en = {'1': 'lift, next to tank', '2': 'lift', '3': 'stairs'}.get(n, '')
    side_en = {'شمالي': 'north', 'جنوبي': 'south'}.get(side, '')
    return (f"كور {n}" + (f" {side}" if side else '') + f" ({use_ar})",
            f"Core {n}" + (f" {side_en}" if side_en else '') + f" ({use_en})")


PERIM = [('N', 'الحائط الشمالي (جدار الجار 1.70م)', 'North wall (neighbour wall 1.70 m)'),
         ('NC', 'أوجه أعمدة C التسعة في الحائط الشمالي', 'Inner faces of the 9 C columns (north wall)'),
         ('W', 'الحائط الغربي', 'West wall'), ('S', 'الحائط الجنوبي', 'South wall'), ('E', 'الحائط الشرقي', 'East wall')]


# ═══════════════════════════════════════════════════════════════════ الترقيم الموحّد
def elements(M):
    """قائمة مرتّبة: dict(no, uid, kind, ar, en, anchor=(x,y), poly) — نفس الأرقام في كل الصور والإكسل."""
    out = []
    def add(uid, kind, ar, en, geom, anchor=None):
        if anchor is None:
            p = geom.representative_point() if geom.geom_type != 'LineString' else geom.interpolate(0.5, normalized=True)
            anchor = (p.x, p.y)
        out.append(dict(no=len(out) + 1, uid=uid, kind=kind, ar=ar, en=en, anchor=anchor, poly=geom))
    add('MAT', 'mat', 'المات العام (وش ‑8.45)', 'General raft (top -8.45)', M.mat_region,
        anchor=(M.D.bounds[0] + 9000, M.D.bounds[1] + 3000))
    for f in M.fz:
        add(f['uid'], 'footing', f"قاعدة سمك {f['th']} (وش {f['top']:+.2f})", f"Footing t={f['th']} (top {f['top']:+.2f})", f['region'])
    for b in M.bz:
        add(b['uid'], 'beam', f"سمل {b['w']}×{b['d']} (ظهر {b['top']:+.2f})", f"Tie beam {b['w']}x{b['d']} (top {b['top']:+.2f})", b['region'])
    for o in M.obs:
        if o['kind'] == 'column':
            c = o['ref']
            add(o['uid'], 'column', f"عمود {c['mark']} {c['w']}×{c['h']}" + (f" (رقم {c['no']} في حصر الأعمدة)" if c['no'] else ''),
                f"Column {c['mark']} {c['w']}x{c['h']}" + (f" (#{c['no']} in columns takeoff)" if c['no'] else ''), o['poly'])
        elif o['kind'] == 'core':
            ar, en = _core_names(o['ref']['label'])
            add(o['uid'], 'core', ar, en, o['poly'])
        elif o['kind'] == 'tank':
            add(o['uid'], 'tank', 'الخزان (حوائطه + داخله + العمودين اللي فيه)', 'Water tank (walls + inside + its columns)', o['poly'])
        elif o['kind'] == 'starter':
            r = o['ref']['ramp'].split()[-1]
            add(o['uid'], 'starter', f"بادئ رامب {r}", f"Ramp {r} starter wall", o['poly'])
    for l in M.lifts:
        ar, en = _core_names(l['ref']['label'])
        add(l['uid'], 'lift', f"داخل {ar.split(' (')[0]} — حفرة أسانسير", f"Inside {en.split(' (')[0]} — lift pit", l['poly'])
    for i, p in enumerate(M.pits, 1):
        add(f"PIT{i}", 'sump', f"حفرة صرف {i}", f"Sump pit {i}", p['inner'])
    x0, y0, x1, y1 = M.D.bounds
    lines = {'N': LineString([(x0 + 4000, y1), (x1 - 4000, y1)]), 'NC': LineString([(x0 + 6000, y1), (x0 + 6001, y1)]),
             'W': LineString([(x0, y0), (x0, y1)]), 'S': LineString([(x0, y0), (x1, y0)]), 'E': LineString([(x1, y0), (x1, y1)])}
    anchors = {'N': ((x0 + x1) / 2, y1 + 1500), 'NC': (x0 + 12000, y1 + 1500), 'W': (x0 - 1800, (y0 + y1) / 2),
               'S': ((x0 + x1) / 2, y0 - 1500), 'E': (x1 + 1800, (y0 + y1) / 2)}
    for k, ar, en in PERIM:
        add('PER:' + k, 'perim', ar, en, lines[k], anchor=anchors[k])
    s = [s for s in M.starters if s['ramp'] == 'RAMP 03'][0]
    R = s['R']
    add('WEDGE', 'wedge', 'بلاطة رامب 03 تحت منسوب الردم (أول 1.89م)', 'Ramp 03 slab below fill level (first 1.89 m)',
        shapely.geometry.box(R['x0'], R['y_start'] - 2140, R['x1'], R['y_start'] - R['wall_t']))
    return out


# ═══════════════════════════════════════════════════════════════════ البند 1: الردم
def backfill(M):
    F = M.FILL
    zones = M.zone_regions_uid()
    zone_rows = []
    for uid, name, kind, reg, top in zones:
        h = max(0.0, F - top); A = reg.area / 1e6
        Ao = reg.intersection(M.O_fill).area / 1e6
        zone_rows.append(dict(uid=uid, name=name, kind=kind, top=top, A=A, Aobs=Ao, Anet=A - Ao, h=h,
                              Vg=A * h, Vnet=(A - Ao) * h, region=reg))
    # الحجم القائم: المات (شامل شرائح السملات) + كل قاعدة بوشّها
    gross_rows = [dict(uid='MAT', top=MAT_TOP, A=M.mat_with_beams.area / 1e6, h=F - MAT_TOP, region=M.mat_with_beams)]
    for f in M.fz:
        gross_rows.append(dict(uid=f['uid'], top=f['top'], A=f['region'].area / 1e6, h=max(0.0, F - f['top']), region=f['region']))
    for g in gross_rows:
        g['V'] = g['A'] * g['h']
    gross = sum(g['V'] for g in gross_rows)
    # السملات: الجزء الظاهر فوق المات. (اللي تحت عنصر رأسي بيتخصم مع العنصر بارتفاعه فوق ظهر السمل → مفيش تكرار)
    beam_rows = []
    for b in M.bz:
        A = b['region'].area / 1e6; hb = b['top'] - MAT_TOP
        beam_rows.append(dict(uid=b['uid'], top=b['top'], L=b['L'], w=b['w'] / 1000.0, A=A, h=hb, V=A * hb))
    # العناصر الرأسية + داخل كوري الأسانسير: Σ مساحة العنصر في كل منطقة وش × ارتفاع الردم فوقها
    obs_rows = []
    for o in M.obs + M.lifts + M.sumps:
        V = 0.0; Aw = 0.0; zs = []
        for uid, name, kind, reg, top in zones:
            a = o['poly'].intersection(reg).area / 1e6
            if a > 1e-9:
                V += a * max(0.0, F - top); Aw += a; zs.append((top, a))
        base = sum(t * a for t, a in zs) / Aw if Aw else MAT_TOP
        obs_rows.append(dict(uid=o['uid'], kind=o['kind'], A=o['poly'].area / 1e6, base=base, h=F - base, V=V))
    tank_split = []
    for nm, g in (("حوائط الخزان 350مم + العمود الفاصل C3", M.tank_walls), ("داخل الخزان (مياه — مفيش ردم)", M.tank_in)):
        V = sum(g.intersection(reg).area / 1e6 * max(0.0, F - top) for _, _, _, reg, top in zones)
        tank_split.append(dict(name=nm, A=g.area / 1e6, V=V))
    wedge = M.ramp03_wedge()
    wedge_V = sum(v[0] for v in wedge.values())
    by_kind = collections.OrderedDict()
    by_kind['beam'] = sum(r['V'] for r in beam_rows)
    for k in ('column', 'core', 'tank', 'starter', 'lift', 'sump'):
        by_kind[k] = sum(r['V'] for r in obs_rows if r['kind'] == k)
    by_kind['wedge'] = wedge_V
    deduct = sum(by_kind.values())
    net = gross - deduct
    check = sum(z['Vnet'] for z in zone_rows) - wedge_V          # نفس الصافي بطريقة المناطق (تحقق داخلي)
    return dict(F=F, zones=zone_rows, gross_rows=gross_rows, gross=gross, beams=beam_rows, obs=obs_rows,
                tank_split=tank_split, wedge=wedge, wedge_V=wedge_V, by_kind=by_kind, deduct=deduct, net=net, check=check)


# ═══════════════════════════════════════════════════════════════════ البند 2: العزل
def insulation(M, pit_depth=PIT_DEPTH):
    F = M.FILL
    # 0) الحفر: 3 مرسومة (بلوك 'sump pit') + حفرتا الأسانسير. القاع الداخلي بند لوحده (بيتشال من ظهر اللبشة تحته)،
    #    والجوانب الداخلية = المحيط الداخلي × العمق (مش مرسوم → PIT_DEPTH).
    pits = []
    for i, p in enumerate(M.pits, 1):
        inner = p['inner'].intersection(M.D).difference(M.O) if p['inner'] is not None else None
        if inner is not None and inner.area > 1.0:
            pits.append(dict(uid=f"PIT{i}", kind='sump', poly=inner, outer=p['outer']))
    for l in M.lifts:
        pits.append(dict(uid=l['uid'], kind='lift', poly=l['poly'], outer=None))
    for q in pits:
        g = q['poly']; c = g.centroid
        q['top'] = float(M.z(np.array([c.x]), np.array([c.y]))[0])
        x0, y0, x1, y1 = g.bounds; q['w'], q['l'] = (x1 - x0) / 1000, (y1 - y0) / 1000
        q['A_bot'] = g.area / 1e6; q['P'] = g.length / 1000.0
        q['depth'] = pit_depth or 0.0; q['bottom'] = q['top'] - q['depth']; q['A_side'] = q['P'] * q['depth']
    pit_union = shapely.union_all([q['poly'] for q in pits]) if pits else None
    # 1) أفقي: ظهر كل منطقة − بصمات العناصر الرأسية والخزان − قاع الحفر (محسوب لوحده)
    horiz = []
    for uid, name, kind, reg, top in M.zone_regions_uid():
        net = reg.difference(M.O)
        if pit_union is not None:
            net = net.difference(pit_union)
        horiz.append(dict(uid=uid, kind=kind, top=top, A=reg.area / 1e6, A_ded=(reg.area - net.area) / 1e6,
                          Anet=net.area / 1e6, region=net))
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
            sides.append(dict(uid=it['uid'], kind=kind, top=it['top'], A=float(np.sum(W[ok] * h[ok])) / 1e3,
                              L=float(np.sum(W[ok])) / 1000.0, rng=_rng(h, ok), segs=_segments(X, Y, NX, NY, W, ok, h)))
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
        vert.append(dict(uid=o['uid'], kind=o['kind'], A=float(np.sum(W[ok] * h[ok])) / 1e3,
                         P=float(np.sum(W[ok])) / 1000.0, rng=_rng(h, ok), segs=_segments(X, Y, NX, NY, W, ok, h)))
    # 4) الوش الداخلي للجدار المحيط (من وش اللبشة جنبه لحد منسوب الردم)
    X, Y, NX, NY, W = M.samples(M.D)
    px, py = X - NX * PROBE, Y - NY * PROBE
    ok = ~shapely.contains_xy(M.O, px, py)
    h = np.maximum(0.0, F - M.z(px, py))
    side = np.where(NX < -0.5, 'W', np.where(NX > 0.5, 'E', np.where(NY < -0.5, 'S', 'N')))
    incol = np.zeros(X.shape, bool)
    for c in M.north_cols:
        x0, _, x1, _ = c.bounds
        incol |= (side == 'N') & (X >= x0) & (X <= x1)
    side = np.where(incol, 'NC', side)
    perim = []
    for k, _, _ in PERIM:
        m = ok & (side == k)
        perim.append(dict(uid='PER:' + k, kind='perim', L=float(np.sum(W[m])) / 1000.0, A=float(np.sum(W[m] * h[m])) / 1e3,
                          rng=_rng(h, m), segs=_segments(X, Y, -NX, -NY, W, m, h)))
    # 5) قاع بلاطة رمب 03 اللي تحت منسوب الردم (أول ~1.9م بعد البادئ)
    wedge = M.ramp03_wedge()
    # 6) أبواب أكوار السلالم: الباب بيبدأ 10سم فوق وش قاعدة الـ1500 → الجزء تحت منسوب الردم
    sill = round(F + DOOR_SILL_ABOVE, 3)
    doors = []
    for c in M.cores:
        for d in c['doors']:
            hd = max(0.0, F - sill)
            doors.append(dict(core=c['label'], w=DOOR_W, sill=sill, h=hd, A=2 * DOOR_W * hd))
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
    t['wedge'] = sum(v[1] for v in wedge.values())
    t['pit_bottom'] = sum(q['A_bot'] for q in pits)
    t['pit_sides'] = sum(q['A_side'] for q in pits)
    t['doors'] = -sum(d['A'] for d in doors)
    return dict(F=F, horiz=horiz, sides=sides, vert=vert, perim=perim, wedge=wedge, doors=doors, sill=sill,
                pits=pits, pit_depth=pit_depth, totals=t, total=sum(t.values()))


# ═══════════════════════════════════════════════════════════════════ الفرضيات والملاحظات
def notes(M):
    F = M.FILL
    return [
        ("منسوب الردم", f"{F:+.2f} = وش القاعدة اللي سمكها 1.50م (بطاقة المنسوب المرسومة جوه القاعدة على لوحة أبعاد خرسانة اللبشة)، وبيطابق قاع التأسيس ‑8.85 + 1.50."),
        ("حدود الردم", f"الوش الداخلي للجدار المحيط: {M.D_dims[0]:.3f} × {M.D_dims[1]:.3f} م = {M.D.area/1e6:.2f} م² (3 أضلاع عالية + جدار الجار 1.70م). الجدار نفسه برّه الحدود."),
        ("الخزان", "جوّه مش بيتردم ومش بيتعزل (ومعاه العمودين اللي جوّاه). بيتعزل من برّه بس."),
        ("كوري الأسانسير (1 و 2)", "جوّاهم مش بيتردم. قاع وجوانب حفرة الأسانسير بيتعزلوا."),
        ("حفر الصرف التلاتة", "فتحتها الداخلية 1.20×1.20 مش بتتردم (بتتخصم من الردم من وش اللبشة لحد منسوب الردم). قاعها وجوانبها الداخلية بيتعزلوا."),
        ("كوري السلالم (3 شمالي و 3 جنوبي)", f"جوّاهم بيتردم لحد {F:+.2f}، وبيتعزلوا من برّه ومن جوّه."),
        ("أبواب كوري السلالم", f"الباب 1.20×2.30 بيبدأ {F+DOOR_SILL_ABOVE:+.2f} (10سم فوق وش قاعدة الـ1.50) → فوق منسوب الردم، فمفيش خصم والحائط تحته مصمت."),
        ("عمق الحفر", f"عمق حفر الصرف التلاتة وحفرتي الأسانسير مش مرسوم → مفترض {PIT_DEPTH:.2f}م تحت وش اللبشة حواليها (تعليمة المهندس)."),
        ("السملات", "17 سمل مرسومين في اللوحة؛ كل سمل بعرضه المرسوم بين خطّيه، وظهره = ‑8.85 + عمقه."),
        ("بلاطة رامب 03", f"قاعها تحت {F:+.2f} في أول 1.89م بعد البادئ (ميل 7.5٪) → بتتخصم من الردم وقاعها بيتعزل."),
        ("هوابط سفلية", "مفيش هوابط لتحت مرسومة؛ قاع اللبشة ثابت ‑8.85 والقواعد مُثخّنة لفوق (محسوبة كمناطق وجوانب)."),
        ("العزل", "دهان → مفيش ركوب ومفيش خصم سُمك من الردم. كله لحد منسوب الردم بالظبط. مفيش عزل تحت أي عنصر رأسي."),
    ]
