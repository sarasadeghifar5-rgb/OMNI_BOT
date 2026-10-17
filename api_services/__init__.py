"""
Unified API Router for routing chat completions and vision/multimodal analysis to the appropriate backend service.
"""
from typing import List, Dict, Optional
import logging
from config import AVAILABLE_MODELS, DEFAULT_MODEL
from api_services.cleanapis import cleanapis_client
from api_services.atria import atria_client
from api_services.agnes import agnes_client
from api_services.gemini import gemini_client

logger = logging.getLogger(__name__)

async def route_chat_completion(model_name: str, messages: List[Dict[str, str]]) -> str:
    """Routes chat completion request to the correct provider with universal fast failover to Agnes AI."""
    model_info = AVAILABLE_MODELS.get(model_name)
    if not model_info:
        model_name = DEFAULT_MODEL
        model_info = AVAILABLE_MODELS.get(DEFAULT_MODEL, {})

    service = model_info.get("service", "cleanapis")
    response_text = ""

    try:
        if service == "cleanapis":
            response_text = await cleanapis_client.generate_chat_response(model=model_name, messages=messages)
        elif service == "atria":
            response_text = await atria_client.generate_chat_response(model=model_name, messages=messages)
        elif service == "agnes":
            response_text = await agnes_client.generate_chat_response(model=model_name, messages=messages)
        elif service == "gemini":
            response_text = await gemini_client.generate_chat_response(model=model_name, messages=messages)
        else:
            response_text = await agnes_client.generate_chat_response(model="agnes-3.0-flash", messages=messages)
    except Exception as e:
        logger.error(f"Provider {service} failed with error: {e}. Falling back to Agnes AI.")
        response_text = ""

    # Universal Failover: If response is empty or contains provider error, fallback to Agnes AI
    if not response_text or response_text.startswith("خطا") or "بیش از حد طول کشید" in response_text:
        logger.info(f"Triggering universal failover to Agnes AI for model {model_name}")
        response_text = await agnes_client.generate_chat_response(
            model="agnes-3.0-flash",
            messages=messages
        )

    return response_text

async def route_vision_completion(
    model_name: str,
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    prompt: str = "این تصویر را به دقت بررسی و تحلیل کن و به زبان فارسی توضیح بده."
) -> str:
    """
    Routes multimodal vision analysis with high-speed Agnes AI vision and deep reasoning support.
    """
    model_info = AVAILABLE_MODELS.get(model_name, {})
    service = model_info.get("service")

    # If model is Atria (deep reasoning): extract visual text via Agnes vision first, then reason via Atria
    if service == "atria":
        visual_desc = await agnes_client.generate_vision_response(
            image_bytes=image_bytes,
            mime_type=mime_type,
            prompt="تمام متون، فرمول‌های ریاضی، روابط جبری، ارقام، نمودارها و جزئیات موجود در این تصویر را با دقت ۱۰۰٪ به زبان فارسی استخراج فرما."
        )
        if visual_desc and not visual_desc.startswith("خطا"):
            atria_prompt = (
                f"بر اساس داده‌ها، فرمول‌ها و مندرجات استخراج شده از تصویر پیوست:\n\n"
                f"{visual_desc}\n\n"
                f"────────────────────\n"
                f"🎯 درخواست و دستور کاربر:\n{prompt}"
            )
            return await atria_client.generate_chat_response(
                model=model_name,
                messages=[{"role": "user", "content": atria_prompt}]
            )

    # If model is Agnes directly
    if service == "agnes":
        res = await agnes_client.generate_vision_response(
            image_bytes=image_bytes,
            mime_type=mime_type,
            prompt=prompt,
            model=model_name
        )
        if res and not res.startswith("خطا"):
            return res

    # If CleanAPIs, try CleanAPIs vision (it auto-falls back to Agnes internally)
    if service == "cleanapis":
        res = await cleanapis_client.generate_vision_response(
            model=model_name,
            image_bytes=image_bytes,
            mime_type=mime_type,
            prompt=prompt
        )
        if res and not res.startswith("خطا"):
            return res

    # Primary reliable vision engine: Agnes AI 3.0 Flash
    res = await agnes_client.generate_vision_response(
        image_bytes=image_bytes,
        mime_type=mime_type,
        prompt=prompt
    )
    if res and not res.startswith("خطا"):
        return res

    # Ultimate fallback to Google Gemini
    return await gemini_client.analyze_image(
        image_bytes=image_bytes,
        mime_type=mime_type,
        prompt=prompt
    )
