# -*- coding: utf-8 -*-
"""
منسوب بداية ونهاية كل عمود في لِفت 1 (اللبشة → سقف البدروم السفلي) من **مستطيل العمود المرسوم** نفسه،
مش من نقطة اسم العمود. ده بديل الجدول اليدوي reference/column_overrides_lift1.json.

  • مستطيل العمود: طبقة `S - column` جوه بلوكات الأعمدة في مسقط COLUMNS&AXES (64 عمود + الأكوار).
  • البداية: وش القاعدة تحت كل جزء من مقطع العمود (‑8.85 + السماكة)، مرجّحة بالمساحة لو العمود على قاعدتين.
  • النهاية: قاع اللي فوق كل جزء من المقطع بالظبط: بلاطة 220 → ‑4.07، هابط 320 → ‑4.17، كمرة → قاع الكمرة
    للجزء اللي تحتها بس (الشريط بين خطّي الكمرة في طبقة S -Beams ممدود على العمود). النهاية المكتوبة = المتوسط المرجّح.
  • أعمدة الرمب "To Ramp Level": العلامة → الليدر → الدائرة اللي حوالين العمود. النهاية = قاع بلاطة الرمب (160)
    عند محطة العمود من بادئ الرمب، على بروفايل قطاع الرمب (7.5٪ أول وآخر 3م، ~15٪ في النص). البداية زي أي عمود.

كل المساقط على نفس الشبكة بإزاحة ثابتة من نقطة المحورين 01/A (انظر PLAN_ORIGIN). لوحة 2026-11-08.
"""
import math, re
import raft_footings as RF

# نقطة تقاطع المحورين 01/A في كل مسقط (إحداثيات اللوحة). المساقط كلها على شبكة واحدة بإزاحة 100000 بالظبط.
PLAN_ORIGIN = {
    'COL':  (-541110.0, 387399.0),   # COLUMNS&AXES
    'RAFT': (-641110.0, 387399.0),   # RAFT CONCRETE DIMENSIONS
    'LBC':  (-641110.0, 487399.0),   # LOWER BASEMENT CEILING (مسقط الخرسانة)
}
COL_BLOCKS = ('A$C46269fcd new', 'FROM FOUNDATION TO UPPER LOWER BASEMENT_COLUMNS(new3)', 'A$C498c0d08',
              'A$C502a855f new', 'str col s', 'wall str n')
LB_SSL, SLAB_T = -3.85, 0.22
RAFT_LOW_TOP = -8.45
# قاع بلاطة الرمب (160) على بروفايل قطاع الرمب: (المحطة من الوش الخارجي لبادئ الرمب مم، المنسوب)
# — من خطوط A-FLOR-PATT في RAMP 03/04 SECTION. y_start = الوش الخارجي للبادئ في إطار 01/A.
RAMP = {
    'RAMP 04': dict(y_start=25338, x0=-5519, x1=-1619, wall_t=250,
                    soffit=[(250, -7.3420), (3036.5, -7.1331), (22036.5, -4.2330), (25000, -4.0104)]),
    'RAMP 03': dict(y_start=26338, x0=42381, x1=46581, wall_t=250,
                    soffit=[(250, -7.4917), (3017.9, -7.2841), (23317.9, -4.2341), (26300, -4.0105)]),
}
IN_PLAN = lambda x, y: -12000 < x < 60000 and -12000 < y < 42000


def _text(e):
    s = e.dxf.text if e.dxftype() == 'TEXT' else e.plain_text()
    return ' '.join((s or '').split())


def _pip(x, y, poly):
    ins = False; n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            ins = not ins
    return ins


def _interp(prof, s):
    if s <= prof[0][0]: (s0, v0), (s1, v1) = prof[0], prof[1]
    elif s >= prof[-1][0]: (s0, v0), (s1, v1) = prof[-2], prof[-1]
    else:
        for i in range(len(prof) - 1):
            if prof[i][0] <= s <= prof[i + 1][0]:
                (s0, v0), (s1, v1) = prof[i], prof[i + 1]; break
    return v0 + (v1 - v0) * (s - s0) / (s1 - s0)


