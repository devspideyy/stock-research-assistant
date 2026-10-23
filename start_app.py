"""Start or reuse the local dashboard and open it in the system browser."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import socket
import subprocess
import time
import urllib.error
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"


def is_ready(url: str) -> bool:
    # Local requests must not be sent through an environment HTTP proxy.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(f"{url}/_stcore/health", timeout=1) as response:
            return response.status == 200 and response.read(32).strip() == b"ok"
    except (OSError, urllib.error.URLError):
        return False


def launch(port: int, open_browser: bool) -> int:
    url = f"http://{HOST}:{port}"
    if is_ready(url):
        print("Using the dashboard that is already running.", flush=True)
    else:
        try:
            with socket.create_connection((HOST, port), timeout=1):
                print(f"Port {port} is occupied but the dashboard is not ready.")
                print("Wait for startup to finish, or choose another port with --port.")
                return 1
        except OSError:
            pass

        python = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if not python.is_file():
            print("The project Python environment is missing. Follow the README setup first.")
            return 1
        log_path = ROOT / "runs" / "dashboard.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        options = (
            {"start_new_session": True}
            if os.name != "nt"
            else {
                "creationflags": subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
            }
        )
        with log_path.open("ab") as log:
            process = subprocess.Popen(
                [
                    str(python),
                    str(ROOT / "scripts/run_dashboard.py"),
                    "--server.address",
                    HOST,
                    "--server.port",
                    str(port),
                ],
                cwd=ROOT,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                **options,
            )
        print("Starting the dashboard...", flush=True)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if process.poll() is not None:
                print(f"Dashboard startup failed. Read the log: {log_path}")
                return 1
            if is_ready(url):
                break
            time.sleep(0.25)
        else:
            print(f"The dashboard has not become ready yet. Read the log: {log_path}")
            return 1

    print(f"Dashboard ready: {url}/", flush=True)
    if open_browser and not webbrowser.open(f"{url}/", new=2):
        print("The default browser did not open. Paste the URL above into its address bar.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8517)
    parser.add_argument(
        "--no-browser", action="store_true", help="Check/start without opening a tab"
    )
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    return launch(args.port, not args.no_browser)


if __name__ == "__main__":
    raise SystemExit(main())
