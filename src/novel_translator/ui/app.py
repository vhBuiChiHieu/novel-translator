from __future__ import annotations


def run_desktop() -> None:
    try:
        from .main_window import run_window
    except ImportError as error:
        raise RuntimeError(
            "Desktop UI dependencies are not installed. Install with: pip install 'novel-translator[desktop]'"
        ) from error
    raise SystemExit(run_window())
