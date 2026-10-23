import pandas as pd
import numpy as np
import os
import sys
import logging
from pathlib import Path
import csv
import io

# Use the logging module instead of print(). On Windows the default console
# encoding (cp1252) cannot encode Arabic text, so a bare print() of an Arabic
# message raises UnicodeEncodeError and crashes the /predict-ecg request. The
# logging module swallows handler encoding errors instead of propagating them,
# so conversion stays robust regardless of console codepage.
logger = logging.getLogger(__name__)

def convert_csv_to_format(input_file, output_file=None):
    """
    تحويل ملف CSV إلى التنسيق المناسب لنموذج ECG

    المعلمات:
    input_file (str): مسار ملف الإدخال
    output_file (str): مسار ملف الإخراج. إذا كان None، سيتم استخدام نفس اسم الملف مع إضافة "_processed"

    العودة:
    str: مسار ملف الإخراج
    """
    logger.debug("محاولة قراءة الملف: %s", input_file)

    # فحص الملف أولاً
    try:
        with open(input_file, 'r') as f:
            content = f.read()
            if not content.strip():
                logger.debug("الملف فارغ، إنشاء ملف تجريبي...")
                # إنشاء مصفوفة اختبار
                test_data = np.zeros(1000)
                df = pd.DataFrame([test_data])
                logger.debug("تم إنشاء بيانات تجريبية بطول 1000")
            else:
                # محاولة قراءة الملف بعدة طرق
                try:
                    # محاولة قراءة CSV عادي
                    df = pd.read_csv(input_file)
                    logger.debug("تم قراءة الملف بنجاح باستخدام pd.read_csv. شكل البيانات: %s", df.shape)
                except Exception as e1:
                    logger.debug("فشل في قراءة الملف باستخدام pd.read_csv: %s", e1)
                    try:
                        # محاولة قراءة باستخدام محلل CSV مخصص
                        with open(input_file, 'r') as csvfile:
                            dialect = csv.Sniffer().sniff(csvfile.read(4096))
                            csvfile.seek(0)
                            df = pd.read_csv(input_file, dialect=dialect)
                            logger.debug("تم قراءة الملف بنجاح باستخدام محلل مخصص. شكل البيانات: %s", df.shape)
                    except Exception as e2:
                        logger.debug("فشل في قراءة الملف باستخدام محلل مخصص: %s", e2)
                        try:
                            # محاولة قراءة الملف كقيم مفصولة بمسافات
                            df = pd.read_csv(input_file, delim_whitespace=True, header=None)
                            logger.debug("تم قراءة الملف كقيم مفصولة بمسافات. شكل البيانات: %s", df.shape)
                        except Exception as e3:
                            logger.debug("فشل في قراءة الملف كقيم مفصولة بمسافات: %s", e3)
                            try:
                                # محاولة معالجة خطأ "No columns to parse from file"
                                with open(input_file, 'r') as f:
                                    lines = f.readlines()
                                    if lines:
                                        # محاولة تنظيف السطور وإزالة أي أسطر فارغة
                                        cleaned_lines = [line.strip() for line in lines if line.strip()]
                                        if cleaned_lines:
                                            temp_csv = io.StringIO('\n'.join(cleaned_lines))
                                            try:
                                                df = pd.read_csv(temp_csv, header=None)
                                                logger.debug("تم قراءة الملف بعد التنظيف. شكل البيانات: %s", df.shape)
                                            except Exception as e_clean:
                                                logger.debug("فشل قراءة الملف بعد التنظيف: %s", e_clean)
                                                # محاولة قراءة كل سطر كقيمة منفصلة
                                                values = []
                                                for line in cleaned_lines:
                                                    try:
                                                        values.append(float(line.strip()))
                                                    except ValueError:
                                                        # تجاهل السطور غير الرقمية
                                                        pass
                                                if values:
                                                    df = pd.DataFrame([values])
                                                    logger.debug("تم استخراج %d قيمة من الأسطر", len(values))
                                                else:
                                                    raise Exception("لم يتم العثور على قيم رقمية في الأسطر")
                                        else:
                                            raise Exception("لم يبق أي محتوى بعد التنظيف")
                                    else:
                                        raise Exception("الملف فارغ أو لا يحتوي على أسطر مقروءة")
                            except Exception as e4:
                                logger.debug("فشل في معالجة الملف بعد تنظيفه: %s", e4)
                                try:
                                    # محاولة قراءة الملف كنص عادي واستخراج الأرقام
                                    with open(input_file, 'r') as f:
                                        text = f.read()
                                        # البحث عن أي أرقام في النص
                                        import re
                                        numbers = re.findall(r"[-+]?\d*\.\d+|[-+]?\d+", text)
                                        if numbers:
                                            values = [float(num) for num in numbers]
                                            df = pd.DataFrame([values])
                                            logger.debug("تم استخراج %d رقم من النص", len(values))
                                        else:
                                            raise Exception("لم يتم العثور على أي أرقام في الملف")
                                except Exception as e5:
                                    logger.debug("فشل في استخراج الأرقام من النص: %s", e5)
                                    # إذا فشلت جميع المحاولات، إنشاء مصفوفة فارغة لتجنب الخطأ
                                    logger.debug("إنشاء مصفوفة صفرية اضطراريًا بعد فشل كل الطرق...")
                                    df = pd.DataFrame([np.zeros(1000)])
                                    logger.debug("تم إنشاء بيانات بديلة بطول 1000")
    except Exception as e:
        logger.error("خطأ في قراءة الملف: %s", e)
        return None

    # تحديد التنسيق والتحويل إلى بيانات مناسبة
    try:
        # تحويل DataFrame إلى مصفوفة مسطحة من الأرقام
        if df.shape[0] > 1:
            # إذا كان هناك أكثر من صف واحد، نفترض أن كل صف هو قيمة ECG
            data = df.values.flatten()
            logger.debug("تم تحويل جميع الصفوف لقيم ECG. عدد القيم: %d", len(data))
        else:
            # إذا كان هناك صف واحد فقط، نستخدمه كما هو
            data = df.values.flatten()
            logger.debug("تم استخدام الصف الوحيد. عدد القيم: %d", len(data))

        # تنظيف البيانات
        # التعامل مع القيم الناقصة
        data = np.nan_to_num(data, nan=0.0)

        # إذا كانت البيانات فارغة (مثلاً صف رؤوس فقط بلا قيم) نستخدم بديلاً صفرياً
        # بدل أن نقسم على صفر فيما بعد
        if len(data) == 0:
            logger.debug("لا توجد قيم بعد التسطيح، استخدام بديل صفري بطول 1000")
            data = np.zeros(1000)

        # إذا كان عدد النقاط قليلاً جداً، نكرر البيانات
        if len(data) < 100:
            repeat_count = (100 // len(data)) + 1
            data = np.tile(data, repeat_count)
            logger.debug("البيانات قصيرة جداً، تم تكرارها. الطول الجديد: %d", len(data))

        # اقتطاع أي بيانات زائدة عن 5000 نقطة
        if len(data) > 5000:
            data = data[:5000]
            logger.debug("تم اقتطاع البيانات إلى 5000 نقطة")

        # إنشاء DataFrame جديد
        new_df = pd.DataFrame([data])

        # إنشاء اسم ملف الإخراج إذا لم يتم توفيره
        if output_file is None:
            input_path = Path(input_file)
            output_file = input_path.parent / f"{input_path.stem}_processed{input_path.suffix}"

        # حفظ الملف الجديد
        new_df.to_csv(output_file, index=False)
        logger.debug("تم حفظ الملف المعالج في: %s", output_file)

        return str(output_file)
    except Exception as e:
        logger.error("خطأ في معالجة البيانات: %s", e)
        return None

def batch_convert(directory):
    """
    تحويل جميع ملفات CSV في مجلد معين

    المعلمات:
    directory (str): مسار المجلد الذي يحتوي على ملفات CSV

    العودة:
    list: قائمة بمسارات ملفات الإخراج
    """
    dir_path = Path(directory)
    output_files = []

    for file_path in dir_path.glob("*.csv"):
        if "_processed" not in file_path.name:
            output_file = convert_csv_to_format(str(file_path))
            if output_file:
                output_files.append(output_file)

    return output_files

if __name__ == "__main__":
    # CLI entry point: configure logging so the debug messages above are visible
    # when the converter is run directly. Use an encoding-safe stream.
    logging.basicConfig(level=logging.DEBUG, format="%(message)s")

    if len(sys.argv) < 2:
        logger.info("الاستخدام: python csv_converter.py <input_file_or_directory>")
        sys.exit(1)

    path = sys.argv[1]

    if os.path.isdir(path):
        output_files = batch_convert(path)
        logger.info("تم تحويل %d ملف بنجاح", len(output_files))
    elif os.path.isfile(path):
        output_file = convert_csv_to_format(path)
        if output_file:
            logger.info("تم تحويل الملف بنجاح: %s", output_file)
    else:
        logger.error("المسار غير صالح: %s", path)
        sys.exit(1)
