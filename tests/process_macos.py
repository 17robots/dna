#!/usr/bin/env python3
"""Exercise Darwin process policy with mocks, then compile its real native seam.

Mock execution requires Linux. macOS objects prove compilation only, not native
spawn, signal or pipe behavior. No production source or installed SDK is edited.
"""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from dyn_path import real_dyn
from sdk_compat import environment as sdk_environment

NATIVE = ROOT / 'src/native/dyn'
NATIVE_MAIN = r'''
#link("System")
extern fn rec_malloc "malloc"(size: usize) *u8
extern fn rec_free "free"(value: rawptr)
extern fn string_length "strlen"(text: *const u8) usize
extern fn copy "memcpy"(output: *u8, source: *const u8, size: usize) rawptr
fn dna_watch(fd: i32, writing: i32) { _ = fd
  _ = writing }
fn dna_unwatch(fd: i32) { _ = fd }
fn main() {
  command: []const u8 = "printf hello\0"
  directory: []const u8 = "/tmp\0"
  child := proc_open(&command[0], &directory[0], true)
  bytes: [32]u8 = []
  _ = proc_write(child.input, &bytes[0], 1)
  _ = proc_read(child.output, &bytes[0], 32)
  _ = proc_peek(&child)
  polls: [1]PollDescriptor = [PollDescriptor{fd: child.output, events: 1}]
  _ = proc_poll(&polls[0], 1, 20)
  proc_close(&child)
}
'''


def replace_once(source, before, after):
    assert source.count(before) == 1, 'Production process mock seam changed: ' + before
    return source.replace(before, after, 1)


def main():
    if not sys.platform.startswith('linux'):
        raise SystemExit('Darwin process mock execution requires a Linux host; use native host tests on macOS.')
    compiler = real_dyn()
    if compiler is None:
        raise SystemExit('Install the pinned Dyn SDK first.')
    environment = sdk_environment(compiler)
    libc = subprocess.check_output(['cc', '-print-file-name=libc.so.6'], text=True).strip()
    if not Path(libc).is_file():
        raise SystemExit('Native libc.so.6 is required for the mock executable.')

    def build(stage, mode, output, *arguments):
        subprocess.run([sys.executable, str(ROOT / 'scripts/compile.py'), str(compiler),
                        'build', str(stage), '--' + mode, '--quiet', '--output', str(output),
                        *arguments], env=environment, check=True, timeout=120)

    with tempfile.TemporaryDirectory(prefix='dna-process-macos-') as directory:
        work = Path(directory)
        mocked = work / 'mock'
        mocked.mkdir()
        source = (NATIVE / 'process_macos.dyn').read_text()
        source = replace_once(source, '#target(kernel: darwin)', '')
        source = replace_once(source, '#link("System")', '')
        source = replace_once(source,
            'extern fn proc_fcntl_native "fcntl$NOCANCEL"(fd: i32, operation: i32, ...) i32',
            'fn proc_fcntl_native(fd: i32, operation: i32, value: i32) i32 { return fake_fcntl(fd, operation, value) }')
        (mocked / 'process.dyn').write_text(source)
        shutil.copyfile(ROOT / 'tests/fixtures/process_macos_mock.dyn', mocked / 'main.dyn')
        for mode in ('debug', 'release'):
            binary = work / ('mock-' + mode)
            build(mocked, mode, binary, '--link', libc)
            result = subprocess.run([str(binary)], env=environment, check=True,
                                    capture_output=True, text=True, timeout=10)
            assert 'PASS Darwin process mock:' in result.stdout, result.stdout
            print(mode + ': ' + result.stdout.strip(), flush=True)

        production = work / 'production'
        production.mkdir()
        for name in ('process_macos.dyn', 'rec_io_macos.dyn', 'clock.dyn',
                     'sync_desktop.dyn', 'sync_macos.dyn'):
            shutil.copyfile(NATIVE / name, production / name)
        marker = "// Dyn's current executable entry point"
        sync_source = (NATIVE / 'sync.dyn').read_text()
        assert marker in sync_source, 'Native subsystem initialization boundary changed'
        (production / 'sync.dyn').write_text(sync_source.split(marker, 1)[0])
        (production / 'main.dyn').write_text(NATIVE_MAIN)
        for target in ('x86_64-macos', 'aarch64-macos'):
            for mode in ('debug', 'release'):
                build(production, mode, work / (target + '-' + mode),
                      '--target', target, '--emit-object', '--no-link')
            print('PASS Darwin process production objects: ' + target + ' (debug/release)', flush=True)
    print('QUALIFICATION GAP: Darwin process mocks and cross objects do not qualify native macOS spawn, signals or pipe execution.')


if __name__ == '__main__':
    main()
