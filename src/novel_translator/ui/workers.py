from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, Signal


class WorkerSignals(QObject):
    result = Signal(object)
    error = Signal(str)
    finished = Signal()
    progress = Signal(object)


class FunctionWorker(QRunnable):
    def __init__(self, function: Callable[..., object], *args: object, **kwargs: object) -> None:
        super().__init__()
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    def run(self) -> None:
        try:
            result = self.function(*self.args, **self.kwargs)
        except Exception as error:
            self.signals.error.emit(str(error))
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()
