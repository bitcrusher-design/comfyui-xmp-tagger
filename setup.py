"""
setup.py - ComfyUI XMP Tagger
Checks and installs all required dependencies, then launches the application.
"""

import sys
import subprocess
import importlib.util

# Force UTF-8 output on Windows consoles that default to cp1252
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ──────────────────────────────────────────────
# Minimum Python version
# ──────────────────────────────────────────────
MIN_PYTHON = (3, 10)

# ──────────────────────────────────────────────
# Required packages:  (import_name, pip_name, min_version)
# ──────────────────────────────────────────────
REQUIREMENTS = [
    ("PIL",           "Pillow",        "10.0.0"),
    ("customtkinter", "customtkinter", "5.2.0"),
]


def _version_tuple(version_str: str):
    """Convert '10.3.0' -> (10, 3, 0)."""
    try:
        return tuple(int(x) for x in version_str.split(".")[:3])
    except ValueError:
        return (0,)


def check_python_version():
    if sys.version_info < MIN_PYTHON:
        print(
            f"\n  ✗ Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ required, "
            f"but found {sys.version.split()[0]}.\n"
            f"  Please download a newer version from https://python.org\n"
        )
        input("Press Enter to exit...")
        sys.exit(1)
    print(f"  ✓ Python {sys.version.split()[0]}")


def get_installed_version(import_name: str) -> str | None:
    """Return the installed version string, or None if not installed."""
    spec = importlib.util.find_spec(import_name)
    if spec is None:
        return None
    try:
        # Try importlib.metadata first (Python 3.8+)
        from importlib.metadata import version, PackageNotFoundError
        pip_name = "Pillow" if import_name == "PIL" else import_name
        return version(pip_name)
    except Exception:
        # Fallback: try __version__ attribute
        try:
            mod = importlib.import_module(import_name)
            return getattr(mod, "__version__", "unknown")
        except Exception:
            return "unknown"


def install_package(pip_name: str):
    """Install a pip package using the current Python interpreter."""
    print(f"  → Installing {pip_name} ...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", pip_name, "--quiet", "--upgrade"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"\n  ✗ Installation of '{pip_name}' failed!\n")
        print(result.stderr)
        return False
    return True


def check_and_install_requirements():
    all_ok = True
    needs_install = []

    for import_name, pip_name, min_ver in REQUIREMENTS:
        installed = get_installed_version(import_name)

        if installed is None:
            print(f"  ✗ {pip_name} — not installed")
            needs_install.append((pip_name, min_ver))
        elif installed == "unknown":
            print(f"  ? {pip_name} — installed (version unknown)")
        elif _version_tuple(installed) < _version_tuple(min_ver):
            print(
                f"  ⚠ {pip_name} — installed v{installed}, "
                f"but v{min_ver}+ required → will upgrade"
            )
            needs_install.append((pip_name, min_ver))
        else:
            print(f"  ✓ {pip_name} v{installed}")

    if needs_install:
        print()
        for pip_name, _ in needs_install:
            success = install_package(pip_name)
            if not success:
                all_ok = False

        if all_ok:
            print("\n  All packages installed successfully.")
        else:
            print(
                "\n  ✗ One or more packages could not be installed.\n"
                "  Try running:  pip install -r requirements.txt\n"
                "  If the problem persists, check your internet connection\n"
                "  or run this script as Administrator.\n"
            )
            input("Press Enter to exit...")
            sys.exit(1)

    return all_ok


def launch_app():
    """Launch main.py via pythonw.exe (no console window) as a detached process."""
    import os

    # pythonw.exe lives next to python.exe and suppresses the console window
    pythonw = sys.executable.replace("python.exe", "pythonw.exe") \
                             .replace("python3.exe", "pythonw.exe")

    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")

    if os.path.exists(pythonw):
        # Detach completely — setup console closes, GUI stays open
        subprocess.Popen(
            [pythonw, script],
            close_fds=True,
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
    else:
        # Fallback: run in the same process (console stays open)
        print("  (pythonw.exe not found — running with console)")
        try:
            import main as _app  # noqa: F401
        except Exception as e:
            print(f"\n  Could not launch the application: {e}\n")
            import traceback
            traceback.print_exc()
            input("\nPress Enter to exit...")
            sys.exit(1)


def main():
    print("=" * 54)
    print("  ComfyUI XMP Tagger — Setup & Launch")
    print("=" * 54)
    print()

    # 1. Python version
    print("Checking Python version ...")
    check_python_version()
    print()

    # 2. Dependencies
    print("Checking dependencies ...")
    check_and_install_requirements()
    print()

    # 3. Launch app without console window
    print("Starting application ...")
    print("=" * 54)
    launch_app()


if __name__ == "__main__":
    main()
