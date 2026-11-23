# -*- coding: utf-8 -*-
"""
لوحات مراجعة بندَي الردم والعزل — صورة PNG بالعربي وصورة بالإنجليزي + نسخة DXF/DWG على اللوحة نفسها.
كل عنصر عليه رقمه من substructure_calc.elements() — نفس الرقم في عمود «رقم على اللوحة» في الإكسل.

ملاحظة الخط العربي: matplotlib 3.11 بيشكّل العربي بنفسه → النص العربي بيتكتب زي ما هو بخط Tahoma
(من غير arabic_reshaper/bidi — دول كانوا بيقلبوا الحروف ويلخبطوا الصورة).
في الـDXF الكتابة أرقام وإنجليزي بس (خطوط الأوتوكاد SHX مش بتشكّل العربي).
"""
import os, sys
import ezdxf
import column_exact as CX

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "output")
RX, RY = CX.PLAN_ORIGIN['RAFT']
FONT = "Tahoma"
TOP_HEX = {-8.45: "#cfe8fc", -8.15: "#9ad1d4", -7.85: "#b7e4a8", -7.75: "#fff2a8", -7.55: "#ffc98b", -7.35: "#f4a3a3"}
TOP_ACI = {-8.45: 151, -8.15: 4, -7.85: 3, -7.75: 2, -7.55: 30, -7.35: 1}
KIND_HEX = {'footing': "#1565c0", 'beam': "#00838f", 'column': "#c62828", 'core': "#8e24aa", 'tank': "#00695c",
            'starter': "#ef6c00", 'perim': "#2e7d32", 'lift': "#d81b60", 'sump': "#d81b60", 'wedge': "#6d4c41", 'mat': "#1565c0"}
KIND_ACI = {'footing': 5, 'beam': 140, 'column': 1, 'core': 6, 'tank': 4, 'starter': 30, 'perim': 3, 'lift': 6,
            'sump': 6, 'wedge': 34, 'mat': 5}

T = {  # نصوص الصور
    'ar': dict(
        fill_title="حصر الردم الداخلي — البدروم السفلي",
        fill_sub="منسوب الردم {F} (وش قاعدة الـ1.50م)  |  الصافي {net} م³  |  بالهالك 5٪ {waste} م³",
        ins_title="حصر العزل بالدهان — البدروم السفلي",
        ins_sub="لحد منسوب الردم {F} بالظبط  |  الصافي {net} م²  |  بالهالك 5٪ {waste} م²",
        lvl="وش {t}  ←  ارتفاع الردم {h} م", lvl_ins="ظهر {t}", ded="مخصوم من الردم (العنصر برقمه)",
        nofill="جوّه مش بيتردم", bound="حدود الردم: الوش الداخلي للجدار",
        num="الأرقام = رقم العنصر في شيت الإكسل", x="X (م) من المحور 01", y="Y (م) من المحور A",
        k=dict(footing="جوانب القواعد", beam="جوانب السملات", column="رقاب الأعمدة", core="الأكوار (برّه وجوّه)",
               perim="الوش الداخلي للجدار المحيط", tank="الخزان (برّه بس)", starter="بادئا الرامب", lift="حفر الأسانسير",
               sump="حفر الصرف", wedge="قاع بلاطة رامب 03"),
        f=dict(beam="السملات", column="رقاب الأعمدة", core="الأكوار", tank="الخزان", starter="بادئا الرامب",
               lift="داخل كوري الأسانسير", sump="حفر الصرف", wedge="بلاطة رامب 03"),
        tank="الخزان — جوّه مش بيتعزل ولا بيتردم", m2="م²", m3="م³", gross="القائم", net="الصافي",
        waste="بالهالك 5٪", horiz="الأفقي (ظهر المات والقواعد والسملات)", total="الإجمالي",
    ),
    'en': dict(
        fill_title="Internal backfill — Lower basement",
        fill_sub="Fill level {F} (top of the 1.50 m footing)  |  Net {net} m³  |  +5% waste {waste} m³",
        ins_title="Bitumen-paint insulation — Lower basement",
        ins_sub="Exactly up to fill level {F}  |  Net {net} m²  |  +5% waste {waste} m²",
        lvl="Top {t}  →  fill height {h} m", lvl_ins="Top {t}", ded="Deducted from fill (element number)",
        nofill="not filled inside", bound="Fill boundary: inner face of perimeter wall",
        num="Numbers = element number in the Excel sheet", x="X (m) from axis 01", y="Y (m) from axis A",
        k=dict(footing="Footing sides", beam="Tie-beam sides", column="Column necks", core="Cores (outside + inside)",
               perim="Perimeter wall inner face", tank="Tank (outside only)", starter="Ramp starters", lift="Lift pits",
               sump="Sump pits", wedge="Ramp 03 slab soffit"),
        f=dict(beam="Tie beams", column="Column necks", core="Cores", tank="Tank", starter="Ramp starters",
               lift="Inside lift cores", sump="Sump pits", wedge="Ramp 03 slab"),
        tank="Tank — inside not insulated, not filled", m2="m²", m3="m³", gross="Gross", net="Net",
        waste="+5% waste", horiz="Horizontal tops (raft, footings, tie beams)", total="Total",
    ),
}


