import asyncio
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.services.codecraft_client import CodeCraftKeyPool
from app.services.atria_client import AtriaKeyPool
from app.services.agnes_client import AgnesKeyPool
from app.providers.codecraft_provider import CodeCraftProvider
from app.providers.atria_provider import AtriaProvider
from app.providers.agnes_provider import AgnesProvider
from app.services.gateway import LLMGateway

async def test_pools():
    print("=" * 60)
    print("🧪 1. Testing Key Pools Initialization & Health Status")
    print("=" * 60)

    cc_pool = CodeCraftKeyPool.get_instance()
    cc_status = cc_pool.get_status()
    print(f"CodeCraft Key Pool: {cc_status['healthy']}/{cc_status['total']} healthy keys.")
    assert cc_status['total'] >= 6, "CodeCraft pool should have at least 6 keys"

    atr_pool = AtriaKeyPool.get_instance()
    atr_status = atr_pool.get_status()
    print(f"Atria Key Pool: {atr_status['healthy']}/{atr_status['total']} healthy keys.")
    assert atr_status['total'] >= 5, "Atria pool should have at least 5 keys"

    agn_pool = AgnesKeyPool.get_instance()
    agn_status = agn_pool.get_status()
    print(f"Agnes Key Pool: {agn_status['healthy']}/{agn_status['total']} healthy keys.")
    assert agn_status['total'] >= 5, "Agnes pool should have at least 5 keys"

    print("\n" + "=" * 60)
    print("🚀 2. Testing Real Streaming Chat Completion with CodeCraft")
    print("=" * 60)
    cc_prov = CodeCraftProvider()
    cc_chunks = []
    async for chunk in cc_prov.stream_chat(
        messages=[{"role": "user", "content": "سلام، یک جمله کوتاه بگو."}],
        model="gpt-5.6-luna",
        max_tokens=30
    ):
        if chunk.get("type") == "content":
            cc_chunks.append(chunk["content"])
    cc_res = "".join(cc_chunks)
    print(f"CodeCraft Response: {cc_res.strip()}")
    assert len(cc_res) > 0, "CodeCraft response should not be empty"

    print("\n" + "=" * 60)
    print("🚀 3. Testing Real Streaming Chat Completion with Atria ASI")
    print("=" * 60)
    atr_prov = AtriaProvider()
    atr_chunks = []
    atr_thinks = []
    async for chunk in atr_prov.stream_chat(
        messages=[{"role": "user", "content": "Hello, short 5 words greeting."}],
        model="Atria-Dawn-Preview",
        max_tokens=150
    ):
        if chunk.get("type") == "content":
            atr_chunks.append(chunk["content"])
        elif chunk.get("type") == "thinking":
            atr_thinks.append(chunk["content"])
    atr_res = "".join(atr_chunks)
    atr_th = "".join(atr_thinks)
    if atr_th:
        print(f"Atria Thinking: {atr_th[:80]}...")
    print(f"Atria Response: {atr_res.strip()}")
    assert len(atr_res) > 0 or len(atr_th) > 0, "Atria response should not be empty"

    print("\n" + "=" * 60)
    print("🚀 4. Testing Real Streaming Chat Completion with Agnes AI")
    print("=" * 60)
    agn_prov = AgnesProvider()
    agn_chunks = []
    agn_thinks = []
    async for chunk in agn_prov.stream_chat(
        messages=[{"role": "user", "content": "Hello, short 5 words greeting."}],
        model="agnes-2.5-flash",
        max_tokens=150
    ):
        if chunk.get("type") == "content":
            agn_chunks.append(chunk["content"])
        elif chunk.get("type") == "thinking":
            agn_thinks.append(chunk["content"])
    agn_res = "".join(agn_chunks)
    agn_th = "".join(agn_thinks)
    print(f"Agnes Thinking: {agn_th[:80]}...")
    print(f"Agnes Response: {agn_res.strip()}")
    assert len(agn_res) > 0 or len(agn_th) > 0, "Agnes response should not be empty"

    print("\n" + "=" * 60)
    print("🔄 5. Testing Gateway Multi-Provider Model Routing")
    print("=" * 60)
    gw = LLMGateway()
    info_cc = gw.get_model_info("gpt-5.6-luna")
    print("Model gpt-5.6-luna provider:", info_cc.get("provider"))
    assert info_cc.get("provider") == "codecraft"

    info_atr = gw.get_model_info("Atria-Dawn-Preview")
    print("Model Atria-Dawn-Preview provider:", info_atr.get("provider"))
    assert info_atr.get("provider") == "atria"

    info_agn = gw.get_model_info("agnes-2.5-flash")
    print("Model agnes-2.5-flash provider:", info_agn.get("provider"))
    assert info_agn.get("provider") == "agnes"

    print("\n" + "=" * 60)
    print("🔄 6. Testing Intelligent Key Rotation & Cooldown Logic")
    print("=" * 60)
    primary_key = cc_pool.get_active_keys()[0]
    print(f"Initial top active key: ...{primary_key[-6:]}")
    cc_pool.record_key_error(primary_key, 429)
    next_key = cc_pool.get_active_keys()[0]
    print(f"Top active key after 429 cooldown: ...{next_key[-6:]}")
    assert primary_key != next_key, "Key rotation must select a different active key on cooldown"
    cc_pool.record_key_success(primary_key)
    print("Recorded success: Cooldown cleared.")

    print("\n" + "=" * 60)
    print("🎉 ALL KEY POOL & PROVIDER TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_pools())
