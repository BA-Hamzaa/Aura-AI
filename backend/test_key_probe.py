"""
test_key_probe.py — Quick test that the OpenRouter API key works.
Run from backend/ directory.
"""

import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

key = os.getenv("OPENROUTER_API_KEY", "")
if not key:
    print("❌ No OPENROUTER_API_KEY found in .env")
    exit(1)

print(f"Testing key: {key[:12]}...")
from openrouter_client import test_key

result = test_key(key)
print(f"\nResult: {result}")

if result.get("ok"):
    print("✅ Key is valid!")
    if result.get("warning"):
        print(f"⚠️  Warning: {result['warning']}")
else:
    print(f"❌ Key failed: {result.get('error')}")