def _polys(g):
    return [g] if g.geom_type == 'Polygon' else [p for p in getattr(g, 'geoms', []) if p.geom_type == 'Polygon']


def _fig():
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams['font.family'] = FONT
    plt.rcParams['axes.unicode_minus'] = False
    fig = plt.figure(figsize=(26, 19))
    ax = fig.add_axes([0.035, 0.07, 0.70, 0.83])
    return plt, fig, ax


def _patch(ax, g, fc, ec='none', lw=0.4, z=1, alpha=1.0):
    """مضلّع بفتحات حقيقية (الفتحة شفافة — اللي تحتها يبان)."""
    from matplotlib.path import Path
    from matplotlib.patches import PathPatch
    from shapely.geometry.polygon import orient
    for p in _polys(g):
        p = orient(p, 1.0); verts = []; codes = []
        for ring in [p.exterior] + list(p.interiors):
            c = [(x / 1000, y / 1000) for x, y in ring.coords]
            verts += c; codes += [Path.MOVETO] + [Path.LINETO] * (len(c) - 2) + [Path.CLOSEPOLY]
        ax.add_patch(PathPatch(Path(verts, codes), fc=fc, ec=ec, lw=lw, zorder=z, alpha=alpha))


def _num(ax, e, small=False, color='#b71c1c'):
    x, y = e['anchor']
    ax.text(x / 1000, y / 1000, str(e['no']), fontsize=6.5 if small else 9, ha='center', va='center', color=color,
            weight='bold', zorder=20, bbox=dict(boxstyle='round,pad=0.15', fc='white', ec=color, lw=0.6, alpha=0.9))


def _frame(ax, M, title, sub, L, lw=2.5, ls='-'):
    xs, ys = M.D.exterior.xy
    ax.plot([v / 1000 for v in xs], [v / 1000 for v in ys], color='#d50000', lw=lw, ls=ls, zorder=15)
    ax.set_aspect('equal'); ax.grid(True, ls=':', alpha=0.35)
    x0, y0, x1, y1 = M.D.bounds
    ax.set_xlim(x0 / 1000 - 4, x1 / 1000 + 4); ax.set_ylim(y0 / 1000 - 3, y1 / 1000 + 3)
    ax.set_xlabel(L['x'], fontsize=11); ax.set_ylabel(L['y'], fontsize=11)
    fig = ax.figure
    fig.text(0.39, 0.965, title, ha='center', fontsize=22, weight='bold')
    fig.text(0.39, 0.932, sub, ha='center', fontsize=14, color='#333')


def _fmt(v, n=2):
    return f"{v:,.{n}f}"


def _box(fig, lines, y, lang):
    ha = 'right' if lang == 'ar' else 'left'
    x = 0.985 if lang == 'ar' else 0.745
    fig.text(x, y, "\n".join(lines), fontsize=13, va='top', ha=ha, linespacing=1.6,
             bbox=dict(boxstyle='round,pad=0.6', fc='#f7f7f7', ec='#999'))


