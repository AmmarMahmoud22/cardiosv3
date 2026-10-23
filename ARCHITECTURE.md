# 🏗️ الرسومات المعمارية — مشروع Cardios

> رسومات جاهزة للكتاب والعرض. كل رسم بصيغة **Mermaid** (تتعرض تلقائيًا في
> GitHub / VS Code / أي عارض Markdown) مع **وصف نصّي** للشرح أمام اللجنة.
> لتصدير صورة: افتح الملف في VS Code (إضافة Mermaid) أو الصق الكود في
> <https://mermaid.live> واحفظه PNG/SVG.

فهرس الأشكال:
- **شكل 1** — المعمارية العامة للنظام (طبقات)
- **شكل 2** — تدفّق البيانات end-to-end (Sequence)
- **شكل 3** — مسار التحليل الحي لإشارة ECG (Pipeline)
- **شكل 4** — معمارية نموذج CNN-LSTM
- **شكل 5** — طبقة التفسير (XAI)
- **شكل 6** — إطار الموثوقية WAT
- **شكل 7** — مخطّط قاعدة البيانات (ER مبسّط)

---

## شكل 1 — المعمارية العامة (Layered System Architecture)

```mermaid
flowchart TB
    subgraph L1["طبقة العتاد - Hardware"]
        S["AD8232 Sensor"] --> E["ESP32 @250Hz"]
        E --> U["usb_bridge.py - Serial→HTTP"]
    end
    subgraph L2["طبقة الخادم - Backend (Flask)"]
        API["REST API"]
        SAFE["Safety Gate - safety.py"]
        VAL["Validation - contracts.py"]
        AUTH["JWT Auth - auth.py"]
        API --- VAL --- AUTH --- SAFE
    end
    subgraph L3["طبقة الذكاء - AI/ML"]
        PIPE["ECG Pipeline - ecg_analysis.py"]
        M1["CNN-LSTM - ECG"]
        M2["XGBoost - Risk"]
        XAI["XAI: Grad-CAM + SHAP"]
        PIPE --> M1
        M2 --- XAI
        M1 --- XAI
    end
    subgraph L4["طبقة البيانات + الواجهة"]
        DB["Supabase + RLS"]
        FE["React/TS UI + Disclaimer Banner"]
    end
    U -->|"POST /device-ecg"| API
    SAFE --> PIPE
    PIPE --> DB
    DB --> FE
    FE -->|"POST /predict"| API
    WAT["WAT Reliability Framework - يلفّ الكل"]:::wat
    WAT -.-> L2
    WAT -.-> L3
    classDef wat fill:#fde,stroke:#a36;
```

**الوصف:** أربع طبقات (عتاد → خادم → ذكاء → بيانات/واجهة)، يلفّها إطار **WAT**
للموثوقية. كل نتيجة تمرّ عبر **بوّابة الأمان** قبل العرض. النقطة للدكتور: *«النظام
مبني بفصل اهتمامات واضح، والأمان قيد معماري لا إضافة».*

---

## شكل 2 — تدفّق البيانات end-to-end (Sequence)

```mermaid
sequenceDiagram
    participant D as ESP32+AD8232
    participant B as usb_bridge
    participant API as Flask /device-ecg
    participant V as Validation+Auth
    participant P as ECG Pipeline
    participant M as CNN-LSTM
    participant DB as Supabase
    participant UI as React UI
    D->>B: عيّنات ECG (250Hz)
    B->>API: POST دفعة JSON
    API->>V: تحقّق المدخلات + JWT
    V-->>API: صالح
    API->>P: تنقية + Pan-Tompkins + تقطيع
    P->>M: نبضات (180,1)
    M-->>P: تصنيف + ثقة لكل نبضة
    P->>API: تقرير (HR + إيقاع + findings + disclaimer)
    API->>DB: حفظ النتيجة
    API-->>UI: JSON + إخلاء مسؤولية
    UI-->>UI: عرض النتيجة + بانر التحذير
```

**الوصف:** يتتبّع طلبًا واحدًا من الحسّاس حتى الشاشة، ويُظهر أين يحدث التحقّق
والتصنيف وإرفاق الإخلاء. مناسب للفصل الرابع (التنفيذ).

---

## شكل 3 — مسار التحليل الحي (Domain-Gap Bridging Pipeline) ⭐

```mermaid
flowchart LR
    A["إشارة خام من الحسّاس - تيار مستمر مشوّش"] --> B["Band-pass Filter - 0.5-40Hz"]
    B --> C["Pan-Tompkins - مشتقة→تربيع→تكامل→عتبة"]
    C --> D["كشف R-peaks - مواضع النبضات"]
    D --> E["تقطيع كل نبضة + Resample → 180"]
    E --> F["تطبيع - min-max"]
    F --> G["CNN-LSTM - تصنيف لكل نبضة"]
    G --> H["تحليل الإيقاع - HR + انتظام RR"]
    H --> I["تجميع - findings + flags"]
    I --> J["+ إخلاء مسؤولية - فرز لا تشخيص"]
    style C fill:#ffe0b2,stroke:#e65100
    style J fill:#ffcdd2,stroke:#b71c1c
```

