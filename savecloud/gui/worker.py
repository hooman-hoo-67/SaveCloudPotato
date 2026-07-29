"""
Running work off the interface thread.

Reaching a cloud provider takes seconds. Qt redraws nothing while a
slot is executing, so doing that on the interface thread produces a
frozen window - the desktop equivalent of the silent minute that
progress reporting was added to explain.

Everything slow goes through here.
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from savecloud.utils import progress


class WorkerSignals(QObject):
    """
    Signals a worker emits.

    Owned separately because QRunnable is not a QObject and cannot
    carry signals itself.
    """

    finished = Signal(object)

    failed = Signal(str)

    progressed = Signal(str)


class Worker(QRunnable):
    """
    Run one callable on a background thread.

    Results and failures both come back as signals, so a caller never
    has to decide whether to catch something.
    """

    def __init__(
        self,
        work: Callable[[], Any],
        report_progress: bool = False,
    ) -> None:

        super().__init__()

        self.work = work

        self.report_progress = report_progress

        self.signals = WorkerSignals()

        #
        # QThreadPool deletes a runnable as soon as run() returns, and
        # the signals object goes with it - while queued deliveries to
        # the interface thread may still be in flight. Handing the pool
        # a deleted sender segfaults. Lifetime is managed here instead.
        #

        self.setAutoDelete(False)

    @Slot()
    def run(self) -> None:

        #
        # The progress reporter is module-level state shared by every
        # backend, so it is installed for the duration of this call and
        # removed afterwards rather than left pointing at a window that
        # may since have closed.
        #

        if self.report_progress:
            progress.set_reporter(self.signals.progressed.emit)

        try:
            self.signals.finished.emit(self.work())

        except Exception as error:
            self.signals.failed.emit(str(error))

        finally:
            if self.report_progress:
                progress.set_reporter(None)


#
# Workers still capable of emitting. A runnable that nothing referenced
# would be collected mid-flight, taking its signals with it.
#

_running: set[Worker] = set()


def run(
    work: Callable[[], Any],
    on_result: Callable[[Any], None],
    on_error: Callable[[str], None] | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> Worker:
    """
    Run ``work`` in the background and deliver its result.

    Returns the worker, though a caller need not keep it: this module
    holds a reference until the work has finished and its result has
    been delivered.
    """

    worker = Worker(work, report_progress=on_progress is not None)

    worker.signals.finished.connect(on_result)

    if on_error is not None:
        worker.signals.failed.connect(on_error)

    if on_progress is not None:
        worker.signals.progressed.connect(on_progress)

    #
    # Released after delivery rather than after run(), so the signals
    # object outlives the queued emission that carries the result.
    #

    _running.add(worker)

    worker.signals.finished.connect(lambda _: _release(worker))

    worker.signals.failed.connect(lambda _: _release(worker))

    QThreadPool.globalInstance().start(worker)

    return worker


def _release(worker: Worker) -> None:
    """
    Forget a worker whose result has been delivered.
    """

    _running.discard(worker)


def wait(milliseconds: int = 3000) -> bool:
    """
    Block until running work finishes.

    Used when closing, and by tests, so background work never outlives
    the widgets its signals are connected to.
    """

    finished = QThreadPool.globalInstance().waitForDone(milliseconds)

    _running.clear()

    return finished
