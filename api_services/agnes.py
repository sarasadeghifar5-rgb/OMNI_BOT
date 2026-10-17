"""
Agnes AI client for:
1. Nano chat models (agnes-3.0-flash, agnes-2.5-pro)
2. Nano image generation (agnes-image-2.5-flash)
3. Nano image editing (image-to-image with agnes-image-2.5-flash)
4. Nano video generation (agnes-video-2.5-flash / agnes-video-2.5)
5. Photo animation / Image-to-Video keyframe control
Includes KeyPool with 10 rotating API keys.
"""
import asyncio
import httpx
import logging
import base64
from typing import List, Dict, Optional, Tuple, Any
from config import AGNES_BASE_URL, AGNES_API_KEYS, AGNES_IMAGE_MODEL, AGNES_VIDEO_MODEL
from api_services.key_pool import KeyPool
from utils.system_prompt import MASTER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

class AgnesClient:
    def __init__(self, base_url: str = AGNES_BASE_URL, keys: List[str] = AGNES_API_KEYS):
        self.base_url = base_url.rstrip("/")
        self.root_url = self.base_url.rsplit("/v1", 1)[0]
        self.pool = KeyPool("Agnes AI", keys, cooldown_seconds=45)

    async def generate_chat_response(
        self,
        model: str = "agnes-3.0-flash",
        messages: List[Dict[str, str]] = None,
        temperature: float = 0.5,
        max_tokens: int = 4096
    ) -> str:
        """Call Agnes AI chat completions endpoint with key rotation."""
        url = f"{self.base_url}/chat/completions"
        full_messages = [{"role": "system", "content": MASTER_SYSTEM_PROMPT}]
        if messages:
            for m in messages:
                if m.get("role") != "system":
                    full_messages.append({"role": m["role"], "content": m["content"]})

        payload = {
            "model": model,
            "messages": full_messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        attempts = min(3, len(self.pool.keys))
        last_error = ""

        async with httpx.AsyncClient(timeout=45.0) as client:
            for _ in range(attempts):
                api_key = self.pool.get_key()
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                try:
                    res = await client.post(url, headers=headers, json=payload)
                    if res.status_code == 200:
                        self.pool.report_success(api_key)
                        data = res.json()
                        choices = data.get("choices", [])
                        if choices:
                            return choices[0]["message"]["content"].strip()
                        return "پاسخی دریافت نشد."
                    elif res.status_code in (429, 401, 403):
                        self.pool.report_failure(api_key, res.status_code)
                        last_error = f"کد خطا {res.status_code}"
                        continue
                    else:
                        self.pool.report_failure(api_key, res.status_code)
                        last_error = f"کد خطا {res.status_code}: {res.text[:100]}"
                except Exception as e:
                    self.pool.report_failure(api_key)
                    last_error = str(e)

        return f"خطا در ارتباط با مدل نانو اگنس: {last_error}"

    async def generate_image(
        self,
        prompt: str,
        size: str = "1024x1024",
        model: str = AGNES_IMAGE_MODEL
    ) -> Tuple[bool, str]:
        """
        Generate image from text prompt using Agnes Image models.
        Returns: (success: bool, url_or_error_message: str)
        """
        url = f"{self.base_url}/images/generations"
        payload = {
            "model": model,
            "prompt": prompt,
            "n": 1,
            "size": size,
            "extra_body": {
                "response_format": "url"
            }
        }

        attempts = min(7, len(self.pool.keys))
        last_error = ""

        async with httpx.AsyncClient(timeout=70.0) as client:
            for _ in range(attempts):
                api_key = self.pool.get_key()
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }

                try:
                    res = await client.post(url, headers=headers, json=payload)
                    if res.status_code == 200:
                        self.pool.report_success(api_key)
                        data = res.json()
                        img_list = data.get("data", [])
                        if img_list and "url" in img_list[0]:
                            return True, img_list[0]["url"]
                        return False, "تصویر تولید شد اما آدرس آن بازگردانده نشد."
                    elif res.status_code == 503 and "queue is full" in res.text:
                        self.pool.report_failure(api_key, 503)
                        await asyncio.sleep(1.0)
                        continue
                    elif res.status_code in (429, 401, 403):
                        self.pool.report_failure(api_key, res.status_code)
                        last_error = f"محدودیت یا خطای کلید ({res.status_code})"
                        continue
                    else:
                        self.pool.report_failure(api_key, res.status_code)
                        last_error = f"خطای سرور اگنس (کد {res.status_code}): {res.text[:120]}"
                except httpx.TimeoutException:
                    self.pool.report_failure(api_key, 408)
                    last_error = "زمان ساخت تصویر به پایان رسید (Timeout)"
                except Exception as e:
                    self.pool.report_failure(api_key)
                    last_error = str(e)

        return False, f"متأسفانه در تولید تصویر مشکلی پیش آمد: {last_error}"

    async def edit_image(
        self,
        image_bytes: bytes,
        prompt: str,
        size: str = "1024x1024",
        mime_type: str = "image/jpeg",
        model: str = AGNES_IMAGE_MODEL
    ) -> Tuple[bool, str]:
        """Edit a single image."""
        return await self.edit_multiple_images(
            images_bytes_list=[image_bytes],
            prompt=prompt,
            size=size,
            mime_type=mime_type,
            model=model
        )

    async def edit_multiple_images(
        self,
        images_bytes_list: List[bytes],
        prompt: str,
        size: str = "1024x1024",
        mime_type: str = "image/jpeg",
        model: str = AGNES_IMAGE_MODEL
    ) -> Tuple[bool, str]:
        """
        Edit or combine multiple images based on prompt instruction (Multi-image Composition).
        Accepts a list of image bytes and sends extra_body.image = [uri1, uri2, ...].
        Returns: (success: bool, url_or_error_message: str)
        """
        url = f"{self.base_url}/images/generations"
        image_uris = []
        for b in images_bytes_list:
            b64 = base64.b64encode(b).decode("utf-8")
            image_uris.append(f"data:{mime_type};base64,{b64}")

        payload = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "extra_body": {
                "image": image_uris,
                "response_format": "url"
            }
        }

        attempts = min(8, len(self.pool.keys))
        last_error = ""

        async with httpx.AsyncClient(timeout=80.0) as client:
            for _ in range(attempts):
                api_key = self.pool.get_key()
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }

                try:
                    res = await client.post(url, headers=headers, json=payload)
                    if res.status_code == 200:
                        self.pool.report_success(api_key)
                        data = res.json()
                        img_list = data.get("data", [])
                        if img_list and "url" in img_list[0]:
                            return True, img_list[0]["url"]
                        return False, "تصویر ویرایش شد اما آدرس آن بازگردانده نشد."
                    elif res.status_code == 503 and "queue is full" in res.text:
                        self.pool.report_failure(api_key, 503)
                        await asyncio.sleep(1.0)
                        continue
                    elif res.status_code in (429, 401, 403):
                        self.pool.report_failure(api_key, res.status_code)
                        continue
                    else:
                        self.pool.report_failure(api_key, res.status_code)
                        last_error = f"کد خطا {res.status_code}: {res.text[:120]}"
                except httpx.TimeoutException:
                    self.pool.report_failure(api_key, 408)
                    last_error = "زمان ویرایش تصویر به پایان رسید (Timeout)"
                except Exception as e:
                    self.pool.report_failure(api_key)
                    last_error = str(e)

        return False, f"متأسفانه در ویرایش تصویر مشکلی پیش آمد: {last_error or 'شلوغی موقت سرورها'}"

    async def generate_video(
        self,
        prompt: str,
        seconds: str = "5",
        size: str = "720P",
        aspect_ratio: str = "16:9",
        model: str = "agnes-video-2.5-flash",
        max_poll_seconds: int = 180
    ) -> Tuple[bool, str]:
        """
        Create text-to-video generation task and poll until complete.
        Returns: (success: bool, video_url_or_message: str)
        """
        return await self._create_and_poll_video(
            payload={
                "model": model,
                "prompt": prompt,
                "mode": "text",
                "seconds": str(seconds),
                "size": size,
                "aspect_ratio": aspect_ratio
            },
            model_name=model,
            max_poll_seconds=max_poll_seconds
        )

    async def animate_image(
        self,
        image_bytes: bytes,
        prompt: str = "Smooth natural cinematic movement, subtle animation",
        seconds: str = "5",
        mime_type: str = "image/jpeg",
        model: str = "agnes-video-2.5-flash",
        max_poll_seconds: int = 180
    ) -> Tuple[bool, str]:
        """
        Animate an image into a video clip (Image-to-Video / Keyframe control).
        Returns: (success: bool, video_url_or_message: str)
        """
        img_b64 = base64.b64encode(image_bytes).decode("utf-8")
        data_uri = f"data:{mime_type};base64,{img_b64}"

        payload = {
            "model": model,
            "prompt": prompt,
            "mode": "keyframe",
            "first_frame": data_uri,
            "seconds": str(seconds),
            "size": "720P",
            "aspect_ratio": "16:9"
        }

        return await self._create_and_poll_video(
            payload=payload,
            model_name=model,
            max_poll_seconds=max_poll_seconds
        )

    async def _create_and_poll_video(
        self,
        payload: Dict[str, Any],
        model_name: str,
        max_poll_seconds: int = 180
    ) -> Tuple[bool, str]:
        """Common helper to submit video task and poll result."""
        url = f"{self.base_url}/videos"
        attempts = min(8, len(self.pool.keys))
        video_id = None
        used_key = None
        queue_full_encountered = False
        quota_encountered = False

        async with httpx.AsyncClient(timeout=45.0) as client:
            for _ in range(attempts):
                api_key = self.pool.get_key()
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }

                try:
                    res = await client.post(url, headers=headers, json=payload)
                    data = res.json()

                    if res.status_code == 200 or "video_id" in data or "task_id" in data:
                        self.pool.report_success(api_key)
                        video_id = data.get("video_id") or data.get("task_id") or data.get("id")
                        used_key = api_key
                        break
                    elif res.status_code == 503 and "queue" in res.text:
                        queue_full_encountered = True
                        self.pool.report_failure(api_key, 503)
                        await asyncio.sleep(1.0)
                        continue
                    elif res.status_code == 403 and "insufficient_user_quota" in res.text:
                        quota_encountered = True
                        self.pool.report_failure(api_key, 403)
                        continue
                    elif res.status_code in (429, 401, 403):
                        self.pool.report_failure(api_key, res.status_code)
                        continue
                    else:
                        self.pool.report_failure(api_key, res.status_code)
                except Exception as e:
                    self.pool.report_failure(api_key)
                    logger.error(f"Video request error: {e}")

            if not video_id:
                if queue_full_encountered:
                    return False, (
                        "⚠️ صف پردازش سرورهای ویدیویی Agnes AI در حال حاضر پر می‌باشد (Video Queue Full).\n"
                        "لطفاً چند دقیقه دیگر مجدداً درخواست خود را ارسال فرمایید."
                    )
                if quota_encountered:
                    return False, (
                        "⚠️ **سهمیه تولید ویدیو Agnes AI:**\n\n"
                        "حساب‌های متصل نیازمند شارژ پلن ویدیو هستند.\n"
                        "💡 بخش **🎨 ساخت عکس** و **✏️ ادیت عکس** هم‌اکنون به طور کاملاً نامحدود و رایگان در دسترس است!"
                    )
                return False, "امکان ایجاد تسک ویدیویی در سرور اگنس میسر نشد. لطفاً مجدداً تلاش کنید."

            # Polling
            poll_url = f"{self.root_url}/agnesapi"
            poll_headers = {"Authorization": f"Bearer {used_key}"}
            start_time = asyncio.get_event_loop().time()

            while (asyncio.get_event_loop().time() - start_time) < max_poll_seconds:
                await asyncio.sleep(4.0)
                try:
                    poll_res = await client.get(
                        poll_url,
                        params={"video_id": video_id, "model_name": model_name},
                        headers=poll_headers,
                        timeout=20.0
                    )
                    if poll_res.status_code == 200:
                        poll_data = poll_res.json()
                        status = poll_data.get("status", "").lower()
                        if status in ("completed", "success"):
                            video_url = poll_data.get("url") or poll_data.get("video_url")
                            if video_url:
                                return True, video_url
                        elif status in ("failed", "error"):
                            err_msg = poll_data.get("error_message") or poll_data.get("message", "خطای تولید ویدیو")
                            return False, f"تولید ویدیو با خطا مواجه شد: {err_msg}"
                except Exception as poll_e:
                    logger.warning(f"Polling error for video {video_id}: {poll_e}")

            return False, "تولید ویدیو بیش از حد مجاز طول کشید (Timeout). ممکن است تسک در صف سرور قرار داشته باشد."

    async def generate_vision_response(
        self,
        image_bytes: bytes,
        prompt: str = "این تصویر را به دقت بررسی و تحلیل کن و به زبان فارسی توضیح بده.",
        mime_type: str = "image/jpeg",
        model: str = "agnes-3.0-flash",
        temperature: float = 0.5,
        max_tokens: int = 4096
    ) -> Optional[str]:
        """
        Multimodal vision analysis using Agnes AI models (agnes-3.0-flash / agnes-3.0-flash-max).
        Supports full base64 image input with master system prompt and key rotation.
        """
        url = f"{self.base_url}/chat/completions"
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:{mime_type};base64,{b64}"

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": MASTER_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}}
                    ]
                }
            ],
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        attempts = min(5, len(self.pool.keys))
        last_error = ""

        async with httpx.AsyncClient(timeout=45.0) as client:
            for _ in range(attempts):
                api_key = self.pool.get_key()
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                try:
                    res = await client.post(url, headers=headers, json=payload)
                    if res.status_code == 200:
                        self.pool.report_success(api_key)
                        data = res.json()
                        choices = data.get("choices", [])
                        if choices:
                            return choices[0]["message"]["content"].strip()
                        return "پاسخی دریافت نشد."
                    elif res.status_code in (429, 401, 403):
                        self.pool.report_failure(api_key, res.status_code)
                        continue
                    else:
                        self.pool.report_failure(api_key, res.status_code)
                        last_error = f"کد خطا {res.status_code}"
                except httpx.TimeoutException:
                    self.pool.report_failure(api_key, 408)
                    last_error = "Timeout"
                except Exception as e:
                    self.pool.report_failure(api_key)
                    last_error = str(e)

        logger.warning(f"Agnes vision failed: {last_error}")
        return None

# Global instance
agnes_client = AgnesClient()
