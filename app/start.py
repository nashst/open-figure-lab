"""Startup script for Open Figure Lab Web UI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root and src to path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from app.api.server import run_server


def main() -> int:
    parser = argparse.ArgumentParser(description="Start Open Figure Lab Web UI")
    parser.add_argument("--port", type=int, default=8080, help="Server port (default: 8080)")
    args = parser.parse_args()

    print("Starting Open Figure Lab Web UI...")
    print(f"Repository: {REPO_ROOT}")
    print(f"Open http://localhost:{args.port} in your browser")
    print("Press Ctrl+C to stop the server")
    print()

    run_server(port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
