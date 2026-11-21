#!/usr/bin/env python3
"""Run the trusted installed platform without relying on PATH or the source clone."""
import os
import sys
from pathlib import Path

skill = Path(__file__).resolve().parents[1]
pointer = skill / 'runtime.path'
if not pointer.is_file():
    sys.exit('Runtime pointer missing. Reinstall from the trusted starter kit.')
runtime = (skill / pointer.read_text(encoding='utf-8').strip()).resolve()
cli = runtime / 'installer/gpp.py'
if not cli.is_file():
    sys.exit('Installed runtime missing. Reinstall from the trusted starter kit: python3 installer/gpp.py install-cli')
os.execv(sys.executable, [sys.executable, str(cli), *sys.argv[1:]])
