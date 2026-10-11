import io
import base64
import logging
from typing import Dict, Any, Optional
import pypdf

logger = logging.getLogger("DocumentService")


class DocumentService:
    """
    Handles parsing and content extraction for documents (PDF, TXT, CSV, Code, etc.)
    with multi-tier intelligence for LLM analysis.
    """

    MAX_TEXT_CHARS = 150_000  # ~35k tokens limit to prevent context overflow

    @staticmethod
    def extract_text_from_pdf(file_bytes: bytes) -> Dict[str, Any]:
        """
        Extracts structured text page-by-page from PDF bytes.
        """
        try:
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            total_pages = len(reader.pages)
            pages_text = []

            for idx, page in enumerate(reader.pages):
                try:
                    text = page.extract_text() or ""
                    clean = text.strip()
                    if clean:
                        pages_text.append(f"--- [صفحه {idx + 1}] ---\n{clean}")
                except Exception as pe:
                    logger.warning(f"Error extracting page {idx + 1}: {pe}")

            combined_text = "\n\n".join(pages_text)

            is_scanned = len(combined_text.strip()) < 50 and total_pages > 0

            return {
                "success": True,
                "total_pages": total_pages,
                "text": combined_text[:DocumentService.MAX_TEXT_CHARS],
                "char_count": len(combined_text),
                "is_scanned": is_scanned,
                "is_truncated": len(combined_text) > DocumentService.MAX_TEXT_CHARS,
            }
        except Exception as e:
            logger.error(f"Failed to parse PDF: {e}")
            return {
                "success": False,
                "total_pages": 0,
                "text": "",
                "char_count": 0,
                "is_scanned": True,
                "error": str(e)
            }

    @staticmethod
    def extract_text_from_plain(file_bytes: bytes) -> Dict[str, Any]:
        """
        Decodes plain text, code, CSV, JSON, Markdown with encoding fallbacks.
        """
        encodings = ["utf-8", "utf-8-sig", "windows-1256", "cp1252", "latin1"]
        for enc in encodings:
            try:
                decoded = file_bytes.decode(enc)
                return {
                    "success": True,
                    "text": decoded[:DocumentService.MAX_TEXT_CHARS],
                    "char_count": len(decoded),
                    "is_truncated": len(decoded) > DocumentService.MAX_TEXT_CHARS,
                }
            except UnicodeDecodeError:
                continue

        return {
            "success": False,
            "text": "",
            "char_count": 0,
            "error": "عدم شناسایی کدگذاری کاراکترها"
        }

    @staticmethod
    def to_pdf_data_uri(file_bytes: bytes) -> str:
        """Encodes PDF as base64 data URI for native Gemini multimodal PDF ingestion."""
        b64 = base64.b64encode(file_bytes).decode("utf-8")
        return f"data:application/pdf;base64,{b64}"

    @staticmethod
    def format_analysis_prompt(file_name: str, extracted_text: str, user_query: str, total_pages: int = 1) -> str:
        has_custom_query = bool(user_query and user_query.strip())

        if has_custom_query:
            task_instruction = f"درخواست و دستور کاربر درباره این سند:\n«{user_query.strip()}»"
        else:
            task_instruction = (
                "دستور کار: لطفاً این سند را به صورت جامع، دقیق و بسیار شکیل و ساختاریافته تحلیل و معرفی نمایید:\n"
                "• شناسنامه و مشخصات سند (عنوان سند، موسسه/دانشگاه، درس/موضوع، تاریخ، اساتید یا طرفین سند)\n"
                "• موضوع، هدف اصلی و خلاصه اجمالی محتوا\n"
                "• تحلیل و دسته‌بندی مباحث کلیدی، بخش‌ها یا سوالات/مسائل مطرح‌شده به تفکیک\n"
                "• نکات کلیدی و جمع‌بندی نهایی"
            )

        formatting_rules = (
            "⚠️ دستورالعمل‌های حیاتی نگارش و قالب‌بندی (پاسخ برای نمایش در پیام‌رسان تلگرام است):\n"
            "۱. پاکیزگی ظاهری و نگارش: پاسخ را به زبان فارسی شیوا، رسا و منظم با رعایت نیم‌فاصله‌ها بنویسید. از نشانه‌های تمیز و یکدست (مانند ▫️ یا ▪️) برای بالت‌پوینت‌ها استفاده کنید.\n"
            "۲. محاسبات و فرمول‌های ریاضی: اگر سند یا درخواست شامل حل مسئله، تمرین یا روابط ریاضی است، مراحل محاسبه را بسیار تمیز، زیبا و گام‌به‌گام تفکیک کنید (مانند: ▫️ گام ۱: فرمول پایه | ▫️ گام ۲: جایگذاری و ساده‌سازی | 🎯 پاسخ نهایی). روابط ریاضی را با نمادهای خوانای یونیکد (مانند توان‌های ², ³, اندیس‌ها ₁, ₂, مشتقات ∂z/∂x, انتگرال ∫, رادیکال √, ضرب · یا ×) یا در کدهای خطی بنویسید و از به کار بردن کدهای خام و ناخوانای لاتک با علامت دلار ($...$) اکیداً پرهیز فرمایید.\n"
            "۳. عدم استفاده از جدول مارک‌داون: از ساخت جدول‌های لوله‌ای با علامت | اکیداً خودداری کنید (زیرا در صفحه موبایل تلگرام به هم می‌ریزند). در صورت نیاز به نمایش داده‌های جدولی، آنها را به شکل کارت‌های خوانا یا لیست‌های کلید-مقدار (مثلاً 🔹 نام فیلد: مقدار) ساختاربندی کنید.\n"
            "۴. عناوین شکیل: برای بخش‌های اصلی از عناوین جذاب با ایموجی‌های مناسب (📌، 📋، 🎯، 🔍، 💡) استفاده کنید و از تو در تو کردن بیش از حد تیترها پرهیز نمایید."
        )

        return (
            f"📄 [سند ارسالی]: «{file_name}» ({total_pages} صفحه)\n\n"
            f"--- متن استخراج‌شده از سند ---\n"
            f"{extracted_text}\n"
            f"--- پایان متن سند ---\n\n"
            f"{task_instruction}\n\n"
            f"{formatting_rules}"
        )
