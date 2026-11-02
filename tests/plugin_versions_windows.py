#!/usr/bin/env python3
"""Crash-safe Windows plugin version publication, without directory exchange."""
import ctypes as c
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from dyn_path import real_dyn
from sdk_compat import environment as sdk_environment

FIXTURE = r'''#link("ucrt")
extern fn string_length "strlen"(text:*const u8)usize
extern fn copy "memcpy"(output:*u8,input:*const u8,length:usize)rawptr
extern fn test_read "_read"(fd:i32,bytes:*u8,length:u32)i32
fn proc_read_raw(fd:i32,bytes:*u8,length:usize)isize {
  size:=length
  if size>2147483647 { size=2147483647 }
  return #cast(isize,test_read(fd,bytes,#cast(u32,size)))
}
fn dna_notify() {}
fn native_initialize() {}
pub fn test_stage(root,name,manifest,executable,leaf:*const u8)i32 {
  plugin_win_prepare()
  parent:=rec_open(root,720896,0)
  if parent<0 { return 0 }
  defer _=rec_close(parent)
  container:=plugin_win_container(parent,name,false)
  if container<0 { return 0 }
  defer _=rec_close(container)
  version:[10]u8=[]
  if plugin_win_build_version(container,manifest,executable,name,leaf,version[..]) { return 1 }
  return 0
}
test_last_errno:i32
test_rename_status:i32
test_force_root:rawptr
test_parent_diagnostics:[9]i32
test_real_rename:fn(rawptr,*InstallWinStatus,rawptr,u32,u32)i32
fn test_tracked_rename(handle:rawptr,status:*InstallWinStatus,info:rawptr,length,kind:u32)i32 {
  if kind==10 && test_force_root!=nil {
    #cast(*InstallWinRename,info).root=test_force_root
  }
  result:=test_real_rename(handle,status,info,length,kind)
  if result<0 { test_rename_status=result }
  return result
}
pub fn test_status()i32 { return test_rename_status }
pub fn test_errno()i32 { return test_last_errno }
pub fn test_install(manifest,executable,root,name,leaf:*const u8)i32 {
  install_win_prepare()
  test_rename_status=0
  test_real_rename=install_win_api.rename
  install_win_api.rename=test_tracked_rename
  result:=dna_plugin_install(manifest,executable,root,name,leaf)
  install_win_api.rename=test_real_rename
  test_last_errno=rec_errno().*
  return result
}
pub fn test_parent_diagnostic(index:usize)i32 {
  if index>=9 { return -1 }
  return test_parent_diagnostics[index]
}
pub fn test_parent_sharing(root:*const u8)i32 {
  plugin_win_prepare()
  parent:=rec_open(root,720896,0)
  if parent<0 { test_parent_diagnostics[0]=rec_errno().*
    return -1 }
  defer _=rec_close(parent)
  name:[]const u8="rename-parent-sharing\0"
  creator:=install_win_create_private(parent,&name[0],true,false)
  if creator<0 { test_parent_diagnostics[0]=rec_errno().*
    return -2 }
  pointer:=PluginWinPointer{}
  value:[]const u8=".v-probe0"
  _=copy(&pointer.active[0],&value[0],9)
  test_real_rename=install_win_api.rename
  install_win_api.rename=test_tracked_rename
  defer install_win_api.rename=test_real_rename
  test_force_root=win_io_handle(creator)
  test_rename_status=0
  rec_errno().*=0
  _=plugin_win_publish(creator,&pointer)
  test_parent_diagnostics[1]=test_rename_status
  test_parent_diagnostics[2]=rec_errno().*
  rec_errno().*=0
  retained:=plugin_win_reopen(creator,160)
  if retained<0 { test_parent_diagnostics[8]=#cast(i32,win_io_api.error()) }
  test_parent_diagnostics[3]=rec_errno().*
  _=rec_close(creator)
  if retained<0 { test_force_root=nil
    return -3 }
  defer _=rec_close(retained)
  test_force_root=win_io_handle(retained)
  test_rename_status=0
  rec_errno().*=0
  _=plugin_win_publish(retained,&pointer)
  test_parent_diagnostics[4]=test_rename_status
  test_parent_diagnostics[5]=rec_errno().*
  test_force_root=nil
  test_rename_status=0
  rec_errno().*=0
  final:=plugin_win_publish(retained,&pointer)
  test_parent_diagnostics[6]=test_rename_status
  test_parent_diagnostics[7]=rec_errno().*
  if !final { return -4 }
  return 1
}
pub fn test_private_primitive(root,name:*const u8,directory,executable:i32)i32 {
  plugin_win_prepare()
  parent:=rec_open(root,720896,0)
  if parent<0 { test_last_errno=rec_errno().*
    return -1 }
  defer _=rec_close(parent)
  fd:=install_win_create_private(parent,name,directory!=0,executable!=0)
  if fd<0 { test_last_errno=rec_errno().*
    return -2 }
  defer _=rec_close(fd)
  test_last_errno=0
  if directory==0 {
    value:[]const u8="primitive data"
    if !plugin_win_write(fd,value) { test_last_errno=rec_errno().*
      return -3 }
  }
  return 1
}
fn main() {}
'''


