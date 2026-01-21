#!/usr/bin/env python
"""
Install Claude Memory to run on Windows startup.
"""

import os
import sys
import subprocess
from pathlib import Path


def get_pythonw_path():
    """Get path to pythonw.exe (no console window)."""
    python_dir = Path(sys.executable).parent
    pythonw = python_dir / "pythonw.exe"
    if pythonw.exists():
        return str(pythonw)
    return sys.executable


def create_startup_shortcut():
    """Create a shortcut in Windows Startup folder."""
    app_dir = Path(__file__).parent.resolve()
    run_script = app_dir / "run.pyw"

    if not run_script.exists():
        print(f"Error: {run_script} not found")
        return False

    # Windows Startup folder
    startup_folder = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    shortcut_path = startup_folder / "Claude Memory.lnk"

    pythonw = get_pythonw_path()

    # PowerShell script to create shortcut
    ps_script = f'''
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
$Shortcut.TargetPath = "{pythonw}"
$Shortcut.Arguments = '"{run_script}"'
$Shortcut.WorkingDirectory = "{app_dir}"
$Shortcut.Description = "Claude Memory - AI-powered memory management"
$Shortcut.Save()
'''

    try:
        result = subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            print(f"Success! Claude Memory will start automatically on login.")
            print(f"Shortcut created: {shortcut_path}")
            return True
        else:
            print(f"Error creating shortcut: {result.stderr}")
            return False

    except Exception as e:
        print(f"Error: {e}")
        return False


def remove_startup_shortcut():
    """Remove the startup shortcut."""
    startup_folder = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    shortcut_path = startup_folder / "Claude Memory.lnk"

    if shortcut_path.exists():
        shortcut_path.unlink()
        print(f"Removed startup shortcut: {shortcut_path}")
        return True
    else:
        print("No startup shortcut found.")
        return False


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--uninstall":
        remove_startup_shortcut()
    else:
        create_startup_shortcut()
        print("\nTo remove from startup, run: python install.py --uninstall")
