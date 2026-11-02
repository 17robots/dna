#!/usr/bin/env python3
"""Qualify the complete Windows DLL/editor on a real native host."""
import contextlib
import ctypes as c
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import native_windows as native

ABI = r'''
#include <stddef.h>
#include <windows.h>
#include <vterm.h>
#include <tree_sitter/api.h>
_Static_assert(sizeof(COORD)==4, "COORD value ABI");
_Static_assert(sizeof(STARTUPINFOEXW)==112 && offsetof(STARTUPINFOEXW,lpAttributeList)==104, "process ABI");
_Static_assert(sizeof(JOBOBJECT_EXTENDED_LIMIT_INFORMATION)==144, "Job limits ABI");
_Static_assert(sizeof(VTermColor)==4 && sizeof(VTermScreenCell)==40, "vterm cell ABI");
_Static_assert(offsetof(VTermScreenCell,width)==24 && offsetof(VTermScreenCell,attrs)==28 && offsetof(VTermScreenCell,fg)==32, "vterm cell fields");
_Static_assert(sizeof(VTermPos)==8 && sizeof(VTermRect)==16, "vterm position ABI");
_Static_assert(sizeof(TSNode)==32 && sizeof(TSQueryCapture)==40 && sizeof(TSQueryMatch)==16, "tree-sitter values ABI");
_Static_assert(sizeof(TSInput)==32 && sizeof(TSParseOptions)==16, "tree-sitter callback ABI");
int main(void) { return 0; }
'''


def run(command, **kwargs):
    return subprocess.run([str(part) for part in command], check=True, timeout=600, **kwargs)


