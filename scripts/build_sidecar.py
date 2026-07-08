import subprocess
import sys
from pathlib import Path


def main():
    target = Path("src-tauri/sidecars/python")
    target.mkdir(parents=True, exist_ok=True)
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
    print(f"Sidecar Python environment prepared at {target}")


if __name__ == "__main__":
    main()
