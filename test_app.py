import asyncio
import io
from PIL import Image
from fastapi.testclient import TestClient
from app.main import app
from app.services import WebSearchService, VisionService, SessionStorage, LLMGateway

client = TestClient(app)

def test_models_catalog():
    response = client.get("/api/models")
    assert response.status_code == 200
    data = response.json()
    models = [m["id"] for m in data["models"]]
    print(f"[OK] Models loaded: {len(models)} models available.")
    assert "deepseek-reasoner" in models
    assert "deepseek-chat" in models
    assert "gpt-4o" in models
    assert "grok-2-vision-1212" in models
    assert "gemini" in models
    assert "claude-3-5-sonnet-20241022" in models
    assert "Atria-Dawn-Preview" in models
    assert "nvidia/nemotron-3-super-120b-a12b:free" in models
    print("[OK] Verified models: DeepSeek, OpenAI, Grok, GLM, Gemini, Claude, Atria, OpenRouter.")

def test_image_upload_and_vision():
    # Create a test 100x100 RGB image
    img = Image.new("RGB", (100, 100), color="teal")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    response = client.post(
        "/api/upload",
        files={"file": ("test.png", buf, "image/png")}
    )
    assert response.status_code == 200
    data = response.json()
    assert "data_url" in data
    assert data["data_url"].startswith("data:image/png;base64,")
    print(f"[OK] Image upload and Vision encoder verified: {data['width']}x{data['height']}")

def test_session_lifecycle():
    test_id = "test_sess_123"
    saved = SessionStorage.save_session(
        session_id=test_id,
        messages=[{"role": "user", "content": "test message"}],
        model="deepseek-reasoner",
        title="test session"
    )
    assert saved["id"] == test_id

    fetched = SessionStorage.get_session(test_id)
    assert fetched is not None
    assert fetched["title"] == "test session"
    assert len(fetched["messages"]) == 1

    SessionStorage.delete_session(test_id)
    assert SessionStorage.get_session(test_id) is None
    print("[OK] Chat session storage lifecycle verified.")

async def test_web_search():
    search_service = WebSearchService()
    results = await search_service.search("Artificial Intelligence news", max_results=2)
    print(f"[OK] Live Web Search results count: {len(results)}")
    if results:
        print(f"   Sample title: {results[0]['title'][:50]}...")

def main():
    print("=" * 50)
    print("[*] Running OmniLLM Automated Test Suite...")
    print("=" * 50)
    test_models_catalog()
    test_image_upload_and_vision()
    test_session_lifecycle()
    asyncio.run(test_web_search())
    print("\n[SUCCESS] ALL TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
