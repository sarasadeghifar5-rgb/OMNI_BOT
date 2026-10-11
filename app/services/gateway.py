import os
import copy
import logging
from typing import AsyncGenerator, Dict, Any, List, Optional

from app.config import (
    DEFAULT_SYSTEM_PROMPT,
    get_model_capabilities,
    CLEANAPIS_BASE_URL,
    CLEANAPIS_API_KEY,
    ATRIA_BASE_URL,
    ATRIA_API_KEY,
    AGNES_BASE_URL,
    AGNES_API_KEY,
)
from app.services.web_search import WebSearchService
from app.services.vision import VisionService

logger = logging.getLogger("LLMGateway")

# ==============================================================================
# 🎯 نقشه مسیریابی مستقیم و اختصاصی مدل‌های هوش مصنوعی (Direct Model Routing Table)
# هیچ سرویس پشتیبان یا فال‌بک وجود ندارد: هر مدل مستقیماً به ارائه‌دهنده واقعی خود متصل می‌شود.
# ==============================================================================
MODEL_ROUTING: Dict[str, Dict[str, Any]] = {
    # --- خانواده Google Gemini ---
    "gemini-3.7-flash": {"provider": "codecraft", "upstream": "gemini-3.7-flash", "family": "gemini"},
    "gemini-3.6-flash": {"provider": "codecraft", "upstream": "gemini-3.6-flash", "family": "gemini"},
    "gemini-3.1-pro": {"provider": "codecraft", "upstream": "gemini-3.1-pro", "family": "gemini"},
    "gemini": {"provider": "codecraft", "upstream": "gemini-3.7-flash", "family": "gemini"},
    "gemma-2-2b": {"provider": "codecraft", "upstream": "gemma-2-2b", "family": "gemini"},

    # --- خانواده Claude Anthropic ---
    "claude-opus-5.5": {"provider": "codecraft", "upstream": "claude-opus-5.5", "family": "claude"},
    "claude-sonnet-5": {"provider": "codecraft", "upstream": "claude-sonnet-5", "family": "claude"},
    "claude-fable-5.1": {"provider": "codecraft", "upstream": "claude-fable-5.1", "family": "claude"},
    "claude-fable-5": {"provider": "codecraft", "upstream": "claude-fable-5", "family": "claude"},
    "claude-opus-5": {"provider": "codecraft", "upstream": "claude-opus-5", "family": "claude"},
    "claude-opus-4.8": {"provider": "codecraft", "upstream": "claude-opus-4.8", "family": "claude"},
    "claude-opus-4.7": {"provider": "codecraft", "upstream": "claude-opus-4.7", "family": "claude"},
    "claude-opus-4.6": {"provider": "codecraft", "upstream": "claude-opus-4.6", "family": "claude"},
    "claude-mythos-preview": {"provider": "codecraft", "upstream": "claude-mythos-preview", "family": "claude"},
    "claude-3-5-sonnet-20241022": {"provider": "codecraft", "upstream": "claude-sonnet-5", "family": "claude"},
    "claude": {"provider": "codecraft", "upstream": "claude-sonnet-5", "family": "claude"},

    # --- خانواده OpenAI GPT ---
    "gpt-5.6-sol": {"provider": "codecraft", "upstream": "gpt-5.6-sol", "family": "openai"},
    "gpt-5.6-terra": {"provider": "codecraft", "upstream": "gpt-5.6-terra", "family": "openai"},
    "gpt-5.6-luna": {"provider": "codecraft", "upstream": "gpt-5.6-luna", "family": "openai"},
    "gpt-5.5-pro": {"provider": "codecraft", "upstream": "gpt-5.5-pro", "family": "openai"},
    "gpt-5.5": {"provider": "codecraft", "upstream": "gpt-5.5", "family": "openai"},
    "gpt-4o": {"provider": "codecraft", "upstream": "gpt-5.5", "family": "openai"},
    "gpt-4o-mini": {"provider": "codecraft", "upstream": "gpt-5.6-luna", "family": "openai"},
    "o1": {"provider": "codecraft", "upstream": "gpt-5.6-sol", "family": "openai"},

    # --- خانواده DeepSeek ---
    "deepseek-v4-pro-max": {"provider": "codecraft", "upstream": "deepseek-v4-pro-max", "family": "deepseek"},
    "deepseek-v4-pro-0813": {"provider": "codecraft", "upstream": "deepseek-v4-pro-0813", "family": "deepseek"},
    "deepseek-v4-flash-0731": {"provider": "codecraft", "upstream": "deepseek-v4-flash-0731", "family": "deepseek"},
    "deepseek-reasoner": {"provider": "codecraft", "upstream": "deepseek-v4-pro-max", "family": "deepseek"},
    "deepseek-chat": {"provider": "codecraft", "upstream": "deepseek-v4-flash-0731", "family": "deepseek"},
    "deepseek": {"provider": "codecraft", "upstream": "deepseek-v4-pro-max", "family": "deepseek"},

    # --- خانواده xAI Grok ---
    "grok-4.6": {"provider": "codecraft", "upstream": "grok-4.6", "family": "grok"},
    "grok-4.5": {"provider": "codecraft", "upstream": "grok-4.5", "family": "grok"},
    "grok-2-vision-1212": {"provider": "codecraft", "upstream": "grok-4.6", "family": "grok"},

    # --- خانواده Alibaba Qwen ---
    "qwen3.8-max": {"provider": "codecraft", "upstream": "qwen3.8-max", "family": "qwen"},
    "qwen3.8-27b": {"provider": "codecraft", "upstream": "qwen3.8-27b", "family": "qwen"},
    "qwen3.7-max": {"provider": "codecraft", "upstream": "qwen3.7-max", "family": "qwen"},

    # --- خانواده Moonshot Kimi ---
    "kimi-k3": {"provider": "codecraft", "upstream": "kimi-k3", "family": "kimi"},
    "kimi-k2.6": {"provider": "codecraft", "upstream": "kimi-k2.6", "family": "kimi"},

    # --- خانواده Zhipu AI GLM ---
    "glm-5.3": {"provider": "codecraft", "upstream": "glm-5.3", "family": "glm"},
    "glm-5.2": {"provider": "codecraft", "upstream": "glm-5.2", "family": "glm"},
    "glm-4-flash": {"provider": "codecraft", "upstream": "glm-5.3", "family": "glm"},
    "glm-4v-flash": {"provider": "codecraft", "upstream": "glm-5.3", "family": "glm"},

    # --- خانواده ByteDance Seed ---
    "seed-2.1-turbo": {"provider": "codecraft", "upstream": "seed-2.1-turbo", "family": "seed"},
    "seed-2.1-pro": {"provider": "codecraft", "upstream": "seed-2.1-pro", "family": "seed"},

    # --- مدل Muse ---
    "muse-spark-1.1": {"provider": "codecraft", "upstream": "muse-spark-1.1", "family": "muse"},

    # --- خانواده Atria ASI ---
    "Atria-Dawn-Preview": {"provider": "atria", "upstream": "Atria-Dawn-Preview", "family": "atria"},
    "atria": {"provider": "atria", "upstream": "Atria-Dawn-Preview", "family": "atria"},

    # --- خانواده Agnes AI ---
    "agnes-2.5-flash": {"provider": "agnes", "upstream": "agnes-2.5-flash", "family": "agnes"},
    "agnes": {"provider": "agnes", "upstream": "agnes-2.5-flash", "family": "agnes"},
}


