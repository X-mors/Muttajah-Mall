# -*- coding: utf-8 -*-
"""
لوحات مراجعة بندَي الردم والعزل — على نسخة من اللوحة نفسها (فوق مسقط RAFT CONCRETE DIMENSIONS) + صورة PNG.
  • الردم: حدود الردم (الوش الداخلي للجدار) + مناطق وش اللبشة ملوّنة بارتفاع الردم + العناصر المخصومة مرقّمة
    بنفس أرقام الإكسل + البنود الناقصة (حفر الصرف/الأسانسير) بخط متقطّع.
  • العزل: الأسطح الأفقية المعزولة ملوّنة + كل وش رأسي معزول مرسوم خط على حافته بلون نوعه + مساحة كل عنصر.
الاستخدام المباشر: python foundation_review.py   (بيعمل اللوحتين؛ نفس اللي بيعمله سكريبتا الحصر)
"""
import os, sys, math
import ezdxf
import column_exact as CX

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "output")
RX, RY = CX.PLAN_ORIGIN['RAFT']
TOP_ACI = {-8.45: 151, -8.15: 4, -7.85: 3, -7.75: 2, -7.55: 30, -7.35: 1}       # لون كل منسوب وش
TOP_HEX = {-8.45: "#bfe3ff", -8.15: "#9ad1d4", -7.85: "#b7e4a8", -7.75: "#fff2a8", -7.55: "#ffc98b", -7.35: "#f4a3a3"}
KIND_ACI = {'footing': 5, 'beam': 140, 'column': 1, 'core': 6, 'tank': 4, 'starter': 30, 'perim': 3}
KIND_HEX = {'footing': "#1565c0", 'beam': "#00838f", 'column': "#c62828", 'core': "#8e24aa", 'tank': "#00897b",
            'starter': "#ef6c00", 'perim': "#2e7d32"}


def arabic(s):
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(s))
    except Exception:
        return s


def _polys(g):
    return [g] if g.geom_type == 'Polygon' else [p for p in getattr(g, 'geoms', []) if p.geom_type == 'Polygon']


def _A(x, y):
    return (x + RX, y + RY)


def _layer(doc, name, color):
    if name not in doc.layers:
        doc.layers.add(name, color=color)


def _hatch(msp, g, layer, aci, transp=0.55):
    for p in _polys(g):
        if p.area < 1e4: continue
        h = msp.add_hatch(color=aci, dxfattribs={'layer': layer})
        h.paths.add_polyline_path([_A(*c) for c in list(p.exterior.coords)[:-1]], is_closed=True,
                                  flags=ezdxf.const.BOUNDARY_PATH_EXTERNAL)
        for r in p.interiors:
            h.paths.add_polyline_path([_A(*c) for c in list(r.coords)[:-1]], is_closed=True,
                                      flags=ezdxf.const.BOUNDARY_PATH_OUTERMOST)
        try: h.transparency = transp
        except Exception: pass


def _outline(msp, g, layer, aci, lw=50, dashed=False):
    for p in _polys(g):
        for ring in [p.exterior] + list(p.interiors):
            e = msp.add_lwpolyline([_A(*c) for c in ring.coords], close=True,
                                   dxfattribs={'layer': layer, 'color': aci, 'lineweight': lw})
            if dashed: e.dxf.linetype = 'DASHED' if 'DASHED' in msp.doc.linetypes else 'CONTINUOUS'


def _text(msp, s, x, y, layer, aci, h=220):
    t = msp.add_text(s, height=h, dxfattribs={'layer': layer, 'color': aci})
    t.set_placement(_A(x, y), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)


def _title(msp, M, layer, lines):
    x0, y0, x1, y1 = M.D.bounds
    for i, s in enumerate(lines):
        _text(msp, s, (x0 + x1) / 2, y1 + 3500 - i * 900, layer, 1 if i == 0 else 7, h=650 if i == 0 else 380)