def configure(binary):
    library = c.CDLL(str(binary))
    library.dna_plugin_install.argtypes = [c.c_char_p] * 5
    library.dna_plugin_remove.argtypes = [c.c_char_p] * 2
    library.dna_plugin_rollback.argtypes = [c.c_char_p] * 2
    library.dna_plugin_resolve.argtypes = [c.c_char_p, c.c_void_p, c.c_size_t]
    library.test_stage.argtypes = [c.c_char_p] * 5
    library.test_install.argtypes = [c.c_char_p] * 5
    library.test_errno.argtypes = []
    library.test_parent_sharing.argtypes = [c.c_char_p]
    library.test_parent_diagnostic.argtypes = [c.c_size_t]
    library.test_private_primitive.argtypes = [c.c_char_p, c.c_char_p, c.c_int, c.c_int]
    return library


def encoded(path):
    return str(path).encode('utf-8')


def resolve(library, path):
    storage = c.create_string_buffer(4096)
    assert library.dna_plugin_resolve(encoded(path), storage, len(storage)) == 1, ('resolve', str(path))
    return Path(storage.value.decode('utf-8'))


def active(library, container):
    manifest = resolve(library, container / 'plugin.json')
    metadata = json.loads(manifest.read_text(encoding='utf-8'))
    source = resolve(library, container / '.dna-source')
    assert source.parent == manifest.parent
    assert (manifest.parent / '.dna-managed').read_bytes() == b'DNA plugin version 1\n'
    assert (manifest.parent / metadata['executable']).is_file()
    return metadata['version'], source.read_text(encoding='utf-8'), manifest.parent


