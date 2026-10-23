// Generate an Arabic (RTL) Word version of WORK_REPORT.md
const path = require("path");
const fs = require("fs");
const gmod = "C:/Users/Administrator/AppData/Roaming/npm/node_modules";
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  AlignmentType, LevelFormat, HeadingLevel, BorderStyle, WidthType,
  ShadingType, PageBreak,
} = require(path.join(gmod, "docx"));

const FONT = "Arial";
const NAVY = "1F3864";
const BLUE = "2E75B6";
const LIGHT = "D9E2F3";
const GREEN = "2E7D32";

// ---- helpers (everything RTL) ----
const run = (text, o = {}) =>
  new TextRun({ text, font: FONT, rightToLeft: true, ...o });

const P = (children, o = {}) =>
  new Paragraph({
    bidirectional: true,
    alignment: AlignmentType.RIGHT,
    spacing: { after: 120, line: 300 },
    children: Array.isArray(children) ? children : [children],
    ...o,
  });

const H1 = (text) =>
  new Paragraph({
    heading: HeadingLevel.HEADING_1,
    bidirectional: true,
    alignment: AlignmentType.RIGHT,
    spacing: { before: 280, after: 160 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: BLUE, space: 4 } },
    children: [run(text, { bold: true, color: NAVY, size: 30 })],
  });

const Hsub = (text) =>
  new Paragraph({
    bidirectional: true,
    alignment: AlignmentType.RIGHT,
    spacing: { before: 120, after: 80 },
    children: [run(text, { bold: true, color: BLUE, size: 24 })],
  });

const bullet = (children) =>
  new Paragraph({
    bidirectional: true,
    alignment: AlignmentType.RIGHT,
    numbering: { reference: "bullets", level: 0 },
    spacing: { after: 60, line: 290 },
    children: Array.isArray(children) ? children : [children],
  });

// label (bold) + body, in one RTL paragraph
const labelP = (label, body) =>
  P([run(label, { bold: true, color: NAVY }), run(body)]);

// ---- table builder (RTL) ----
const cellBorder = { style: BorderStyle.SINGLE, size: 1, color: "BFBFBF" };
const borders = { top: cellBorder, bottom: cellBorder, left: cellBorder, right: cellBorder };

function tbl(headers, rows, widths) {
  const total = widths.reduce((a, b) => a + b, 0);
  const mkCell = (text, w, opts = {}) =>
    new TableCell({
      borders,
      width: { size: w, type: WidthType.DXA },
      shading: { fill: opts.fill || "FFFFFF", type: ShadingType.CLEAR },
      margins: { top: 60, bottom: 60, left: 100, right: 100 },
      children: [
        new Paragraph({
          bidirectional: true,
          alignment: AlignmentType.RIGHT,
          children: [run(text, { bold: !!opts.bold, color: opts.color, size: 22 })],
        }),
      ],
    });
  const headerRow = new TableRow({
    tableHeader: true,
    children: headers.map((h, i) => mkCell(h, widths[i], { bold: true, color: "FFFFFF", fill: BLUE })),
  });
  const bodyRows = rows.map((r, ri) =>
    new TableRow({
      children: r.map((c, i) =>
        mkCell(c, widths[i], { fill: ri % 2 ? "F2F6FC" : "FFFFFF" })),
    }));
  return new Table({
    width: { size: total, type: WidthType.DXA },
    columnWidths: widths,
    visuallyRightToLeft: true,
    rows: [headerRow, ...bodyRows],
  });
}

const HR = () =>
  new Paragraph({
    spacing: { before: 80, after: 80 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: "D0D0D0", space: 2 } },
    children: [run("")],
  });

// ============ CONTENT ============
const children = [];

// Title block
children.push(
  new Paragraph({
    bidirectional: true,
    alignment: AlignmentType.CENTER,
    spacing: { before: 200, after: 80 },
    children: [run("تقرير العمل المُنجَز — مشروع Cardios", { bold: true, color: NAVY, size: 40 })],
  }),
  new Paragraph({
    bidirectional: true,
    alignment: AlignmentType.CENTER,
    spacing: { after: 60 },
    children: [run("نظام ذكي للكشف القلبي: تقييم خطورة + تحليل تخطيط القلب (ECG)", { color: BLUE, size: 24 })],
  }),
  HR(),
);

children.push(
  labelP("الموضوع: ", "تطوير وتقوية نظام Cardios للكشف القلبي (تقييم خطورة + تحليل ECG)"),
  labelP("طبيعة العمل: ", "حل مشاكل تقنية + إضافة تفسيرية ML + تقييم كمّي + تأمين النظام"),
);

