#!/usr/bin/env python3
"""Native signed language pointers and retained-handle Windows tree cleanup."""
import ctypes as c
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from dyn_path import real_dyn
from sdk_compat import environment as sdk_environment

FIXTURE = r'''#link("ucrt")
extern fn string_length "strlen"(text:*const u8)usize
extern fn copy "memcpy"(output:*u8,input:*const u8,length:usize)rawptr
extern fn rec_alloc "calloc"(count:usize,size:usize)rawptr
extern fn rec_free "free"(value:rawptr)
extern fn test_read "_read"(fd:i32,bytes:*u8,length:u32)i32
fn proc_read_raw(fd:i32,bytes:*u8,length:usize)isize {
  return #cast(isize,test_read(fd,bytes,#cast(u32,length)))
}
pub fn test_syntax(path:*const u8,output:*u8,capacity:usize)isize {
  return syntax_language_directory(path,output,capacity)
}
fn main() {}
'''
MAGIC = b'DNA language version 1\n'


def encoded(path):
    return str(path).encode('utf-8')


def configure(binary):
    library = c.CDLL(str(binary))
    library.dna_language_pointer.argtypes = [c.c_char_p, c.c_char_p]
    for name in ('dna_language_read_link', 'dna_language_resolve_directory', 'test_syntax'):
        function = getattr(library, name)
        function.argtypes = [c.c_char_p, c.c_void_p, c.c_size_t]
        function.restype = c.c_ssize_t
    library.dna_install_temporary.argtypes = [c.c_void_p]
    library.dna_install_temporary.restype = c.c_void_p
    library.dna_install_remove_tree.argtypes = [c.c_char_p]
    return library


def read_link(library, path, resolver=False):
    output = c.create_string_buffer(4096)
    function = library.dna_language_resolve_directory if resolver else library.dna_language_read_link
    length = function(encoded(path), output, len(output))
    assert length >= 0 and length == len(output.value), ('pointer resolution', str(path), length)
    return Path(output.value.decode('utf-8'))


def junction(path, target):
    subprocess.run(['cmd.exe', '/d', '/c', 'mklink', '/J', str(path), str(target)],
        check=True, capture_output=True)


