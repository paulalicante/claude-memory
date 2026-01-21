#!/usr/bin/env python
"""
Claude Memory - Launcher script.
Run this file to start the app (no console window with .pyw extension).
"""

import sys
from pathlib import Path

# Add the app directory to path so we can import the package
app_dir = Path(__file__).parent
sys.path.insert(0, str(app_dir))

from claude_memory.main import main

if __name__ == "__main__":
    main()
