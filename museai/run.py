#!/usr/bin/env -S arch -arm64 python3
"""
Muse.ai Unified Runner
Supports:
1. Headless RPC Server (No Browser, Noise_XX protocol, high-concurrency multi-account)
2. In-Browser RPC Bridge Server (Legacy Playwright browser mode)
3. Direct CLI Batch Generation (No Browser)
4. Direct CLI Single Generation (No Browser)
5. Standalone client
"""

import argparse
import asyncio
import json
import os
import sys

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT_DIR)


def run_headless(args):
    from bridge.headless_server import HeadlessBridgeServer
    print("\n[+] Starting Headless Noise RPC Server (No Browser)...")
    server = HeadlessBridgeServer(
        cookies_dir=args.cookies,
        port=args.port,
        host=args.host,
        concurrency=args.concurrency
    )
    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        print("\n[+] Headless server stopped.")


def run_bridge(args):
    if getattr(args, "no_browser", False):
        return run_headless(args)
    from bridge.server import MuseBridgeServer
    print("\n[+] Starting In-Browser RPC Bridge Server...")
    server = MuseBridgeServer(
        port=args.port,
        cdp_url=args.cdp_url,
        cookies_path=args.cookies,
        headless=not args.headful
    )
    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        print("\n[+] Bridge server stopped.")


def run_gen(args):
    from client.muse_noise_engine import MuseNoisePool
    pool = MuseNoisePool(args.cookies)
    files = [args.file] if args.file else []
    print(f"\n[+] Headless Generation:")
    print(f"    Prompt: '{args.prompt}'")
    if files:
        print(f"    File: {files}")
    res = pool.generate_one(args.prompt, files=files, timeout_s=args.timeout)
    print("\n=== RESULT ===")
    print("OK:", res.get("ok"))
    if res.get("content"):
        print("Content:", res.get("content"))
    if res.get("media"):
        print("Media URLs:", res.get("media"))
    if res.get("local_paths"):
        print("Local Paths:", res.get("local_paths"))
    print(f"Duration: {res.get('duration_ms')}ms")


def run_batch(args):
    from client.muse_noise_engine import MuseNoisePool
    pool = MuseNoisePool(args.cookies)

    if not os.path.exists(args.input):
        print(f"[-] Input file not found: {args.input}")
        return

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        items = [{"prompt": it} if isinstance(it, str) else it for it in data]
    elif isinstance(data, dict):
        items = data.get("items") or [{"prompt": p} for p in data.get("prompts", [])]
    else:
        print("[-] Invalid input format: must be JSON list of prompts or items")
        return

    print(f"\n[+] Executing batch of {len(items)} items (concurrency={args.concurrency})...")
    t0 = time.time()
    results = pool.generate_batch(items, concurrency=args.concurrency, timeout_s=args.timeout)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"[+] Saved results to {args.output}")

    ok_count = sum(1 for r in results if r and r.get("ok"))
    print(f"\n=== BATCH SUMMARY ===")
    print(f"Success: {ok_count}/{len(items)}")
    for idx, r in enumerate(results):
        media = r.get("media", [])
        dur = r.get("duration_ms", 0)
        status = "OK" if r.get("ok") else f"FAIL ({r.get('error')})"
        print(f"  #{idx+1}: {status} | media={media} | {dur}ms")


def run_test_bridge(args):
    import requests
    url = f"http://127.0.0.1:{args.port}"
    print(f"\n[+] Testing Bridge Server at {url}...")
    try:
        status = requests.get(f"{url}/v1/status").json()
        print("Status:", json.dumps(status, indent=2))
        if not status.get("ok"):
            print("[-] Bridge is not ready.")
            return

        print(f"\n[+] Sending prompt: {args.prompt}")
        resp = requests.post(f"{url}/v1/chat", json={"prompt": args.prompt}, timeout=120).json()
        print("\n=== RESPONSE ===")
        print(resp.get("content", ""))
        if resp.get("media"):
            print("\n[+] Media:", resp.get("media"))
        print(f"\n[+] Duration: {resp.get('duration_ms')}ms")
    except Exception as e:
        print(f"[-] Error: {e}")


