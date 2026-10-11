import os
import sys
import webbrowser
import uvicorn
from pathlib import Path

def main():
    # Ensure UTF-8 output encoding if possible
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print("=" * 60)
    print("[*] Starting OmniLLM Hub Service...")
    print("=" * 60)

    # Check for .env file
    env_path = Path(".env")
    if not env_path.exists():
        example_path = Path(".env.example")
        if example_path.exists():
            print("[INFO] Creating .env from template...")
            with open(example_path, "r", encoding="utf-8") as src, open(env_path, "w", encoding="utf-8") as dst:
                dst.write(src.read())

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 8000))
    url = f"http://{host}:{port}"

    print(f"\n[READY] OmniLLM is running at: {url}")
    print(f"Open your browser and navigate to: {url}")
    print("Press Ctrl + C to stop the server.\n")

    uvicorn.run("app.main:app", host=host, port=port, reload=True)

if __name__ == "__main__":
    main()