**الوصف:** **أهم رسم** — يجسّد مساهمتك الأساسية: تحويل إشارة الحسّاس الخام إلى
مدخلات يفهمها النموذج. أبرز **Pan-Tompkins** (البرتقالي) كقلب الحل، و**الإخلاء**
(الأحمر) كنهاية إلزامية.

---

## شكل 4 — معمارية نموذج CNN-LSTM

```mermaid
flowchart LR
    IN["Input (180,1) - نبضة واحدة"] --> C1["Conv1D + ReLU"]
    C1 --> P1["MaxPool"]
    P1 --> C2["Conv1D + ReLU"]
    C2 --> P2["MaxPool"]
    P2 --> L1["LSTM - تسلسل زمني"]
    L1 --> DO["Dropout"]
    DO --> FC["Dense"]
    FC --> OUT["Softmax - 5 فئات AAMI"]
    style C1 fill:#bbdefb
    style C2 fill:#bbdefb
    style L1 fill:#c8e6c9
```

**الوصف:** طبقات **Conv1D** تلتقط الأنماط المحلية في الموجة (شكل QRS)، و**LSTM**
تلتقط التسلسل الزمني، ثم **Softmax** على 5 فئات. الجملة: *«اخترنا الهجين لأن
الإشارة لها بُعدان: شكل محلي + تسلسل زمني».*

---

## شكل 5 — طبقة التفسير (XAI)

```mermaid
flowchart TB
    subgraph ECG["تفسير نموذج ECG"]
        G1["Grad-CAM"] --> G2["خريطة حرارية فوق الإشارة - أي جزء قاد التصنيف"]
    end
    subgraph RISK["تفسير نموذج الخطورة"]
        S1["SHAP - native pred_contribs"] --> S2["مساهمة كل عامل: Stroke +0.70, Age +0.35..."]
    end
    ECG --> DOC["الطبيب يتحقّق من المنطق - بدل الثقة العمياء"]
    RISK --> DOC
    style DOC fill:#fff9c4,stroke:#f57f17
```

**الوصف:** تغطية مزدوجة — تفسير بصري للإشارة (Grad-CAM) وتفسير عددي للعوامل
(SHAP) — تحوّل النظام من صندوق أسود لأداة قابلة للمراجعة الطبية.

---

## شكل 6 — إطار الموثوقية WAT

```mermaid
flowchart TB
    WF["Workflow YAML - DAG"] --> ENG["Engine - topo-sort + retry"]
    ENG --> REG["Registry - عقود pydantic"]
    REG --> T1["Tool: classify_ecg"]
    REG --> T2["Tool: predict_risk"]
    REG --> T3["Tool: normalize_csv"]
    ENG --> ST["State - checkpoints"]
    ENG --> TEL["Telemetry - JSON spans"]
    T1 -.->|"يلفّ"| BK["backend/ - منطق موجود"]
    T2 -.->|"يلفّ"| BK
    style ENG fill:#e1bee7,stroke:#6a1b9a
```

**الوصف:** الأدوات **تلفّ** منطق `backend/` الموجود (لا تعيد كتابته)، بعقود
إدخال/إخراج، مع نقاط حفظ وتتبّع — ما يجعل التشغيل قابلًا للتكرار والتدقيق.

---

## شكل 7 — قاعدة البيانات (ER مبسّط)

```mermaid
erDiagram
    profiles ||--o{ predictions : "يملك"
    profiles ||--|| extended_profiles : "يمتد"
    profiles ||--o{ user_roles : "له أدوار"
    profiles {
        uuid id PK
        text email
        timestamptz created_at
    }
    predictions {
        uuid id PK
        uuid user_id FK
        jsonb result
        text type
        timestamptz created_at
    }
    extended_profiles {
        uuid user_id PK_FK
        jsonb health_data
    }
    user_roles {
        uuid user_id FK
        text role
    }
```

**الوصف:** مخطّط مطابق لـ `supabase/setup.sql`، نتائج التنبؤ تُخزَّن JSONB مرتبطة
بالمستخدم، مع **RLS** يضمن أن كل مستخدم يرى بياناته فقط.

---

## كيف تصدّر الصور للكتاب
1. **VS Code:** ثبّت إضافة *Markdown Preview Mermaid Support* → افتح الملف →
   من المعاينة احفظ الرسم صورة.
2. **mermaid.live:** الصق كود كل رسم → Export → PNG/SVG (احفظها في `analysis/outputs/diagrams/`).
3. ضع كل صورة في الكتاب برقم وتعليق (Caption) كما في `THESIS_OUTLINE.md`.