class LiftOne:
    """يقرا اللوحة مرة واحدة ويحسب بداية/نهاية أي عمود من مستطيله."""

    def __init__(self, msp):
        from ezdxf import bbox as BB
        CX, CY = PLAN_ORIGIN['COL']
        # ---- مستطيلات الأعمدة + علامات "To ..." والدوائر والليدرز (مسقط الأعمدة)
        self.rects = []
        for e in msp.query('INSERT'):
            if e.dxf.name not in COL_BLOCKS:
                continue
            b = BB.extents([e])
            if not (-552000 < b.extmin.x < -484000 and 370000 < b.extmin.y < 432000):
                continue
            for v in e.virtual_entities():
                if v.dxftype() == 'LWPOLYLINE' and v.dxf.layer == 'S - column':
                    pts = [(p[0] - CX, p[1] - CY) for p in v.get_points('xy')]
                    if len(pts) == 4:
                        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
                        self.rects.append(dict(x0=min(xs), x1=max(xs), y0=min(ys), y1=max(ys),
                                               cx=(min(xs) + max(xs)) / 2, cy=(min(ys) + max(ys)) / 2, blk=e.dxf.name))
        notes, leaders, circles = [], [], []
        for e in msp.query('TEXT MTEXT'):
            if e.dxf.layer != '00-EG-Text':
                continue
            x, y = e.dxf.insert.x - CX, e.dxf.insert.y - CY
            s = _text(e)
            if IN_PLAN(x, y) and s.startswith('To '):
                notes.append((x, y, s))
        for e in msp.query('LWPOLYLINE CIRCLE'):
            if e.dxf.layer != '00-DE-Hatch':
                continue
            if e.dxftype() == 'CIRCLE':
                x, y = e.dxf.center.x - CX, e.dxf.center.y - CY
                if IN_PLAN(x, y): circles.append((x, y))
            else:
                pts = [(p[0] - CX, p[1] - CY) for p in e.get_points('xy')]
                if IN_PLAN(*pts[0]): leaders.append(pts)
        # علامة كل عمود: الدائرة حوالين العمود → الليدر اللي طالع منها → النص عند آخر الليدر
        for r in self.rects:
            r['note'] = None
            circ = [c for c in circles if math.hypot(c[0] - r['cx'], c[1] - r['cy']) < 700]
            if not circ: continue
            c = circ[0]
            ld = [L for L in leaders if math.hypot(L[0][0] - c[0], L[0][1] - c[1]) < 800]
            if not ld: continue
            (ax, ay), (bx, by) = ld[0][-2], ld[0][-1]
            lo, hi = min(ax, bx) - 300, max(ax, bx) + 300
            nn = sorted((abs(ny - ay), s) for nx, ny, s in notes if lo <= nx <= hi and ay - 450 <= ny <= ay + 50)
            if nn: r['note'] = nn[0][1]
        # ---- مناطق اللبشة (القواعد المُثخّنة)
        RX, RY = PLAN_ORIGIN['RAFT']
        fts = RF.assign_thickness(RF.collect_footings(msp), RF.collect_thickness_bubbles(msp))
        self.zones = []
        for f in fts:
            pts = [(x - RX, y - RY) for x, y in f['pts']]
            if IN_PLAN(min(p[0] for p in pts), min(p[1] for p in pts)):
                self.zones.append(dict(pts=pts, th=f['th'], top=f['top']))
        # ---- سقف البدروم السفلي: هوابط + خطوط الكمرات + أسماء الكمرات
        LX, LY = PLAN_ORIGIN['LBC']
        drops, self.beam_lines, self.beam_labels, stext = [], [], [], []
        for e in msp:
            L = e.dxf.layer; t = e.dxftype()
            if t == 'LWPOLYLINE':
                pts = [(p[0] - LX, p[1] - LY) for p in e.get_points('xy')]
                if IN_PLAN(*pts[0]) and L in ('SLAB', 'S -Beams') and len(pts) == 4 and e.closed:
                    drops.append(pts)
            elif t == 'LINE' and L == 'S -Beams':
                a, b = e.dxf.start, e.dxf.end
                l = (a.x - LX, a.y - LY, b.x - LX, b.y - LY)
                if IN_PLAN(l[0], l[1]): self.beam_lines.append(l)
            elif t in ('TEXT', 'MTEXT'):
                x, y = e.dxf.insert.x - LX, e.dxf.insert.y - LY
                if not IN_PLAN(x, y): continue
                s = _text(e)
                if L == 'S-TEXT' and re.fullmatch(r'3[2-9]0|400', s):
                    stext.append((x, y, int(s)))
                m = re.search(r'(B\d|CA\d)\s*\(\s*(\d+)\s*[xX]\s*(\d+)', s)
                if m and L in ('ST-203-SLAB-TXT', 'BEAMS'):
                    rot = e.dxf.get('rotation', 0) if t == 'TEXT' else 0
                    self.beam_labels.append((x, y, m.group(1), int(m.group(2)), int(m.group(3)), rot))
        self.drop_polys = []   # الهابط = مستطيل مقفول جواه رقم 320
        for pts in drops:
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            inside = [v for (x, y, v) in stext if min(xs) <= x <= max(xs) and min(ys) <= y <= max(ys)]
            if inside: self.drop_polys.append((min(xs), max(xs), min(ys), max(ys), max(inside)))

    # ------------------------------------------------------------------ البداية
    def base_profile(self, c, n=24):
        """[(منسوب وش القاعدة، السماكة، نسبة من مقطع العمود)]"""
        acc = {}
        for i in range(n):
            for j in range(n):
                px = c['x0'] + (i + 0.5) * (c['x1'] - c['x0']) / n; py = c['y0'] + (j + 0.5) * (c['y1'] - c['y0']) / n
                hit = [z for z in self.zones if _pip(px, py, z['pts'])]
                key = (max(hit, key=lambda z: z['th'])['top'], max(hit, key=lambda z: z['th'])['th']) if hit else (RAFT_LOW_TOP, 400)
                acc[key] = acc.get(key, 0) + 1
        return [(k[0], k[1], v / (n * n)) for k, v in acc.items()]

    # ------------------------------------------------------------------ النهاية
    def _touches(self, c, l, tol=30):
        ax, ay, bx, by = l
        for px, py in ((ax, ay), (bx, by)):
            if c['x0'] - tol <= px <= c['x1'] + tol and c['y0'] - tol <= py <= c['y1'] + tol:
                return True
        if abs(ay - by) < 1 and c['y0'] - tol <= ay <= c['y1'] + tol and min(ax, bx) < c['x0'] and max(ax, bx) > c['x1']:
            return True
        if abs(ax - bx) < 1 and c['x0'] - tol <= ax <= c['x1'] + tol and min(ay, by) < c['y0'] and max(ay, by) > c['y1']:
            return True
        return False

    def _beam_label(self, l):
        mx, my = (l[0] + l[2]) / 2, (l[1] + l[3]) / 2
        horiz = abs(l[1] - l[3]) < 1; best = None
        for (x, y, mk, W, D, rot) in self.beam_labels:
            if horiz and abs(rot) > 1: continue
            if (not horiz) and abs(rot - 90) > 1: continue
            d = math.hypot(x - mx, y - my)
            if best is None or d < best[0]: best = (d, mk, W, D)
        return best

    def beam_strips(self, c):
        """بصمة كل كمرة داخلة على العمود: الشريط بين خطّي الكمرة ممدود على العمود."""
        out = []
        for horiz in (True, False):
            ls = []
            for l in self.beam_lines:
                if (abs(l[1] - l[3]) < 1) != horiz or not self._touches(c, l): continue
                bl = self._beam_label(l)
                if bl and bl[0] < 9000: ls.append((l[1] if horiz else l[0], bl))
            ls.sort(key=lambda t: t[0]); used = set()
            for i, (ci, bi) in enumerate(ls):
                if i in used: continue
                partner = None
                for j in range(i + 1, len(ls)):
                    if j not in used and (abs((ls[j][0] - ci) - bi[2]) <= 40 or abs((ls[j][0] - ci) - ls[j][1][2]) <= 40):
                        partner = j; break
                if partner is not None:
                    used.update((i, partner)); a, b = ci, ls[partner][0]
                    lab = bi if bi[3] >= ls[partner][1][3] else ls[partner][1]
                else:
                    used.add(i); ctr = c['cy'] if horiz else c['cx']
                    a, b = (ci, ci + bi[2]) if ctr >= ci else (ci - bi[2], ci); lab = bi
                out.append((c['x0'], c['x1'], a, b, lab) if horiz else (a, b, c['y0'], c['y1'], lab))
        return out

    def top_profile(self, c):
        """[(منسوب النهاية، اللي فوقه، نسبة من المقطع)] — تقسيم مضبوط للمقطع على حدود الكمرات والهوابط."""
        st = self.beam_strips(c); cells = {}
        xs = sorted({c['x0'], c['x1']} | {v for s in st for v in s[:2] if c['x0'] < v < c['x1']}
                    | {v for d in self.drop_polys for v in d[:2] if c['x0'] < v < c['x1']})
        ys = sorted({c['y0'], c['y1']} | {v for s in st for v in s[2:4] if c['y0'] < v < c['y1']}
                    | {v for d in self.drop_polys for v in d[2:4] if c['y0'] < v < c['y1']})
        A = (c['x1'] - c['x0']) * (c['y1'] - c['y0'])
        for i in range(len(xs) - 1):
            for j in range(len(ys) - 1):
                px = (xs[i] + xs[i + 1]) / 2; py = (ys[j] + ys[j + 1]) / 2
                w = (xs[i + 1] - xs[i]) * (ys[j + 1] - ys[j]) / A
                under = [s for s in st if s[0] <= px <= s[1] and s[2] <= py <= s[3]]
                if under:
                    lab = max(under, key=lambda s: s[4][3])[4]
                    k = (round(LB_SSL - lab[3] / 1000.0, 4), f"كمرة {lab[1]}({lab[2]}×{lab[3]})")
                else:
                    d = [v for (x0, x1, y0, y1, v) in self.drop_polys if x0 <= px <= x1 and y0 <= py <= y1]
                    k = (round(LB_SSL - max(d) / 1000.0, 4), f"هابط {max(d)}مم") if d else (round(LB_SSL - SLAB_T, 4), 'بلاطة 220مم')
                cells[k] = cells.get(k, 0) + w
        return [(t, what, f) for (t, what), f in sorted(cells.items()) if f > 1e-9]

    # ------------------------------------------------------------------ عمود كامل
    def levels(self, c):
        """dict(base, end, ramp, H, tops) لمستطيل عمود c"""
        ramp = None
        if c.get('note') == 'To Ramp Level':
            for name, R in RAMP.items():
                if R['x0'] - 400 <= c['cx'] <= R['x1'] + 400 and c['cy'] <= R['y_start'] + 100:
                    ramp = (name, R); break
        if ramp:
            s = ramp[1]['y_start'] - c['cy']
            tops = [(_interp(ramp[1]['soffit'], s), f"قاع بلاطة {ramp[0]} عند المحطة {s/1000:.2f}م", 1.0)]
        else:
            tops = self.top_profile(c)
        end = sum(t * f for t, _, f in tops)
        prof = self.base_profile(c)
        H = sum(f * (end - b) for b, _, f in prof)
        return dict(base=round(end - H, 4), end=round(end, 4), H=H, ramp=ramp[0] if ramp else None,
                    tops=tops, footings=prof)

    def match(self, cols, sizes):
        """يربط كل عمود في قائمة الريبو (sn, mark, x, y) — نقطة اسم العمود — بمستطيله المرسوم:
        أقرب مستطيل بنفس مقاس الماركة (من الجدول)، بأولوية الأقرب على مستوى المسقط كله."""
        CX, CY = PLAN_ORIGIN['COL']
        pairs = []
        for i, (sn, m, x, y) in enumerate(cols):
            wh = sizes.get(m)
            if not wh: continue
            dims = tuple(sorted(wh))
            for j, r in enumerate(self.rects):
                if tuple(sorted((round(r['x1'] - r['x0']), round(r['y1'] - r['y0'])))) == dims:
                    pairs.append((math.hypot(x - CX - r['cx'], y - CY - r['cy']), i, j))
        pairs.sort(); ui, uj, out = set(), set(), {}
        for d, i, j in pairs:
            if i in ui or j in uj or d > 2500: continue
            ui.add(i); uj.add(j); out[i] = self.rects[j]
        return out   # {index في cols: مستطيل}

    def starter_overlap(self):
        """مساحة الأعمدة الداخلة في شريط بادئ كل رمب (م²) — تُخصَم من البادئ عشان ماتتحسبش مرتين."""
        out = {}
        for name, R in RAMP.items():
            yw0, yw1 = R['y_start'] - R['wall_t'], R['y_start']; ov = 0.0
            for c in self.rects:
                ox = max(0, min(c['x1'], R['x1']) - max(c['x0'], R['x0']))
                oy = max(0, min(c['y1'], yw1) - max(c['y0'], yw0))
                ov += ox * oy / 1e6
            out[name] = ov
        return out
