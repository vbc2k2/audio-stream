"""
Build script for creating Windows EXE using PyInstaller (PyQt6 version).
Run: python build_pyqt.py
"""

import subprocess
import sys
from pathlib import Path

def main():
    # Check PyInstaller is installed
    try:
        import PyInstaller
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
    
    # Build command
    script_dir = Path(__file__).parent
    
    # Path separator: ; on Windows, : on Linux/Mac
    import platform
    sep = ";" if platform.system() == "Windows" else ":"
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=AudioStreamPyQt",
        "--onefile",
        "--windowed",  # No console window
        "--icon=NONE",  # No custom icon (you can add one later)
        f"--add-data={script_dir / 'client.html'}{sep}.",
        f"--add-data={script_dir / 'server.py'}{sep}.",
        "--hidden-import=server",
        "--hidden-import=aiortc",
        "--hidden-import=aiortc.contrib.media",
        "--hidden-import=aiohttp",
        "--hidden-import=av",
        "--hidden-import=sounddevice",
        "--hidden-import=numpy",
        "--hidden-import=qrcode",
        "--hidden-import=PIL",
        "--hidden-import=fractions",
        "--hidden-import=PyQt6",
        "--collect-all=aiortc",
        "--collect-all=av",
        "--collect-all=PyQt6",
        str(script_dir / "app_pyqt.py")
    ]
    
    print("Building AudioStreamPyQt.exe...")
    print("This may take a few minutes...")
    print()
    
    subprocess.run(cmd)
    
    print()
    print("=" * 50)
    print("Build complete!")
    print(f"EXE location: {script_dir / 'dist' / 'AudioStreamPyQt.exe'}")
    print("=" * 50)

if __name__ == "__main__":
    main()
