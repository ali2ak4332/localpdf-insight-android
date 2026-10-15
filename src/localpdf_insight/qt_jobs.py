"""Deliver child-process results and worker callbacks on the GUI thread."""

import multiprocessing

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from .pdf_jobs import run_pdf_job


class Callbacks(QObject):
    settled = Signal()

    def __init__(self, progress, done, error, parent=None):
        super().__init__(parent)
        self.on_progress, self.on_done, self.on_error = progress, done, error

    @Slot(str)
    def progress(self, message):
        self.on_progress(message)

    @Slot(object)
    def finished(self, result):
        try:
            if self.on_done:
                self.on_done(result)
        except Exception as exc:
            self.on_error(str(exc))
        finally:
            self.settled.emit()

    @Slot(str)
    def error(self, message):
        try:
            self.on_error(message)
        finally:
            self.settled.emit()


class PDFJob(QObject):
    progress = Signal(str)
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, operation, payload, parent=None):
        super().__init__(parent)
        context = multiprocessing.get_context("spawn")
        self.cancel_event = context.Event()
        self.connection, self._sender = context.Pipe(duplex=False)
        self.process = context.Process(
            target=run_pdf_job,
            args=(self._sender, self.cancel_event, operation, payload),
            daemon=True,
        )
        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.poll)
        self._stopped = False

    def start(self):
        if self._stopped:
            return
        try:
            self.process.start()
            self._sender.close()
            self.timer.start()
        except Exception as exc:
            self.connection.close()
            self._sender.close()
            self.error.emit(str(exc))

    def cancel(self):
        self.cancel_event.set()

    @Slot()
    def poll(self):
        try:
            while self.connection.poll():
                kind, value = self.connection.recv()
                if kind == "progress":
                    self.progress.emit(value)
                else:
                    self.stop()
                    if kind == "finished":
                        self.finished.emit(value)
                    else:
                        self.error.emit(value)
                    return
            if not self.process.is_alive():
                code = self.process.exitcode
                self.stop()
                self.error.emit(f"PDF processing stopped unexpectedly (exit code {code}).")
        except (EOFError, OSError):
            self.stop()
            self.error.emit("PDF processing ended without returning a result.")

    def stop(self):
        if self._stopped:
            return
        self._stopped = True
        self.timer.stop()
        self.cancel_event.set()
        if self.process.pid is not None:
            self.process.join(timeout=0.2)
            if self.process.is_alive():
                self.process.terminate()
                self.process.join(timeout=1)
            if not self.process.is_alive():
                self.process.close()
        self.connection.close()
