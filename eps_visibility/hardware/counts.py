"""Live 10-channel count sources: direct FPGA UART, or producer.py's shared memory."""
import os
import queue
import sys
import threading
import time

import numpy as np
import serial

from ..config import CHANNEL_LABELS, COUNTER_NAMES, SHM_NAME, ensure_qutess_on_path


class CountsSource:
    """Background reader that publishes one 10-value report at a time with a sequence number."""

    def __init__(self, log):
        self.log = log
        self.seq = 0
        self.counts = None
        self.error = None
        self._cond = threading.Condition()
        self._stop = threading.Event()
        self._thread = None

    @property
    def alive(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        self._thread = threading.Thread(target=self._guarded_run, daemon=True)
        self._thread.start()

    def stop(self, timeout=4.0):
        self._stop.set()
        with self._cond:
            self._cond.notify_all()
        if self._thread is not None:
            self._thread.join(timeout)

    def _run(self):
        raise NotImplementedError

    def _guarded_run(self):
        try:
            self._run()
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"
            self.log(f"COUNTS ERROR: {self.error}")
        finally:
            with self._cond:
                self._cond.notify_all()

    def _publish(self, counts):
        with self._cond:
            self.seq += 1
            self.counts = [int(c) for c in counts[:10]]
            self._cond.notify_all()

    def wait_after(self, seq, timeout, abort):
        """Block until a report newer than `seq` arrives; returns (seq, counts)."""
        deadline = time.monotonic() + timeout
        with self._cond:
            while self.seq <= seq:
                if abort.is_set():
                    raise InterruptedError("scan aborted")
                if self.error or self._stop.is_set() or not self.alive:
                    raise RuntimeError(f"counts source stopped ({self.error or 'no error'})")
                left = deadline - time.monotonic()
                if left <= 0:
                    raise TimeoutError("no new count report arrived in time")
                self._cond.wait(min(left, 0.1))
            return self.seq, list(self.counts)


class UartCounts(CountsSource):
    """Drives the Qutess FPGA directly via Qutess_1.record_uart_counts (same as producer.py)."""

    def __init__(self, log, port, interval_ms, taps, raw_csv, publish_shm):
        super().__init__(log)
        self.port, self.interval_ms, self.taps = port, interval_ms, taps
        self.raw_csv, self.publish_shm = raw_csv, publish_shm

    def _run(self):
        ensure_qutess_on_path()
        from Qutess_1 import record_uart_counts
        from source import (StatusReceiver, send_command, cmd_set_mode, cmd_set_tap,
                            cmd_set_run_id, cmd_set_interval_and_start, cmd_stop)
        shm = shm_array = None
        if self.publish_shm:     # same layout as producer.py: 10 counts + sequence number
            from multiprocessing import shared_memory
            try:
                stale = shared_memory.SharedMemory(name=SHM_NAME)
                stale.close()
                stale.unlink()
            except FileNotFoundError:
                pass
            shm = shared_memory.SharedMemory(name=SHM_NAME, create=True, size=11 * 8)
            shm_array = np.ndarray((11,), dtype=np.uint64, buffer=shm.buf)
            shm_array.fill(0)
            self.log(f"Publishing counts to shared memory '{SHM_NAME}'")

        def on_counts(counts):
            self._publish(counts)
            if shm_array is not None:
                shm_array[:10] = counts[:10]
                shm_array[10] = self.seq

        config = dict(mode="Serial", com_port=self.port, report_interval_str=str(self.interval_ms),
                      out_path=self.raw_csv, taps=list(self.taps))
        rows = 0
        try:
            _, rows = record_uart_counts(
                config, serial_factory=serial.Serial, receiver_factory=StatusReceiver,
                commands=dict(send=send_command, mode=cmd_set_mode, tap=cmd_set_tap,
                              sync=lambda *a, **kw: b"", run=cmd_set_run_id,
                              start=cmd_set_interval_and_start, stop=cmd_stop),
                counter_names=COUNTER_NAMES, column_names=CHANNEL_LABELS,
                updates=queue.Queue(), stop_event=self._stop,
                running=lambda: not self._stop.is_set(), on_counts=on_counts, log=self.log)
        finally:
            if shm is not None:
                shm.close()
                try:
                    shm.unlink()
                except FileNotFoundError:
                    pass
            if not rows and self.seq == 0:
                _remove_header_only_csv(self.raw_csv)


def _remove_header_only_csv(path):
    """A failed connection leaves a CSV with just the header line; don't litter data/."""
    try:
        with open(path, encoding="utf-8") as fh:
            if sum(1 for _ in fh) <= 1:
                os.remove(path)
    except OSError:
        pass


def _attach_shared_memory(name):
    """Attach without registering with the resource tracker.

    On Linux/macOS (Python < 3.13) an attaching process otherwise *unlinks* the segment when it
    exits, which would destroy producer.py's shared memory when this app closes.
    """
    from multiprocessing import shared_memory
    if sys.version_info >= (3, 13):
        return shared_memory.SharedMemory(name=name, track=False)
    shm = shared_memory.SharedMemory(name=name)
    if os.name == "posix":
        from multiprocessing import resource_tracker
        try:
            resource_tracker.unregister(shm._name, "shared_memory")
        except Exception:
            pass
    return shm


class ShmCounts(CountsSource):
    """Reads what producer.py writes (run producer.py separately; it owns the FPGA port)."""

    def _run(self):
        try:
            shm = _attach_shared_memory(SHM_NAME)
        except FileNotFoundError:
            raise RuntimeError(f"shared memory '{SHM_NAME}' not found - start producer.py first")
        try:
            arr = np.ndarray((11,), dtype=np.uint64, buffer=shm.buf)
            last = int(arr[10])
            self.log(f"Attached to shared memory '{SHM_NAME}'")
            while not self._stop.wait(0.01):
                seq = int(arr[10])
                if seq != last:
                    last = seq
                    self._publish(arr[:10].copy())
        finally:
            shm.close()        # consumer never unlinks
