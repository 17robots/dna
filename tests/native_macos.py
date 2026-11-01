#!/usr/bin/env python3
"""Qualify the full Darwin service bridge and Cocoa editor on a native host."""
import ctypes as c
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
if sys.platform != 'darwin':
    raise SystemExit('Native macOS execution is required; this is not a cross-object test')


def run(command, **kwargs):
    subprocess.run([str(part) for part in command], check=True, timeout=600, **kwargs)


# The application owns these FFI records. Validate against native headers before
# exercising them. kevent has packing 4, but our stronger alignment preserves
# every field offset and the 32-byte array stride.
ABI = r'''
#include <stddef.h>
#include <sys/stat.h>
#include <sys/event.h>
#include <sys/ioctl.h>
#include <termios.h>
#include <signal.h>
#include <spawn.h>
#include <time.h>
#include <dirent.h>
#include <fcntl.h>
_Static_assert(sizeof(struct stat)==144 && offsetof(struct stat,st_ino)==8 && offsetof(struct stat,st_size)==96, "stat ABI");
_Static_assert(sizeof(struct dirent)==1048 && offsetof(struct dirent,d_name)==21, "dirent ABI");
_Static_assert(sizeof(struct termios)==72 && offsetof(struct termios,c_cc)==32 && offsetof(struct termios,c_ispeed)==56, "termios ABI");
_Static_assert(sizeof(struct sigaction)==16 && offsetof(struct sigaction,sa_mask)==8 && offsetof(struct sigaction,sa_flags)==12, "sigaction ABI");
_Static_assert(sizeof(siginfo_t)==104 && offsetof(siginfo_t,si_pid)==12 && offsetof(siginfo_t,si_status)==20, "waitid ABI");
_Static_assert(sizeof(posix_spawnattr_t)==8 && sizeof(posix_spawn_file_actions_t)==8, "spawn pointer ABI");
_Static_assert(sizeof(struct kevent)==32 && offsetof(struct kevent,filter)==8 && offsetof(struct kevent,data)==16 && offsetof(struct kevent,udata)==24, "kevent ABI");
_Static_assert(TIOCGWINSZ==1074295912 && TIOCSWINSZ==2148037735 && SIGTSTP==18 && SIGBUS==10, "tty constants");
_Static_assert(O_EVTONLY==32768 && O_CLOEXEC==16777216 && EV_DISPATCH==128 && EV_CLEAR==32, "watch constants");
_Static_assert(CLOCK_THREAD_CPUTIME_ID==16 && CLOCK_PROCESS_CPUTIME_ID==12, "CPU clock identifiers");
int main(void) { return 0; }
'''
with tempfile.TemporaryDirectory(prefix='dna-native-macos-') as temporary:
    work = Path(temporary)
    probe = work/'abi'
    subprocess.run(['cc', '-std=c11', '-x', 'c', '-', '-o', str(probe)], input=ABI, text=True, check=True)
    run([probe])
    print('PASS native Darwin header ABI', flush=True)
    environment = dict(os.environ, XDG_CONFIG_HOME=str(work/'config'), XDG_STATE_HOME=str(work/'state'),
                       DNA_RECOVERY='0', DNA_DEFAULT_SERVERS='0', DYN_EDITOR_SMOKE='1')
    for mode in ('debug', 'release'):
        binary = ROOT/('build/dna-cocoa-'+mode)
        run([sys.executable, ROOT/'scripts/build_native.py', '--mode', mode, '--backend', 'native', '--output', binary])
        run([binary, '--version'], env=environment)
        run([binary, '--gui'], cwd=work, env=environment)
        print('PASS full Cocoa startup, presentation and cleanup '+mode, flush=True)
    # The support library is shared by both editor build modes. These tests use
    # real process pipes, cancellation, filesystem replacement and vnode events.
    for test in ('jobs.py', 'disk.py'):
        run([sys.executable, ROOT/'tests'/test], env=environment)
    sys.path.insert(0,str(ROOT/'scripts'))
    from dyn_path import real_dyn
    from native_macos import linker_environment
    compile_environment, links = linker_environment(real_dyn())
    run([sys.executable, ROOT/'scripts/compile.py', real_dyn(), 'build',
         ROOT/'examples/plugins/uppercase', '--release', '--output',
         ROOT/'examples/plugins/uppercase/uppercase', *links], env=compile_environment)
    service_environment = dict(environment, DNA_NATIVE_LIBRARY=str(ROOT/'build/deps/install/lib/libdna_native.dylib'))
    for test in ('plugins.py', 'recovery.py'):
        run([sys.executable, ROOT/'tests'/test], env=service_environment)
    lib = c.CDLL(str(ROOT/'build/deps/install/lib/libdna_native.dylib'))
    callback_type = c.CFUNCTYPE(None, c.c_void_p)
    notified = threading.Event()
    callback = callback_type(lambda context: notified.set())
    lib.dna_native_gui_attach.argtypes = [callback_type, c.c_void_p]
    lib.dna_watch.argtypes = [c.c_int, c.c_int]
    lib.dna_unwatch.argtypes = [c.c_int]
    lib.dna_native_gui_attach(callback, None)
    assert lib.dna_notify_start() == 1
    read_fd, write_fd = os.pipe()
    try:
        for payload in (b'a', b'b'):
            notified.clear()
            lib.dna_watch(read_fd, 0)
            os.write(write_fd, payload)
            assert notified.wait(3), 'kqueue readiness/rearm deadline'
            assert os.read(read_fd, 1) == payload
        lib.dna_unwatch(read_fd)
    finally:
        lib.dna_notify_stop()
        lib.dna_native_gui_attach(callback_type(), None)
        os.close(read_fd)
        os.close(write_fd)
    print('PASS native Darwin one-shot readiness and rearm', flush=True)
    lib.dna_path_watch_open.argtypes = [c.c_char_p]
    lib.dna_path_watch_open.restype = c.c_void_p
    lib.dna_path_watch_poll.argtypes = [c.c_void_p]
    lib.dna_path_watch_close.argtypes = [c.c_void_p]
    watched_path = work/'config.txt'
    watched_path.write_bytes(b'old')
    watched = lib.dna_path_watch_open(os.fsencode(watched_path))
    assert watched
    try:
        watched_path.write_bytes(b'new')
        deadline = time.monotonic()+3
        while lib.dna_path_watch_poll(watched) == 0:
            assert time.monotonic()<deadline, 'existing file vnode write deadline'
            time.sleep(.005)
    finally:
        lib.dna_path_watch_close(watched)
    print('PASS native Darwin existing-file config change', flush=True)
    lib.dna_terminal_open.argtypes = [c.c_char_p]*3
    lib.dna_terminal_open.restype = c.c_void_p
    for name in ('dna_terminal_poll', 'dna_terminal_alive', 'dna_terminal_close'):
        getattr(lib,name).argtypes = [c.c_void_p]
    lib.dna_terminal_snapshot.argtypes = [c.c_void_p,c.c_void_p,c.c_size_t]
    lib.dna_terminal_snapshot.restype = c.c_size_t
    terminal = lib.dna_terminal_open(os.fsencode(work), b'/bin/sh', b'printf native-pty')
    assert terminal, 'native forkpty'
    try:
        deadline = time.monotonic()+10
        while lib.dna_terminal_alive(terminal):
            assert time.monotonic()<deadline, 'native PTY exit deadline'
            lib.dna_terminal_poll(terminal)
            time.sleep(.005)
        # Drain any last bytes after the child exit notification.
        lib.dna_terminal_poll(terminal)
        output = c.create_string_buffer(65536)
        length = lib.dna_terminal_snapshot(terminal, output, len(output))
        assert b'native-pty' in output.raw[:length], output.raw[:length]
    finally:
        lib.dna_terminal_close(terminal)
    print('PASS native Darwin PTY output and child lifecycle', flush=True)
print('PASS full native macOS qualification', flush=True)
