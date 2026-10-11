import json
import uuid
import time
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import StreamingResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import AVAILABLE_MODELS, PROVIDER_ENDPOINTS, DEFAULT_SYSTEM_PROMPT
from app.services import LLMGateway, WebSearchService, VisionService, SessionStorage, ImageGenService, GeminiTTSService, PuterImageService

app = FastAPI(
    title="OmniLLM Hub API",
    description="Full-featured Multi-Provider LLM Chat Platform with Vision & Live Web Search",
    version="1.0.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

gateway = LLMGateway()
web_search = WebSearchService()
vision_service = VisionService()

_active_sessions: Dict[str, float] = {}
_session_lock = asyncio.Lock()

# Pydantic Schemas
class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    model: str = "gemini"
    messages: List[Dict[str, Any]]
    temperature: float = 0.7
    enable_web_search: bool = False
    images: Optional[List[str]] = None
    api_keys: Optional[Dict[str, str]] = None
    system_prompt: Optional[str] = None

class SearchRequest(BaseModel):
    query: str
    max_results: int = 5
    api_key: Optional[str] = None

class ImageGenerateRequest(BaseModel):
    prompt: str
    model: str = "nano-banana"
    width: int = 1024
    height: int = 1024
    aspect_ratio: Optional[str] = "1:1"
    resolution: Optional[str] = "1K"
    api_key: Optional[str] = None
    openrouter_key: Optional[str] = None
    puter_token: Optional[str] = None

class TTSGenerateRequest(BaseModel):
    text: str
    voice: Optional[str] = "kore"
    api_key: Optional[str] = None

class SessionSaveRequest(BaseModel):
    messages: List[Dict[str, Any]]
    model: str
    title: Optional[str] = None

# --- API Routes ---

@app.get("/api/models")
async def get_models():
    """Return catalog of available models across all providers"""
    return {
        "models": AVAILABLE_MODELS,
        "providers": list(PROVIDER_ENDPOINTS.keys())
    }

@app.post("/api/chat")
async def chat_stream(request: ChatRequest):
    """
    Main Server-Sent Events (SSE) streaming endpoint.
    Handles multi-model routing, web search grounding, image generation, and vision.
    """
    async def event_generator():
        session_id = request.session_id
        if session_id:
            async with _session_lock:
                now = time.time()
                if session_id in _active_sessions and (now - _active_sessions[session_id]) < 180.0:
                    yield f"data: {json.dumps({'type': 'content', 'content': '⏳ لطفاً منتظر بمانید تا پاسخ پیام قبلی داده شود.'}, ensure_ascii=False)}\n\n"
                    yield f"data: [DONE]\n\n"
                    return
                _active_sessions[session_id] = now

        try:
            # Check if user requested image generation via prompt prefix or slash command
            latest_text = ""
            for m in reversed(request.messages):
                if m.get("role") == "user":
                    c = m.get("content", "")
                    if isinstance(c, str):
                        latest_text = c.strip()
                    elif isinstance(c, list):
                        for p in c:
                            if p.get("type") == "text":
                                latest_text = p.get("text", "").strip()
                                break
                    break

            clean_lower = latest_text.lower().strip()
            is_image_cmd = any(
                clean_lower.startswith(cmd)
                for cmd in [
                    "/banana", "/nano_banana", "/nano",
                    "/gemini_image", "/gemini_img", "/image", "/img",
                    "عکس بساز", "تصویر بساز", "یک عکس از", "یک تصویر از",
                    "با نانو بنانا بساز", "با نانو موز بساز", "عکس با نانو موز",
                    "با جمینای بساز", "عکس با جمینای", "تصویر جمینای",
                    "تولید عکس", "تولید تصویر"
                ]
            )

            # Check if this is an explicit conversational edit/modification of a previous image
            is_image_edit = any(
                clean_lower.startswith(phrase)
                for phrase in ["/edit_img", "/edit_image", "عکس قبلی رو تغییر بده", "تصویر رو تغییر بده"]
            )

            # Search conversation history for the most recent image prompt
            prev_image_prompt = None
            if is_image_edit:
                for past_m in reversed(request.messages[:-1]):
                    past_content = str(past_m.get("content", ""))
                    if "**پرامپت:**" in past_content or "**پرامپت اصلی:**" in past_content or "**پرامپت ترکیبی کامل:**" in past_content:
                        try:
                            if "**پرامپت:**" in past_content:
                                prev_image_prompt = past_content.split("**پرامپت:**")[1].split("\n")[0].strip()
                            elif "**پرامپت ترکیبی کامل:**" in past_content:
                                prev_image_prompt = past_content.split("**پرامپت ترکیبی کامل:**")[1].split("\n")[0].strip()
                            elif "**پرامپت اصلی:**" in past_content:
                                prev_image_prompt = past_content.split("**پرامپت اصلی:**")[1].split("\n")[0].strip()
                            if prev_image_prompt:
                                break
                        except Exception:
                            pass

            is_banana_selected = any(k in request.model.lower() for k in ["banana", "nano"])

            if (is_image_cmd or (is_image_edit and prev_image_prompt) or is_banana_selected) and not request.images:
                engine = "nano-banana"
                clean_p = latest_text

                # Strip command prefixes
                for prefix in [
                    "/banana", "/nano_banana", "/nano",
                    "/gemini_image", "/gemini_img", "/image", "/img", "/edit_image", "/edit_img",
                    "با نانو بنانا بساز:", "با نانو بنانا بساز", "با نانو موز بساز:", "با نانو موز بساز",
                    "عکس با نانو موز:", "عکس با نانو موز", "عکس با نانو بنانا:", "عکس با نانو بنانا",
                    "با جمینای بساز:", "با جمینای بساز", "عکس با جمینای:", "عکس با جمینای",
                    "تصویر جمینای:", "تصویر جمینای", "تصویر بساز:", "عکس بساز:",
                    "تصویر بساز", "عکس بساز", "یک تصویر از", "یک عکس از",
                    "تولید عکس:", "تولید عکس", "تولید تصویر:", "تولید تصویر"
                ]:
                    if clean_p.lower().startswith(prefix.lower()):
                        clean_p = clean_p[len(prefix):].strip()
                        break
                clean_p = clean_p.lstrip(": ").strip()

                target_m = "nano-banana-pro" if "pro" in request.model.lower() else ("nano-banana-2" if "2" in request.model.lower() else "nano-banana")
                engine_label = "Google Nano Banana (Puter AI)"
                or_key = request.api_keys.get("openrouter") if request.api_keys else None
                gem_key = request.api_keys.get("gemini") if request.api_keys else None
                puter_k = request.api_keys.get("puter") if request.api_keys else None

                if is_image_edit and prev_image_prompt:
                    combined_prompt = f"{prev_image_prompt}, modified with: {clean_p}"
                    yield f"data: {json.dumps({'type': 'status', 'message': f'🔄 در حال ویرایش تصویر با {engine_label}...'}, ensure_ascii=False)}\n\n"
                    gen_result = await PuterImageService.generate_image(
                        prompt=combined_prompt,
                        model=target_m,
                        user_token=puter_k
                    )
                    img_url = gen_result.get("image_url", "")
                    model_title = gen_result.get("model_name", "Google Nano Banana")

                    if gen_result.get("status") == "error" or not img_url:
                        err_msg = gen_result.get("error_message", "خطا در تولید تصویر.")
                        md_resp = f"⚠️ **خطا در تولید تصویر:**\n\n{err_msg}"
                    else:
                        md_resp = (
                            f"### 🍌 تصویر به‌روزرسانی شده با {model_title}:\n\n"
                            f"**تغییرات درخواستی:** {clean_p}\n\n"
                            f"**پرامپت اصلی:** {combined_prompt}\n\n"
                            f"![{combined_prompt}]({img_url})\n\n"
                            f"[📥 مشاهده و دانلود تصویر با کیفیت بالا]({img_url})\n\n"
                            f"*(می‌توانید در ادامه گفتگو تغییرات دیگری مانند تغییر سبک، زاویه یا عناصر را درخواست کنید)*"
                        )
                else:
                    if not clean_p:
                        clean_p = "یک منظره مدرن و سینمایی با نورپردازی دیجیتال و کیفیت بالا"
                    yield f"data: {json.dumps({'type': 'status', 'message': f'🍌 در حال تولید تصویر با {engine_label}: {clean_p[:40]}...'}, ensure_ascii=False)}\n\n"
                    gen_result = await PuterImageService.generate_image(
                        prompt=clean_p,
                        model=target_m,
                        user_token=puter_k
                    )
                    img_url = gen_result.get("image_url", "")
                    model_title = gen_result.get("model_name", "Google Nano Banana")

                    if gen_result.get("status") == "error" or not img_url:
                        err_msg = gen_result.get("error_message", "خطا در تولید تصویر.")
                        md_resp = f"⚠️ **خطا در تولید تصویر:**\n\n{err_msg}"
                    else:
                        md_resp = (
                            f"### 🍌 تصویر تولید شده با {model_title}:\n\n"
                            f"**پرامپت:** {clean_p}\n\n"
                            f"![{clean_p}]({img_url})\n\n"
                            f"[📥 مشاهده و دانلود تصویر با کیفیت بالا]({img_url})\n\n"
                            f"*(برای ایجاد تغییرات کافیست در پیام بعدی بگویید: «تغییر بده: ...» یا «حالا ... اضافه کن»)*"
                        )

                yield f"data: {json.dumps({'type': 'content', 'content': md_resp}, ensure_ascii=False)}\n\n"
                yield f"data: [DONE]\n\n"
                return

            async for chunk in gateway.stream_chat(
                messages=request.messages,
                model_id=request.model,
                temperature=request.temperature,
                enable_web_search=request.enable_web_search,
                images=request.images,
                user_keys=request.api_keys,
                system_prompt=request.system_prompt
            ):
                # Send formatted SSE chunk
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        except Exception as e:
            err_data = {"type": "error", "message": f"خطای سرور: {str(e)}"}
            yield f"data: {json.dumps(err_data, ensure_ascii=False)}\n\n"
        finally:
            if session_id:
                async with _session_lock:
                    _active_sessions.pop(session_id, None)
        
        # Signal completion
        yield f"data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@app.post("/api/upload")
async def upload_image(file: UploadFile = File(...)):
    """
    Upload and compress an image, returning base64 Data URL for multimodal input.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="فایل ارسالی باید یک تصویر معتبر باشد.")

    contents = await file.read()
    data_url, width, height = vision_service.process_and_encode_image(
        file_bytes=contents,
        mime_type=file.content_type
    )

    return {
        "filename": file.filename,
        "content_type": file.content_type,
        "data_url": data_url,
        "width": width,
        "height": height,
        "size_kb": len(contents) // 1024
    }

@app.post("/api/search")
async def perform_search(request: SearchRequest):
    """Standalone web search endpoint"""
    results = await web_search.search(
        query=request.query,
        max_results=request.max_results,
        api_key=request.api_key
    )
    return {"query": request.query, "results": results}

@app.post("/api/generate-image")
async def generate_image_api(request: ImageGenerateRequest):
    """Generate high quality AI image from text prompt via Google Nano Banana or Puter"""
    if not request.prompt or not request.prompt.strip():
        raise HTTPException(status_code=400, detail="متن پرامپت نمی‌تواند خالی باشد.")
    
    # If Agnes / GPT image model requested
    if any(k in request.model.lower() for k in ["agnes", "gpt-image", "gpt_image"]):
        from app.services.agnes_image import AgnesImageService
        agnes = AgnesImageService(api_key=request.api_key)
        res = await agnes.generate_image(
            prompt=request.prompt,
            size=request.resolution or "1K",
            ratio=request.aspect_ratio or "1:1"
        )
        if res.get("success"):
            return {
                "status": "success",
                "engine": "nano_banana",
                "model_name": "ادیت عکس نانو بنانا 🍌",
                "image_url": res["url"],
                "prompt": request.prompt,
                "is_fallback": False,
                "description": "تصویر تولید شده با مدل فوق‌حرفه‌ای نانو بنانا"
            }
        return {
            "status": "error",
            "error_message": res.get("error", "خطا در تولید تصویر")
        }

    # If a Nano Banana or Puter model is requested or by default
    if any(k in request.model.lower() for k in ["banana", "nano", "sdxl", "puter"]) or request.puter_token:
        data = await PuterImageService.generate_image(
            prompt=request.prompt,
            model=request.model,
            aspect_ratio=request.aspect_ratio or "1:1",
            resolution=request.resolution or "1K",
            user_token=request.puter_token
        )
    else:
        data = await ImageGenService.generate_image(
            prompt=request.prompt,
            model=request.model,
            width=request.width,
            height=request.height,
            api_key=request.api_key,
            openrouter_key=request.openrouter_key
        )
    return data

@app.post("/api/tts/gemini")
async def tts_gemini_api(request: TTSGenerateRequest):
    """
    Generate high-fidelity voice audio directly from Google Gemini neural TTS.
    Returns standard 24kHz WAV audio data URL ready for instant playback.
    """
    if not request.text or not request.text.strip():
        raise HTTPException(status_code=400, detail="متن برای خوانش صوتی نمی‌تواند خالی باشد.")
    try:
        data = await GeminiTTSService.synthesize_speech(
            text=request.text,
            voice_name=request.voice or "kore",
            api_key=request.api_key
        )
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطا در تولید صدای جمینای: {str(e)}")

@app.get("/api/sessions")
async def list_sessions():
    """List all saved chat sessions"""
    return {"sessions": SessionStorage.list_sessions()}

@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """Retrieve chat history for a session"""
    session = SessionStorage.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="جلسه چت یافت نشد.")
    return session

@app.post("/api/sessions/{session_id}")
async def save_session(session_id: str, request: SessionSaveRequest):
    """Save or update chat messages for a session"""
    saved = SessionStorage.save_session(
        session_id=session_id,
        messages=request.messages,
        model=request.model,
        title=request.title
    )
    return saved

@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a chat session"""
    deleted = SessionStorage.delete_session(session_id)
    return {"success": deleted}

@app.get("/api/config-status")
async def check_config_status():
    """Check which provider API keys are pre-configured on the server and return pool health"""
    import os
    from app.services.codecraft_client import CodeCraftKeyPool
    from app.services.atria_client import AtriaKeyPool
    from app.services.agnes_client import AgnesKeyPool

    providers = [
        "openai", "deepseek", "grok", "glm", "gemini", "claude",
        "openrouter", "pollinations", "tavily", "puter", "atria",
        "codecraft", "agnes"
    ]
    status = {}
    for p in providers:
        if p == "puter":
            status["puter"] = bool(os.getenv("PUTER_AUTH_TOKEN") or os.getenv("PUTER_API_KEY"))
        else:
            key = gateway.resolve_api_key(p)
            status[p] = bool(key)

    pools = {
        "codecraft": CodeCraftKeyPool.get_instance().get_status(),
        "atria": AtriaKeyPool.get_instance().get_status(),
        "agnes": AgnesKeyPool.get_instance().get_status(),
    }
    return {"configured_keys": status, "pools": pools}

# Mount static files
static_path = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_path), name="static")

@app.get("/banana")
@app.get("/studio")
async def banana_studio_page():
    studio_file = static_path / "banana_studio.html"
    if studio_file.exists():
        return FileResponse(studio_file)
    return HTMLResponse("<h1>Nano Banana Studio</h1>")

@app.get("/")
async def root():
    index_file = static_path / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse("<h1>OmniLLM Service Running</h1>")
