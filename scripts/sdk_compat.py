"""Reproducible, build-local fixes for the pinned SDK; never edit its installation."""
import hashlib
import os
from pathlib import Path
import shutil
from build_limits import compiler_lock

ROOT = Path(__file__).resolve().parents[1]


def environment(compiler, base=None):
    result = dict(os.environ if base is None else base)
    compiler = Path(compiler).resolve()
    roots = [Path(result['DYN_SDK'])] if result.get('DYN_SDK') else []
    roots += [compiler.parent.parent / 'compiler', compiler.parent.parent,
              compiler.parent.parent / 'share/dyn']
    source = next((root for root in roots if (root/'std/dynlib/windows.dyn').is_file()), None)
    if source is None:
        installed = compiler.parent.parent/'share/dyn'
        if not (installed/'dynlib/windows.dyn').is_file():
            raise SystemExit('Cannot locate pinned SDK for compatibility fixes')
        source = installed
    installed_layout = not (source/'std').is_dir()
    standard = source if installed_layout else source/'std'
    original = (standard/'dynlib/windows.dyn').read_text()
    declaration = 'extern fn native_error "dyn_win_last_error"() u32'
    errno_files = ('thread/macos.dyn', 'process/macos.dyn', 'fs/watch/macos.dyn')
    darwin_sources = [(standard/name).read_text() for name in errno_files if (standard/name).is_file()]
    needs_darwin = sum('extern fn native_errno "__error"() *i32' in text for text in darwin_sources) > 1
    if declaration not in original and not needs_darwin:
        return result
    fingerprint = hashlib.sha256((str(source.resolve())+'v3').encode())
    # A developer SDK can change in place. Never retain stale modules behind
    # an overlay whose one patched declaration happened to stay unchanged.
    for path in sorted(source.rglob('*')):
        if path.is_file() and path.suffix in ('.dyn', '.py', '.c', '.h'):
            fingerprint.update(str(path.relative_to(source)).encode())
            fingerprint.update(path.read_bytes())
    digest = fingerprint.hexdigest()[:16]
    destination = ROOT/'build/sdk-compat'/digest
    destination.parent.mkdir(parents=True, exist_ok=True)
    with compiler_lock(destination.parent/'prepare.lock'):
        if not (destination/'.ready').is_file():
            destination.mkdir(parents=True, exist_ok=True)
            if installed_layout:
                shutil.copytree(standard, destination/'std', dirs_exist_ok=True,
                                ignore=shutil.ignore_patterns('vendor'))
                shutil.copytree(source/'vendor', destination/'vendor', dirs_exist_ok=True)
            else:
                shutil.copytree(source/'std', destination/'std', dirs_exist_ok=True)
                shutil.copytree(source/'vendor', destination/'vendor', dirs_exist_ok=True)
            patched = original.replace(declaration,
                'use "std/os/windows" compat_windows\n'
                'fn native_error() u32 { return #cast(u32, 0 - compat_windows.thread_error()) }')
            (destination/'std/dynlib/windows.dyn').write_text(patched)
            # The pinned Darwin thread/process/watch modules independently import
            # __error. Route all three through one declaration, without calling a
            # loader after a failed syscall (which could overwrite errno).
            errno_module = destination/'std/os/darwin/errno'
            errno_module.mkdir(parents=True, exist_ok=True)
            (errno_module/'errno.dyn').write_text(
                '#target(kernel: darwin)\n'
                'extern fn get_error "__error"() *i32\n'
                'pub fn get() *i32 { return get_error() }\n')
            for relative in errno_files:
                path = destination/'std'/relative
                if not path.is_file():
                    continue
                text = path.read_text()
                declaration = 'extern fn native_errno "__error"() *i32'
                if declaration in text:
                    path.write_text(text.replace(declaration,
                        'use "std/os/darwin/errno" sdk_errno\n'
                        'fn native_errno() *i32 { return sdk_errno.get() }'))
            (destination/'.ready').write_text(str(source.resolve()))
    result['DYN_SDK'] = str(destination)
    return result