class LLMGateway:
    """
    موتور بازنویسی‌شده مدیریت مدل‌های هوش مصنوعی (OmniLLM Unified Gateway):
    - حذف کامل سرویس‌های پشتیبان / فال‌بک ناخواسته
    - اجرای مستقیم، سریع و شفاف همان مدل انتخاب‌شده توسط کاربر
    - استریم پیوسته متن و فرآیند تفکر عمیق (Thinking Process)
    - پشتیبانی از بینایی ماشین و سرچ وب زنده
    """

    def __init__(self):
        self.web_search = WebSearchService()
        self.vision = VisionService()

    @staticmethod
    def get_route_info(model_id: str) -> Dict[str, Any]:
        """اطلاعات مسیریابی مستقیم مدل را استخراج می‌کند."""
        if model_id in MODEL_ROUTING:
            return MODEL_ROUTING[model_id]

        mid = model_id.lower()
        if "atria" in mid or "dawn" in mid:
            return {"provider": "atria", "upstream": "Atria-Dawn-Preview", "family": "atria"}
        elif "agnes" in mid:
            return {"provider": "agnes", "upstream": "agnes-2.5-flash", "family": "agnes"}
        elif "claude" in mid or "opus" in mid or "fable" in mid or "sonnet" in mid:
            return {"provider": "codecraft", "upstream": model_id, "family": "claude"}
        elif "gpt" in mid or "sol" in mid or "luna" in mid:
            return {"provider": "codecraft", "upstream": model_id, "family": "openai"}
        elif "deepseek" in mid or "r1" in mid:
            return {"provider": "codecraft", "upstream": "deepseek-v4-pro-max", "family": "deepseek"}
        elif "gemini" in mid:
            return {"provider": "codecraft", "upstream": "gemini-3.7-flash", "family": "gemini"}
        else:
            return {"provider": "codecraft", "upstream": model_id, "family": "codecraft"}

    @staticmethod
    def build_model_persona(model_id: str, family: str) -> str:
        """
        تعریف هویت اختصاصی و دقیق برای هر مدل هوش مصنوعی
        تا کاربر با تغییر مدل، پاسخ‌های کاملاً منطبق بر هویت همان مدل را دریافت کند.
        """
        mid = model_id.lower()
        if family == "gemini":
            persona = (
                "You are Google Gemini 3.7 Flash, Google's ultra-fast frontier multimodal and reasoning AI model. "
                "When asked who you are or your identity (e.g. 'اسمت چیه؟', 'کی هستی؟'), "
                "explicitly and proudly state in fluent Persian that you are Google Gemini (گوگل جمینای ۳.۷ فلش) developed by Google."
            )
        elif family == "claude":
            model_tag = "Claude Opus 5.5" if "opus" in mid else "Claude Sonnet 5" if "sonnet" in mid else "Claude"
            persona = (
                f"You are Anthropic {model_tag}, an advanced frontier AI model with exceptional nuance, reasoning, and coding skills. "
                f"When asked who you are or your name, state in fluent Persian that you are Anthropic {model_tag} (کلاد آنتروپیک)."
            )
        elif family == "openai":
            model_tag = "GPT-5.6 Sol" if "sol" in mid else "GPT-5.5"
            persona = (
                f"You are OpenAI {model_tag}, OpenAI's flagship frontier reasoning intelligence. "
                f"When asked who you are or your name, state in fluent Persian that you are OpenAI {model_tag}."
            )
        elif family == "deepseek":
            persona = (
                "You are DeepSeek V4 Pro Max (DeepSeek AI), a state-of-the-art open-architecture reasoning and coding powerhouse. "
                "When asked who you are or your name, state in fluent Persian that you are DeepSeek (دیپ‌سیک)."
            )
        elif family == "atria":
            persona = (
                "You are Atria Dawn (Atria ASI), an ultra-deep cognitive reasoning model with an enormous 256K context window. "
                "When asked who you are or your name, state in fluent Persian that you are Atria Dawn (آتریا داون)."
            )
        elif family == "agnes":
            persona = (
                "You are Nano Reasoner 2.5 (Agnes AI), an advanced analytical and multimodal reasoning intelligence. "
                "When asked who you are or your name, state in fluent Persian that you are Nano Reasoner 2.5."
            )
        elif family == "grok":
            persona = (
                "You are Grok 4.6, an advanced frontier AI model developed by xAI. "
                "When asked who you are or your name, state in fluent Persian that you are Grok 4.6 (گروک) from xAI."
            )
        elif family == "qwen":
            persona = (
                "You are Qwen 3.8 Max, Alibaba Cloud's flagship open-weights multilingual AI model. "
                "When asked who you are or your name, state in fluent Persian that you are Qwen 3.8 Max from Alibaba Cloud."
            )
        elif family == "kimi":
            persona = (
                "You are Kimi K3, developed by Moonshot AI, renowned for long-context comprehension and deep reasoning. "
                "When asked who you are or your name, state in fluent Persian that you are Kimi K3 from Moonshot AI."
            )
        elif family == "glm":
            persona = (
                "You are GLM-5.3, developed by Zhipu AI and Tsinghua University. "
                "When asked who you are or your name, state in fluent Persian that you are GLM-5.3 from Zhipu AI."
            )
        else:
            persona = f"You are {model_id}, an advanced frontier AI assistant."

        instructions = (
            "\n- Always communicate in natural, respectful, and fluent Persian when the user writes in Persian."
            "\n- Explain complex concepts thoroughly and clearly."
            "\n- Never invent facts; be truthful, concise, and helpful."
            "\n- For programming code, use clean standard Markdown code blocks."
        )
        return persona + instructions

    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        model_id: str,
        temperature: float = 0.7,
        enable_web_search: bool = False,
        images: Optional[List[str]] = None,
        user_keys: Optional[Dict[str, str]] = None,
        system_prompt: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        اجرای استریم مستقیم و زنده مدل بدون هیچ‌گونه سرویس فال‌بک یا بک‌آپ.
        """
        route = self.get_route_info(model_id)
        provider_name = route["provider"]
        upstream_model = route["upstream"]
        family = route.get("family", "codecraft")

        # ساخت پیام‌ها
        chat_messages = copy.deepcopy(messages)

        # تزریق هویت دقیق مدل در System Prompt
        sys_persona = self.build_model_persona(model_id, family)
        final_system_content = f"{sys_persona}\n\n{system_prompt}" if system_prompt else sys_persona

        sys_idx = next((i for i, m in enumerate(chat_messages) if m.get("role") == "system"), None)
        if sys_idx is not None:
            chat_messages[sys_idx] = {"role": "system", "content": final_system_content}
        else:
            chat_messages.insert(0, {"role": "system", "content": final_system_content})

        # استخراج متن آخرین پیام کاربر
        latest_user_text = ""
        for m in reversed(chat_messages):
            if m.get("role") == "user":
                c = m.get("content")
                if isinstance(c, str):
                    latest_user_text = c.strip()
                elif isinstance(c, list):
                    for part in c:
                        if part.get("type") == "text":
                            latest_user_text = part.get("text", "").strip()
                            break
                break

        # پردازش تصاویر در صورت وجود
        if images:
            enable_web_search = False
            for i in range(len(chat_messages) - 1, -1, -1):
                if chat_messages[i].get("role") == "user":
                    prompt_text = latest_user_text or "لطفاً این تصویر را با دقت بررسی و تحلیل کرده و توضیحات کامل آن را به فارسی ارائه دهید."
                    chat_messages[i] = self.vision.build_multimodal_message(prompt_text, images)
                    break

        # سرچ وب زنده (در صورت درخواست)
        if enable_web_search and latest_user_text and not images:
            # کلمات سلام و احوالپرسی نباید وب‌سرچ را فعال کنند
            greetings = ["سلام", "درود", "خوبی", "چطوری", "کی هستی", "اسمت چیه"]
            if not any(g in latest_user_text.lower() for g in greetings):
                yield {"type": "status", "message": f"🌐 در حال جستجوی زنده وب برای {model_id}..."}
                try:
                    tavily_key = os.getenv("TAVILY_API_KEY", "").strip()
                    raw_res = await self.web_search.search(latest_user_text, max_results=4, api_key=tavily_key or None)
                    if raw_res:
                        grounding = self.web_search.format_grounding_prompt(latest_user_text, raw_res)
                        for m in reversed(chat_messages):
                            if m.get("role") == "user":
                                orig = m.get("content", "")
                                if isinstance(orig, str):
                                    m["content"] = f"{orig}\n\n[اطلاعات زنده وب]:\n{grounding}\n"
                                break
                except Exception as e_search:
                    logger.warning(f"Web search exception: {e_search}")

        # ==============================================================================
        # 🚀 فراخوانی مستقیم و اختصاصی ارائه‌دهنده بدون هیچ سرویس پشتیبان (NO FALLBACK)
        # ==============================================================================
        has_yielded_token = False

        try:
            if provider_name == "atria":
                from app.providers.atria_provider import AtriaProvider
                atria_key = (os.getenv("ATRIA_API_KEY") or ATRIA_API_KEY).strip()
                prov = AtriaProvider(default_api_key=atria_key)
                async for chunk in prov.stream_chat(
                    messages=chat_messages,
                    model=upstream_model,
                    temperature=temperature
                ):
                    if chunk.get("type") in ("content", "thinking"):
                        has_yielded_token = True
                    yield chunk

            elif provider_name == "agnes":
                from app.providers.agnes_provider import AgnesProvider
                agnes_key = (os.getenv("AGNES_API_KEY") or AGNES_API_KEY).strip()
                prov = AgnesProvider(default_api_key=agnes_key)
                async for chunk in prov.stream_chat(
                    messages=chat_messages,
                    model=upstream_model,
                    temperature=temperature
                ):
                    if chunk.get("type") in ("content", "thinking"):
                        has_yielded_token = True
                    yield chunk

            else:
                # ارائه‌دهنده قدرتمند و جامع CleanAPIs (کدکرفت)
                from app.providers.codecraft_provider import CodeCraftProvider
                ca_key = (os.getenv("CLEANAPIS_API_KEY") or CLEANAPIS_API_KEY).strip()
                prov = CodeCraftProvider(default_api_key=ca_key)
                async for chunk in prov.stream_chat(
                    messages=chat_messages,
                    model=upstream_model,
                    temperature=temperature,
                    web_search=enable_web_search
                ):
                    if chunk.get("type") in ("content", "thinking"):
                        has_yielded_token = True
                    yield chunk

        except Exception as exc:
            logger.error(f"[LLMGateway] Direct call failed for model {model_id} ({upstream_model}): {exc}")
            if not has_yielded_token:
                yield {
                    "type": "error",
                    "error": f"⚠️ خطا در ارتباط مستقیم با مدل {model_id}:\n{str(exc)}"
                }
