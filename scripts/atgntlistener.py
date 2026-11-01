#!/usr/bin/env python3
import runpy
from pathlib import Path

target = Path(r"D:\hermes-main\scripts\atg_nt_listener.py")
runpy.run_path(str(target), run_name="__main__")