def await_value(predicate, description, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(.005)
    raise AssertionError(description)


def private_acl(path):
    security = c.WinDLL('advapi32', use_last_error=True)
    kernel = c.WinDLL('kernel32', use_last_error=True)
    security.GetNamedSecurityInfoW.argtypes = [c.c_wchar_p, c.c_uint32, c.c_uint32,
        c.c_void_p, c.c_void_p, c.POINTER(c.c_void_p), c.c_void_p, c.POINTER(c.c_void_p)]
    security.GetNamedSecurityInfoW.restype = c.c_uint32
    security.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes = [c.c_void_p,
        c.c_uint32, c.c_uint32, c.POINTER(c.c_void_p), c.POINTER(c.c_uint32)]
    security.ConvertSecurityDescriptorToStringSecurityDescriptorW.restype = c.c_int
    kernel.LocalFree.argtypes = [c.c_void_p]
    descriptor, dacl, text = c.c_void_p(), c.c_void_p(), c.c_void_p()
    assert security.GetNamedSecurityInfoW(str(path), 1, 4, None, None, c.byref(dacl), None, c.byref(descriptor)) == 0
    try:
        length = c.c_uint32()
        assert security.ConvertSecurityDescriptorToStringSecurityDescriptorW(descriptor, 1, 4, c.byref(text), c.byref(length))
        value = c.wstring_at(text)
        assert value.startswith('D:P') and value.count('(A;') == 1 and ';;;OW)' in value, value
    finally:
        if text:
            kernel.LocalFree(text)
        kernel.LocalFree(descriptor)


def service_tests(library, work):
    native.audit_runtime([library])
    with contextlib.ExitStack() as directories:
        directories.enter_context(os.add_dll_directory(str(library.parent)))
        lib = c.CDLL(str(library))
        test_jobs(lib, work)
        test_picker_search(lib, work)
        test_recovery(lib, work)
        test_disk(lib, work)
        test_terminal(lib, work)
    print('PASS complete Windows service DLL: jobs, picker, content search, recovery, disk and ConPTY', flush=True)


def test_jobs(lib, work):
    lib.dna_job_open.argtypes = [c.c_char_p, c.c_char_p, c.c_void_p, c.c_size_t, c.c_uint32]
    lib.dna_job_open.restype = c.c_void_p
    lib.dna_job_status.argtypes = [c.c_void_p]
    lib.dna_job_output_length.argtypes = [c.c_void_p]
    lib.dna_job_output_length.restype = c.c_ssize_t
    lib.dna_job_output.argtypes = [c.c_void_p, c.c_void_p, c.c_size_t]
    lib.dna_job_output.restype = c.c_size_t
    lib.dna_job_close.argtypes = [c.c_void_p]
    helper = work / 'job helper.py'
    helper.write_text('import sys;sys.stdout.buffer.write(sys.stdin.buffer.read().upper())', encoding='utf-8')
    command = f'"{sys.executable}" "{helper}"'.encode('utf-8')
    data = b'hello\x00world\r\n' * 30000
    job = lib.dna_job_open(command, str(work).encode('utf-8'), data, len(data), 5000)
    assert job, 'full DLL job creation'
    try:
        await_value(lambda: lib.dna_job_status(job) != 1, 'full DLL job exit')
        assert lib.dna_job_status(job) == 2
        size = lib.dna_job_output_length(job)
        output = c.create_string_buffer(size + 1)
        assert lib.dna_job_output(job, output, len(output)) == len(data)
        assert output.raw[:size] == data.upper()
    finally:
        lib.dna_job_close(job)
    for command, expected in ((b'exit /b 7', 3), (b'ping -n 20 127.0.0.1 >nul', 5)):
        job = lib.dna_job_open(command, str(work).encode('utf-8'), b'', 0, 100)
        assert job
        try:
            await_value(lambda: lib.dna_job_status(job) != 1, 'job failure/timeout')
            assert lib.dna_job_status(job) == expected
        finally:
            lib.dna_job_close(job)
    print('PASS full DLL jobs: Unicode cwd, binary input, output, failed exit and timeout', flush=True)


def test_picker_search(lib, work):
    tree = work / 'indexed café 日本語'
    tree.mkdir()
    (tree / 'cleanup.sh').write_text('native needle\n', encoding='utf-8')
    (tree / 'cleanup2.sh').write_text('second payload\n', encoding='utf-8')
    lib.dna_picker_open.restype = c.c_void_p
    lib.dna_picker_submit.argtypes = [c.c_void_p, c.c_char_p]
    lib.dna_picker_submit.restype = c.c_uint64
    lib.dna_picker_poll.argtypes = [c.c_void_p, c.c_uint64, c.POINTER(c.c_size_t), c.POINTER(c.c_size_t), c.POINTER(c.c_uint32)]
    lib.dna_picker_row.argtypes = [c.c_void_p, c.c_uint64, c.c_size_t, c.c_void_p, c.c_size_t]
    lib.dna_picker_row.restype = c.c_size_t
    lib.dna_picker_close.argtypes = [c.c_void_p]
    picker = lib.dna_picker_open()
    assert picker
    try:
        generation = lib.dna_picker_submit(picker, str(tree).encode('utf-8'))
        count, visited, flags = c.c_size_t(), c.c_size_t(), c.c_uint32()
        result = await_value(lambda: lib.dna_picker_poll(picker, generation, c.byref(count), c.byref(visited), c.byref(flags)), 'picker completion')
        assert result == 1 and flags.value == 0, ('picker result', result, flags.value)
        names = []
        for index in range(count.value):
            output = c.create_string_buffer(4096)
            size = lib.dna_picker_row(picker, generation, index, output, len(output))
            names.append(output.raw[:size].decode('utf-8'))
        assert set(names) == {'cleanup.sh', 'cleanup2.sh'}, names
    finally:
        lib.dna_picker_close(picker)
    class Row(c.Structure):
        _fields_ = [('path', c.c_char * 4096), ('text', c.c_char * 256),
                    ('start', c.c_size_t), ('end', c.c_size_t), ('line', c.c_size_t), ('column', c.c_size_t)]
    lib.dna_search_open.restype = c.c_void_p
    lib.dna_search_submit.argtypes = [c.c_void_p, c.c_char_p, c.c_char_p]
    lib.dna_search_count.argtypes = [c.c_void_p, c.POINTER(c.c_int)]
    lib.dna_search_count.restype = c.c_size_t
    lib.dna_search_row.argtypes = [c.c_void_p, c.c_size_t, c.POINTER(Row)]
    lib.dna_search_close.argtypes = [c.c_void_p]
    search = lib.dna_search_open()
    assert search
    try:
        lib.dna_search_submit(search, str(tree).encode('utf-8'), b'needle')
        status = c.c_int()
        def complete():
            count = lib.dna_search_count(search, c.byref(status))
            return (count, status.value) if status.value != 1 else None
        count, status = await_value(complete, 'content search completion')
        assert status == 0 and count == 1, ('content search result', count, status)
        row = Row()
        assert lib.dna_search_row(search, 0, c.byref(row)) == 1
        assert bytes(row.path).endswith(b'cleanup.sh') and b'needle' in bytes(row.text)
    finally:
        lib.dna_search_close(search)
    print('PASS full DLL file picker and content search in Unicode directory', flush=True)


def test_recovery(lib, work):
    from recovery_windows import shared_read
    lib.dna_recovery_open.argtypes = [c.c_char_p]
    lib.dna_recovery_open.restype = c.c_void_p
    lib.dna_recovery_submit.argtypes = [c.c_void_p, c.c_char_p, c.c_size_t]
    lib.dna_recovery_error.argtypes = [c.c_void_p]
    lib.dna_recovery_close.argtypes = [c.c_void_p]
    root = work / 'private session/recovery'
    recovery = lib.dna_recovery_open(str(root).encode('utf-8'))
    assert recovery
    payload = b'final recovery snapshot\n' * 10000
    try:
        for index in range(12):
            assert lib.dna_recovery_submit(recovery, payload, len(payload)) == 1
        def complete():
            for path in root.glob('session-*'):
                if not path.name.endswith('.tmp'):
                    try:
                        if shared_read(path) == payload:
                            return path
                    except (FileNotFoundError, PermissionError):
                        pass
            return None
        path = await_value(complete, 'atomic recovery publication')
        assert lib.dna_recovery_error(recovery) == 0
        private_acl(path)
    finally:
        lib.dna_recovery_close(recovery)
    assert not list(root.iterdir())
    print('PASS full DLL recovery: atomic bytes, private Windows ACL and cleanup', flush=True)


def test_disk(lib, work):
    path = work / 'watched.txt'
    path.write_bytes(b'old')
    lib.dna_disk_open.restype = c.c_void_p
    lib.dna_disk_watch_checked.argtypes = [c.c_void_p, c.c_size_t, c.c_uint64, c.c_char_p, c.c_void_p, c.c_size_t]
    lib.dna_disk_pending_at.argtypes = [c.c_void_p, c.c_size_t, c.c_uint64]
    lib.dna_disk_pending_at.restype = c.c_ssize_t
    lib.dna_disk_take_at.argtypes = [c.c_void_p, c.c_size_t, c.c_uint64, c.c_void_p, c.c_size_t]
    lib.dna_disk_close.argtypes = [c.c_void_p]
    disk = lib.dna_disk_open()
    assert disk
    try:
        assert lib.dna_disk_watch_checked(disk, 0, 77, str(path).encode('utf-8'), b'old', 3) == 1
        path.write_bytes(b'updated')
        await_value(lambda: lib.dna_disk_pending_at(disk, 0, 77) > 0, 'background file-change detection')
        output = c.create_string_buffer(64)
        assert lib.dna_disk_take_at(disk, 0, 77, output, len(output)) == 1 and output.value == b'updated'
    finally:
        lib.dna_disk_close(disk)
    print('PASS full DLL disk worker: native change notification and snapshot publication', flush=True)


def test_terminal(lib, work):
    lib.dna_terminal_open.argtypes = [c.c_char_p] * 3
    lib.dna_terminal_open.restype = c.c_void_p
    for name in ('dna_terminal_poll', 'dna_terminal_alive', 'dna_terminal_close'):
        getattr(lib, name).argtypes = [c.c_void_p]
    lib.dna_terminal_snapshot.argtypes = [c.c_void_p, c.c_void_p, c.c_size_t]
    lib.dna_terminal_snapshot.restype = c.c_size_t
    terminal = lib.dna_terminal_open(str(work).encode('utf-8'), b'/bin/sh', b'echo full-native-pty')
    assert terminal
    try:
        output = c.create_string_buffer(65536)
        def finished_frame():
            lib.dna_terminal_poll(terminal)
            length = lib.dna_terminal_snapshot(terminal, output, len(output))
            return lib.dna_terminal_alive(terminal) == 0 and b'full-native-pty' in output.raw[:length]
        await_value(finished_frame, 'full DLL ConPTY child exit and final frame')
    finally:
        lib.dna_terminal_close(terminal)
    print('PASS full DLL ConPTY, libvterm, snapshot and child cleanup', flush=True)


def main():
    if len(sys.argv) == 4 and sys.argv[1] == '--services':
        service_tests(Path(sys.argv[2]), Path(sys.argv[3]))
        return
    if os.name != 'nt':
        native.cross_objects()
        print('QUALIFICATION GAP: complete Windows objects do not prove native linking, GUI, or service execution.', flush=True)
        return
    compiler = native.dependencies()
    env = native.environment(compiler)
    with tempfile.TemporaryDirectory(prefix='dna-full-windows-') as temporary:
        work = Path(temporary)
        c_source = work / 'abi.c'
        c_source.write_text(ABI, encoding='utf-8')
        abi = work / 'abi.exe'
        flags = shlex.split(subprocess.check_output([str(native.tool('pkg-config')), '--cflags', 'vterm', 'tree-sitter'], text=True, env=env))
        run([native.tool('gcc'), '-std=c11', '-Werror', c_source, *flags, '-o', abi], env=env)
        run([abi], env=env)
        print('PASS Windows/MSYS2 native headers: process, Job, ConPTY, libvterm and Tree-sitter ABI', flush=True)
        runtime = work / 'native services café 日本語'
        runtime.mkdir()
        run([sys.executable, Path(__file__).resolve(), '--services', native.DEPS / 'install/lib/dna_native.dll', runtime], env=env)
        cwd = work / 'GUI cwd café 日本語'
        cwd.mkdir()
        font = Path(os.environ['SystemRoot']) / 'Fonts/consola.ttf'
        if not font.is_file():
            raise SystemExit('Native GUI qualification requires the system Consolas TrueType font: ' + str(font))
        config = work / 'dna.toml'
        config.write_text('font = "' + font.as_posix() + '"\nreduced_motion = true\n', encoding='utf-8')
        isolated = dict(env, HOME=str(work), USERPROFILE=str(work), XDG_CONFIG_HOME=str(work / 'config'),
            XDG_STATE_HOME=str(work / 'state'), DNA_CONFIG=str(config), DNA_RECOVERY='0',
            DNA_DEFAULT_SERVERS='0', DYN_EDITOR_SMOKE='1', LIBGL_ALWAYS_SOFTWARE='true', GALLIUM_DRIVER='llvmpipe')
        for mode in ('debug', 'release'):
            binary = ROOT / ('build/windows-' + mode + '/dna.exe')
            native.build(SimpleNamespace(backend='native', mode=mode, release=mode == 'release',
                source=ROOT / 'src', smoke=False, output=binary, no_cache=False))
            # Prove the complete captured runtime works after relocation, with
            # checkout provider/helper directories removed from DLL lookup.
            relocated = work / ('relocated native editor café 日本語-' + mode)
            import shutil
            shutil.copytree(binary.parent, relocated)
            standalone = dict(isolated, PATH=str(Path(os.environ['SystemRoot'])/'System32')+os.pathsep+os.environ['SystemRoot'])
            run([relocated/binary.name, '--version'], env=standalone)
            run([relocated/binary.name, '--gui'], cwd=cwd, env=standalone)
            manifest = json.loads((binary.parent / 'dna-runtime.json').read_text(encoding='utf-8'))
            assert {'dna_native.dll', 'dyn_window.dll', 'conpty.dll', 'openconsole.exe', 'dna-language.exe', 'libharfbuzz-0.dll', 'libfribidi-0.dll', 'libfreetype-6.dll'} <= {entry['name'].lower() for entry in manifest}
            print('PASS full native Win32 editor startup, GL presentation and cleanup (' + mode + ')', flush=True)
    print('PASS full Windows service/editor qualification; installer workflows run separately.', flush=True)


if __name__ == '__main__':
    main()
