import os
import io
import time
import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable, Awaitable
import httpx

from app.services.agnes_client import AgnesKeyPool, DEFAULT_BASE_URL
from app.services.http_client import get_shared_http_client

logger = logging.getLogger("AgnesVideoService")


class AgnesVideoService:
    """
    Dedicated client for Video & Synchronized Audio-Video Generation.
    Models supported:
      - agnes-video-v2.0 (Active Free tier / ti2vid - proven 100% working)
      - agnes-video-2.5-flash (Modern Free tier / text-to-video & keyframe)
      - agnes-video-2.5 (High-fidelity / Token Plan)
    Features:
      - Text to Video (ساخت ویدیو با پرامپت متنی)
      - Image to Video / Animation (متحرک‌سازی تصویر)
      - Multi-Model fallback cascade & automatic error recovery
      - Live progress polling
      - Multi-Key automatic rotation & failover
    """

    SUPPORTED_RATIOS = ["16:9", "9:16", "1:1", "4:3", "3:4", "21:9"]
    SUPPORTED_SIZES = ["720P", "1080P", "1K", "2K"]
    SUPPORTED_DURATIONS = ["4", "5", "6", "8", "10", "12"]

    RATIO_TO_DIMS = {
        "16:9": (1280, 720),
        "9:16": (720, 1280),
        "1:1": (832, 832),
        "4:3": (1152, 864),
        "3:4": (864, 1152),
        "21:9": (1344, 576),
    }

    def __init__(self, base_url: Optional[str] = None):
        # Always use apihub.agnes-ai.com/v1 for video tasks
        self.base_url = (base_url or os.getenv("AGNES_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        if "api.agnes-ai.com" in self.base_url:
            self.base_url = "https://apihub.agnes-ai.com/v1"
        self.pool = AgnesKeyPool.get_instance()

    def _build_payload_for_model(
        self,
        model_name: str,
        prompt: str,
        mode: str,
        seconds: str,
        size: str,
        aspect_ratio: str,
        first_frame: Optional[str] = None,
        last_frame: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Builds proper schema payload according to model requirements."""
        if model_name == "agnes-video-v2.0":
            w, h = self.RATIO_TO_DIMS.get(aspect_ratio, (1280, 720))
            payload: Dict[str, Any] = {
                "model": "agnes-video-v2.0",
                "prompt": prompt.strip(),
                "mode": "ti2vid",
                "width": w,
                "height": h,
                "aspect_ratio": aspect_ratio,
                "ratio": aspect_ratio,
                "num_frames": 121,
                "frame_rate": 24,
            }
            if first_frame:
                payload["image"] = first_frame
            return payload

        elif model_name == "agnes-video-2.5-flash":
            payload = {
                "model": "agnes-video-2.5-flash",
                "prompt": prompt.strip(),
                "seconds": str(seconds),
                "size": "720P",
                "aspect_ratio": aspect_ratio if aspect_ratio in self.SUPPORTED_RATIOS else "16:9",
                "ratio": aspect_ratio if aspect_ratio in self.SUPPORTED_RATIOS else "16:9",
            }
            if first_frame:
                payload["mode"] = "keyframe"
                payload["first_frame"] = first_frame
                if last_frame:
                    payload["last_frame"] = last_frame
            else:
                payload["mode"] = "text"
            return payload

        else:  # agnes-video-2.5
            payload = {
                "model": "agnes-video-2.5",
                "prompt": prompt.strip(),
                "seconds": str(seconds),
                "size": size if size in self.SUPPORTED_SIZES else "720P",
                "aspect_ratio": aspect_ratio if aspect_ratio in self.SUPPORTED_RATIOS else "16:9",
                "ratio": aspect_ratio if aspect_ratio in self.SUPPORTED_RATIOS else "16:9",
            }
            if first_frame:
                payload["mode"] = "keyframe"
                payload["first_frame"] = first_frame
                if last_frame:
                    payload["last_frame"] = last_frame
            else:
                payload["mode"] = "text"
            return payload

    async def create_video_task(
        self,
        prompt: str,
        mode: str = "text",
        seconds: str = "5",
        size: str = "720P",
        aspect_ratio: str = "16:9",
        first_frame: Optional[str] = None,
        last_frame: Optional[str] = None,
        audio_urls: Optional[List[str]] = None,
        image_urls: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Creates an asynchronous video generation task using a resilient multi-model cascade.
        Tries:
          1. agnes-video-v2.0 (Active Free tier, verified working)
          2. agnes-video-2.5-flash (Modern Free tier, when queue is open)
          3. agnes-video-2.5 (Paid / Token Plan tier)
        Rotates across available keys upon errors.
        """
        if not prompt or not prompt.strip():
            return {"success": False, "error": "متن پرامپت تولید ویدیو خالی است."}

        size = size if size in self.SUPPORTED_SIZES else "720P"
        aspect_ratio = aspect_ratio if aspect_ratio in self.SUPPORTED_RATIOS else "16:9"
        seconds = str(seconds) if str(seconds) in self.SUPPORTED_DURATIONS else "5"

        endpoint = f"{self.base_url}/videos"
        candidate_models = ["agnes-video-2.5-flash", "agnes-video-2.5", "agnes-video-v2.0"]
        last_raw_error = "هیچ کلید معتبری در دسترس نیست."

        for model_candidate in candidate_models:
            payload = self._build_payload_for_model(
                model_name=model_candidate,
                prompt=prompt,
                mode=mode,
                seconds=seconds,
                size=size,
                aspect_ratio=aspect_ratio,
                first_frame=first_frame,
                last_frame=last_frame,
            )

            keys = self.pool.get_active_keys()
            client = get_shared_http_client()
            for key in keys:
                headers = self.pool.get_headers(key)
                self.pool.acquire_key(key)
                try:
                    resp = await client.post(
                        endpoint,
                        headers=headers,
                        json=payload,
                        timeout=httpx.Timeout(25.0, connect=6.0)
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        self.pool.record_key_success(key)
                        video_id = data.get("video_id") or data.get("id") or data.get("task_id")
                        task_id = data.get("id") or data.get("task_id") or video_id
                        logger.info(f"Video task created successfully! Model={model_candidate}, TaskID={task_id}, VideoID={video_id}")
                        return {
                            "success": True,
                            "video_id": video_id,
                            "task_id": task_id,
                            "model_used": model_candidate,
                            "key_used": key,
                            "raw": data,
                        }
                    elif resp.status_code == 503:
                        # Queue full on this model
                        self.pool.record_key_error(key, 503)
                        last_raw_error = "video_queue_full"
                        logger.warning(f"Model {model_candidate} queue full on key {key[-6:]}")
                        break  # Try next model candidate
                    elif resp.status_code == 403:
                        # Paid quota required or forbidden for this model
                        self.pool.record_key_error(key, 403)
                        last_raw_error = "insufficient_user_quota"
                        logger.warning(f"Model {model_candidate} 403 quota error on key {key[-6:]}")
                        break  # Try next model candidate
                    elif resp.status_code == 429:
                        self.pool.record_key_error(key, 429)
                        last_raw_error = "rate_limit_exceeded"
                        continue
                    else:
                        self.pool.record_key_error(key, resp.status_code)
                        last_raw_error = f"{resp.status_code}: {resp.text[:120]}"
                        continue
                except Exception as e:
                    self.pool.record_key_error(key, 500)
                    last_raw_error = str(e)
                    continue
                finally:
                    self.pool.release_key(key)

        # Format user-friendly Persian error message
        friendly_error = self._format_error_message(last_raw_error)
        return {"success": False, "error": friendly_error, "raw_error": last_raw_error}

    def _format_error_message(self, raw_err: str) -> str:
        """Converts raw API error codes to helpful Persian explanations."""
        if "video_queue_full" in raw_err:
            return (
                "⚠️ **صف سرورهای رندر ویدیو در حال حاضر شلوغ است.**\n\n"
                "توضیح: در سرورهای هوش مصنوعی، صف پردازش ویدیو در ساعات پرمصرف موقتاً پر می‌شود (`video queue is full`). "
                "لطفاً ۲ الی ۵ دقیقه دیگر مجدداً تلاش کنید."
            )
        elif "insufficient_user_quota" in raw_err or "403" in raw_err:
            return (
                "⚠️ **محدودیت سهمیه حساب کاربری (اعتبار ویدیویی):**\n\n"
                "توضیح: سرور اعلام کرده که برای این مدل نیاز به سهمیه یا پلن اشتراکی فعال وجود دارد. "
                "سایر مدل‌های رایگان سرور نیز به دلیل ترافیک بالا در دسترس نبودند. لطفاً کمی بعد امتحان کنید."
            )
        elif "rate_limit_exceeded" in raw_err or "429" in raw_err:
            return (
                "⚠️ **محدودیت تعداد درخواست در دقیقه (Rate Limit):**\n\n"
                "سرعت ارسال درخواست‌ها به حداکثر مجاز در دقیقه رسیده است. لطفاً ۱ دقیقه صبر کرده و دوباره دستور دهید."
            )
        return f"خطا در ایجاد تسک ویدیو: {raw_err}"

    async def poll_video_task(
        self,
        video_id: str,
        task_id: Optional[str] = None,
        model_name: Optional[str] = None,
        key: Optional[str] = None,
        max_wait_seconds: int = 300,
        poll_interval: float = 5.0,
        progress_callback: Optional[Callable[[int, str], Awaitable[None]]] = None,
    ) -> Dict[str, Any]:
        """
        Polls until the video is completed or failed.
        Strictly uses the creator API key (`key`) to preserve task ownership.
        """
        keys = [key] if key else self.pool.get_active_keys()
        query_key = keys[0] if keys else None

        if not query_key:
            return {"success": False, "error": "کلیدی برای بررسی وضعیت ویدیو یافت نشد."}

        headers = self.pool.get_headers(query_key)
        start_time = time.time()
        last_reported_progress = -1

        # Use the most direct endpoint based on task_id or video_id.
        # Single endpoint per cycle avoids 429 rate limits.
        primary_endpoint = None
        secondary_endpoint = None

        if task_id:
            primary_endpoint = f"https://apihub.agnes-ai.com/v1/videos/{task_id}"
            if video_id:
                secondary_endpoint = f"https://apihub.agnes-ai.com/agnesapi?video_id={video_id}"
        elif video_id:
            primary_endpoint = f"https://apihub.agnes-ai.com/agnesapi?video_id={video_id}"

        target_endpoint = primary_endpoint
        client = get_shared_http_client()

        while time.time() - start_time < max_wait_seconds:
            try:
                resp = await client.get(
                    target_endpoint,
                    headers=headers,
                    timeout=httpx.Timeout(15.0, connect=5.0)
                )
                if resp.status_code == 200:
                    data = resp.json()
                    status = (data.get("status") or data.get("state") or data.get("internal_status") or "").lower()
                    raw_progress = data.get("progress") or data.get("internal_progress") or 0
                    try:
                        progress = int(raw_progress)
                    except Exception:
                        progress = 0

                    # Compute realistic progress (server progress or time-based smooth estimation up to 92%)
                    elapsed = time.time() - start_time
                    estimated_pct = min(92, int(5 + (elapsed / 120.0) * 87))
                    effective_progress = max(progress, estimated_pct)

                    # Report progress update if changed significantly
                    if progress_callback and effective_progress > last_reported_progress and effective_progress < 100:
                        last_reported_progress = effective_progress
                        try:
                            await progress_callback(effective_progress, f"{int(elapsed)}s / ~2m")
                        except Exception:
                            pass

                    video_url = (
                        data.get("url")
                        or (data.get("data") or {}).get("url")
                        or (data.get("metadata") or {}).get("url")
                    )

                    if status in ("completed", "success") or (progress >= 100 and video_url):
                        if video_url:
                            return {
                                "success": True,
                                "status": "completed",
                                "url": video_url,
                                "raw": data,
                            }

                    elif status in ("failed", "error"):
                        err_msg = data.get("error") or data.get("message") or "تولید ویدیو با خطا متوقف شد."
                        return {
                            "success": False,
                            "status": "failed",
                            "error": str(err_msg),
                        }

                elif resp.status_code == 429:
                    # Rate limit hit: sleep extra without changing keys!
                    logger.warning(f"Agnes API rate limit 429 on task {task_id or video_id}. Backing off 8s...")
                    await asyncio.sleep(8.0)
                    continue

                elif resp.status_code in (400, 404):
                    # If primary endpoint returned 404/400 and we have a secondary endpoint, try switching once
                    if secondary_endpoint and target_endpoint != secondary_endpoint:
                        logger.info(f"Primary endpoint returned {resp.status_code}, trying secondary endpoint {secondary_endpoint}")
                        target_endpoint = secondary_endpoint
                        continue
                    logger.warning(f"Polling {target_endpoint} returned {resp.status_code}: {resp.text[:100]}")

                else:
                    logger.warning(f"Polling {target_endpoint} returned {resp.status_code}")

            except Exception as e:
                logger.warning(f"Error while polling video {task_id or video_id}: {e}")

            await asyncio.sleep(poll_interval)

        return {"success": False, "error": "مدت زمان ساخت ویدیو به پایان رسید (Timeout). لطفا دقایقی دیگر مجددا بررسی فرمایید."}

    async def download_video(self, video_url: str, timeout: float = 35.0) -> Optional[bytes]:
        """
        Downloads generated mp4 video bytes with connection pooling and DNS fallback.
        """
        client = get_shared_http_client()
        # 1. Attempt standard download with connection reuse
        try:
            resp = await client.get(video_url, timeout=httpx.Timeout(timeout, connect=8.0))
            if resp.status_code == 200 and len(resp.content) > 1000:
                return resp.content
        except Exception as e:
            logger.warning(f"Standard download failed for {video_url}: {e}. Trying DoH/Direct-IP fallback...")

        # 2. Attempt DoH and Direct IP fallback for DNS poisoned domains (e.g. Tencent COS .cn)
        try:
            import urllib.parse
            parsed = urllib.parse.urlparse(video_url)
            hostname = parsed.hostname or ""

            ips = []
            if "agnes-ai.cn" in hostname or "myqcloud.com" in hostname:
                ips.extend(["119.45.110.19", "119.45.110.23"])

            # Resolve real IP via Cloudflare / Google DoH
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
                    direct_url = video_url.replace(f"://{hostname}", f"://{ip}")
                    resp = await client.get(
                        direct_url,
                        headers={"Host": hostname},
                        timeout=httpx.Timeout(timeout, connect=8.0)
                    )
                    if resp.status_code == 200 and len(resp.content) > 1000:
                        logger.info(f"Video downloaded successfully via IP {ip} ({len(resp.content)} bytes)")
                        return resp.content
                except Exception as ex:
                    logger.warning(f"Fallback download via IP {ip} failed: {ex}")
        except Exception as e2:
            logger.error(f"Error in fallback video download: {e2}")

        return None