// مقدمة
children.push(H1("مقدمة"));
children.push(P(run(
  "كان المشروع يعمل وظيفيًا لكن تنقصه عناصر جوهرية: لم تكن نماذج الذكاء الاصطناعي مُتحقَّقًا من تشغيلها فعليًا، ولا يوجد تفسير لقراراتها، ولا تقييم كمّي لدقتها، ولا طبقة أمان طبية. هذا التقرير يوثّق المشاكل التي ووجِهت والحلول المطبّقة والنتائج."
)));

// 1
children.push(H1("١. تشغيل نماذج الذكاء الاصطناعي والتحقق منها"));
children.push(Hsub("المشكلة:"));
children.push(
  bullet(run("نسخة Python على النظام (3.14) غير مدعومة من TensorFlow، فالنماذج لم تكن تعمل.")),
  bullet(run("بيئة العمل الافتراضية كانت تنقصها مكتبة pydantic.")),
  bullet(run("ملفات النماذج المُدرّبة (‎.keras‎ و‎.pkl‎) لم تكن متاحة في نسخة العمل.")),
);
children.push(Hsub("الحل:"));
children.push(
  bullet(run("اعتماد بيئة Python 3.11 (.venv) المتوافقة مع TensorFlow.")),
  bullet(run("تثبيت المكتبات الناقصة وتوثيق المتطلبات.")),
  bullet(run("توفير ملفات النماذج في مساراتها الصحيحة (backend/model/ و backend/ECG model/).")),
);
children.push(labelP("النتيجة: ",
  "النموذجان يعملان فعليًا — CNN-LSTM يصنّف إشارة ECG (مثال: انقباض بطيني سابق لأوانه PVC بثقة 93%)، و XGBoost يقيّم خطورة القلب من البيانات الصحية."));

// 2
children.push(H1("٢. تفسير قرارات النماذج (Explainable AI)"));
children.push(labelP("المشكلة: ",
  "النماذج كانت «صندوقًا أسود» — تُخرِج تصنيفًا دون توضيح السبب، وهو أمر غير مقبول في السياق الطبي ويُضعف ثقة الطبيب."));
children.push(Hsub("الحل: تطبيق طريقتي تفسير:"));
children.push(
  bullet([run("Grad-CAM ", { bold: true }), run("لنموذج ECG (analysis/explain_ecg_gradcam.py): خريطة حرارية فوق الإشارة تُظهر أي جزء منها أثّر في التصنيف.")]),
  bullet([run("SHAP ", { bold: true }), run("لنموذج الخطورة (analysis/explain_risk_shap.py): يوضّح مساهمة كل عامل صحي في رفع/خفض الخطورة (باستخدام SHAP الدقيق المدمج في XGBoost).")]),
);
children.push(labelP("النتيجة: ",
  "مخرجات منطقية طبيًا — مثلًا للمريض عالي الخطورة كانت العوامل الأعلى تأثيرًا: السكتة الدماغية (+0.70)، العمر (+0.35)، صعوبة المشي (+0.25). الصور محفوظة في analysis/outputs/."));

// 3
children.push(H1("٣. سدّ الفجوة بين بيانات التدريب وإشارة السنسور (مسار التحليل الحي)"));
children.push(Hsub("المشكلة:"));
children.push(
  bullet(run("النموذج مُدرّب على نبضات مفردة نظيفة (قاعدة MIT-BIH)، بينما جهاز السنسور (ESP32) يرسل تيارًا مستمرًا متعدد النبضات بخصائص مختلفة (تردد، تشويش، مدى).")),
  bullet(run("التطبيق كان يضغط نافذة السنسور كاملةً إلى 180 عيّنة، مما يشوّه الإشارة.")),
);
children.push(Hsub("الحل: بناء مسار معالجة إشارة كامل في backend/ecg_analysis.py:"));
children.push(
  bullet(run("تنقية (band-pass filter) لإزالة انحراف الخط والضوضاء.")),
  bullet(run("كشف النبضات بخوارزمية Pan-Tompkins (مشتقة ← تربيع ← تكامل نافذي ← عتبة تكيّفية).")),
  bullet(run("تقطيع كل نبضة على حدة.")),
  bullet(run("تصنيف كل نبضة بالنموذج.")),
  bullet(run("تحليل الإيقاع (معدل النبض + انتظام فترات RR).")),
  bullet(run("تقرير نتائج وتنبيهات + إخلاء مسؤولية.")),
);
children.push(P(run("ثم دمج المسار في نقطة النهاية /device-ecg كحقل analysis إضافي دون كسر الحقول الحالية.")));
children.push(Hsub("النتيجة:"));
children.push(
  bullet(run("على إشارة اختبار بمعدل نبض معروف: كشف 10 من 10 نبضات ومعدل نبض دقيق (75).")),
  bullet(run("اختبار حي على /device-ecg: أعاد معدل نبض صحيح (80) مع الحفاظ على توافق الواجهة.")),
);

