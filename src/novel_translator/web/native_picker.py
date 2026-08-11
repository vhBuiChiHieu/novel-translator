from __future__ import annotations

from pathlib import Path


class NativePickerUnavailable(RuntimeError):
    """Raised when the local machine cannot open a directory picker."""


def choose_directory(*, title: str) -> Path | None:
    """Open the OS directory picker and return the selected absolute path."""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError as error:
        raise NativePickerUnavailable("The native folder picker is not available in this Python installation.") from error

    root: tk.Tk | None = None
    try:
        root = tk.Tk()
        root.withdraw()
        try:
            root.attributes("-topmost", True)
        except tk.TclError:
            pass
        root.update()
        selected = filedialog.askdirectory(title=title, mustexist=True)
    except (OSError, tk.TclError) as error:
        raise NativePickerUnavailable("The native folder picker could not be opened.") from error
    finally:
        if root is not None:
            root.destroy()

    return Path(selected).expanduser().resolve() if selected else None