def native_tests(binary, work):
    lib = configure(binary)
    from private_executable_windows import acl_mask
    root = work / 'grammar café 日本語'
    root.mkdir()
    versions = [root / '.c-ABC123', root / '.c-DEF456']
    for index, version in enumerate(versions):
        version.mkdir()
        (version / 'parser.dll').write_bytes(('parser ' + str(index)).encode())
    target = root / 'c'
    template = c.create_string_buffer(encoded(root / '.install-XXXXXX'))
    assert lib.dna_install_temporary(template)
    stage = Path(template.value.decode('utf-8'))
    assert len(stage.name[-6:]) == 6 and stage.name[-6:].isalnum(), stage.name
    assert acl_mask(stage), 'temporary directory is protected owner-only'
    pointer = stage / 'active'
    assert lib.dna_language_pointer(encoded(versions[0]), encoded(pointer)) == 1
    assert pointer.read_bytes() == MAGIC + encoded(versions[0]) + b'\n'
    assert not acl_mask(pointer) & 0x20, 'pointer is private data, not executable'
    # Staging deliberately has a different parent and basename. Reading is
    # accepted only after the installer atomically publishes the final name.
    output = c.create_string_buffer(4096)
    assert lib.dna_language_read_link(encoded(pointer), output, len(output)) < 0
    assert lib.dna_language_pointer(encoded(versions[1]), encoded(pointer)) == 0, 'exclusive creation'
    os.replace(pointer, target)
    assert read_link(lib, target) == versions[0]
    assert read_link(lib, target, resolver=True) == versions[0]
    assert read_link(lib, versions[0], resolver=True) == versions[0], 'real stage directory passthrough'
    assert lib.test_syntax(encoded(target), output, len(output)) == len(encoded(versions[0]))
    before = target.read_bytes()
    bounded = c.create_string_buffer(b'UNCHANGED', 16)
    assert lib.dna_language_read_link(encoded(target), bounded, 3) < 0
    assert bounded.raw.startswith(b'UNCHANGED')
    assert lib.dna_language_pointer(encoded(versions[1]), encoded(pointer)) == 1
    os.replace(pointer, target)
    assert read_link(lib, target) == versions[1]

    for corrupt in (b'', b'/not-a-signature', MAGIC + encoded(versions[1]),
                    MAGIC + encoded(versions[1]) + b'\nextra', MAGIC + b'C:relative\n',
                    MAGIC + encoded(versions[1]) + b'\x00\n'):
        target.write_bytes(corrupt)
        assert lib.dna_language_read_link(encoded(target), output, len(output)) < 0
    target.write_bytes(MAGIC + encoded(versions[1]) + b'\n')
    other = work / 'other'
    other.mkdir()
    foreign = other / '.foreign-ABC123'
    foreign.mkdir()
    foreign_pointer = root / 'foreign'
    assert lib.dna_language_pointer(encoded(foreign), encoded(foreign_pointer)) == 1
    assert lib.dna_language_read_link(encoded(foreign_pointer), output, len(output)) < 0, 'same parent identity required'
    assert lib.dna_install_remove_tree(encoded(foreign_pointer)) == 1
    wrong = root / 'wrong'
    assert lib.dna_language_pointer(encoded(versions[0]), encoded(wrong)) == 1
    assert lib.dna_language_read_link(encoded(wrong), output, len(output)) < 0, 'version stem must match active name'
    assert lib.dna_install_remove_tree(encoded(wrong)) == 1
    for invalid in (root / '.c-AB_CD1', root / '.c-ABCDE-', root / '.c-ABC12', root / 'c-ABC123'):
        invalid.mkdir()
        assert lib.dna_language_pointer(encoded(invalid), encoded(pointer)) == 0
        invalid.rmdir()
    assert lib.dna_language_pointer(b'C:relative', encoded(pointer)) == 0
    assert lib.dna_language_pointer(encoded(versions[0]) + b'\n', encoded(pointer)) == 0

    outside = work / 'outside'
    outside.mkdir()
    sentinel = outside / 'KEEP.txt'
    sentinel.write_bytes(b'outside must survive')
    alias = root / '.c-GHI789'
    junction(alias, outside)
    try:
        assert lib.dna_language_pointer(encoded(alias), encoded(pointer)) == 0
        target.write_bytes(MAGIC + encoded(alias) + b'\n')
        assert lib.dna_language_read_link(encoded(target), output, len(output)) < 0
        assert lib.dna_language_resolve_directory(encoded(alias), output, len(output)) < 0
    finally:
        target.write_bytes(MAGIC + encoded(versions[1]) + b'\n')
        assert lib.dna_install_remove_tree(encoded(alias)) == 1
    assert sentinel.read_bytes() == b'outside must survive'
    ancestor = work / 'ancestor-link'
    junction(ancestor, root)
    assert lib.dna_language_resolve_directory(encoded(ancestor / '.c-ABC123'), output, len(output)) < 0
    ancestor_template = c.create_string_buffer(encoded(ancestor / '.install-XXXXXX'))
    assert not lib.dna_install_temporary(ancestor_template)
    assert lib.dna_install_remove_tree(encoded(ancestor)) == 1
    assert versions[0].exists()

    tree = work / 'remove me'
    (tree / 'nested/deeper').mkdir(parents=True)
    (tree / 'nested/deeper/file.txt').write_bytes(b'data')
    junction(tree / 'nested/outside-link', outside)
    assert lib.dna_install_remove_tree(encoded(tree)) == 1 and not tree.exists()
    assert sentinel.read_bytes() == b'outside must survive'
    # A read-only object may refuse deletion; cleanup must not chmod it or leak
    # its retained handles. The caller can later resolve the policy explicitly.
    readonly = work / 'readonly'
    readonly.mkdir()
    locked = readonly / 'data'
    locked.write_bytes(b'READONLY')
    locked.chmod(stat.S_IREAD)
    assert lib.dna_install_remove_tree(encoded(readonly)) == 0
    assert locked.exists() and not locked.stat().st_mode & stat.S_IWRITE
    locked.chmod(stat.S_IREAD | stat.S_IWRITE)
    assert lib.dna_install_remove_tree(encoded(readonly)) == 1
    assert lib.dna_install_remove_tree(encoded(Path(work.anchor))) == 0, 'volume root deletion refused'

    # Native handles avoid MAX_PATH during descent. The extended prefix also
    # lets Python build and finally remove this deliberately excessive depth.
    deep = Path('\\\\?\\' + str(work / 'deep'))
    deep.mkdir()
    current = deep
    for _ in range(130):
        current = current / 'd'
        current.mkdir()
    (current / 'keep').write_bytes(b'depth limit')
    assert lib.dna_install_remove_tree(encoded(deep)) == 0, 'bounded 128-directory descent'
    assert (current / 'keep').read_bytes() == b'depth limit'
    shutil.rmtree(deep)

    kernel = c.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = c.c_void_p
    kernel.GetProcessHandleCount.argtypes = [c.c_void_p, c.POINTER(c.c_uint32)]
    count = c.c_uint32()
    assert kernel.GetProcessHandleCount(kernel.GetCurrentProcess(), c.byref(count))
    handles_before = count.value
    for _ in range(32):
        temporary = c.create_string_buffer(encoded(root / '.scratch-XXXXXX'))
        assert lib.dna_install_temporary(temporary)
        directory = Path(temporary.value.decode('utf-8'))
        (directory / 'child').write_bytes(b'data')
        assert read_link(lib, target) == versions[1]
        assert lib.dna_install_remove_tree(encoded(directory)) == 1
    assert kernel.GetProcessHandleCount(kernel.GetCurrentProcess(), c.byref(count))
    assert count.value == handles_before, ('language helper handle leak', handles_before, count.value)
    assert lib.dna_install_remove_tree(encoded(stage)) == 1
    assert lib.dna_install_remove_tree(encoded(target)) == 1
    assert versions[1].is_dir(), 'removing pointer never removes its immutable version'
    print('PASS Windows languages: private signed pointers, atomic publication, retained same-parent '
          'validation, grammar resolver, nofollow ancestors/versions, alnum temporary names, safe bounded tree cleanup and handles', flush=True)