def run_standalone(args):
    from client.muse_client import MuseClient

    if not os.path.exists(args.config):
        print(f"[-] Config file '{args.config}' not found.")
        print("    Run client/extract_keys.js in Chrome console to export your config JSON.")
        return

    with open(args.config, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    cookies = cfg.get("cookies", "")
    rv_key_hex = cfg.get("rvKeyHex")
    vm_id = cfg.get("vmId")

    if not cookies:
        print("[-] 'cookies' missing in config file.")
        return

    client = MuseClient(cookies=cookies, rv_key_hex=rv_key_hex)

    async def _execute():
        print("[+] Fetching gateway tokens from muse.ai...")
        token_data = client.fetch_gateway_token(vm_name=vm_id)
        gateway_url = token_data.get("gatewayUrl", "wss://gateway.muse.ai/")
        auth_token = token_data.get("token", "")
        notary_token = token_data.get("notary_token")

        print(f"[+] Gateway URL: {gateway_url}")
        target_vm = vm_id or token_data.get("vmId", "default")

        await client.connect(
            vm_id=target_vm,
            gateway_url=gateway_url,
            auth_token=auth_token,
            notary_token=notary_token
        )

        print(f"\n[+] Sending prompt: '{args.prompt}'")
        async for event in client.chat_stream(args.prompt):
            print("Event:", event)

        await client.close()

    asyncio.run(_execute())


def main():
    parser = argparse.ArgumentParser(description="Muse.ai API CLI & Server")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Headless server (No Browser)
    p_headless = subparsers.add_parser("headless", help="Start Headless RPC Server (No Browser, Noise_XX)")
    p_headless.add_argument("--port", type=int, default=8770, help="Port to listen on (default: 8770)")
    p_headless.add_argument("--host", type=str, default="0.0.0.0", help="Host address (default: 0.0.0.0)")
    p_headless.add_argument("--cookies", type=str, default=os.path.join(ROOT_DIR, "cookies"), help="Path to cookies directory or file")
    p_headless.add_argument("--concurrency", type=int, default=4, help="Concurrency limit across pool")
    p_headless.set_defaults(func=run_headless)

    # CLI Single generation (Headless)
    p_gen = subparsers.add_parser("gen", help="Generate single image/video directly without browser")
    p_gen.add_argument("--prompt", "-p", type=str, required=True, help="Prompt text")
    p_gen.add_argument("--file", "-f", type=str, default=None, help="Reference image file path or URL")
    p_gen.add_argument("--cookies", type=str, default=os.path.join(ROOT_DIR, "cookies.json"), help="Cookies path")
    p_gen.add_argument("--timeout", type=int, default=240, help="Timeout in seconds")
    p_gen.set_defaults(func=run_gen)

    # CLI Batch generation (Headless)
    p_batch = subparsers.add_parser("batch", help="Generate batch of images/videos concurrently without browser")
    p_batch.add_argument("--input", "-i", type=str, required=True, help="Path to input JSON file with prompts")
    p_batch.add_argument("--output", "-o", type=str, default=None, help="Path to save result JSON")
    p_batch.add_argument("--cookies", type=str, default=os.path.join(ROOT_DIR, "cookies"), help="Cookies path")
    p_batch.add_argument("--concurrency", "-c", type=int, default=2, help="Concurrency level")
    p_batch.add_argument("--timeout", type=int, default=300, help="Timeout per task in seconds")
    p_batch.set_defaults(func=run_batch)

    # Bridge server (Legacy Browser mode)
    p_bridge = subparsers.add_parser("bridge", help="Start In-Browser RPC Bridge Server")
    p_bridge.add_argument("--port", type=int, default=8765, help="Port to listen on (default: 8765)")
    p_bridge.add_argument("--cdp-url", type=str, default=None, help="Chrome CDP URL")
    p_bridge.add_argument("--cookies", type=str, default=None, help="Path to cookies.json")
    p_bridge.add_argument("--headful", action="store_true", help="Launch visible browser")
    p_bridge.add_argument("--no-browser", action="store_true", help="Switch to headless Noise mode")
    p_bridge.add_argument("--concurrency", type=int, default=4, help="Concurrency limit")
    p_bridge.add_argument("--host", type=str, default="0.0.0.0", help="Host address")
    p_bridge.set_defaults(func=run_bridge)

    # Test bridge
    p_test = subparsers.add_parser("test-bridge", help="Send a prompt to the running Bridge Server")
    p_test.add_argument("--port", type=int, default=8765, help="Bridge port (default: 8765)")
    p_test.add_argument("--prompt", type=str, default="Xin chào Muse!", help="Prompt to send")
    p_test.set_defaults(func=run_test_bridge)

    # Standalone client
    p_stand = subparsers.add_parser("standalone", help="Run Standalone Python Client with Noise Protocol")
    p_stand.add_argument("--config", type=str, default="muse_config.json", help="Path to config file")
    p_stand.add_argument("--prompt", type=str, default="Xin chào Muse!", help="Prompt to send")
    p_stand.set_defaults(func=run_standalone)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
