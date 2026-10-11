import asyncio
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
from app.services.gateway import LLMGateway

async def test():
    gw = LLMGateway()
    print("[*] Testing DeepSeek R1 / Free without API keys...")
    chunks = []
    thinkings = []
    async for event in gw.stream_chat(
        messages=[{"role": "user", "content": "Hello, answer in 1 sentence."}],
        model_id="deepseek-reasoner",
        enable_web_search=False,
        user_keys={}
    ):
        if event["type"] == "status":
            print(f"[STATUS] {event['message']}")
        elif event["type"] == "thinking":
            thinkings.append(event["content"])
        elif event["type"] == "content":
            chunks.append(event["content"])
        elif event["type"] == "error":
            print(f"[ERROR] {event['message']}")
    
    if thinkings:
        print(f"[OK] Thinking received: {len(''.join(thinkings))} chars")
    print(f"[OK] Content received: {''.join(chunks).strip()}")

if __name__ == "__main__":
    asyncio.run(test())
