#!/usr/bin/env python3
"""
MuseAI Wrapper for Muse.AI Cookie Extractor.
Forward commands or launches Cookie Extractor CLI / Web Server directly.
"""

import os
import sys
import subprocess

MUSEAI_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARENT_DIR = os.path.dirname(MUSEAI_DIR)
MUSE_REG_DIR = os.path.join(PARENT_DIR, "MuseAIRegAcc")
EXTRACTOR_CLI = os.path.join(MUSE_REG_DIR, "cookie_extractor.py")
EXTRACTOR_SERVER = os.path.join(MUSE_REG_DIR, "cookie_extractor_server.py")

def main():
    if not os.path.exists(EXTRACTOR_CLI):
        print(f"❌ Không tìm thấy module tại: {EXTRACTOR_CLI}", file=sys.stderr)
        sys.exit(1)

    args = sys.argv[1:]
    if "--server" in args or "-s" in args:
        args = [a for a in args if a not in ("--server", "-s")]
        cmd = [sys.executable, EXTRACTOR_SERVER] + args
    else:
        cmd = [sys.executable, EXTRACTOR_CLI] + args

    try:
        proc = subprocess.run(cmd, cwd=MUSE_REG_DIR)
        sys.exit(proc.returncode)
    except KeyboardInterrupt:
        sys.exit(0)

if __name__ == "__main__":
    main()
