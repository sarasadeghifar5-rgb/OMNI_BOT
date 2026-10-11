"""
===================================================================
🍌 اسکریپت تولید تصویر با مدل‌های Google Nano Banana از طریق Puter AI
کاملاً رایگان و با کیفیت فوق‌العاده بالا
===================================================================

نحوه استفاده سریع:
  python generate_banana.py "یک فضانورد در حال قدم زدن روی سطح مریخ"
  python generate_banana.py "A futuristic flying car in neon Tokyo" --model nano-banana-pro --ratio 16:9
"""

import sys
import os
import argparse
import asyncio
import time
from pathlib import Path
from dotenv import load_dotenv

# حل مشکل انکودینگ کاراکترهای فارسی و اموجی در کنسول ویندوز
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# بارگذاری متغیرهای محیطی از .env
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

sys.path.insert(0, str(BASE_DIR))

from app.services.puter_image import PuterImageService

OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


async def main():
    parser = argparse.ArgumentParser(description="🍌 Google Nano Banana Image Generator via Puter AI")
    parser.add_argument("prompt", nargs="?", help="متن یا توصیف تصویر مورد نظر (فارسی یا انگلیسی)")
    parser.add_argument(
        "--model", "-m",
        choices=["nano-banana", "nano-banana-2", "nano-banana-pro", "sdxl-lightning"],
        default="nano-banana",
        help="مدل هوش مصنوعی (پیش‌فرض: nano-banana)"
    )
    parser.add_argument(
        "--ratio", "-r",
        choices=["1:1", "16:9", "9:16", "4:3", "21:9"],
        default="1:1",
        help="نسبت ابعاد تصویر (پیش‌فرض: 1:1)"
    )
    parser.add_argument(
        "--res",
        choices=["1K", "2K", "4K"],
        default="1K",
        help="رزولوشن خروجی برای Nano Banana 2 و Pro (پیش‌فرض: 1K)"
    )
    parser.add_argument("--token", "-t", help="توکن اختصاصی Puter JWT (اختیاری)")
    parser.add_argument("--no-open", action="store_true", help="عدم باز کردن خودکار تصویر پس از تولید")

    args = parser.parse_args()

    prompt = args.prompt
    if not prompt:
        print("=" * 60)
        print("🍌 به استودیوی تصویرسازی Google Nano Banana خوش آمدید!")
        print("=" * 60)
        prompt = input("لطفاً توصیف تصویر مورد نظر خود را بنویسید:\n> ").strip()

    if not prompt:
        print("❌ متن پرامپت خالی است. عملیات لغو شد.")
        return

    print()
    print(f"🎨 پرامپت دریافتی: {prompt}")
    print(f"🤖 مدل انتخابی: {args.model}")
    print(f"📐 نسبت ابعاد: {args.ratio} | رزولوشن: {args.res}")
    print("⏳ در حال ارسال به Puter AI و تولید تصویر با کیفیت بالا... لطفاً شکیبا باشید.")
    
    start_time = time.time()

    res = await PuterImageService.generate_image(
        prompt=prompt,
        model=args.model,
        aspect_ratio=args.ratio,
        resolution=args.res,
        user_token=args.token
    )

    duration = round(time.time() - start_time, 1)

    if res.get("status") == "success" and res.get("image_url"):
        img_url = res["image_url"]
        
        # اگر آدرس وب محلی است، مسیر مطلق فایل را پیدا کنیم
        local_file_path = None
        if img_url.startswith("/static/generated/"):
            rel_path = img_url.replace("/static/generated/", "")
            full_path = BASE_DIR / "app" / "static" / "generated" / rel_path
            if full_path.exists():
                local_file_path = full_path
                # یک کپی هم در پوشه output قرار می‌دهیم
                dest = OUTPUT_DIR / rel_path
                try:
                    dest.write_bytes(full_path.read_bytes())
                    local_file_path = dest
                except Exception:
                    pass

        print()
        print("=" * 60)
        print(f"✅ تصویر با موفقیت در {duration} ثانیه تولید شد!")
        print(f"🏷️ مدل: {res.get('model_name', args.model)}")
        if local_file_path and local_file_path.exists():
            print(f"📁 ذخیره در دیسک: {local_file_path.resolve()}")
        print(f"🌐 لینک تصویر: {img_url}")
        print("=" * 60)

        # باز کردن تصویر در ویندوز به صورت خودکار
        if not args.no_open and local_file_path and local_file_path.exists():
            try:
                os.startfile(str(local_file_path))
            except Exception:
                pass
    else:
        print()
        print("❌ خطا در تولید تصویر:")
        print(res.get("error_message", "خطای ناشناخته در ارتباط با سرور Puter"))


if __name__ == "__main__":
    asyncio.run(main())
