# -*- coding: utf-8 -*-
"""
نموذج هندسي دقيق لِما تحت منسوب الردم في البدروم السفلي — Muttajah Mall (لوحة 2026-11-08).
يخدم البندين: الردم الداخلي (backfill_takeoff.py) والعزل بالدهان (insulation_takeoff.py).

كل حاجة مقروءة من اللوحة (DXF) على الشبكة الموحّدة column_exact.PLAN_ORIGIN (نقطة المحورين 01/A):
  • منسوب الردم FILL = بطاقة المنسوب المرسومة جوه القاعدة اللي سمكها 1500 (‑7.35m S.S.L)، ويتأكّد = ‑8.85 + 1.50.
  • حدود الردم D = الوش الداخلي للجدار المحيط: الجدار U (بلوك 'A$C46269fcd new'، طبقة R.C. footing) للأضلاع
    الغربي/الجنوبي/الشرقي + الوش الداخلي لجدار الجار الشمالي 1.70م (بلوك 'wall str n') وأعمدة C اللي فيه.
  • مناطق وش اللبشة: القواعد (R.C. footing + بابلة السماكة) وشّها = ‑8.85 + السماكة؛ الباقي مات ‑8.45.
  • السملات: MLINE على R.C. footing — الشريحة بين الخطّين المرسومين فعلاً (justification=top، مش خط وسط)،
    والعمق من ليبل S(WxD) → الظهر = ‑8.85 + العمق.
  • الأعمدة: مستطيلات S - column من column_exact.LiftOne.rects، ومربوطة بأسمائها (نفس ترقيم حصر العناصر الرأسية).
  • الأكوار: حدودها المرسومة (S - column، بلوك الأعمدة الرئيسي) + فتحات الأبواب (S-OPENING 1200×300).
    الباب بيبدأ ‑7.25 (10سم فوق ‑7.35) → تحت منسوب الردم الحائط مصمت، فالفتحة بتتقفل في النموذج.
  • الخزان: حدّه الخارجي والداخلي المرسومين (بلوك 'A$C498c0d08'، طبقة S -Beams). جوّه مفيش ردم ولا عزل.
  • بادئ الرمب: column_exact.RAMP (حائط 250مم، من القطاع). وبلاطة رمب 03 قاعها تحت ‑7.35 في أول ~1.9م.
  • حفر الصرف (sump pit ×3): مرسومة على لوحة RAFT RFT بس من غير قطاع → بتتعرض كبند ناقص (مش بتتفترض).
"""
import math, re, collections
import numpy as np
import ezdxf
import shapely
from shapely.geometry import Polygon, box, Point
from shapely.ops import unary_union
import raft_footings as RF, column_exact as CX, columns_takeoff as ct, concrete_columns_takeoff as cc
import column_base_levels as cbl

FORMATION = RF.FORMATION_LEVEL          # ‑8.85 قاع التأسيس
MAT_TOP   = CX.RAFT_LOW_TOP             # ‑8.45 وش المات العام
FILL_THK  = 1500                        # القاعدة اللي منسوبها = منسوب الردم
DOOR_W, DOOR_H, DOOR_SILL_ABOVE = 1.20, 2.30, 0.10   # باب كور السلالم (تعليمة المهندس)
RFT_ORIGIN = (-741110.0, 387399.0)      # لوحة RAFT RFT (نفس الشبكة، إزاحة 100000)
LIFT_CORES = ('CORE1', 'CORE2')         # كوري الأسانسير — داخلهم مش بيتردم
STEP = 20.0                             # مم — تقسيم الحواف عند حساب الأسطح الرأسية
PROBE = 5.0                             # مم — نقطة الفحص على جانبَي الحافة


def _txt(e):
    try:
        return " ".join(((e.plain_text() if e.dxftype() == "MTEXT" else e.dxf.text) or "").split())
    except Exception:
        return ""


def _snap(g):
    """تقريب الإحداثيات لأقرب 1مم — الرسومات فيها كسور (31331.31 مقابل 31331.36) بتعمل شرائح وهمية بين العناصر."""
    return shapely.set_precision(g, 1.0)


def _poly(pts):
    p = Polygon(pts)
    return _snap(p if p.is_valid else p.buffer(0))