def native_tests(binary, work):
    lib = configure(binary)
    probe = lib.test_parent_sharing(encoded(work))
    diagnostic = [lib.test_parent_diagnostic(at) for at in range(9)]
    print('Directory rename comparison (result; early errno, broad NT/errno, reopen errno, narrow NT/errno, null-root NT/errno, reopen WinError):', probe, diagnostic, flush=True)
    assert probe == 1, ("directory parent rename sharing", probe, diagnostic)
    payload = (Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/whoami.exe').read_bytes()
    name = 'café 日本語'
    sources = []
    for version in ('1', '2'):
        source = work / ('source ' + version)
        source.mkdir()
        manifest = source / 'plugin.json'
        manifest.write_text(json.dumps({'name': name, 'executable': 'run.exe', 'version': version}), encoding='utf-8')
        executable = source / 'run.exe'
        executable.write_bytes(payload)
        sources.append((manifest, executable))
    root = work / 'installed plugins'
    container = root / name

    def install(index=0, plugin=name, leaf='run.exe'):
        manifest, executable = sources[index]
        return lib.test_install(encoded(manifest), encoded(executable), encoded(root), encoded(plugin), encoded(leaf))

    assert resolve(lib, sources[0][0]) == sources[0][0], 'external manifest passthrough'
    installed = install()
    if installed != 1:
        first_errno = lib.test_errno()
        native_status = hex(lib.test_status() & 0xffffffff)
        tree = []
        for path in sorted(root.rglob('*')) if root.exists() else []:
            if path.is_symlink():
                tree.append((str(path.relative_to(root)), 'reparse'))
            elif path.is_file():
                tree.append((str(path.relative_to(root)), path.stat().st_size,
                             path.read_bytes()[:64] if path.suffix != '.exe' else b'PE'))
            else:
                tree.append((str(path.relative_to(root)), 'directory'))
        parent = container if container.is_dir() else root if root.is_dir() else work
        probes = []
        for label, directory, executable in (('directory', 1, 0), ('data', 0, 0), ('executable', 0, 1)):
            result = lib.test_private_primitive(encoded(parent), ('private-probe-' + label).encode(), directory, executable)
            probes.append((label, result, lib.test_errno()))
        raise AssertionError(('first plugin install', installed, first_errno, native_status, tree, 'relative private primitives', probes))
    first = active(lib, container)
    assert first[:2] == ('1', str(sources[0][0]))
    assert (container / '.dna-managed').read_bytes() == b'DNA plugin versions 1\n'
    assert lib.dna_plugin_rollback(encoded(root), encoded(name)) == 0, 'no previous version yet'
    assert install(1) == 1
    second = active(lib, container)
    assert second[:2] == ('2', str(sources[1][0])) and second[2] != first[2]
    assert json.loads((first[2] / 'plugin.json').read_text())['version'] == '1', 'immutable retained version'
    assert lib.dna_plugin_rollback(encoded(root), encoded(name)) == 1
    assert active(lib, container)[:2] == first[:2]
    assert lib.dna_plugin_rollback(encoded(root), encoded(name)) == 1
    assert active(lib, container)[:2] == second[:2]
    executable = active(lib, container)[2] / 'run.exe'
    from private_executable_windows import acl_mask
    assert acl_mask(executable) & 0x20
    assert not acl_mask(container / '.dna-current') & 0x20
    assert executable.read_bytes() == payload
    result = subprocess.run([str(executable)], cwd=executable.parent, capture_output=True, check=True, timeout=10)
    assert result.stdout.strip(), 'installed private PE actually executes'
    destination = c.create_string_buffer(b'UNCHANGED', 16)
    assert lib.dna_plugin_resolve(encoded(container / 'plugin.json'), destination, 3) == 0
    assert destination.raw.startswith(b'UNCHANGED'), 'bounded resolver must not truncate output'

    # Unmanaged contents are never adopted or overwritten by an install.
    unmanaged = root / 'unmanaged'
    unmanaged.mkdir()
    (unmanaged / 'keep.txt').write_bytes(b'KEEP')
    assert install(plugin='unmanaged') == 0
    assert lib.dna_plugin_remove(encoded(root), b'unmanaged') == 0
    assert [(p.name, p.read_bytes()) for p in unmanaged.iterdir()] == [('keep.txt', b'KEEP')]
    for bad in ('../escape', 'a/b', 'a\\b', 'file:stream', 'trailing.', 'trailing ', 'CON', 'nul.txt', 'COM1.exe', 'LPT9', 'COM¹.exe'):
        assert install(plugin=bad) == 0, bad
    for bad in ('plugin.json', '.dna-source', '.dna-managed', '.dna-current', 'nul.exe', 'stream:payload', 'run\\exe'):
        assert install(leaf=bad) == 0, bad

    # A held managed container cannot be replaced with a junction and adopted.
    outside = work / 'outside'
    outside.mkdir()
    (outside / '.dna-managed').write_bytes(b'DNA plugin versions 1\n')
    (outside / 'keep.txt').write_bytes(b'OUTSIDE')
    junction = root / 'junction'
    subprocess.run(['cmd.exe', '/d', '/c', 'mklink', '/J', str(junction), str(outside)], check=True, capture_output=True)
    try:
        assert install(plugin='junction') == 0
        assert lib.dna_plugin_remove(encoded(root), b'junction') == 0
        storage = c.create_string_buffer(4096)
        assert lib.dna_plugin_resolve(encoded(junction / 'plugin.json'), storage, len(storage)) == 0
    finally:
        os.rmdir(junction)
    assert (outside / 'keep.txt').read_bytes() == b'OUTSIDE'

    current = container / '.dna-current'
    before = current.read_bytes()
    for corrupt in (b'', b'../outside\n\n', b'.v-ABCDEF\n\n', before + b'garbage'):
        current.write_bytes(corrupt)
        storage = c.create_string_buffer(4096)
        assert lib.dna_plugin_resolve(encoded(container / 'plugin.json'), storage, len(storage)) == 0
        assert lib.dna_plugin_rollback(encoded(root), encoded(name)) == 0
        assert install() == 0, 'corrupt owned pointer must not be silently replaced'
    current.write_bytes(before)
    assert active(lib, container)[0] == '2'
    # A complete-looking version behind a junction must still be rejected.
    outside_version = work / 'outside complete version'
    shutil.copytree(active(lib, container)[2], outside_version)
    alias_name = '.v-ZZZZZZ'
    alias = container / alias_name
    subprocess.run(['cmd.exe', '/d', '/c', 'mklink', '/J', str(alias), str(outside_version)], check=True, capture_output=True)
    try:
        old_active = before.splitlines()[0]
        current.write_bytes(alias_name.encode('ascii') + b'\n' + old_active + b'\n')
        storage = c.create_string_buffer(4096)
        assert lib.dna_plugin_resolve(encoded(container / 'plugin.json'), storage, len(storage)) == 0
        assert lib.dna_plugin_rollback(encoded(root), encoded(name)) == 0
        assert install() == 0
    finally:
        current.write_bytes(before)
        os.rmdir(alias)
    assert (outside_version / 'run.exe').read_bytes() == payload

    # The crash child calls exact production staging or full installation.
    # Before publication, even a complete orphan version never becomes active.
    for mode in ('before', 'after'):
        expected = active(lib, container)[0] if mode == 'before' else '1'
        subprocess.run([sys.executable, str(Path(__file__).resolve()), '--crash', mode,
            str(binary), str(root), name, str(sources[0][0]), str(sources[0][1])],
            check=True, timeout=30)
        assert active(lib, container)[0] == expected
        pointer = current.read_text(encoding='ascii').splitlines()
        assert all((container / version / '.dna-managed').read_bytes() == b'DNA plugin version 1\n' for version in pointer if version)

    kernel = c.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = c.c_void_p
    kernel.GetProcessHandleCount.argtypes = [c.c_void_p, c.POINTER(c.c_uint32)]
    count = c.c_uint32()
    assert kernel.GetProcessHandleCount(kernel.GetCurrentProcess(), c.byref(count))
    handles_before = count.value
    for index in range(16):
        assert install(index % 2) == 1
        assert lib.dna_plugin_rollback(encoded(root), encoded(name)) == 1
        assert active(lib, container)[0] in ('1', '2')
    assert kernel.GetProcessHandleCount(kernel.GetCurrentProcess(), c.byref(count))
    assert count.value == handles_before, ('plugin handle leak', handles_before, count.value)
    deadline = time.monotonic() + 5
    while lib.dna_plugin_remove(encoded(root), encoded(name)) != 1:
        # A temporarily locked PE may refuse the container rename. Refusal
        # must leave its existing active version and pointer intact.
        assert active(lib, container)[0] in ('1', '2')
        assert time.monotonic() < deadline, 'managed container removal deadline'
        time.sleep(.01)
    assert not container.exists()
    removed = list(root.glob('.removed-' + name + '-*'))
    assert len(removed) == 1 and (removed[0] / '.dna-current').is_file()
    assert len(list(removed[0].glob('.v-*'))) >= 2, 'remove retains immutable versions'
    print('PASS Windows plugins: private PE install/execute, immutable update, atomic rollback/roll-forward, '
          'provenance, retained removal, unmanaged/reparse protection, corrupt pointers, crash publication and handles', flush=True)


def main():
    compiler = real_dyn()
    if compiler is None:
        raise SystemExit('Install the pinned Dyn SDK first.')
    environment = sdk_environment(compiler)
    with tempfile.TemporaryDirectory(prefix='dna-plugin-versions-') as temporary:
        work = Path(temporary)
        stage = work / 'stage'
        stage.mkdir()
        for module in ('filesystem', 'host', 'cstring', 'owned_arena'):
            shutil.copytree(ROOT / 'src' / module, stage / module)
        for name in ('rec_io_windows.dyn', 'install_windows.dyn', 'plugin_versions_windows.dyn',
                     'recovery.dyn', 'sync_desktop.dyn', 'sync_windows.dyn', 'clock.dyn'):
            shutil.copyfile(ROOT / 'src/native/dyn' / name, stage / name)
        common = (ROOT / 'src/native/dyn/install.dyn').read_text(encoding='utf-8').split('pub fn ', 1)[0]
        (stage / 'install_helpers.dyn').write_text(common, encoding='utf-8')
        sync = (ROOT / 'src/native/dyn/sync.dyn').read_text(encoding='utf-8').split('// Dyn\'s current executable entry point', 1)[0]
        (stage / 'sync.dyn').write_text(sync, encoding='utf-8')
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
                    print('PASS Windows plugin version object: ' + target + ' ' + mode, flush=True)
    if os.name != 'nt':
        print('UNAVAILABLE Windows runtime; objects do not qualify plugin publication.', flush=True)


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == '--native-library':
        native_tests(Path(sys.argv[2]), Path(sys.argv[3]))
    elif len(sys.argv) == 8 and sys.argv[1] == '--crash':
        mode, binary, root, name, manifest, executable = sys.argv[2:]
        lib = configure(Path(binary))
        if mode == 'before':
            assert lib.test_stage(encoded(root), encoded(name), encoded(manifest), encoded(executable), b'run.exe') == 1
        else:
            assert lib.dna_plugin_install(encoded(manifest), encoded(executable), encoded(root), encoded(name), b'run.exe') == 1
        os._exit(0)
    else:
        main()