def _save(doc, path, dwg=True):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    doc.saveas(path); out = [path]
    if dwg:
        try:
            import takeoff
            d = takeoff.to_dwg(path)
            if d: out.append(d)
        except Exception as e:
            print("تعذّر تحويل DWG:", e)
    return out


# ═══════════════════════════════════════════════════════════════════ الردم
def backfill_dxf(doc, M, B, pend, path):
    msp = doc.modelspace()
    for n, c in (("CHK-FILL-ZONES", 2), ("CHK-FILL-DEDUCT", 8), ("CHK-FILL-BOUNDARY", 1), ("CHK-FILL-TEXT", 7), ("CHK-PENDING", 6)):
        _layer(doc, n, c)
    for z in B['zones']:
        _hatch(msp, z['region'], "CHK-FILL-ZONES", TOP_ACI.get(round(z['top'], 2), 8))
    for i, o in enumerate(B['obs'], 1):
        _hatch(msp, o['poly'], "CHK-FILL-DEDUCT", 8, transp=0.2)
        _outline(msp, o['poly'], "CHK-FILL-DEDUCT", 250, lw=30)
        c = o['poly'].centroid
        _text(msp, f"{i}", c.x, c.y, "CHK-FILL-TEXT", 1, h=180 if o['kind'] == 'column' else 300)
    _outline(msp, M.D, "CHK-FILL-BOUNDARY", 1, lw=100)
    for z in B['gross_rows'][1:]:
        c = z['region'].centroid
        _text(msp, f"وش {z['top']:+.2f} | ردم {z['h']:.2f}م | {z['A']:.1f}م²", c.x, c.y - 450, "CHK-FILL-TEXT", 7, h=200)
    x0, y0, x1, y1 = M.D.bounds
    _text(msp, f"المات ‑8.45 | ردم 1.10م", x0 + 9000, y0 + 2500, "CHK-FILL-TEXT", 7, h=300)
    for p in M.pits:
        _outline(msp, p['outer'], "CHK-PENDING", 6, lw=50, dashed=True)
        c = p['outer'].centroid
        _text(msp, "حفرة صرف - عمقها مش في اللوحة", c.x, c.y + 1100, "CHK-PENDING", 6, h=180)
    _title(msp, M, "CHK-FILL-TEXT", [
        f"مراجعة الردم الداخلي — منسوب الردم {M.FILL:+.2f} — صافي {B['net']:.2f} م³",
        f"حدود الردم: الوش الداخلي للجدار {M.D_dims[0]:.3f} × {M.D_dims[1]:.3f} م (أحمر). الألوان = وش اللبشة. الرمادي المرقّم = المخصوم (نفس أرقام الإكسل)."])
    return _save(doc, path)


