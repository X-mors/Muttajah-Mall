# -*- coding: utf-8 -*-
"""
حصر أعداد أسياخ التسليح الإضافي لبلاطة لوحة واحدة من ملف الـ DXF.
Rebar COUNT takeoff for one plan drawing inside the STR-MOTTAGAH DXF.

الاستخدام / usage:
    python takeoff.py "ADDITIONAL TOP REINFORCEMENT PLAN FOR LOWER BASEMENT CEILING"
    python takeoff.py "LOWER BASEMENT CEILING" --top          # فلترة إضافية بالكلمة
    python takeoff.py "<title>" --dwg                          # وأنتج نسخة DWG لملف المراجعة
    python takeoff.py "<title>" --bbox -752000 -690000 474000 524000   # تجاوز الحدود يدوياً

يخرج ملفين في مجلد output:
  - <title>.xlsx            : الأعداد حسب (الطول × القطر) + ورقة تفاصيل
  - <title> - review.dxf    : نسخة من اللوحة عليها دوائر الحصر (طبقة CHECK-COUNT)

القواعد المطبّقة (راجع ذاكرة المشروع):
  * العدد = ceil(عرض التوزيع ÷ التباعد)  — تقريب لأعلى، بلا +1.
  * العرض = أقرب DIMENSION أحمر عمودي على السيخ يقع الكولّ ضمن مداه.
  * الأسياخ الحافّية تأخذ البُعد الكامل (~53335) لذا الحدّ الأقصى للعرض = 60000.
  * تُستبعد السلالم: كولّ بلا L= وبقرب علامة "with stair".
  * الأطوال L= تُطابَق 1-إلى-1 بالأقرب.
"""
import argparse, os, re, math, collections, tempfile, shutil, subprocess
import ezdxf
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# ------------------------- إعدادات ثابتة -------------------------
DEFAULT_DXF = r"D:\مشروع الحصر\2026-09-22-STR-MOTTAGAH.dxf"
DEFAULT_OUT = r"D:\مشروع الحصر\output"
ODA_EXE     = r"C:\Program Files\ODA\ODAFileConverter 27.1.0\ODAFileConverter.exe"

CALLOUT_RE  = re.compile(r"^T(\d{1,2})-(\d{2,4})-([TB])(?:-ADD)?$", re.I)
LEN_RE      = re.compile(r"^L\s*=\s*(\d+)$", re.I)
TITLE_HINTS = ("PLAN FOR", "REINFORCEMENT PLAN", "RAMPS REINFORCEMENT")
DIAS        = [12, 16, 18]
DIM_MIN, DIM_MAX = 300, 60000     # حدود عرض معقولة (تشمل البُعد الكامل ~53335)
L_MATCH_R   = 1800                # نصف قطر مطابقة L= بالكولّ
STAIR_DX, STAIR_DY = 4000, 9000   # نطاق قرب علامة السلّم
PERP_MAX    = 4000                # أقصى بُعد عمودي مقبول للربط
PERP_CONF   = 2500                # فوقه = ثقة منخفضة (سماوي) — للطريقة الاحتياطية فقط
WIDTH_ROUND = 100                 # تدوير العرض لأقرب
# علامة التقاطع: دائرة برتقالية صغيرة عند نقطة تقاطع السيخ ببُعده (ربط دقيق)
CIRCLE_COLOR = 30                 # برتقالي ACI
CIRCLE_MAXR  = 400                # نصف قطر العلامة صغير (~75)
CIRCLE_ONBAR = 500                # تحمّل انحراف علامة الكولّ عن خط السيخ (العلامة قد تبعد ~350)
CIRCLE_ONDIM = 400                # العلامة يجب أن تقع على خط البُعد
BAR_MAXDIST  = 6000               # أقصى مسافة بين علامة الكولّ ومركز خط الحديد المطابق له

# ------------------------- أدوات مساعدة -------------------------
def text_of(e):
    try:
        t = e.plain_text() if e.dxftype() == "MTEXT" else e.dxf.text
    except Exception:
        t = getattr(e.dxf, "text", "")
    return " ".join((t or "").split())

def all_titles(msp):
    out = []
    for e in msp.query("TEXT MTEXT"):
        t = text_of(e); tu = t.upper()
        if any(h in tu for h in TITLE_HINTS):
            try:
                ip = e.dxf.insert; out.append((float(ip.x), float(ip.y), t))
            except Exception:
                pass
    return out

