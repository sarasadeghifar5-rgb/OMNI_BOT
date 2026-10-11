import os
import io
import base64
import logging
from typing import Dict, Any, Optional, Union
import httpx
from PIL import Image

from app.services.agnes_client import AgnesKeyPool, DEFAULT_BASE_URL
from app.services.http_client import get_shared_http_client

logger = logging.getLogger("AgnesImageService")

class AgnesImageService:
    """
    Dedicated client for Agnes AI Image Generation & Editing API.
    Model: agnes-image-2.5-flash
    Features:
      - Text to Image (تولید عکس با پرامپت متنی)
      - Image to Image / Editing (ادیت و تغییر هوشمند عکس با حفظ ترکیب)
      - Multi-aspect ratio (1:1, 16:9, 9:16, 4:3, 3:4, etc.)
      - Resolution tiers (1K, 2K, 3K, 4K)
      - Multi-Key automatic failover pool
    """

    SUPPORTED_RATIOS = ["1:1", "16:9", "9:16", "4:3", "3:4", "2:3", "3:2", "21:9"]
    SUPPORTED_SIZES = ["1K", "2K", "3K", "4K"]

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.base_url = (base_url or os.getenv("AGNES_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.model_name = "agnes-image-2.5-flash"
        self.pool = AgnesKeyPool.get_instance()
        self.override_key = api_key

    @staticmethod
    def optimize_image_to_data_uri(raw_bytes: bytes, max_dimension: int = 1280, quality: int = 85) -> str:
        """
        Optimizes and compresses image bytes to JPEG data URI,
        preventing oversized payloads and network timeouts.
        """
        try:
            img = Image.open(io.BytesIO(raw_bytes))
            # Handle alpha channel / transparencies
            if img.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "RGBA":
                    background.paste(img, mask=img.split()[3])
                else:
                    background.paste(img.convert("RGB"))
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")

            # Resize if dimensions exceed threshold
            w, h = img.size
            if max(w, h) > max_dimension:
                scale = max_dimension / max(w, h)
                new_w, new_h = int(w * scale), int(h * scale)
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            output_io = io.BytesIO()
            img.save(output_io, format="JPEG", quality=quality, optimize=True)
            encoded = base64.b64encode(output_io.getvalue()).decode("utf-8")
            return f"data:image/jpeg;base64,{encoded}"
        except Exception as e:
            logger.error(f"Error optimizing image bytes: {e}")
            encoded = base64.b64encode(raw_bytes).decode("utf-8")
            return f"data:image/png;base64,{encoded}"

    async def generate_image(
        self,
        prompt: str,
        size: str = "1K",
        ratio: str = "1:1",
        timeout: float = 120.0
    ) -> Dict[str, Any]:
        """
        Generates an image from natural language prompt using Agnes Image 2.5 Flash.
        """
        if not prompt or not prompt.strip():
            return {"success": False, "error": "متن پرامپت خالی است."}

        size = size if size in self.SUPPORTED_SIZES else "1K"
        ratio = ratio if ratio in self.SUPPORTED_RATIOS else "1:1"

        payload = {
            "model": self.model_name,
            "prompt": prompt.strip(),
            "size": size,
            "ratio": ratio,
            "aspect_ratio": ratio,
            "extra_body": {
                "response_format": "url",
                "aspect_ratio": ratio,
                "ratio": ratio
            }
        }

        endpoint = f"{self.base_url}/images/generations"
        keys = [self.override_key] if self.override_key else self.pool.get_active_keys()
        last_error = "هیچ کلید معتبری در دسترس نیست."

        client = get_shared_http_client()
        for key in keys:
            headers = self.pool.get_headers(key)
            self.pool.acquire_key(key)
            try:
                response = await client.post(
                    endpoint,
                    headers=headers,
                    json=payload,
                    timeout=httpx.Timeout(timeout, connect=8.0)
                )
                
                if response.status_code == 200:
                    self.pool.record_key_success(key)
                    data = response.json()
                    results = data.get("data", [])
                    if results and results[0].get("url"):
                        img_url = results[0]["url"]
                        task_id = data.get("task_id", "")
                        return {
                            "success": True,
                            "url": img_url,
                            "task_id": task_id,
                            "prompt": prompt,
                            "size": size,
                            "ratio": ratio,
                            "model": self.model_name
                        }
                    return {"success": False, "error": "هیچ لینک خروجی در پاسخ دریافت نشد."}

                elif response.status_code in (403, 429):
                    self.pool.record_key_error(key, response.status_code)
                    last_error = f"محدودیت سهمیه یا نرخ درخواست کلید (کد {response.status_code})"
                    continue
                else:
                    self.pool.record_key_error(key, response.status_code)
                    try:
                        err_json = response.json()
                        err_msg = err_json.get("error", {}).get("message") or response.text
                    except Exception:
                        err_msg = response.text
                    last_error = f"خطا در تولید تصویر (کد {response.status_code}): {err_msg}"
                    continue

            except httpx.TimeoutException:
                self.pool.record_key_error(key, 504)
                last_error = "مهلت زمان درخواست (Timeout) به پایان رسید."
                continue
            except Exception as e:
                self.pool.record_key_error(key, 500)
                last_error = f"خطای پیش‌بینی نشده: {str(e)}"
                continue
            finally:
                self.pool.release_key(key)

        logger.error(f"All Agnes keys exhausted for generation: {last_error}")
        return {"success": False, "error": last_error}

    async def edit_image(
        self,
        image_input: Union[bytes, str],
        prompt: str,
        size: str = "1K",
        ratio: str = "1:1",
        timeout: float = 120.0
    ) -> Dict[str, Any]:
        """
        Edits or transforms an input image based on prompt instructions
        while preserving original layout and composition.
        `image_input` can be raw bytes (downloaded from Telegram) or a public URL/data URI string.
        """
        if not prompt or not prompt.strip():
            return {"success": False, "error": "دستور ویرایش عکس خالی است."}

        # Convert bytes to optimized data URI
        if isinstance(image_input, bytes):
            data_uri = self.optimize_image_to_data_uri(image_input)
        elif isinstance(image_input, str):
            data_uri = image_input.strip()
        else:
            return {"success": False, "error": "فرمت تصویر نامعتبر است."}

        size = size if size in self.SUPPORTED_SIZES else "1K"
        ratio = ratio if ratio in self.SUPPORTED_RATIOS else "1:1"

        payload = {
            "model": self.model_name,
            "prompt": prompt.strip(),
            "size": size,
            "ratio": ratio,
            "aspect_ratio": ratio,
            "extra_body": {
                "image": [data_uri],
                "response_format": "url",
                "aspect_ratio": ratio,
                "ratio": ratio
            }
        }

        endpoint = f"{self.base_url}/images/generations"
        keys = [self.override_key] if self.override_key else self.pool.get_active_keys()
        last_error = "هیچ کلید معتبری در دسترس نیست."

        client = get_shared_http_client()
        for key in keys:
            headers = self.pool.get_headers(key)
            self.pool.acquire_key(key)
            try:
                response = await client.post(
                    endpoint,
                    headers=headers,
                    json=payload,
                    timeout=httpx.Timeout(timeout, connect=8.0)
                )
                
                if response.status_code == 200:
                    self.pool.record_key_success(key)
                    data = response.json()
                    results = data.get("data", [])
                    if results and results[0].get("url"):
                        img_url = results[0]["url"]
                        task_id = data.get("task_id", "")
                        return {
                            "success": True,
                            "url": img_url,
                            "task_id": task_id,
                            "prompt": prompt,
                            "size": size,
                            "ratio": ratio,
                            "model": self.model_name
                        }
                    return {"success": False, "error": "هیچ لینک خروجی در پاسخ ادیت دریافت نشد."}

                elif response.status_code in (403, 429):
                    self.pool.record_key_error(key, response.status_code)
                    last_error = f"محدودیت سهمیه یا نرخ درخواست کلید (کد {response.status_code})"
                    continue
                else:
                    self.pool.record_key_error(key, response.status_code)
                    try:
                        err_json = response.json()
                        err_msg = err_json.get("error", {}).get("message") or response.text
                    except Exception:
                        err_msg = response.text
                    last_error = f"خطا در ادیت تصویر (کد {response.status_code}): {err_msg}"
                    continue

            except httpx.TimeoutException:
                self.pool.record_key_error(key, 504)
                last_error = "مهلت زمان ادیت تصویر به پایان رسید."
                continue
            except Exception as e:
                self.pool.record_key_error(key, 500)
                last_error = f"خطای پیش‌بینی نشده: {str(e)}"
                continue
            finally:
                self.pool.release_key(key)

        logger.error(f"All Agnes keys exhausted for edit: {last_error}")
        return {"success": False, "error": last_error}

    async def download_image(self, url: str, timeout: float = 20.0) -> Optional[bytes]:
        """
        Downloads image bytes from URL with connection pooling and DoH fallback.
        """
        client = get_shared_http_client()
        # 1. Attempt standard download with connection reuse
        try:
            res = await client.get(url, timeout=httpx.Timeout(timeout, connect=5.0))
            if res.status_code == 200 and len(res.content) > 100:
                return res.content
        except Exception as e:
            logger.warning(f"Standard image download failed for {url}: {e}. Trying DoH/Direct-IP fallback...")

        # 2. Attempt DoH and Direct IP fallback for DNS-poisoned endpoints
        try:
            import urllib.parse
            parsed = urllib.parse.urlparse(url)
            hostname = parsed.hostname or ""

            ips = []
            if "agnes-ai.cn" in hostname or "myqcloud.com" in hostname:
                ips.extend(["119.45.110.19", "119.45.110.23"])

            for doh_url in [
                f"https://1.1.1.1/dns-query?name={hostname}&type=A",
                f"https://dns.google/resolve?name={hostname}&type=A"
            ]:
                try:
                    d_resp = await client.get(
                        doh_url,
                        headers={"accept": "application/dns-json"},
                        timeout=httpx.Timeout(2.5, connect=1.5)
                    )
                    if d_resp.status_code == 200:
                        for ans in d_resp.json().get("Answer", []):
                            ip = ans.get("data")
                            if ans.get("type") == 1 and ip and ip != "0.0.0.1" and ip not in ips:
                                ips.append(ip)
                    if ips:
                        break
                except Exception:
                    pass

            for ip in ips:
                try:
                    direct_url = url.replace(f"://{hostname}", f"://{ip}")
                    res = await client.get(
                        direct_url,
                        headers={"Host": hostname},
                        timeout=httpx.Timeout(timeout, connect=4.0)
                    )
                    if res.status_code == 200 and len(res.content) > 100:
                        logger.info(f"Image downloaded successfully via IP {ip} ({len(res.content)} bytes)")
                        return res.content
                except Exception as ex:
                    logger.warning(f"Fallback image download via IP {ip} failed: {ex}")
        except Exception as e2:
            logger.error(f"Error in fallback image download: {e2}")

        return None