def backfill_png(M, B, path):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon as PP
    fig, ax = plt.subplots(figsize=(22, 19))
    for z in B['zones']:
        for p in _polys(z['region']):
            ax.add_patch(PP([(x / 1000, y / 1000) for x, y in p.exterior.coords], fc=TOP_HEX.get(round(z['top'], 2), '#ddd'),
                            ec='#666', lw=0.4))
    for i, o in enumerate(B['obs'], 1):
        for p in _polys(o['poly']):
            ax.add_patch(PP([(x / 1000, y / 1000) for x, y in p.exterior.coords], fc='#9e9e9e', ec='#212121', lw=0.6))
            for r in p.interiors:
                ax.add_patch(PP([(x / 1000, y / 1000) for x, y in r.coords], fc=TOP_HEX[-7.75], ec='#212121', lw=0.6))
        c = o['poly'].centroid
        ax.text(c.x / 1000, c.y / 1000, str(i), fontsize=6 if o['kind'] == 'column' else 9, ha='center', va='center',
                color='#b71c1c', weight='bold')
    for p in M.pits:
        xs, ys = p['outer'].exterior.xy
        ax.plot([v / 1000 for v in xs], [v / 1000 for v in ys], ls='--', color='#6a1b9a', lw=1.5)
    xs, ys = M.D.exterior.xy
    ax.plot([v / 1000 for v in xs], [v / 1000 for v in ys], color='#d50000', lw=3)
    for z in B['gross_rows'][1:]:
        c = z['region'].centroid
        ax.text(c.x / 1000, c.y / 1000 - 0.6, f"{z['top']:+.2f}\nh={z['h']:.2f}", fontsize=8, ha='center', va='top')
    from matplotlib.patches import Patch
    hand = [Patch(fc=v, ec='#666', label=f"{k:+.2f} → h={M.FILL-k:.2f} m") for k, v in sorted(TOP_HEX.items())]
    hand += [Patch(fc='#9e9e9e', ec='#212121', label=arabic("مخصوم (مرقّم زي الإكسل)"))]
    ax.legend(handles=hand, loc='upper left', bbox_to_anchor=(1.0, 1.0), fontsize=11, title=arabic("وش اللبشة → ارتفاع الردم"))
    ax.set_aspect('equal'); ax.autoscale_view(); ax.grid(True, ls=':', alpha=0.4)
    ax.set_title(arabic(f"مراجعة الردم الداخلي — منسوب الردم {M.FILL:+.2f} — الصافي {B['net']:.2f} م³ (+هدر 5٪ = {B['net']*1.05:.2f})"),
                 fontsize=16, weight='bold')
    ax.set_xlabel(arabic("X م من المحور 01")); ax.set_ylabel(arabic("Y م من المحور A"))
    fig.tight_layout(); os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(path, dpi=110, facecolor='white'); plt.close(fig)
    return path


# ═══════════════════════════════════════════════════════════════════ العزل
def _segs(I):
    """(النوع، الاسم، القطع، المساحة) لكل وش رأسي معزول."""
    out = [('footing' if s['kind'] == 'footing' else 'beam', s['name'], s['segs'], s['A']) for s in I['sides']]
    out += [(v['kind'], v['name'], v['segs'], v['A']) for v in I['vert']]
    out += [('perim', p['name'], p['segs'], p['A']) for p in I['perim']]
    return out


def insulation_dxf(doc, M, I, path):
    msp = doc.modelspace()
    for n, c in (("CHK-INS-HORIZ", 3), ("CHK-INS-VERT", 1), ("CHK-INS-TEXT", 7), ("CHK-PENDING", 6)):
        _layer(doc, n, c)
    for h in I['horiz']:
        _hatch(msp, h['region'], "CHK-INS-HORIZ", TOP_ACI.get(round(h['top'], 2), 8), transp=0.65)
    for kind, name, segs, A in _segs(I):
        for (x0, y0, x1, y1, nx, ny, hh) in segs:
            off = 60
            msp.add_lwpolyline([_A(x0 + nx * off, y0 + ny * off), _A(x1 + nx * off, y1 + ny * off)],
                               dxfattribs={'layer': "CHK-INS-VERT", 'color': KIND_ACI[kind], 'lineweight': 70})
    for v in I['vert']:
        if v['A'] <= 0: continue
        c = v['ref']['poly'].centroid if v['ref'] and 'poly' in v['ref'] else None
        if c is None:
            o = [o for o in M.obs if o['name'] == v['name']][0]; c = o['poly'].centroid
        _text(msp, f"{v['A']:.2f}", c.x, c.y, "CHK-INS-TEXT", KIND_ACI[v['kind']], h=160)
    for s in I['sides']:
        if s['A'] <= 0: continue
        ref = (M.footings if s['kind'] == 'footing' else M.beams)
        it = [r for r in ref if r['name'] == s['name'] and abs(r['top'] - s['top']) < 1e-6]
        c = [r for r in it if f"({r['poly'].centroid.x/1000:.2f}, {r['poly'].centroid.y/1000:.2f})" == s['loc']]
        c = (c or it)[0]['poly'].centroid
        _text(msp, f"جوانب {s['A']:.2f}م²", c.x, c.y - 350, "CHK-INS-TEXT", KIND_ACI[s['kind']], h=170)
    for p in M.pits:
        _outline(msp, p['outer'], "CHK-PENDING", 6, lw=50, dashed=True)
    _title(msp, M, "CHK-INS-TEXT", [
        f"مراجعة العزل بالدهان — لحد منسوب الردم {M.FILL:+.2f} — صافي {I['total']:.2f} م²",
        "الملوّن = أسطح أفقية معزولة. الخطوط = أوش رأسية معزولة: أزرق جوانب قواعد، سماوي جوانب سملات، أحمر رقاب أعمدة، بنفسجي أكوار، أخضر الجدار المحيط، تركواز الخزان (برّه بس)، برتقالي بادئ الرمب."])
    return _save(doc, path)