class Substructure:
    def __init__(self, msp, dxf_path=None):
        self.msp = msp
        self.L = CX.LiftOne(msp)
        RX, RY = CX.PLAN_ORIGIN['RAFT']; CXo, CYo = CX.PLAN_ORIGIN['COL']
        self._read_fill_level(RX, RY)
        self._read_perimeter(CXo, CYo)
        self._read_footings()
        self._read_beams(RX, RY)
        self._read_columns()
        self._read_cores_tank(CXo, CYo)
        self._read_starters()
        self._read_pits()
        self._build()

    # ------------------------------------------------------------------ قراءة
    def _read_fill_level(self, RX, RY):
        """بطاقة المنسوب (FLOOR-LEVEL-FFL) المرسومة جوه قاعدة الـ1500 في لوحة RAFT CONCRETE DIMENSIONS."""
        fts = [z for z in self.L.zones]
        thick = [z for z in fts if z['th'] == FILL_THK]
        tags = []
        for e in self.msp.query('INSERT'):
            x, y = e.dxf.insert.x - RX, e.dxf.insert.y - RY
            if not CX.IN_PLAN(x, y):
                continue
            try:
                at = {a.dxf.tag: a.dxf.text for a in e.attribs}
            except Exception:
                continue
            v = at.get('FLOOR-LEVEL-FFL')
            if v:
                m = re.search(r'[-+]?\d+(?:\.\d+)?', v)
                if m:
                    inside = [z for z in thick if CX._pip(x, y, z['pts'])]
                    tags.append((float(m.group()), x, y, bool(inside)))
        on1500 = [t for t in tags if t[3]]
        derived = round(FORMATION + FILL_THK / 1000.0, 3)
        if on1500:
            self.FILL = on1500[0][0]
            self.fill_src = f"بطاقة منسوب '{on1500[0][0]:+.2f}m S.S.L' مرسومة جوه قاعدة الـ1500 (لوحة RAFT CONCRETE DIMENSIONS)"
        else:
            self.FILL = derived
            self.fill_src = "مشتق: قاع التأسيس ‑8.85 + سماكة القاعدة 1.50"
        self.fill_check = (derived, abs(self.FILL - derived) < 1e-6)

    def _read_perimeter(self, CXo, CYo):
        from ezdxf import bbox as BB
        U = None; north = []; ccols = []
        for e in self.msp.query('INSERT'):
            if e.dxf.name not in ('A$C46269fcd new', 'wall str n', 'str col s'):
                continue
            b = BB.extents([e])
            if not b.has_data or not (-552000 < b.extmin.x < -484000 and 370000 < b.extmin.y < 432000):
                continue
            for v in e.virtual_entities():
                if v.dxftype() != 'LWPOLYLINE':
                    continue
                pts = [(p[0] - CXo, p[1] - CYo) for p in v.get_points('xy')]
                if e.dxf.name == 'A$C46269fcd new' and v.dxf.layer == 'R.C. footing' and len(pts) == 8:
                    U = pts
                elif e.dxf.name == 'wall str n' and v.dxf.layer == 'R.C. footing':
                    north.append(_poly(pts))
                elif e.dxf.name == 'str col s' and v.dxf.layer == 'S - column':
                    ccols.append(_poly(pts))
        Up = _poly(U)
        outer = Up.envelope                                    # الحدّ الخارجي للجدار
        xs = sorted({round(p[0]) for p in U}); ys = sorted({round(p[1]) for p in U})
        xi0, xi1 = xs[1], xs[2]; yi0 = ys[1]                    # الوش الداخلي للأضلاع الثلاثة
        yN = round(min(p.bounds[1] for p in north + ccols))     # الوش الداخلي لجدار الجار
        self.D = _snap(box(xi0, yi0, xi1, yN))
        self.D_dims = ((xi1 - xi0) / 1000.0, (yN - yi0) / 1000.0)
        self.outer = outer
        self.north_walls = north; self.north_cols = ccols
        self.wall_t = round((xi0 - outer.bounds[0]) / 1000.0, 3)

    def _read_footings(self):
        self.footings = []
        for i, z in enumerate(sorted(self.L.zones, key=lambda z: (-z['th'], z['pts'][0]))):
            p = _poly(z['pts'])
            self.footings.append(dict(poly=p, th=z['th'], top=round(z['top'], 3), name=f"قاعدة {z['th']}"))

    def _read_beams(self, RX, RY):
        rx = re.compile(r"S\s*\(\s*(\d+)\s*[xX]\s*(\d+)\s*\)")
        labels = []
        for e in self.msp.query('TEXT MTEXT'):
            m = rx.search(_txt(e))
            if m:
                labels.append((int(m.group(1)), int(m.group(2)), e.dxf.insert.x - RX, e.dxf.insert.y - RY))
        self.beams = []
        for e in self.msp.query('MLINE'):
            if e.dxf.layer != RF.FOOTING_LAYER:
                continue
            lines = [v for v in e.virtual_entities() if v.dxftype() == 'LINE']
            if len(lines) != 2:
                continue
            a = [(l.dxf.start.x - RX, l.dxf.start.y - RY, l.dxf.end.x - RX, l.dxf.end.y - RY) for l in lines]
            if not CX.IN_PLAN(a[0][0], a[0][1]):
                continue
            pts = [(a[0][0], a[0][1]), (a[0][2], a[0][3]), (a[1][2], a[1][3]), (a[1][0], a[1][1])]
            p = _poly(pts)
            c = p.centroid
            d, best = 1e18, None
            for (w, dd, lx, ly) in labels:
                q = math.hypot(lx - c.x, ly - c.y)
                if q < d: d, best = q, (w, dd)
            if best is None or d > 3000:
                continue
            w, dd = best
            L = math.hypot(a[0][2] - a[0][0], a[0][3] - a[0][1])
            self.beams.append(dict(poly=p, w=w, d=dd, top=round(FORMATION + dd / 1000.0, 3), L=L / 1000.0,
                                   name=f"S({w}×{dd})", c=(c.x, c.y)))
        self.beams.sort(key=lambda b: (-b['d'], -b['c'][1], b['c'][0]))

    def _read_columns(self):
        """مستطيلات الأعمدة المرسومة + اسم/رقم كل عمود (نفس ترتيب حصر العناصر الرأسية)."""
        plan, sched = ct.collect(self.msp)
        stages, _ = cc.parse_schedule_stages(sched)
        cols = cc.columns_list(plan)
        colcols = [c for c in cols if not c[1].startswith('CORE')]
        colcols.sort(key=lambda c: (-c[3], c[2]))
        sizes = {m: v[0] for m, v in stages.items() if v and v[0]}
        match = self.L.match(colcols, sizes)
        tank_c3 = [c for c in colcols if c not in cbl.drop_tank_c3(colcols, cols)]
        num = {}; k = 0
        for i, c in enumerate(colcols):
            if c in tank_c3: continue
            k += 1; num[i] = k
        by_rect = {}
        for i, r in match.items():
            by_rect[id(r)] = (num.get(i), colcols[i][1])
        self.columns = []
        for r in self.L.rects:
            n, m = by_rect.get(id(r), (None, '?'))
            self.columns.append(dict(poly=_snap(box(r['x0'], r['y0'], r['x1'], r['y1'])), no=n, mark=m,
                                     w=round(r['x1'] - r['x0']), h=round(r['y1'] - r['y0']), c=(r['cx'], r['cy'])))

    def _read_cores_tank(self, CXo, CYo):
        from ezdxf import bbox as BB
        core_polys = []; tank_out = tank_in = None
        for e in self.msp.query('INSERT'):
            b = BB.extents([e])
            if not b.has_data or not (-552000 < b.extmin.x < -484000 and 370000 < b.extmin.y < 432000):
                continue
            for v in e.virtual_entities():
                if v.dxftype() != 'LWPOLYLINE':
                    continue
                pts = [(p[0] - CXo, p[1] - CYo) for p in v.get_points('xy')]
                if v.dxf.layer == 'S - column' and len(pts) > 4:
                    if len(pts) > 4 and pts[0] == pts[-1]: pts = pts[:-1]
                    core_polys.append(_poly(pts))
                elif e.dxf.name == 'A$C498c0d08' and v.dxf.layer == 'S -Beams':
                    if len(pts) == 6: tank_out = _poly(pts)
                    elif len(pts) > 6: tank_in = _poly(pts)
        doors = []
        for e in self.msp.query('LWPOLYLINE'):
            if e.dxf.layer != 'S-OPENING' or not e.closed:
                continue
            pts = [(p[0] - CXo, p[1] - CYo) for p in e.get_points('xy')]
            if CX.IN_PLAN(*pts[0]): doors.append(_poly(pts))
        labels = []
        for e in self.msp.query('TEXT'):
            s = _txt(e)
            if re.fullmatch(r'CORE\s*\d', s):
                labels.append((s.replace(' ', ''), e.dxf.insert.x - CXo, e.dxf.insert.y - CYo))
        self.cores = []
        for p in core_polys:
            env = p.envelope.buffer(800)
            nm = [s for s, x, y in labels if env.contains(Point(x, y))]
            nm = nm[0] if nm else 'CORE?'
            dr = [d for d in doors if d.distance(p) < 1]
            solid = _snap(unary_union([p] + dr))               # تحت منسوب الردم الحائط مصمت تحت الباب
            self.cores.append(dict(name=nm, poly=p, solid=solid, doors=dr))
        self.cores.sort(key=lambda c: (c['name'], -c['poly'].centroid.y))
        cnt = collections.Counter(c['name'] for c in self.cores); seen = collections.Counter()
        for c in self.cores:
            seen[c['name']] += 1
            c['label'] = c['name'] + (f" ({'شمالي' if seen[c['name']] == 1 else 'جنوبي'})" if cnt[c['name']] > 1 else '')
        self.tank_out, self.tank_in = tank_out, tank_in
        self.tank_walls = tank_out.difference(tank_in)
        self.doors = doors

    def _read_starters(self):
        self.starters = []
        for name, R in CX.RAMP.items():
            p = _snap(box(R['x0'], R['y_start'] - R['wall_t'], R['x1'], R['y_start']))
            top = CX._interp(R['soffit'], R['wall_t'])        # قاع بلاطة الرمب فوق البادئ
            self.starters.append(dict(name=f"بادئ {name}", ramp=name, poly=p, top=round(top, 4), R=R))

    def _read_pits(self):
        """حفر الصرف (بلوك 'sump pit' على لوحة RAFT RFT): مربع خارجي 1.50 وداخلي 1.20."""
        from ezdxf import bbox as BB
        OX, OY = RFT_ORIGIN; sq = []
        for e in self.msp.query('INSERT'):
            if e.dxf.name != 'sump pit':
                continue
            for v in e.virtual_entities():
                if v.dxftype() == 'LWPOLYLINE':
                    pts = [(p[0] - OX, p[1] - OY) for p in v.get_points('xy')]
                    sq.append(_poly(pts))
        outer = [p for p in sq if p.area > 2.0e6]; inner = [p for p in sq if p.area < 2.0e6]
        self.pits = []
        for o in sorted(outer, key=lambda p: (-p.centroid.y, p.centroid.x)):
            i = [q for q in inner if o.contains(q.centroid)]
            self.pits.append(dict(outer=o, inner=i[0] if i else None))

    # ------------------------------------------------------------------ بناء النموذج
    def _build(self):
        D = self.D
        # مناطق وش اللبشة (القاعدة الأعلى تغلب لو فيه تداخل)
        fz = []
        taken = Polygon()
        for f in sorted(self.footings, key=lambda f: -f['top']):
            g = f['poly'].intersection(D).difference(taken)
            taken = taken.union(f['poly'])
            fz.append(dict(f, region=g))
        self.fz = fz
        foot_union = unary_union([f['poly'] for f in self.footings])
        bz = []; taken = foot_union
        for b in sorted(self.beams, key=lambda b: -b['top']):
            g = b['poly'].intersection(D).difference(taken)
            taken = taken.union(b['poly'])
            bz.append(dict(b, region=g))
        self.bz = bz
        beam_union = unary_union([b['poly'] for b in self.beams])
        self.mat_region = D.difference(foot_union).difference(beam_union)
        self.mat_with_beams = D.difference(foot_union)

        # العناصر الرأسية/المستبعدة — بأولوية لمنع العدّ مرتين
        obs = []; taken = Polygon()
        def add(kind, name, poly, ref=None):
            nonlocal taken
            g = poly.intersection(D).difference(taken)
            if g.area > 1.0:                     # > 1 مم²
                obs.append(dict(kind=kind, name=name, poly=g, ref=ref))
                taken = taken.union(g)
        add('tank', 'الخزان T1 (الحوائط + الداخل)', self.tank_out)
        for c in self.cores:
            add('core', c['label'], c['solid'], c)
        for c in sorted(self.columns, key=lambda c: (c['no'] or 999)):
            add('column', f"{c['mark']}" + (f" #{c['no']}" if c['no'] else ''), c['poly'], c)
        for s in self.starters:
            add('starter', s['name'], s['poly'], s)
        self.obs = obs
        self.O = unary_union([o['poly'] for o in obs]) if obs else Polygon()
        # داخل كوري الأسانسير (CORE1 جنب الخزان + CORE2): مش بيتردم (تعليمة المهندس 2026-11-23) — بيتخصم من الردم بس؛
        # قاعه وجوانبه الداخلية لحد منسوب الردم بيتعزلوا (قاع/جوانب حفرة الأسانسير كما هي مرسومة).
        self.lifts = []
        for c in self.cores:
            if c['name'] not in LIFT_CORES:
                continue
            inner = c['poly'].envelope.difference(c['poly'])
            if c['name'] == 'CORE1':
                inner = inner.difference(self.tank_out)
            inner = _snap(inner).intersection(D).difference(self.O)
            if inner.area > 1.0:
                self.lifts.append(dict(kind='lift', name=f"داخل {c['label']} (أسانسير — مش بيتردم)", poly=inner, ref=c))
        self.O_fill = unary_union([self.O] + [l['poly'] for l in self.lifts])

        # z-field (للفحص النقطي)
        self._zpolys = [(f['poly'], f['top']) for f in self.footings] + [(b['poly'], b['top']) for b in self.beams]

    # ------------------------------------------------------------------ أدوات
    def z(self, x, y):
        x = np.asarray(x, float); y = np.asarray(y, float)
        z = np.full(x.shape, MAT_TOP)
        for p, t in self._zpolys:
            m = shapely.contains_xy(p, x, y)
            z = np.where(m & (t > z), t, z)
        return z

    def zone_regions(self):
        """[(الاسم، النوع، المنطقة، الوش)] لكل منطقة وش لبشة داخل D (المات + القواعد + السملات)."""
        out = [("المات العام", 'mat', self.mat_region, MAT_TOP)]
        out += [(f['name'], 'footing', f['region'], f['top']) for f in self.fz]
        out += [(b['name'], 'beam', b['region'], b['top']) for b in self.bz]
        return [r for r in out if r[2].area > 1.0]

    @staticmethod
    def samples(geom, step=STEP):
        """نقاط على كل حواف الشكل: (x, y, nx, ny, طول) — nx,ny عمودي للخارج (للحلقة الخارجية)."""
        rings = []
        polys = [geom] if geom.geom_type == 'Polygon' else list(getattr(geom, 'geoms', []))
        for p in polys:
            if p.geom_type != 'Polygon' or p.is_empty:
                continue
            ext = shapely.geometry.polygon.orient(p, 1.0)        # الخارجي عكس عقارب الساعة
            rings.append(list(ext.exterior.coords))
            for r in ext.interiors: rings.append(list(r.coords))   # الداخلي مع عقارب الساعة → العمودي للخارج برضه
        X, Y, NX, NY, W = [], [], [], [], []
        for ring in rings:
            for (x1, y1), (x2, y2) in zip(ring[:-1], ring[1:]):
                L = math.hypot(x2 - x1, y2 - y1)
                if L < 1e-6: continue
                n = max(1, int(math.ceil(L / step)))
                tx, ty = (x2 - x1) / L, (y2 - y1) / L
                nx, ny = ty, -tx                                   # يمين الاتجاه = للخارج في CCW
                for k in range(n):
                    t = (k + 0.5) / n
                    X.append(x1 + t * (x2 - x1)); Y.append(y1 + t * (y2 - y1)); NX.append(nx); NY.append(ny); W.append(L / n)
        return tuple(np.array(a) for a in (X, Y, NX, NY, W))

    def free(self, x, y):
        """النقطة في منطقة الردم (جوه D ومش جوه عنصر رأسي/الخزان)."""
        return shapely.contains_xy(self.D, x, y) & ~shapely.contains_xy(self.O, x, y)

    def ramp03_wedge(self, step=10.0):
        """بلاطة الرمب اللي قاعها تحت منسوب الردم (رمب 03 أول ~1.9م بعد البادئ): (حجم م³، مساحة قاع م²، طول م)."""
        out = {}
        for s in self.starters:
            R = s['R']; prof = R['soffit']
            s0 = R['wall_t']
            if CX._interp(prof, s0) >= self.FILL:
                out[s['ramp']] = (0.0, 0.0, 0.0); continue
            # المحطة اللي القاع فيها = منسوب الردم
            s1 = s0
            while CX._interp(prof, s1) < self.FILL: s1 += 1.0
            V = A = 0.0
            ss = np.arange(s0 + step / 2, s1, step)
            for sv in ss:
                y = R['y_start'] - sv
                strip = box(R['x0'], y - step / 2, R['x1'], y + step / 2).difference(self.O)
                h = self.FILL - CX._interp(prof, sv)
                V += strip.area * h; A += strip.area
            slope = (CX._interp(prof, s1) - CX._interp(prof, s0)) / ((s1 - s0) / 1000.0)
            out[s['ramp']] = (V / 1e6, A / 1e6 * math.sqrt(1 + slope ** 2), (s1 - s0) / 1000.0)
        return out