def main():
    compiler = real_dyn()
    if compiler is None:
        raise SystemExit('Install the pinned Dyn SDK first.')
    environment = sdk_environment(compiler)
    with tempfile.TemporaryDirectory(prefix='dna-language-versions-') as temporary:
        work = Path(temporary)
        stage = work / 'stage'
        stage.mkdir()
        for module in ('filesystem', 'host', 'cstring', 'owned_arena'):
            shutil.copytree(ROOT / 'src' / module, stage / module)
        for name in ('rec_io_windows.dyn', 'install_windows.dyn', 'language_versions_windows.dyn'):
            shutil.copyfile(ROOT / 'src/native/dyn' / name, stage / name)
        common = (ROOT / 'src/native/dyn/install.dyn').read_text(encoding='utf-8').split('fn install_copy(', 1)[0]
        (stage / 'install_helpers.dyn').write_text(common, encoding='utf-8')
        (stage / 'main.dyn').write_text(FIXTURE, encoding='utf-8')
        if os.name == 'nt':
            kits = Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')) / 'Windows Kits/10/Lib'
            libraries = work / 'lib'
            libraries.mkdir()
            for name, folder in (('kernel32', 'um'), ('advapi32', 'um'), ('ucrt', 'ucrt')):
                candidates = sorted(kits.glob('*/' + folder + '/x64/' + name + '.lib'))
                if not candidates:
                    raise SystemExit('Windows SDK x64 ' + name + '.lib is required.')
                shutil.copyfile(candidates[-1], libraries / ('lib' + name + '.dll.a'))
            environment['DYN_LIBRARY_PATH'] = str(libraries)
        targets = ('native',) if os.name == 'nt' else ('x86_64-windows', 'aarch64-windows')
        for target in targets:
            for mode in ('debug', 'release'):
                binary = work / (target + '-' + mode + ('.dll' if target == 'native' else '.o'))
                command = [sys.executable, str(ROOT / 'scripts/compile.py'), str(compiler), 'build', str(stage), '--' + mode, '--output', str(binary)]
                if target == 'native':
                    command += ['--shared']
                else:
                    command += ['--target', target, '--emit-object', '--no-link']
                subprocess.run(command, check=True, env=environment, timeout=120)
                if target == 'native':
                    native_work = work / ('café 日本語-' + mode)
                    native_work.mkdir()
                    subprocess.run([sys.executable, str(Path(__file__).resolve()), '--native-library',
                        str(binary), str(native_work)], check=True, env=environment, timeout=180)
                else:
                    print('PASS Windows language version object: ' + target + ' ' + mode, flush=True)
    if os.name != 'nt':
        print('UNAVAILABLE Windows runtime; objects do not qualify language pointers or cleanup.', flush=True)


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == '--native-library':
        native_tests(Path(sys.argv[2]), Path(sys.argv[3]))
    else:
        main()
