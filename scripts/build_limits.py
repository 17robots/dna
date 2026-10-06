"""Build-only serialization and Windows process-tree memory containment."""
from contextlib import contextmanager
import errno
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid


@contextmanager
def compiler_lock(path):
    # Never truncate: Windows locks an existing byte; all contenders use byte 0.
    with path.open('a+b') as lock:
        if os.name == 'nt':
            import msvcrt
            if os.fstat(lock.fileno()).st_size == 0:
                lock.write(b'\0')
                lock.flush()
            lock.seek(0)
            while True:
                try:
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError as error:
                    if error.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                        raise
                    time.sleep(0.1)
            try:
                yield
            finally:
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield


def windows_api():
    import ctypes as c
    from ctypes import wintypes as w
    kernel = c.WinDLL('kernel32', use_last_error=True)
    signatures = {
        'CreateJobObjectW': ([w.LPVOID, w.LPCWSTR], w.HANDLE),
        'SetInformationJobObject': ([w.HANDLE, c.c_int, w.LPVOID, w.DWORD], w.BOOL),
        'AssignProcessToJobObject': ([w.HANDLE, w.HANDLE], w.BOOL),
        'CreateEventW': ([w.LPVOID, w.BOOL, w.BOOL, w.LPCWSTR], w.HANDLE),
        'OpenEventW': ([w.DWORD, w.BOOL, w.LPCWSTR], w.HANDLE),
        'SetEvent': ([w.HANDLE], w.BOOL),
        'WaitForSingleObject': ([w.HANDLE, w.DWORD], w.DWORD),
        'OpenProcess': ([w.DWORD, w.BOOL, w.DWORD], w.HANDLE),
        'CloseHandle': ([w.HANDLE], w.BOOL),
    }
    for name, (args, result) in signatures.items():
        function = getattr(kernel, name)
        function.argtypes, function.restype = args, result
    return c, w, kernel


def run_windows(command, memory_bytes):
    c, w, kernel = windows_api()

    class BasicLimits(c.Structure):
        _fields_ = [('process_time', c.c_int64), ('job_time', c.c_int64),
                    ('flags', w.DWORD), ('min_working_set', c.c_size_t),
                    ('max_working_set', c.c_size_t), ('active_processes', w.DWORD),
                    ('affinity', c.c_size_t), ('priority', w.DWORD),
                    ('scheduling', w.DWORD)]

    class ExtendedLimits(c.Structure):
        _fields_ = [('basic', BasicLimits), ('io', c.c_uint64 * 6),
                    ('process_memory', c.c_size_t), ('job_memory', c.c_size_t),
                    ('peak_process_memory', c.c_size_t), ('peak_job_memory', c.c_size_t)]

    job = kernel.CreateJobObjectW(None, None)
    if not job:
        raise c.WinError(c.get_last_error())
    gate = process_handle = None
    child = None
    try:
        limits = ExtendedLimits()
        # Aggregate committed memory; closing our sole job handle kills descendants.
        limits.basic.flags = 0x200 | 0x2000  # JOB_MEMORY | KILL_ON_JOB_CLOSE
        limits.job_memory = memory_bytes
        if not kernel.SetInformationJobObject(job, 9, c.byref(limits), c.sizeof(limits)):
            raise c.WinError(c.get_last_error())
        name = 'Local\\DNA-compiler-' + uuid.uuid4().hex
        gate = kernel.CreateEventW(None, True, False, name)
        if not gate:
            raise c.WinError(c.get_last_error())
        # The helper may initialize Python, but cannot start compiler work until
        # assignment succeeds. Compiler and linker inherit job membership.
        child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()),
                                  '--windows-gate', name, *command])
        process_handle = kernel.OpenProcess(0x100 | 0x1, False, child.pid)
        if not process_handle:
            raise c.WinError(c.get_last_error())
        if not kernel.AssignProcessToJobObject(job, process_handle):
            raise c.WinError(c.get_last_error())
        if not kernel.SetEvent(gate):
            raise c.WinError(c.get_last_error())
        return child.wait()
    finally:
        # Includes assignment failure: the unsignalled helper must not linger.
        if child is not None and child.poll() is None:
            child.kill()
        kernel.CloseHandle(job)
        if child is not None:
            child.wait()
        if process_handle:
            kernel.CloseHandle(process_handle)
        if gate:
            kernel.CloseHandle(gate)


def gated_child(name, command):
    c, _, kernel = windows_api()
    gate = kernel.OpenEventW(0x100000, False, name)  # SYNCHRONIZE
    if not gate:
        raise c.WinError(c.get_last_error())
    try:
        # A dead parent cannot leave an indefinitely blocked orphan before job
        # assignment. Only WAIT_OBJECT_0 authorizes compiler launch.
        status = kernel.WaitForSingleObject(gate, 60000)
        if status != 0:
            raise RuntimeError(f'Compiler memory-limit gate failed: {status}')
    finally:
        kernel.CloseHandle(gate)
    return subprocess.call(command)


if __name__ == '__main__':
    if os.name != 'nt' or len(sys.argv) < 4 or sys.argv[1] != '--windows-gate':
        raise SystemExit('Internal build-limit helper; invoke compile.py instead')
    raise SystemExit(gated_child(sys.argv[2], sys.argv[3:]))
