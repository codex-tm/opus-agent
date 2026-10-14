"""
OPUS Agent - Launcher Script
"""
import sys
import os
from pathlib import Path

# Garante suporte pleno a UTF-8 no Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Garante que o diretório atual está no sys.path
sys.path.insert(0, str(Path(__file__).parent.resolve()))

from opus.cli import main

if __name__ == "__main__":
    main()