// 4
children.push(H1("٤. عطل تشغيلي على نظام Windows"));
children.push(labelP("المشكلة: ",
  "استدعاء model.predict كان يطبع شريط تقدّم برموز Unicode، مما يسبّب انهيارًا (UnicodeEncodeError) على ترميز Windows الافتراضي (cp1252) ويُرجِع خطأ 500."));
children.push(labelP("الحل: ", "تمرير verbose=0 لإيقاف طباعة شريط التقدّم."));
children.push(labelP("النتيجة: ", "الطلبات تكتمل بنجاح، وسجلّات الخادم نظيفة."));

// 5
children.push(H1("٥. التقييم الكمّي للنموذج"));
children.push(labelP("المشكلة: ", "لم تكن هناك أرقام دقة موثّقة — وهي أول ما تطلبه أي لجنة علمية."));
children.push(labelP("الحل: ",
  "سكربت تقييم (analysis/evaluate_ecg_model.py) على 21,892 نبضة من مجموعة اختبار MIT-BIH الرسمية، مع تجربة طريقتي تطبيع للمدخلات لتحديد الصحيحة."));
children.push(Hsub("النتيجة:"));
children.push(tbl(
  ["المقياس", "القيمة"],
  [
    ["الدقة (Accuracy)", "97.98%"],
    ["Macro-F1", "0.90"],
    ["F1 لكل فئة", "Normal 0.99 · PVC 0.96 · Paced 0.98 · Atrial 0.81 · Fusion V+N 0.76"],
  ],
  [3000, 6360],
));
children.push(new Paragraph({ spacing: { after: 60 }, children: [run("")] }));
children.push(
  bullet(run("إنتاج مصفوفة الالتباس (Confusion Matrix) — analysis/outputs/confusion_matrix.png.")),
  bullet(run("توثيق عدم توازن الفئات (Normal = 83% من البيانات)، والتأكيد على الاعتماد على Macro-F1 و recall لكل فئة بدل الدقة الإجمالية وحدها.")),
);

// 6
children.push(H1("٦. اكتشاف خلل في المعالجة (نتيجة التقييم)"));
children.push(labelP("المشكلة: ",
  "كشف التقييم أن النموذج مُدرّب على بيانات مُطبّعة في المدى 0-1 (min-max)، بينما التطبيق يطبّق z-normalization — والفرق كبير: 98% بالطريقة الصحيحة مقابل 70% بالطريقة الحالية."));
children.push(labelP("الحل (طُبِّق): ",
  "عُدِّلت خطوة المعالجة في النشر إلى min-max في backend/ecg_service.py و backend/ecg_analysis.py. وللتحقّق، حاكينا إشارة سنسور بمقياس مختلف تمامًا (قراءات ADC: ×350 + 1700): الطريقة الجديدة أعادت 97.97% دقة / 0.90 Macro-F1 مقابل 69.6% / 0.21 للطريقة القديمة — إصلاح حقيقي وليس نظريًا. الدليل البصري: analysis/outputs/preprocessing_comparison.png."));
children.push(labelP("الأهمية: ",
  "يُثبت أن التقييم لم يكن شكليًا، بل اكتشف خللًا حقيقيًا في النظام وأصلحه وتحقّق من الإصلاح كميًا."));

// 7
children.push(H1("٧. الأمان والمسؤولية الطبية"));
children.push(labelP("المشكلة: ",
  "كان التطبيق يعرض نتائج طبية دون إخلاء مسؤولية (خطر قانوني/أخلاقي)، وواجهات الـ API مفتوحة دون مصادقة، والمدخلات غير مُتحقَّق منها."));
children.push(Hsub("الحل:"));
children.push(
  bullet([run("backend/safety.py: ", { bold: true }), run("مصدر واحد لإخلاء المسؤولية، يُرفَق بكل نتيجة (في الخادم وكبانر في الواجهة) — فيستحيل عرض نتيجة دونه.")]),
  bullet([run("backend/contracts.py: ", { bold: true }), run("تحقّق من المدخلات بـ pydantic على /predict و /device-ecg (ترفض المدخلات الخاطئة برسالة 400 واضحة).")]),
  bullet([run("backend/auth.py: ", { bold: true }), run("تحقّق من توكن Supabase (JWT) لحماية نقاط نهاية المستخدم، قابل للتفعيل عبر AUTH_ENABLED دون كسر بيئة التطوير.")]),
);
children.push(labelP("النتيجة: ",
  "كل نتيجة تحمل تحذيرًا طبيًا، والمدخلات تُتحقَّق، ونقاط نهاية المستخدم محمية."));

