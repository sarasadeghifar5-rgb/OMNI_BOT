import os
import io
import wave
import base64
import httpx
from typing import Dict, Any, Optional
from app.providers.gemini_provider import GeminiKeyPool

class GeminiTTSService:
    """
    Text-to-Speech (TTS) Service using Google Gemini's native neural audio synthesis.
    Converts text to high-fidelity 24kHz WAV audio.
    """
    SUPPORTED_VOICES = [
        "kore", "puck", "fenrir", "aoede", "charon",
        "despina", "enceladus", "leda", "zephyr"
    ]

    TTS_MODELS = [
        "gemini-3.8-flash-tts",
        "gemini-3.1-flash-tts-preview"
    ]

    @classmethod
    async def synthesize_speech(
        cls,
        text: str,
        voice_name: str = "kore",
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        pool = GeminiKeyPool.get_instance()

        clean_text = text.strip()
        if not clean_text:
            raise ValueError("Text for speech synthesis cannot be empty.")

        # =========================================================================
        # 🎙️ محدودیت ۲ خط: تحت هیچ شرایطی صوت برای بیشتر از ۲ خط تولید نشود
        # =========================================================================
        lines = [line.strip() for line in clean_text.splitlines() if line.strip()]
        if len(lines) > 2:
            clean_text = "\n".join(lines[:2])
        elif len(clean_text) > 200:
            # اگر متن پیوسته بدون شکست خط بود، به اندازه حداکثر دو خط گفتاری (~200 کاراکتر) محدود می‌شود
            clean_text = clean_text[:200].rsplit(" ", 1)[0] + "..."

        selected_voice = voice_name if voice_name in cls.SUPPORTED_VOICES else "kore"
        payload = {
            "contents": [{"parts": [{"text": clean_text}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": selected_voice
                        }
                    }
                }
            }
        }

        attempted_keys = set()
        all_pool_nodes = pool.get_all_nodes()
        max_attempts = max(2, len(all_pool_nodes))

        last_error = None
        for attempt in range(max_attempts):
            node = pool.select_best_node(user_override_key=api_key, exclude_keys=attempted_keys)
            if not node:
                break
            attempted_keys.add(node.key)
            await node.acquire_slot()

            for tts_model in cls.TTS_MODELS:
                endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{tts_model}:generateContent?key={node.key}"
                try:
                    async with node._semaphore:
                        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
                            response = await client.post(endpoint, json=payload)
                            if response.status_code == 200:
                                node.record_success()
                                data = response.json()
                                parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                                pcm_base64 = None
                                for p in parts:
                                    if "inlineData" in p and p["inlineData"].get("data"):
                                        pcm_base64 = p["inlineData"]["data"]
                                        break

                                if pcm_base64:
                                    pcm_bytes = base64.b64decode(pcm_base64)
                                    wav_buffer = io.BytesIO()
                                    with wave.open(wav_buffer, "wb") as wf:
                                        wf.setnchannels(1)      # Mono
                                        wf.setsampwidth(2)      # 16-bit
                                        wf.setframerate(24000)  # 24kHz
                                        wf.writeframes(pcm_bytes)

                                    wav_bytes = wav_buffer.getvalue()
                                    wav_base64 = base64.b64encode(wav_bytes).decode("ascii")
                                    audio_data_url = f"data:audio/wav;base64,{wav_base64}"

                                    return {
                                        "status": "success",
                                        "audio_url": audio_data_url,
                                        "voice": selected_voice,
                                        "format": "wav",
                                        "duration_estimate": round(len(pcm_bytes) / 48000.0, 1),
                                        "size_kb": len(wav_bytes) // 1024
                                    }
                            else:
                                node.record_error(response.status_code)
                                last_error = f"Gemini TTS error ({response.status_code}): {response.text[:120]}"
                except Exception as e:
                    node.record_error(500)
                    last_error = str(e)

        raise RuntimeError(last_error or "خطا در تولید صوت با هوش مصنوعی.")