# ═══════════════════════════════════════════════════════════════════ الردم
def backfill_png(M, B, E, lang, path):
    L = T[lang]; plt, fig, ax = _fig()
    from matplotlib.patches import Patch
    for z in B['zones']:
        _patch(ax, z['region'], TOP_HEX.get(round(z['top'], 2), '#ddd'), ec='#777', lw=0.4)
    for e in E:
        if e['kind'] in ('column', 'core', 'tank', 'starter', 'lift', 'sump', 'wedge'):
            fc = '#ffd6e7' if e['kind'] in ('lift', 'sump') else ('#e0c9b8' if e['kind'] == 'wedge' else '#9e9e9e')
            _patch(ax, e['poly'], fc, ec='#212121', lw=0.6, z=5, alpha=0.9 if e['kind'] != 'wedge' else 0.7)
    for e in E:
        if e['kind'] in ('mat', 'footing', 'beam', 'column', 'core', 'tank', 'starter', 'lift', 'sump', 'wedge'):
            _num(ax, e, small=e['kind'] in ('column', 'beam'))
        if e['kind'] in ('lift', 'sump'):
            x, y = e['anchor']; ax.text(x / 1000, y / 1000 - 0.9, L['nofill'], fontsize=8, ha='center', color='#ad1457', zorder=21)
    _frame(ax, M, L['fill_title'], L['fill_sub'].format(F=f"{M.FILL:+.2f}", net=_fmt(B['net']), waste=_fmt(B['net'] * 1.05)), L)
    hand = [Patch(fc=v, ec='#777', label=L['lvl'].format(t=f"{k:+.2f}", h=f"{M.FILL-k:.2f}")) for k, v in sorted(TOP_HEX.items())]
    hand += [Patch(fc='#9e9e9e', ec='#212121', label=L['ded']), Patch(fc='#ffd6e7', ec='#212121', label=L['f']['lift'] + " + " + L['f']['sump'] + " — " + L['nofill']),
             Patch(fc='white', ec='#d50000', lw=2, label=L['bound'])]
    ax.legend(handles=hand, loc='upper left', bbox_to_anchor=(1.01, 1.0), fontsize=13, frameon=True)
    bk = B['by_kind']
    lines = [f"{L['gross']}  {_fmt(B['gross'])} {L['m3']}"]
    lines += [f"−  {L['f'][k]}  {_fmt(bk[k])}" for k in ('beam', 'column', 'core', 'tank', 'starter', 'lift', 'sump', 'wedge')]
    lines += [f"{L['net']}  {_fmt(B['net'])} {L['m3']}", f"{L['waste']}  {_fmt(B['net']*1.05)} {L['m3']}", "", L['num']]
    _box(fig, lines, 0.50, lang)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(path, dpi=130, facecolor='white'); plt.close(fig)
    return path


# ═══════════════════════════════════════════════════════════════════ العزل
def insulation_png(M, I, E, lang, path):
    L = T[lang]; plt, fig, ax = _fig()
    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D
    for h in I['horiz']:
        _patch(ax, h['region'], TOP_HEX.get(round(h['top'], 2), '#ddd'), alpha=0.85)
    for q in I['pits']:
        _patch(ax, q['poly'], '#f8bbd0', ec=KIND_HEX[q['kind']], lw=1.2, z=4)
    tk = [e for e in E if e['kind'] == 'tank'][0]
    _patch(ax, tk['poly'], '#e0e0e0', z=3)
    x, y = tk['anchor']; ax.text(x / 1000, y / 1000 - 1.2, L['tank'], ha='center', fontsize=10, zorder=21)
    segs = [(s['kind'], s['segs']) for s in I['sides']] + [(v['kind'], v['segs']) for v in I['vert']] + [('perim', p['segs']) for p in I['perim']]
    for kind, ss in segs:
        off = 280 if kind == 'perim' else 0          # الجدار المحيط: الخط جوّه الحدود عشان يبان
        for (x0, y0, x1, y1, nx, ny, hh) in ss:
            ax.plot([(x0 + nx * off) / 1000, (x1 + nx * off) / 1000], [(y0 + ny * off) / 1000, (y1 + ny * off) / 1000],
                    color=KIND_HEX[kind], lw=3.2 if kind == 'perim' else 2.4, solid_capstyle='butt', zorder=16 if kind == 'perim' else 6)
    we = [e for e in E if e['kind'] == 'wedge'][0]
    _patch(ax, we['poly'], '#d7ccc8', ec=KIND_HEX['wedge'], lw=1.0, z=4, alpha=0.8)
    for e in E:
        _num(ax, e, small=e['kind'] in ('column', 'beam'), color='#1a237e' if e['kind'] in ('mat', 'footing', 'beam') else '#b71c1c')
    _frame(ax, M, L['ins_title'], L['ins_sub'].format(F=f"{M.FILL:+.2f}", net=_fmt(I['total']), waste=_fmt(I['total'] * 1.05)), L, lw=1.0, ls='--')
    t = I['totals']
    val = dict(footing=t['s_foot'], beam=t['s_beam'], column=t['col'], core=t['core'], perim=t['perim'], tank=t['tank'],
               starter=t['starter'], lift=sum(q['A_bot'] + q['A_side'] for q in I['pits'] if q['kind'] == 'lift'),
               sump=sum(q['A_bot'] + q['A_side'] for q in I['pits'] if q['kind'] == 'sump'), wedge=t['wedge'])
    hand = [Line2D([0], [0], color=KIND_HEX[k], lw=5, label=f"{L['k'][k]}  {_fmt(v)} {L['m2']}") for k, v in val.items()]
    hand += [Patch(fc=v, label=L['lvl_ins'].format(t=f"{k:+.2f}")) for k, v in sorted(TOP_HEX.items())]
    ax.legend(handles=hand, loc='upper left', bbox_to_anchor=(1.01, 1.0), fontsize=12.5, frameon=True)
    hz = t['h_mat'] + t['h_foot'] + t['h_beam']
    lines = [f"{L['horiz']}  {_fmt(hz)} {L['m2']}", f"{L['total']}  {_fmt(I['total'])} {L['m2']}",
             f"{L['waste']}  {_fmt(I['total']*1.05)} {L['m2']}", "", L['num']]
    _box(fig, lines, 0.33, lang)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(path, dpi=130, facecolor='white'); plt.close(fig)
    return path