// 8
children.push(H1("٨. جودة الكود والتنظيم"));
children.push(labelP("المشكلة: ",
  "كود مبعثر، لا اختبارات آلية، أرقام «سحرية» غير موثّقة، استخدام pickle (غير موصى به)، وأخطاء أنواع في الواجهة."));
children.push(Hsub("الحل:"));
children.push(
  bullet(run("إطار تنظيم WAT (محرّك + أدوات + سيناريوهات) يلفّ المنطق الموجود دون إعادة كتابته.")),
  bullet(run("مجموعة اختبارات آلية (17 اختبارًا: 11 للإطار + 6 للمصادقة).")),
  bullet(run("تحويل تحميل النماذج من pickle إلى joblib (الموصى به لـ scikit-learn).")),
  bullet(run("توثيق عتبة الثقة كثابت مُسمّى CONFIDENCE_THRESHOLD.")),
  bullet(run("إصلاح 3 أخطاء TypeScript في الواجهة (فحص الأنواع أصبح نظيفًا تمامًا).")),
);
children.push(labelP("النتيجة: ", "17 اختبارًا ناجحًا، وبناء واجهة نظيف."));

// 9
children.push(H1("٩. قاعدة البيانات"));
children.push(labelP("المشكلة: ",
  "ملفات الـ migrations كانت متعارضة (جدول predictions مُعرَّف بطريقتين مختلفتين)، مما يربك الإعداد."));
children.push(labelP("الحل: ",
  "ملف إعداد موحّد وآمن للتكرار supabase/setup.sql مطابق لما يستخدمه الكود فعليًا (مع سياسات RLS والفهارس)."));
children.push(labelP("النتيجة: ", "إعداد قاعدة بيانات واضح وقابل لإعادة التشغيل بأمان."));

// الخلاصة (page break before)
children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(H1("الخلاصة"));
children.push(tbl(
  ["المجال", "النتيجة"],
  [
    ["تشغيل النماذج", "✅ CNN-LSTM + XGBoost يعملان"],
    ["التفسيرية (XAI)", "✅ Grad-CAM + SHAP"],
    ["التحليل الحي", "✅ Pan-Tompkins + تقطيع + تصنيف + إيقاع"],
    ["التقييم", "✅ دقة 97.98% · Macro-F1 0.90 · مصفوفة التباس"],
    ["الأمان", "✅ إخلاء مسؤولية + تحقّق مدخلات + JWT"],
    ["الجودة", "✅ 17 اختبارًا · joblib · فحص أنواع نظيف"],
    ["قاعدة البيانات", "✅ سكربت إعداد موحّد"],
  ],
  [3200, 6160],
));
children.push(new Paragraph({ spacing: { after: 80 }, children: [run("")] }));
children.push(labelP("الأثر: ",
  "انتقل المشروع من «تطبيق يعمل» إلى نظام مُقيَّم كميًا، قابل للتفسير، آمن طبيًا، ومُختبَر — مع اكتشاف وإصلاح خلل حقيقي في معالجة الإشارة عبر التقييم."));

// مرجعية الملفات
children.push(H1("ملفات العمل المرجعية"));
children.push(
  bullet([run("backend/ecg_analysis.py", { bold: true }), run(" — مسار التحليل الحي")]),
  bullet([run("analysis/explain_ecg_gradcam.py · analysis/explain_risk_shap.py", { bold: true }), run(" — التفسيرية")]),
  bullet([run("analysis/evaluate_ecg_model.py", { bold: true }), run(" — التقييم الكمّي")]),
  bullet([run("analysis/outputs/", { bold: true }), run(" — الصور (Grad-CAM · SHAP · Confusion Matrix)")]),
  bullet([run("backend/safety.py · backend/contracts.py · backend/auth.py", { bold: true }), run(" — الأمان")]),
  bullet([run("supabase/setup.sql", { bold: true }), run(" — إعداد قاعدة البيانات")]),
  bullet([run("GRADUATION_GUIDE.md", { bold: true }), run(" — دليل المناقشة")]),
);

// ============ DOC ============
const doc = new Document({
  styles: {
    default: { document: { run: { font: FONT, size: 24 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 30, bold: true, font: FONT, color: NAVY },
        paragraph: { spacing: { before: 280, after: 160 }, outlineLevel: 0 } },
    ],
  },
  numbering: {
    config: [
      { reference: "bullets",
        levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.RIGHT,
          style: { paragraph: { indent: { right: 480, hanging: 280 } } } }] },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838 }, // A4
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
      },
    },
    children,
  }],
});

const out = path.join("D:/Final Project/cardios/.claude/worktrees/angry-nightingale-471048", "WORK_REPORT.docx");
Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(out, buf);
  console.log("written:", out, buf.length, "bytes");
});