def find_title(titles, needle, extra=None):
    n = needle.upper(); hits = [t for t in titles if n in t[2].upper()]
    if extra:
        hits = [t for t in hits if extra.upper() in t[2].upper()]
    return hits

def plan_bbox(titles, tx, ty):
    """حدود اللوحة من الشبكة: العنوان أسفل يسار اللوحة، الخلايا ~100000×100000."""
    row = sorted([t for t in titles if abs(t[1] - ty) < 40000], key=lambda t: t[0])
    xs = [t[0] for t in row]
    i = min(range(len(row)), key=lambda k: abs(row[k][0] - tx))
    x_left = tx - 6000
    x_right = (row[i + 1][0] - 4000) if i + 1 < len(row) else (tx + 98000)
    x_right = min(x_right, tx + 98000)
    return (x_left, x_right, ty - 5000, ty + 92000)

# ------------------------- الاستخراج -------------------------
def extract(msp, box):
    xmin, xmax, ymin, ymax = box
    def inbox(x, y): return xmin <= x <= xmax and ymin <= y <= ymax
    callouts, Ls, stair_markers = [], [], []
    for e in msp.query("TEXT MTEXT"):
        t = text_of(e)
        try:
            ip = e.dxf.insert; x, y = float(ip.x), float(ip.y)
        except Exception:
            continue
        if not inbox(x, y):
            continue
        if re.search(r"stair", t, re.I):
            stair_markers.append((x, y))
        m = CALLOUT_RE.match(t)
        if m:
            callouts.append(dict(x=x, y=y, dia=int(m.group(1)), sp=int(m.group(2)),
                                 face=m.group(3).upper(),
                                 rot=round(float(getattr(e.dxf, "rotation", 0) or 0)) % 180, txt=t))
        else:
            lm = LEN_RE.match(t)
            if lm:
                Ls.append((x, y, int(lm.group(1))))
    # مطابقة L= 1-إلى-1 (الأقرب أولاً)
    pairs = []
    for ci, c in enumerate(callouts):
        for li, (lx, ly, lv) in enumerate(Ls):
            d = math.hypot(lx - c["x"], ly - c["y"])
            if d < L_MATCH_R:
                pairs.append((d, ci, li, lv))
    pairs.sort()
    usedC, usedL = {}, set()
    for d, ci, li, lv in pairs:
        if ci in usedC or li in usedL:
            continue
        usedC[ci] = lv; usedL.add(li)
    for ci, c in enumerate(callouts):
        c["L"] = usedC.get(ci)
    # السلالم
    for c in callouts:
        near = any(abs(c["x"] - mx) < STAIR_DX and abs(c["y"] - my) < STAIR_DY for (mx, my) in stair_markers)
        c["stair"] = near and (c["L"] is None)
    # الأبعاد (عرض التوزيع)
    dims = []
    for e in msp.query("DIMENSION"):
        try:
            p2 = e.dxf.defpoint2; p3 = e.dxf.defpoint3
            ax, ay, bx, by = float(p2.x), float(p2.y), float(p3.x), float(p3.y)
        except Exception:
            continue
        seg = math.hypot(bx - ax, by - ay)
        if seg == 0:
            continue
        try:
            v = e.get_measurement(); val = float(v) if isinstance(v, (int, float)) else 0
        except Exception:
            val = 0
        w = max(val, seg); mx, my = (ax + bx) / 2, (ay + by) / 2
        if not inbox(mx, my) or w < DIM_MIN or w > DIM_MAX:
            continue
        dims.append(dict(ax=ax, ay=ay, bx=bx, by=by, w=w, ux=(bx - ax) / seg, uy=(by - ay) / seg))
    # خطوط الحديد (البارات) على طبقات ST-RFT-* — نجدها بالطبقة لا باللون (T→TOP، B→BOT)
    def _med(vals):
        s = sorted(vals); n = len(s)
        return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0
    bars = {"T": [], "B": []}
    for e in msp.query("LWPOLYLINE LINE"):
        face = "T" if e.dxf.layer == "ST-RFT-TOP" else ("B" if e.dxf.layer == "ST-RFT-BOT" else None)
        if face is None:
            continue
        try:
            if e.dxftype() == "LINE":
                pts = [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]
            else:
                pts = [(p[0], p[1]) for p in e.get_points("xy")]
        except Exception:
            continue
        xs = [float(p[0]) for p in pts]; ys = [float(p[1]) for p in pts]
        cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
        if not inbox(cx, cy):
            continue
        orient = "H" if (max(xs) - min(xs)) >= (max(ys) - min(ys)) else "V"
        bars[face].append(dict(cx=cx, cy=cy, mx=_med(xs), my=_med(ys),
                               xmin=min(xs), xmax=max(xs), ymin=min(ys), ymax=max(ys), orient=orient))

    # علامات التقاطع البرتقالية (حيث تُقرأ): تُحدّد السيخ المعنيّ حين يعبر بُعدٌ مجموعةَ أسياخ
    lc = {l.dxf.name: l.dxf.color for l in msp.doc.layers}
    circles = []
    for e in msp.query("CIRCLE"):
        try:
            cx0, cy0, rr = float(e.dxf.center.x), float(e.dxf.center.y), float(e.dxf.radius)
        except Exception:
            continue
        col = e.dxf.color if e.dxf.hasattr("color") else 256
        if col == 256:
            col = lc.get(e.dxf.layer, 7)
        if inbox(cx0, cy0) and col == CIRCLE_COLOR and rr < CIRCLE_MAXR:
            circles.append((cx0, cy0))

    def circle_on_bar(bar):
        """الدائرة الواقعة على هذا السيخ تحديداً (انزياح عمودي صغير + ضمن امتداده)."""
        best = None
        for (cx0, cy0) in circles:
            if bar["orient"] == "H":
                if abs(cy0 - bar["my"]) < CIRCLE_ONBAR and bar["xmin"] - 300 <= cx0 <= bar["xmax"] + 300:
                    d = abs(cx0 - bar["cx"])
                    if best is None or d < best[0]: best = (d, cx0, cy0)
            else:
                if abs(cx0 - bar["mx"]) < CIRCLE_ONBAR and bar["ymin"] - 300 <= cy0 <= bar["ymax"] + 300:
                    d = abs(cy0 - bar["cy"])
                    if best is None or d < best[0]: best = (d, cx0, cy0)
        return best

    def dim_through(px, py, vertical):
        """البُعد العمودي المارّ عبر نقطة (px,py) وتقع النقطة ضمن مداه."""
        best = None
        for d in dims:
            if (abs(d["ux"]) < abs(d["uy"])) != vertical: continue
            if vertical:
                x = (d["ax"] + d["bx"]) / 2.0; perp = abs(px - x)
                den = d["by"] - d["ay"]; t = (py - d["ay"]) / den if den else 9
            else:
                y = (d["ay"] + d["by"]) / 2.0; perp = abs(py - y)
                den = d["bx"] - d["ax"]; t = (px - d["ax"]) / den if den else 9
            if perp >= CIRCLE_ONDIM or not (-0.02 <= t <= 1.02): continue
            if best is None or perp < best[0]: best = (perp, d["w"])
        return best

    # ربط العرض: (1) دائرة السيخ حيث تُقرأ ؛ (2) تقاطع خط الحديد بالبُعد ضمن مداه ؛ (3) أقرب بُعد للعلامة
    for c in callouts:
        barx, bary = (1.0, 0.0) if c["rot"] == 0 else (0.0, 1.0)
        w = perp = src = None
        want = "H" if c["rot"] == 0 else "V"
        cand = [b for b in bars[c["face"]] if b["orient"] == want]
        bar = min(cand, key=lambda b: math.hypot(b["cx"] - c["x"], b["cy"] - c["y"]), default=None)
        if bar and math.hypot(bar["cx"] - c["x"], bar["cy"] - c["y"]) < BAR_MAXDIST:
            cir = circle_on_bar(bar)                  # الدائرة تحدّد السيخ المعنيّ عند عبور بُعد لمجموعة
            if cir:
                b2 = dim_through(cir[1], cir[2], vertical=(c["rot"] == 0))
                if b2:
                    w, perp, src = round(b2[1] / WIDTH_ROUND) * WIDTH_ROUND, round(b2[0]), "circle"
            best = None
            if c["rot"] == 0:                         # سيخ أفقي: محوره y=bar.my، البُعد العمودي رأسي
                by = bar["my"]
                for d in dims:
                    if abs(d["ux"]) >= abs(d["uy"]):
                        continue
                    dx = (d["ax"] + d["bx"]) / 2.0
                    if not (bar["xmin"] - 300 <= dx <= bar["xmax"] + 300):
                        continue
                    den = d["by"] - d["ay"]; t = (by - d["ay"]) / den if den else 9
                    if not (-0.02 <= t <= 1.02):
                        continue
                    dist = abs(dx - c["x"])
                    if best is None or dist < best[0]:
                        best = (dist, d["w"])
            else:                                     # سيخ رأسي: محوره x=bar.mx، البُعد العمودي أفقي
                bx = bar["mx"]
                for d in dims:
                    if abs(d["ux"]) < abs(d["uy"]):
                        continue
                    dy = (d["ay"] + d["by"]) / 2.0
                    if not (bar["ymin"] - 300 <= dy <= bar["ymax"] + 300):
                        continue
                    den = d["bx"] - d["ax"]; t = (bx - d["ax"]) / den if den else 9
                    if not (-0.02 <= t <= 1.02):
                        continue
                    dist = abs(dy - c["y"])
                    if best is None or dist < best[0]:
                        best = (dist, d["w"])
            if best and w is None:
                w, perp, src = round(best[1] / WIDTH_ROUND) * WIDTH_ROUND, round(best[0]), "barline"
        if w is None:                                 # احتياطي: أقرب بُعد عمودي قرب علامة الكولّ
            best = None
            for d in dims:
                if abs(d["ux"] * barx + d["uy"] * bary) > 0.35:
                    continue
                vx, vy = d["bx"] - d["ax"], d["by"] - d["ay"]; L2 = vx * vx + vy * vy
                t = ((c["x"] - d["ax"]) * vx + (c["y"] - d["ay"]) * vy) / L2
                if not (-0.05 <= t <= 1.05):
                    continue
                px, py = d["ax"] + t * vx, d["ay"] + t * vy
                pp = math.hypot(c["x"] - px, c["y"] - py)
                if best is None or pp < best[0]:
                    best = (pp, d["w"])
            if best and best[0] < PERP_MAX:
                w, perp, src = round(best[1] / WIDTH_ROUND) * WIDTH_ROUND, round(best[0]), "heur"
            else:
                perp = round(best[0]) if best else None
        c["w"], c["perp"], c["src"] = w, perp, src
        c["count"] = math.ceil(c["w"] / c["sp"]) if c["w"] else None
    return callouts

