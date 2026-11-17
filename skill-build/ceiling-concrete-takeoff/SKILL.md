---
name: ceiling-concrete-takeoff
description: >-
  Ceiling/slab concrete-VOLUME takeoff (حصر خرسانة الأسقف / السقف) from an AutoCAD structural ceiling plan
  (.dwg/.dxf) for Muttajah Mall. Computes a ceiling's concrete m³ = slab (area × thickness − openings) +
  beams (each beam's below-slab stem only) + drop panels (extra over the slab), so the slab and the beams
  are never double-counted. Beam sections are read PER-LABEL from the plan as MARK(W x D) — e.g. B2(300X600)
  — not from a schedule (the same mark carries several sections); beam concrete = W × (depth − slab) ×
  length. Slab thickness from SLAB=###mm; openings deducted; INVERTED beams project up. Outputs a per-element
  Excel (slab panels + each beam: W, depth, exposed stem, length, volume + total) and a marked review drawing.
  Use for حصر خرسانة السقف / البلاطة / الكمرات / كمية أو حجم خرسانة سقف (م³) / ceiling slab + beam concrete
  volume per floor. Do NOT use it for COLUMN concrete (that is concrete-takeoff), to COUNT anything, or for
  rebar/حديد (that is rebar-takeoff — beam reinforcement is folded in there).
compatibility: Requires Python 3 with ezdxf and openpyxl. DWG⇄DXF conversion needs the ODA File Converter.
---

# حصر خرسانة الأسقف — ceiling-concrete-takeoff

يحسب **حجم خرسانة السقف** (م³) من اللوحة الإنشائية. السقف = **بلاطة + كمرات + هوابط**، ويُحصَر بحيث
**لا تُحسب الخرسانة مرتين** (الجزء المشترك بين الكمرة والبلاطة يُنسَب للبلاطة، والكمرة تأخذ الظاهر أسفلها فقط).

> ⚠️ **نطاق العمل:** مُعايَرة على **أعراف لوحات هذا المكتب (مشروع Muttajah Mall)** — ترميز الكمرات
> `MARK(WxD)` على طبقتَي `BEAMS`/`ST-203-SLAB-TXT`، سُمك البلاطة `SLAB=###mm`، الهوابط `320` على `S-TEXT`.
> قد لا تعمل كما هي على مشروع آخر بأعراف مختلفة.

## المعادلة (منع الازدواج)

```
خرسانة السقف = خرسانة البلاطة + خرسانة الكمرات + خرسانة الهوابط           (م³)

• البلاطة = (مساحة البلاطة − الفتحات) × سُمك البلاطة t          [t = SLAB=###mm، عادةً 0.22]
• كل كمرة = العرض W × (العمق D − t) × الطول L                   ← الظاهر أسفل البلاطة فقط
• كل هابط = مساحة الهابط × (سُمك الهابط − t)                     [هابط 0.32 → إضافي 0.10 فوق البلاطة]
```

**لماذا (D − t) للكمرة؟** الكمرة مصبوبة متجانسة مع البلاطة ومتداخلة معها بسُمك البلاطة؛ الجزء الذي داخل
سُمك البلاطة محسوب ضمن مساحة البلاطة، فلو حسبناه مع الكمرة لاحتُسب مرتين. مثال: بلاطة 20سم، كمرة 30×70
→ الظاهر أسفل البلاطة = 70 − 20 = **50سم**، وحجم الكمرة = 0.30 × 0.50 × الطول.

## قراءة الكمرات (مقاطعها) — المصدر: ليبل المسقط، لا جدول

- **المقطع مكتوب في ليبل كل كمرة** بصيغة `MARK(W X D)` مثل `B2(300X600)` (العرض×العمق مم).
  **لا يوجد جدول أبعاد**؛ جدول «Beams Reinforcement Table» يعطي التسليح فقط (→ rebar-takeoff).
- **الماركة الواحدة لها مقاطع متعددة** (B2 = 300×600/200×700/250×700/250×600/300×500/300×700…)،
  فيُقرأ المقطع **لكل كمرة من ليبلها**، لا من الماركة.
- **عمق متغيّر** `MARK(W X D1/D2)` (مثل `B5(300X600/1350)`، `B3(300X400/850)`) = كمرة بعمقين؛
  استخدم ((D1+D2)/2 − t) أو قسّمها لجزأين عند نقطة الكسر المُبعَّدة.
- **`INVERTED`/`INV.`** = كمرة مقلوبة (ناشزة لأعلى فوق البلاطة) — نفس معادلة الحجم `W×(D−t)×L`.
- الطبقات: `ST-203-SLAB-TXT` + `BEAMS`. **`S -Beams` = سملات الأساس `S(WxD)` — ليست كمرات سقف
  (تُعالَج في raft_footings)، تُستبعَد.**
- الماركات المرصودة: B1 B2 B3 B4 B5 CA2 CA3 CA4 (CA = كمرات كابولي؛ CA1 في جدول التسليح فقط).
  التفاصيل والمقاطع الكاملة في `references/ceiling-concrete-method.md` و `reference/project-reference.yaml` (`beams`).

## المُخرَجات (الهدف)

1. **شيت Excel (RTL):** قسم للبلاطة (المساحة × السُمك − الفتحات) + صف لكل كمرة
   (الماركة | المقطع WxD | الظاهر D−t | الطول | الحجم م³) + صفوف الهوابط، ثم الإجمالي والإجمالي × 1.05 (هدر 5%).
2. **لوحة مراجعة:** دائرة ورقم تسلسلي على كل كمرة/منطقة بلاطة يطابق صفوف الإكسل، عشان المهندس يراجع بالعين.

## الربط بالمهارات الأخرى

- **concrete-takeoff (الأعمدة):** العمود يُحصَر حتى **قاع ما يعلوه** — كمرة عادية فوقه → قاع الكمرة (خصم
  العمق الكامل D)؛ بلاطة فقط → قاع البلاطة (0.22/0.32). الكمرة المقلوبة لا تُنقِص العمود.
- **rebar-takeoff (حديد السقف):** تسليح الكمرات (B1–B5/CA1–CA4) محفوظ في
  `skill-build/rebar-takeoff/references/beam-reinforcement.md` ليُضاف لحصر حديد السقف عند طلبه.

## الاستخدام — **مُنفَّذ** `scripts/ceiling_concrete_takeoff.py`

```
python ceiling_concrete_takeoff.py "LOWER BASEMENT CEILING" --dwg
python ceiling_concrete_takeoff.py "LOWER BASEMENT CEILING" --with-ramp --ramp-slope-pct 12 --ramp-area 350 --dwg
```
- `--slab` سُمك البلاطة مم (افتراضي 220 أو من `SLAB=`). `--with-ramp` يضيف رامبات البدروم (لوحة RAMPS).
- `--ramp-slope-pct` ميل الرامب ٪ → المعامل `sqrt(1+(p/100)²)` يُطبَّق على أطوال/مساحة الرامب.
- `--ramp-area` مساحة بلاطة الرامب المسقطية م² (**من المهندس** — لا تُقاس آلياً بثقة، انظر أدناه).
- المخرجات: Excel (بلاطة/كمرات/رامب + الإجمالي × هدر 5٪) + شيت «تفاصيل الكمرات» + لوحة مراجعة بخطوط الكمرات.

## الحالة والدقّة (أمانة)

- **البلاطة المسطّحة + كمراتها: مُنفَّذ وموثوق.** المساحة من `slab_mesh.rebar_extent` − الفتحات (نفس مساحة
  حصر الحديد)، والكمرات من `beams_rebar.extract_beams` (الطول من حواف `S -Beams`). نموذج البدروم السفلي:
  بلاطة ≈488.5 م³ + كمرات ≈11.6 م³.
- **الرامب على ميل:** مساحة بلاطة الرامب **تُقاس آلياً** من شرائط `RAMP 0N` داخل لوحة الرامبات (كل رامب
  شريط رأسي ضيّق؛ يُقاس bbox جيومتريه → عرض×طول). رامبات البدروم السفلي = **RAMP 03 (4.2×26.3م=110.5م²)
  + RAMP 04 (3.9×25.0م=97.5م²) = 208 م²**. تُضرب في معامل الميل `sqrt(1+ميل²)` → بلاطة ≈46 م³. `--ramp-area`
  يتجاوز القياس يدوياً. كمرات الرامب (مقلوبة INVERTED) تُستخرَج آلياً — **تغطية جزئية، راجع لوحة المراجعة**.
- **الهوابط (drop panels):** غير مضافة بعد (تؤثّر أساساً على الأعمدة). تُضاف لاحقاً = مساحة الهابط × (سُمكه − سُمك البلاطة).
- تختار الأداة أحدث لوحة في `drawings/`. حديد الكمرات (شامل الرامب) في مهارة rebar-takeoff (`full_takeoff.py --with-ramp`).
