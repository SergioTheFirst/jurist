"""Windows desktop launcher for bundled LegalDesk builds."""

from __future__ import annotations

from argparse import ArgumentParser, Namespace
from datetime import datetime
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
import webbrowser

import httpx
import uvicorn

from backend.runtime_paths import runtime_data_root


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
STARTUP_TIMEOUT = 25.0


def logs_dir(data_dir: Path | None = None) -> Path:
    """Return the writable log directory for launcher and server diagnostics."""

    root = data_dir if data_dir is not None else runtime_data_root()
    path = root / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def launcher_log_path(data_dir: Path | None = None) -> Path:
    """Return the launcher log path."""

    return logs_dir(data_dir) / "launcher.log"


def server_log_path(data_dir: Path | None = None) -> Path:
    """Return the embedded server log path."""

    return logs_dir(data_dir) / "server.log"


def append_log(message: str, data_dir: Path | None = None) -> None:
    """Append a timestamped diagnostic line to the launcher log."""

    timestamp = datetime.now().isoformat(timespec="seconds")
    with launcher_log_path(data_dir).open("a", encoding="utf-8") as handle:
        handle.write(f"{timestamp} {message}\n")


def build_argument_parser() -> ArgumentParser:
    """Build the launcher CLI parser."""

    parser = ArgumentParser(prog="LegalDesk")
    parser.add_argument("--serve", action="store_true", help="Run the embedded FastAPI server.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Host for the local HTTP server.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port for the local HTTP server.")
    parser.add_argument("--data-dir", default=None, help="Writable runtime directory for DBs, uploads, and caches.")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the browser automatically.")
    parser.add_argument("--stop", action="store_true", help="Stop the running local HTTP server.")
    return parser


def is_server_ready(base_url: str, timeout: float = 2.0) -> bool:
    """Return True when /health responds successfully."""

    try:
        with httpx.Client(base_url=base_url, timeout=timeout) as client:
            response = client.get("/health")
        return response.status_code == 200
    except httpx.HTTPError:
        return False


def wait_for_server(base_url: str, timeout: float = STARTUP_TIMEOUT) -> bool:
    """Wait until the local HTTP server becomes healthy."""

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if is_server_ready(base_url):
            return True
        time.sleep(0.4)
    return False


def wait_for_server_stop(base_url: str, timeout: float = 10.0) -> bool:
    """Wait until the local HTTP server stops responding."""

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not is_server_ready(base_url):
            return True
        time.sleep(0.3)
    return False


def open_browser(base_url: str) -> None:
    """Open the application URL in the default browser."""

    webbrowser.open(base_url, new=1)


def request_server_shutdown(base_url: str, timeout: float = 5.0) -> bool:
    """Request graceful shutdown from the running local server."""

    try:
        with httpx.Client(base_url=base_url, timeout=timeout) as client:
            response = client.post("/api/system/shutdown")
        return response.status_code == 200
    except httpx.HTTPError:
        return False


def build_server_command(host: str, port: int, data_dir: Path | None) -> list[str]:
    """Build the child-process command that runs the embedded server."""

    executable = sys.executable
    command = [executable]
    if not getattr(sys, "frozen", False):
        command.append(str(Path(__file__).resolve()))
    command.extend(["--serve", "--host", host, "--port", str(port), "--no-browser"])
    if data_dir is not None:
        command.extend(["--data-dir", str(data_dir)])
    return command


def launch_server_process(host: str, port: int, data_dir: Path | None) -> subprocess.Popen[bytes]:
    """Start the detached background server process."""

    command = build_server_command(host, port, data_dir)
    env = os.environ.copy()
    if data_dir is not None:
        env["LEGALDESK_DATA_DIR"] = str(data_dir)

    server_log = server_log_path(data_dir)
    server_log.parent.mkdir(parents=True, exist_ok=True)
    append_log(f"Launching embedded server: {' '.join(command)}", data_dir)
    server_log_handle = server_log.open("a", encoding="utf-8")
    popen_kwargs: dict[str, object] = {
        "env": env,
        "stdout": server_log_handle,
        "stderr": server_log_handle,
    }
    if os.name == "nt":
        creationflags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        popen_kwargs["creationflags"] = creationflags

    return subprocess.Popen(command, **popen_kwargs)


def run_server(args: Namespace) -> int:
    """Run the embedded FastAPI server in the current process."""

    data_dir = Path(args.data_dir) if args.data_dir else runtime_data_root()
    try:
        if args.data_dir:
            os.environ["LEGALDESK_DATA_DIR"] = args.data_dir
        append_log(f"Server mode boot requested on {args.host}:{args.port}", data_dir)
        from backend.main import app

        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
        append_log("Embedded server exited normally", data_dir)
        return 0
    except Exception as exc:
        append_log(f"Embedded server crashed: {exc}", data_dir)
        with server_log_path(data_dir).open("a", encoding="utf-8") as handle:
            handle.write(traceback.format_exc())
        return 1


def run_launcher(args: Namespace) -> int:
    """Start the server if needed and open the browser."""

    if args.data_dir:
        os.environ["LEGALDESK_DATA_DIR"] = args.data_dir

    base_url = f"http://{args.host}:{args.port}"
    data_dir = Path(args.data_dir) if args.data_dir else runtime_data_root()
    append_log(f"Launcher start for {base_url}", data_dir)

    if is_server_ready(base_url):
        append_log("Existing local server detected", data_dir)
        if not args.no_browser:
            open_browser(base_url)
        return 0

    process = launch_server_process(args.host, args.port, data_dir)
    if not wait_for_server(base_url):
        append_log(
            f"Embedded server did not become healthy. exit_code={process.poll()} server_log={server_log_path(data_dir)}",
            data_dir,
        )
        if process.poll() is None:
            process.terminate()
        return 1

    append_log("Embedded server became healthy", data_dir)
    if not args.no_browser:
        open_browser(base_url)
    return 0


def run_stop(args: Namespace) -> int:
    """Stop the running local server if it is active."""

    if args.data_dir:
        os.environ["LEGALDESK_DATA_DIR"] = args.data_dir

    base_url = f"http://{args.host}:{args.port}"
    data_dir = Path(args.data_dir) if args.data_dir else runtime_data_root()
    append_log(f"Shutdown requested for {base_url}", data_dir)

    if not is_server_ready(base_url):
        append_log("No running local server detected during shutdown request", data_dir)
        return 0

    if not request_server_shutdown(base_url):
        append_log("Shutdown request failed", data_dir)
        return 1

    if not wait_for_server_stop(base_url):
        append_log("Local server did not stop in time", data_dir)
        return 1

    append_log("Local server stopped successfully", data_dir)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point for the bundled desktop launcher."""

    parser = build_argument_parser()
    args = parser.parse_args(argv)
    if args.serve:
        return run_server(args)
    if args.stop:
        return run_stop(args)
    return run_launcher(args)


if __name__ == "__main__":
    raise SystemExit(main())