# ------------------------- المخرجات -------------------------
def build_excel(callouts, title, path):
    slab = [c for c in callouts if not c["stair"]]
    stair = [c for c in callouts if c["stair"]]
    dias = sorted({c["dia"] for c in slab}) or [12, 16]   # أعمدة الأقطار ديناميكية (تشمل Ø10 وغيره)
    last = get_column_letter(1 + len(dias))
    piv = collections.defaultdict(lambda: {d: 0 for d in dias}); tot = {d: 0 for d in dias}
    for c in slab:
        if not c["count"]:
            continue
        Lk = c["L"] if c["L"] else "unknown"
        piv[Lk][c["dia"]] += c["count"]; tot[c["dia"]] += c["count"]
    lengths = sorted([k for k in piv if k != "unknown"]) + (["unknown"] if "unknown" in piv else [])

    wb = Workbook(); ws = wb.active; ws.title = "الأعداد"; ws.sheet_view.rightToLeft = True
    NAVY, BLUE, LT, GREY = "1F3864", "2E5496", "D9E1F2", "F2F2F2"
    thin = Side(style="thin", color="BFBFBF"); bd = Border(thin, thin, thin, thin)
    def st(c, *, b=False, sz=11, color="000000", fill=None, ha="center", wrap=False):
        c.font = Font(bold=b, size=sz, color=color)
        c.alignment = Alignment(horizontal=ha, vertical="center", wrap_text=wrap)
        if fill: c.fill = PatternFill("solid", fgColor=fill)
        c.border = bd
    ws.merge_cells(f"A1:{last}1"); st(ws["A1"], b=True, sz=13, color="FFFFFF", fill=NAVY)
    ws["A1"] = f"حصر أعداد الأسياخ — {title}"
    ws.merge_cells(f"A2:{last}2"); st(ws["A2"], sz=9, color="FFFFFF", fill=BLUE)
    ws["A2"] = "تسليح البلاطة الإضافي فقط (السلالم مستبعدة) | العدد = عرض ÷ تباعد، تقريب لأعلى"
    ws.row_dimensions[1].height = 24
    st(ws["A4"], b=True, fill=NAVY, color="FFFFFF"); ws["A4"] = "طول القطعية (م)"
    for j, d in enumerate(dias):
        st(ws.cell(4, 2 + j), b=True, fill=BLUE, color="FFFFFF"); ws.cell(4, 2 + j).value = f"قطر Ø{d} (عدد)"
    r = 5
    for Lk in lengths:
        lbl = "غير محدّد ⚠" if Lk == "unknown" else f"{Lk/1000:g}"
        st(ws.cell(r, 1, lbl), b=(Lk == "unknown"), fill=("FFF2CC" if Lk == "unknown" else GREY))
        for j, d in enumerate(dias):
            v = piv[Lk][d]; st(ws.cell(r, 2 + j, v if v else None), fill=("FFF2CC" if Lk == "unknown" else None))
        r += 1
    st(ws.cell(r, 1, "الإجمالي"), b=True, fill=NAVY, color="FFFFFF")
    for j, d in enumerate(dias):
        st(ws.cell(r, 2 + j, tot[d] or None), b=True, fill=LT)
    r += 2
    ws.merge_cells(f"A{r}:{last}{r}")
    red = sum(1 for c in slab if c["count"] is None)
    cyan = sum(1 for c in slab if c["count"] and c.get("src") == "heur")
    st(ws.cell(r, 1, f"سلالم مستبعدة: {len(stair)} | كولّات بلا عرض (أحمر): {red} | عرض غير مؤكّد (سماوي): {cyan}."),
       sz=9, color="1F3864", fill="E2EFDA", ha="right", wrap=True); ws.row_dimensions[r].height = 30
    ws.column_dimensions["A"].width = 16
    for j in range(len(dias)): ws.column_dimensions[get_column_letter(2 + j)].width = 14

    ws2 = wb.create_sheet("التفاصيل"); ws2.sheet_view.rightToLeft = True
    hdr = ["#", "النوع", "القطر", "التباعد", "الوجه", "الطول L", "العرض", "العدد", "الثقة", "الكولّ", "x", "y"]
    for j, h in enumerate(hdr, 1): st(ws2.cell(1, j, h), b=True, fill=NAVY, color="FFFFFF")
    for i, c in enumerate(sorted(callouts, key=lambda c: (c["stair"], c["dia"], str(c["L"]), -c["y"])), 1):
        typ = "سلّم (مستبعد)" if c["stair"] else "بلاطة"
        fill = "E7E6E6" if c["stair"] else (None if c.get("src") in ("circle", "barline") else "FFF2CC")
        row = [i, typ, f"Ø{c['dia']}", c["sp"], ("علوي" if c["face"] == "T" else "سفلي"), c["L"], c["w"],
               (None if c["stair"] else c["count"]), c["perp"], c["txt"], round(c["x"]), round(c["y"])]
        for j, v in enumerate(row, 1): st(ws2.cell(i + 1, j, v), fill=fill)
    for j, wd in enumerate([5, 14, 7, 8, 7, 9, 8, 7, 8, 15, 10, 10], 1):
        ws2.column_dimensions[get_column_letter(j)].width = wd
    ws2.freeze_panes = "A2"
    wb.save(path)
    return dict(tot=tot, piv=piv, lengths=lengths, dias=dias, n_slab=len(slab), n_stair=len(stair), red=red, cyan=cyan)

