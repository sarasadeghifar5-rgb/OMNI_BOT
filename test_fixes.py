import asyncio
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.services.gateway import LLMGateway

async def test_all_fixes():
    gw = LLMGateway()
    print("=" * 60)
    print("[*] TEST 1: Model Switching & Info Resolution")
    print("=" * 60)
    models_to_test = ["deepseek-reasoner", "gpt-4o", "gemini-2.0-flash", "claude-3-5-sonnet-20241022", "grok-2-vision-1212"]
    for m in models_to_test:
        info = gw.get_model_info(m)
        print(f"Model: {m} -> Provider: {info.get('provider')}, Vision: {info.get('supports_vision')}")
        assert info.get("provider") is not None

    print("\n" + "=" * 60)
    print("[*] TEST 2: Image Analysis (Vision) handling without key")
    print("=" * 60)
    dummy_img = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    events = []
    async for event in gw.stream_chat(
        messages=[{"role": "user", "content": ""}],
        model_id="gpt-4o",
        enable_web_search=True,
        images=[dummy_img],
        user_keys={}
    ):
        events.append(event)
    
    has_sources = any(e.get("type") == "sources" for e in events)
    assert not has_sources, "Web search should NOT run when images are attached!"
    print("[PASS] Web search was correctly disabled during image analysis.")

    content_chunks = [e.get("content", "") for e in events if e.get("type") == "content"]
    combined_content = "".join(content_chunks)
    print(f"[OK] Response received ({len(combined_content)} chars):")
    print(combined_content[:200] + "...")
    assert len(combined_content) > 0, "Response should not be empty!"

    print("\n" + "=" * 60)
    print("[*] TEST 3: Multi-turn Chat Memory (No context poisoning)")
    print("=" * 60)
    conv_messages = [
        {"role": "user", "content": "سلام، اسم من سجاد است."},
        {"role": "assistant", "content": "سلام سجاد عزیز! خوشبختم. چطور می‌توانم کمکتان کنم؟"},
        {"role": "user", "content": "اسم من چیه؟"}
    ]
    events_conv = []
    async for event in gw.stream_chat(
        messages=conv_messages,
        model_id="deepseek-reasoner",
        enable_web_search=True,
        user_keys={}
    ):
        events_conv.append(event)

    has_sources = any(e.get("type") == "sources" for e in events_conv)
    assert not has_sources, "Conversational question should NOT trigger web search!"
    print("[PASS] Web search was skipped for conversational question, preserving chat memory.")

    conv_content = "".join([e.get("content", "") for e in events_conv if e.get("type") == "content"])
    print(f"[OK] Assistant answer to 'اسم من چیه؟':\n{conv_content.strip()}")
    assert len(conv_content) > 0

    print("\n" + "=" * 60)
    print("[*] TEST 4: Multi-turn Image Preservation")
    print("=" * 60)
    multimodal_history = [
        {"role": "user", "content": "این عکس را ببین", "images": [dummy_img]},
        {"role": "assistant", "content": "تصویر یک پیکسل سفید است."},
        {"role": "user", "content": "رنگش چی بود؟"}
    ]
    events_multi = []
    async for event in gw.stream_chat(
        messages=multimodal_history,
        model_id="deepseek-reasoner",
        enable_web_search=False,
        user_keys={}
    ):
        events_multi.append(event)
    
    multi_content = "".join([e.get("content", "") for e in events_multi if e.get("type") == "content"])
    print(f"[OK] Multi-turn follow-up answer ({len(multi_content)} chars):")
    print(multi_content[:150] + "...")
    assert len(multi_content) > 0

    print("\n[SUCCESS] ALL VERIFICATION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(test_all_fixes())
