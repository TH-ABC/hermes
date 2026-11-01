#!/usr/bin/env python3
import sys
import runpy
from pathlib import Path

# Cụm NT Receiver - Mặc định cổng 8998
if "--port" not in sys.argv and "-p" not in sys.argv:
    has_port = False
    for arg in sys.argv[1:]:
        if arg.isdigit():
            has_port = True
            break
    if not has_port:
        sys.argv.extend(["--port", "8998"])

target = Path(__file__).resolve().parent / "sever_hermes_receiver.py"
runpy.run_path(str(target), run_name="__main__")