def build_review_dxf(dxf_path, callouts, box, out_path):
    doc = ezdxf.readfile(dxf_path); msp = doc.modelspace()
    LAYER = "CHECK-COUNT"
    if LAYER not in doc.layers: doc.layers.add(LAYER, color=7)
    R = 850; GREEN, CYAN, RED, MAG = 3, 4, 1, 6
    n = dict(g=0, c=0, r=0, s=0)
    for c in callouts:
        if c["stair"]:
            col, lbl = MAG, "درج"; n["s"] += 1
        elif c["count"] is None:
            col, lbl = RED, "?"; n["r"] += 1
        elif c.get("src") == "heur":
            col, lbl = CYAN, str(c["count"]); n["c"] += 1
        else:
            col, lbl = GREEN, str(c["count"]); n["g"] += 1
        msp.add_circle((c["x"], c["y"]), R, dxfattribs={"layer": LAYER, "color": col})
        tt = msp.add_text(lbl, height=260, dxfattribs={"layer": LAYER, "color": col})
        tt.dxf.insert = (c["x"] + R * 0.8, c["y"] + R * 0.8)
    lx, ly = box[0] + 1500, box[3] - 1500
    legend = [("HESR CHECK (auto)", 7), (f"GREEN counted={n['g']}", GREEN),
              (f"CYAN low-conf={n['c']}", CYAN), (f"RED not counted={n['r']}", RED),
              (f"MAGENTA stair excluded={n['s']}", MAG)]
    for i, (txt, col) in enumerate(legend):
        tt = msp.add_text(txt, height=360, dxfattribs={"layer": LAYER, "color": col})
        tt.dxf.insert = (lx, ly - i * 700)
    doc.saveas(out_path)

