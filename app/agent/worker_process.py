"""Bounded temporary-worker primitives; no persistent service or background thread."""
from __future__ import annotations

import os
import selectors
import signal
import subprocess


class WorkerDeadlineExceeded(Exception):
    """The absolute wall-clock budget expired during worker I/O."""


class WorkerProtocolError(Exception):
    """The worker violated the bounded pipe protocol."""


class WorkerOutputTooLarge(Exception):
    """The worker exceeded the bounded IPC output budget."""


_SPAWN_SIGNALS = tuple(
    candidate
    for candidate in (getattr(signal, "SIGALRM", None), getattr(signal, "SIGINT", None))
    if candidate is not None
)


def block_spawn_signals():
    """Defer turn cancellation until a spawned child has an owner."""
    if not _SPAWN_SIGNALS or not hasattr(signal, "pthread_sigmask"):
        return None
    return signal.pthread_sigmask(signal.SIG_BLOCK, _SPAWN_SIGNALS)


def restore_spawn_signals(previous) -> None:
    """Restore the caller's mask; a queued turn signal is delivered here."""
    if previous is not None:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous)


def terminate(process) -> None:
    """Kill and reap a worker, then close both private pipes. Idempotent."""
    if process is None:
        return
    try:
        if process.poll() is None:
            process.kill()
        process.wait()
    except (ProcessLookupError, ChildProcessError, OSError):
        pass
    for stream in (getattr(process, "stdin", None), getattr(process, "stdout", None)):
        try:
            if stream is not None and not stream.closed:
                stream.close()
        except OSError:
            pass


def supervise_pipe(process, packet: bytes, deadline, max_output: int) -> bytes:
    """Feed one bounded packet and collect one bounded response within a deadline."""
    if deadline.expired:
        raise WorkerDeadlineExceeded
    output = bytearray()
    pending = memoryview(packet)
    try:
        with selectors.DefaultSelector() as selector:
            os.set_blocking(process.stdin.fileno(), False)
            os.set_blocking(process.stdout.fileno(), False)
            selector.register(process.stdin, selectors.EVENT_WRITE)
            selector.register(process.stdout, selectors.EVENT_READ)
            while selector.get_map():
                remaining = deadline.remaining()
                if remaining <= 0:
                    raise WorkerDeadlineExceeded
                for key, _ in selector.select(remaining):
                    if key.fileobj is process.stdin:
                        try:
                            count = os.write(process.stdin.fileno(), pending[:8192])
                        except BrokenPipeError:
                            pending = pending[:0]
                        else:
                            pending = pending[count:]
                        if not pending:
                            selector.unregister(process.stdin)
                            try:
                                process.stdin.close()
                            except OSError:
                                pass
                    else:
                        chunk = os.read(process.stdout.fileno(), 16384)
                        if not chunk:
                            selector.unregister(process.stdout)
                            continue
                        output.extend(chunk)
                        if len(output) > max_output:
                            raise WorkerOutputTooLarge
        try:
            process.wait(timeout=deadline.remaining())
        except subprocess.TimeoutExpired:
            raise WorkerDeadlineExceeded from None
        if deadline.expired:
            raise WorkerDeadlineExceeded
        return bytes(output)
    finally:
        terminate(process)
