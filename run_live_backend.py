from __future__ import annotations

import os
import pathlib
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"


def main() -> int:
    os.environ["USE_LIVE_APIFY"] = "True"
    os.environ["DEBUG_MODE"] = "False"
    os.chdir(BACKEND_DIR)
    return subprocess.call(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8003",
        ],
    )


if __name__ == "__main__":
    raise SystemExit(main())
