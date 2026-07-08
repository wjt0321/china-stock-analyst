import os
import subprocess
import sys
from pathlib import Path


def main():
    target = Path("src-tauri/sidecars/python")
    target.mkdir(parents=True, exist_ok=True)

    # Install desktop Python dependencies into the sidecar package tree.
    # These packages can be picked up by a bundled Python interpreter later.
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "-r",
            "scripts/requirements-desktop.txt",
            "--target",
            str(target / "Lib" / "site-packages"),
        ],
        check=True,
    )
    print(f"Sidecar Python packages installed at {target / 'Lib' / 'site-packages'}")

    if os.environ.get("FULL_PYTHON_SIDECAR"):
        print("FULL_PYTHON_SIDECAR is set: a full embedded Python runtime would be bundled.")
    else:
        print("FULL_PYTHON_SIDECAR is not set: only Python packages are bundled.")
        print("The desktop runtime will use the system Python via src-tauri/sidecars/python.bat.")
        print("Ensure a Python interpreter is available on the target system.")


if __name__ == "__main__":
    main()
