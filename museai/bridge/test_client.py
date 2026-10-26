#!/usr/bin/env python3
"""
Test client to demonstrate calling the Muse.ai RPC Bridge REST API.
"""

import sys
import requests
import json

BASE_URL = "http://127.0.0.1:8765"

def check_status():
    try:
        r = requests.get(f"{BASE_URL}/v1/status", timeout=5)
        print("Status:", json.dumps(r.json(), indent=2))
        return r.json().get("ok", False)
    except Exception as e:
        print(f"Failed to connect to bridge server at {BASE_URL}: {e}")
        return False

def get_history():
    try:
        r = requests.get(f"{BASE_URL}/v1/history", timeout=5)
        data = r.json()
        print("\n[Client] Recent Conversation History:")
        for i, msg in enumerate(data.get("history", [])[-6:]):
            print(f"  {i+1}. {msg[:100]}...")
    except Exception as e:
        print(f"[Client] Failed to fetch history: {e}")

def send_chat(prompt: str, new_thread: bool = False):
    print(f"\n[Client] Sending prompt: '{prompt}'...")
    try:
        r = requests.post(
            f"{BASE_URL}/v1/chat",
            json={"prompt": prompt, "new_thread": new_thread, "timeout_ms": 90000},
            timeout=120
        )
        data = r.json()
        if data.get("ok"):
            print("\n[Client] Response received:")
            print("--------------------------------------------------")
            print(data.get("content"))
            print("--------------------------------------------------")
            if data.get("media"):
                print("[Client] Attached media:", data.get("media"))
            print(f"[Client] Duration: {data.get('duration_ms')}ms")
        else:
            print("[Client] Error:", data)
    except Exception as e:
        print(f"[Client] Request failed: {e}")

if __name__ == "__main__":
    prompt = sys.argv[1] if len(sys.argv) > 1 else "Muse là gì và bạn được phát triển bởi ai?"
    if check_status():
        get_history()
        send_chat(prompt)
    else:
        print("\nPlease start the bridge server first: python3 bridge/server.py")
