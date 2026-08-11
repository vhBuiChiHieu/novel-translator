from __future__ import annotations

import socket
import threading
import time
import webbrowser
from pathlib import Path

import typer
import uvicorn

from .app import create_app
from .errors import WebError
from .runtime import WebRuntime

app = typer.Typer(add_completion=False, help="Run the Novel Translator local web app.")


def _available_port(requested: int) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", requested))
        except OSError as error:
            raise typer.BadParameter(f"Port {requested} is already in use on 127.0.0.1") from error
        return int(probe.getsockname()[1])


@app.command()
def run(
    project: Path | None = typer.Option(None, "--project", help="Absolute project directory to open."),
    port: int = typer.Option(0, "--port", min=0, max=65535, help="Loopback port; 0 chooses a free port."),
    no_open: bool = typer.Option(False, "--no-open", help="Do not open the system browser."),
) -> None:
    runtime = WebRuntime()
    if project is not None:
        try:
            runtime.open_project(project)
        except WebError as error:
            runtime.set_startup_error([error.message, *[str(value) for value in error.details.get("errors", [])]])

    selected_port = _available_port(port)
    local_app = create_app(runtime)
    config = uvicorn.Config(local_app, host="127.0.0.1", port=selected_port, log_level="info", access_log=False)
    server = uvicorn.Server(config)
    local_app.state.server = server
    thread = threading.Thread(target=server.run, name="novel-web-server")
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.02)
        if not server.started:
            raise typer.Exit(code=1)
        url = f"http://127.0.0.1:{selected_port}/#/launch/{runtime.startup_token}"
        if no_open:
            typer.echo(url)
        else:
            typer.echo(f"Novel Translator local web app listening on 127.0.0.1:{selected_port}")
            webbrowser.open(url)
        thread.join()
    except KeyboardInterrupt:
        server.should_exit = True
        thread.join(timeout=30)
    finally:
        if thread.is_alive():
            server.should_exit = True
            thread.join(timeout=30)


def main() -> None:
    app()