# ═══════════════════════════════════════════════════════════════════ DXF (أرقام + إنجليزي)
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


def _text(msp, s, x, y, layer, aci, h=220):
    t = msp.add_text(s, height=h, dxfattribs={'layer': layer, 'color': aci})
    t.set_placement(_A(x, y), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)


def review_dxf(doc, M, E, item, data, path):
    msp = doc.modelspace(); P = f"CHK-{item.upper()}"
    for n, c in ((P + "-AREAS", 2), (P + "-ELEMENTS", 8), (P + "-FACES", 1), (P + "-NUMBERS", 1), (P + "-BOUNDARY", 1)):
        _layer(doc, n, c)
    if item == 'fill':
        for z in data['zones']:
            _hatch(msp, z['region'], P + "-AREAS", TOP_ACI.get(round(z['top'], 2), 8))
        for e in E:
            if e['kind'] in ('column', 'core', 'tank', 'starter', 'lift', 'sump', 'wedge'):
                _hatch(msp, e['poly'], P + "-ELEMENTS", 8 if e['kind'] not in ('lift', 'sump') else 6, transp=0.2)
        show = ('mat', 'footing', 'beam', 'column', 'core', 'tank', 'starter', 'lift', 'sump', 'wedge')
        head = f"INTERNAL BACKFILL - fill level {M.FILL:+.2f} - net {data['net']:.2f} m3 (+5% {data['net']*1.05:.2f})"
    else:
        for h in data['horiz']:
            _hatch(msp, h['region'], P + "-AREAS", TOP_ACI.get(round(h['top'], 2), 8), transp=0.65)
        segs = [(s['kind'], s['segs']) for s in data['sides']] + [(v['kind'], v['segs']) for v in data['vert']] + [('perim', p['segs']) for p in data['perim']]
        for kind, ss in segs:
            for (x0, y0, x1, y1, nx, ny, hh) in ss:
                msp.add_lwpolyline([_A(x0 + nx * 60, y0 + ny * 60), _A(x1 + nx * 60, y1 + ny * 60)],
                                   dxfattribs={'layer': P + "-FACES", 'color': KIND_ACI[kind], 'lineweight': 70})
        for q in data['pits']:
            _hatch(msp, q['poly'], P + "-ELEMENTS", 6, transp=0.3)
        show = tuple(KIND_ACI)
        head = f"BITUMEN-PAINT INSULATION - up to fill level {M.FILL:+.2f} - net {data['total']:.2f} m2 (+5% {data['total']*1.05:.2f})"
    for e in E:
        if e['kind'] in show:
            x, y = e['anchor']
            _text(msp, str(e['no']), x, y, P + "-NUMBERS", 1, h=170 if e['kind'] in ('column', 'beam') else 320)
    msp.add_lwpolyline([_A(*c) for c in M.D.exterior.coords], close=True,
                       dxfattribs={'layer': P + "-BOUNDARY", 'color': 1, 'lineweight': 100})
    x0, y0, x1, y1 = M.D.bounds
    _text(msp, head, (x0 + x1) / 2, y1 + 3600, P + "-NUMBERS", 1, h=650)
    _text(msp, "Numbers = element number in the Excel sheet (same as the PNG review images)", (x0 + x1) / 2, y1 + 2600, P + "-NUMBERS", 7, h=380)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    doc.saveas(path); out = [path]
    try:
        import takeoff
        d = takeoff.to_dwg(path)
        if d: out.append(d)
    except Exception as e:
        print("تعذّر تحويل DWG:", e)
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    import backfill_takeoff, insulation_takeoff
    backfill_takeoff.main(); insulation_takeoff.main()