def to_dwg(dxf_path):
    """يحوّل DXF→DWG عبر ODA باستخدام اسم مؤقّت إنجليزي (المُحوّل يفشل مع الأسماء العربية)."""
    if not os.path.exists(ODA_EXE):
        return None
    tin = tempfile.mkdtemp(); tout = tempfile.mkdtemp()
    try:
        shutil.copy(dxf_path, os.path.join(tin, "conv.dxf"))
        subprocess.run([ODA_EXE, tin, tout, "ACAD2018", "DWG", "0", "0", "*.DXF"], check=False)
        src = os.path.join(tout, "conv.dwg")
        if os.path.exists(src):
            dst = os.path.splitext(dxf_path)[0] + ".dwg"
            shutil.copy(src, dst); return dst
    finally:
        shutil.rmtree(tin, ignore_errors=True); shutil.rmtree(tout, ignore_errors=True)
    return None

def safe(name):
    return re.sub(r"[^A-Za-z0-9 _.-]", "", name).strip()[:80] or "plan"

# ------------------------- التشغيل -------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("title", help="جزء من عنوان اللوحة، مثل: LOWER BASEMENT CEILING")
    ap.add_argument("--extra", help="كلمة إضافية لتضييق المطابقة (مثل TOP)")
    ap.add_argument("--dxf", default=DEFAULT_DXF)
    ap.add_argument("--outdir", default=DEFAULT_OUT)
    ap.add_argument("--bbox", nargs=4, type=float, metavar=("XMIN", "XMAX", "YMIN", "YMAX"))
    ap.add_argument("--dwg", action="store_true", help="أنتج نسخة DWG لملف المراجعة")
    args = ap.parse_args()

    doc = ezdxf.readfile(args.dxf); msp = doc.modelspace()
    titles = all_titles(msp)
    hits = find_title(titles, args.title, args.extra)
    if not hits:
        print("لم يُعثر على عنوان مطابق. العناوين المتاحة:")
        for t in sorted(titles, key=lambda t: (-t[1], t[0])): print("   -", t[2])
        return
    if len(hits) > 1:
        print(f"تحذير: {len(hits)} عناوين مطابقة، سأستخدم الأول. ضيّق بـ --extra:")
        for t in hits: print("   -", t[2])
    tx, ty, ttl = hits[0]
    box = tuple(args.bbox) if args.bbox else plan_bbox(titles, tx, ty)
    print(f"اللوحة: {ttl}\nالحدود: x[{box[0]:.0f}..{box[1]:.0f}] y[{box[2]:.0f}..{box[3]:.0f}]")

    callouts = extract(msp, box)
    xs = [c["x"] for c in callouts]; ys = [c["y"] for c in callouts]
    if xs:
        print(f"كولّات: {len(callouts)}  ضمن x[{min(xs):.0f}..{max(xs):.0f}] y[{min(ys):.0f}..{max(ys):.0f}]")

    os.makedirs(args.outdir, exist_ok=True)
    base = os.path.join(args.outdir, safe(ttl))
    xlsx = base + ".xlsx"; review = base + " - review.dxf"
    summ = build_excel(callouts, ttl, xlsx)
    build_review_dxf(args.dxf, callouts, box, review)
    print(f"\nSAVED: {xlsx}\nSAVED: {review}")
    print("الإجمالي:", {f"Ø{d}": summ["tot"][d] for d in summ["dias"]},
          f"| بلاطة={summ['n_slab']} سلالم={summ['n_stair']} أحمر={summ['red']} سماوي={summ['cyan']}")
    for Lk in summ["lengths"]:
        print(f"   L={Lk}: " + " ".join(f"Ø{d}={summ['piv'][Lk][d]}" for d in summ["dias"]))
    if args.dwg:
        d = to_dwg(review)
        print("DWG:", d or "فشل التحويل")

if __name__ == "__main__":
    main()