def insulation_png(M, I, path):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon as PP, Patch
    from matplotlib.lines import Line2D
    fig, ax = plt.subplots(figsize=(22, 19))
    for h in I['horiz']:
        for p in _polys(h['region']):
            ax.add_patch(PP([(x / 1000, y / 1000) for x, y in p.exterior.coords], fc=TOP_HEX.get(round(h['top'], 2), '#ddd'),
                            ec='none', alpha=0.8))
            for r in p.interiors:
                ax.add_patch(PP([(x / 1000, y / 1000) for x, y in r.coords], fc='white', ec='none'))
    for kind, name, segs, A in _segs(I):
        for (x0, y0, x1, y1, nx, ny, hh) in segs:
            ax.plot([x0 / 1000, x1 / 1000], [y0 / 1000, y1 / 1000], color=KIND_HEX[kind], lw=2.2, solid_capstyle='butt')
    for o in M.obs:
        if o['kind'] == 'tank':
            xs, ys = o['poly'].exterior.xy
            ax.fill([v / 1000 for v in xs], [v / 1000 for v in ys], fc='#e0e0e0', ec='none')
            c = o['poly'].centroid
            ax.text(c.x / 1000, c.y / 1000, arabic("الخزان — جوّه مش بيتعزل"), ha='center', fontsize=10)
    for p in M.pits:
        xs, ys = p['outer'].exterior.xy
        ax.plot([v / 1000 for v in xs], [v / 1000 for v in ys], ls='--', color='#6a1b9a', lw=1.5)
    t = I['totals']
    lab = {'footing': f"جوانب القواعد {t['s_foot']:.1f}", 'beam': f"جوانب السملات {t['s_beam']:.1f}",
           'column': f"رقاب الأعمدة {t['col']:.1f}", 'core': f"الأكوار {t['core']:.1f}", 'perim': f"الجدار المحيط {t['perim']:.1f}",
           'tank': f"الخزان (برّه) {t['tank']:.1f}", 'starter': f"بادئ الرمب {t['starter']:.1f}"}
    hand = [Line2D([0], [0], color=KIND_HEX[k], lw=4, label=arabic(v + " م²")) for k, v in lab.items()]
    hand += [Patch(fc=v, label=f"{arabic('ظهر')} {k:+.2f}") for k, v in sorted(TOP_HEX.items())]
    ax.legend(handles=hand, loc='upper left', bbox_to_anchor=(1.0, 1.0), fontsize=11)
    ax.set_aspect('equal'); ax.autoscale_view(); ax.grid(True, ls=':', alpha=0.4)
    ax.set_title(arabic(f"مراجعة العزل بالدهان — لحد منسوب الردم {M.FILL:+.2f} — الصافي {I['total']:.2f} م² (+هدر 5٪ = {I['total']*1.05:.2f})"),
                 fontsize=16, weight='bold')
    fig.tight_layout(); os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(path, dpi=110, facecolor='white'); plt.close(fig)
    return path


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    import backfill_takeoff, insulation_takeoff
    backfill_takeoff.main(); insulation_takeoff.main()
