#!/usr/bin/env python3
"""Build pinned SDL3, SDL_ttf and the native library boundary into build/deps.

SDL is built from a pinned, checksum-verified release instead of using the
system package, so DNA builds and runs where SDL is not installed. Development
binaries find build/deps/install/lib through their embedded relative library
path. build/deps/static holds linker scripts that resolve the same `#link`
names to static archives, so a plain `dyn build src` (DYN_LIBRARY_PATH from
mise.toml) produces a binary that needs no SDL, SDL_ttf or DNA library at run
time, wherever it is launched from.
"""
import hashlib
from pathlib import Path
import subprocess
import tarfile
import urllib.request
if subprocess.run(['pkg-config', '--exists', 'libpcre2-8', 'libutf8proc']).returncode:
    raise SystemExit('PCRE2 and utf8proc development files are required (libpcre2-dev and libutf8proc-dev on Debian; pcre2 and utf8proc on Arch).')
ROOT = Path(__file__).resolve().parents[1]
DEPS = ROOT / 'build/deps'
# SDL 3.4.16, signed by Sam Lantinga (key 1528635D8053A57F77D1E08630A59377A7763BE6).
SDL_VERSION = '3.4.16'
SDL_SHA256 = '7322236cd12090c3eb40b9728be4d49c76f66ad17d04369584d4ecad5cf77c68'
SDL_BUILD_ID = hashlib.sha256((SDL_VERSION + SDL_SHA256 + 'shared-static-release-2').encode()).hexdigest()
SDL_STAMP = DEPS / 'sdl-build-id'
VERSION = '3.2.2'
SHA256 = '63547d58d0185c833213885b635a2c0548201cc8f301e6587c0be1a67e1e045d'
# SDL_ttf 3.2.2 measures every remaining suffix while splitting unwrapped
# newlines. With max_width == 0, measurement always consumes all remaining
# bytes; scanning directly preserves layout and avoids quadratic shaping work.
TTF_OLD = "size_t max_length = 0;\n            if (!TTF_Size_Internal(font, spot, left,"
TTF_NEW = "size_t max_length = left;\n            if (wrap_width != 0 && !TTF_Size_Internal(font, spot, left,"
RENDER_POSITIONS = """        float *position = sequence->positions;
        for (int i = 0; i < sequence->num_rects; ++i) {
            const SDL_Rect *dst = &sequence->rects[i];
            float minx = x + dst->x;
            float maxx = x + dst->x + dst->w;
            float miny = y + dst->y;
            float maxy = y + dst->y + dst->h;

            *position++ = minx;
            *position++ = miny;
            *position++ = maxx;
            *position++ = miny;
            *position++ = maxx;
            *position++ = maxy;
            *position++ = minx;
            *position++ = maxy;
        }

"""
RENDER_DRAW = """        SDL_RenderGeometryRaw(renderer,
                              sequence->texture,
                              sequence->positions, 2 * sizeof(float),
                              &color, 0,
                              sequence->texcoords, 2 * sizeof(float),
                              sequence->num_rects * 4,
                              sequence->indices, sequence->num_rects * 6, sizeof(*sequence->indices));"""
RENDER_CULLED = """        SDL_Rect clip;
        bool clipped = SDL_RenderClipEnabled(renderer) && SDL_GetRenderClipRect(renderer, &clip);
        int begin = 0;
        while (begin < sequence->num_rects) {
            int end = begin;
            while (end < sequence->num_rects) {
                const SDL_Rect *dst = &sequence->rects[end];
                float minx = x + dst->x, maxx = minx + dst->w;
                float miny = y + dst->y, maxy = miny + dst->h;
                bool outside = clipped && (maxx <= clip.x || minx >= clip.x + clip.w || maxy <= clip.y || miny >= clip.y + clip.h);
                if (outside) {
                    if (end == begin) { begin++; end++; continue; }
                    break;
                }
                float *position = sequence->positions + end * 8;
                position[0] = minx; position[1] = miny;
                position[2] = maxx; position[3] = miny;
                position[4] = maxx; position[5] = maxy;
                position[6] = minx; position[7] = maxy;
                end++;
            }
            if (end > begin) {
                // Every quad uses the same zero-based index pattern. Retain the
                // atlas/layout; submit only contiguous visible glyph runs.
                SDL_RenderGeometryRaw(renderer, sequence->texture,
                    sequence->positions + begin * 8, 2 * sizeof(float), &color, 0,
                    sequence->texcoords ? sequence->texcoords + begin * 8 : NULL, 2 * sizeof(float),
                    (end - begin) * 4, sequence->indices, (end - begin) * 6, sizeof(*sequence->indices));
            }
            begin = end;
        }"""
# SDL_ttf creates and destroys a HarfBuzz buffer for every shaped run: about
# a thousand allocations per redrawn screen. Keep one per thread and reset it.
HB_PATCHES = [
    ("""    // Create a buffer for harfbuzz to use
    hb_buffer_t *hb_buffer = hb_buffer_create();
    if (!hb_buffer) {
        SDL_SetError("Cannot create harfbuzz buffer");
        return false;
    }
""", """    // DNA: one reusable shaping buffer per thread.
    static _Thread_local hb_buffer_t *dna_hb_buffer;
    if (!dna_hb_buffer) {
        dna_hb_buffer = hb_buffer_create();
    }
    if (!hb_buffer_allocation_successful(dna_hb_buffer)) {
        SDL_SetError("Cannot create harfbuzz buffer");
        return false;
    }
    hb_buffer_t *hb_buffer = dna_hb_buffer;
    hb_buffer_reset(hb_buffer);
"""),
    ("""            positions->pos = saved;
            hb_buffer_destroy(hb_buffer);
            return false;""", """            positions->pos = saved;
            return false;"""),
    ("""    }
    hb_buffer_destroy(hb_buffer);

#else""", """    }

#else"""),
]
TTF_BUILD_ID = hashlib.sha256((SDL_BUILD_ID + VERSION + SHA256 + TTF_OLD + TTF_NEW + RENDER_POSITIONS + RENDER_DRAW + RENDER_CULLED + repr(HB_PATCHES)).encode()).hexdigest()
TTF_STAMP = DEPS / 'ttf-build-id'

from runpath import runpath
import os as _os
# Dependency builds link the shared libraries; the static scripts are outputs.
_os.environ['DYN_LIBRARY_PATH'] = str(DEPS/'install/lib')
# Resolve sdl3 (and SDL3_ttf) from the bundled install before system packages.
_os.environ['PKG_CONFIG_PATH'] = str(DEPS/'install/lib/pkgconfig') + (':' + _os.environ['PKG_CONFIG_PATH'] if _os.environ.get('PKG_CONFIG_PATH') else '')
def build_sdl():
    if (DEPS/'install/lib/libSDL3.so').exists() and (DEPS/'install/lib/libSDL3.a').exists() and SDL_STAMP.exists() and SDL_STAMP.read_text().strip() == SDL_BUILD_ID:
        return
    DEPS.mkdir(parents=True, exist_ok=True)
    sdl_archive = DEPS/f'SDL3-{SDL_VERSION}.tar.gz'
    if not sdl_archive.exists():
        urllib.request.urlretrieve(f'https://github.com/libsdl-org/SDL/releases/download/release-{SDL_VERSION}/{sdl_archive.name}', sdl_archive)
    if hashlib.sha256(sdl_archive.read_bytes()).hexdigest() != SDL_SHA256:
        raise SystemExit('SDL archive checksum mismatch')
    with tarfile.open(sdl_archive) as source:
        source.extractall(DEPS, filter='data')
    jobs = str(max(1, (_os.cpu_count() or 2) // 2))
    subprocess.run(['cmake', '-S', str(DEPS/f'SDL3-{SDL_VERSION}'), '-B', str(DEPS/'sdl-build'), '-DCMAKE_BUILD_TYPE=Release',
                    '-DSDL_SHARED=ON', '-DSDL_STATIC=ON', '-DCMAKE_POSITION_INDEPENDENT_CODE=ON', '-DSDL_TESTS=OFF', '-DSDL_TEST_LIBRARY=OFF', '-DSDL_EXAMPLES=OFF',
                    '-DCMAKE_INSTALL_LIBDIR=lib', f'-DCMAKE_INSTALL_PREFIX={DEPS}/install'], check=True)
    subprocess.run(['cmake', '--build', str(DEPS/'sdl-build'), '-j', jobs], check=True)
    subprocess.run(['cmake', '--install', str(DEPS/'sdl-build')], check=True)
    SDL_STAMP.write_text(SDL_BUILD_ID + '\n')
def dyn_runtime():
    """Directory holding Dyn's shared-runtime objects, found from the real
    dyn executable behind any version-manager shim."""
    from dyn_path import real_dyn
    compiler = real_dyn()
    if compiler:
        for directory in (compiler.parent, compiler.parent.parent/'lib/dyn'):
            if (directory/'dynrt_shared.o').is_file() and (directory/'dynrt_support_pic.o').is_file():
                return directory
    raise SystemExit('Cannot find the Dyn runtime objects (dynrt_shared.o, dynrt_support_pic.o); '
                     'set DYN to the dyn executable inside its install directory.')
def native():
    import shlex
    import os
    import shutil
    required = ['sdl3', 'vterm', 'tree-sitter >= 0.25', 'fontconfig', 'libpcre2-8', 'libutf8proc']
    if subprocess.run(['pkg-config', '--exists', *required]).returncode:
        raise SystemExit('Install libvterm, Tree-sitter >= 0.25, Fontconfig, PCRE2 and utf8proc development packages (SDL3 is built from source).')
    flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'sdl3', 'vterm', 'tree-sitter', 'fontconfig', 'libpcre2-8', 'libutf8proc'], text=True))
    subprocess.run(['python3', str(ROOT/'tests/native_abi.py')], check=True)
    # Build DNA-owned adapters in Dyn; keep their stable C ABI for native callers.
    subprocess.run(['python3', str(ROOT/'scripts/compile.py'), os.environ.get('DYN', 'dyn'),
                    'build', str(ROOT/'src/native/dyn'), '--shared', '--release',
                    '--emit-object', '--output', str(DEPS/'dna-support.so')], check=True)
    runtime = dyn_runtime()
    support_objects = [str(DEPS/'dna-support.so.o'), str(runtime/'dynrt_shared.o'), str(runtime/'dynrt_support_pic.o')]
    subprocess.run(['cc', '-shared', '-Wl,-soname,libdna_native.so', '-Wl,'+hide_runtime(),
                    '-Wl,-z,defs', "-Wl,-rpath,$ORIGIN", *support_objects,
                    '-L'+str(DEPS/'install/lib'), '-lSDL3_ttf', '-lutil', '-pthread', '-ldl',
                    '-o', str(DEPS/'install/lib/libdna_native.so.tmp'), *flags], check=True)
    (DEPS/'install/lib/libdna_native.so.tmp').replace(DEPS/'install/lib/libdna_native.so')
    static_libraries(support_objects[0], flags)
    import os
    import shutil
    (DEPS/'install/bin').mkdir(parents=True, exist_ok=True)
    (DEPS/'install/share/dna').mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT/'languages/registry.toml', DEPS/'install/share/dna/languages.toml')
    shutil.copytree(ROOT/'languages/queries', DEPS/'install/share/dna/queries', dirs_exist_ok=True)
    subprocess.run(['python3', str(ROOT/'scripts/compile.py'), os.environ.get('DYN', 'dyn'), 'build', str(ROOT/'installer'), '--debug', '--output', str(DEPS/'install/bin/dna-language'), '--link', str(DEPS/'install/lib/libdna_native.so'), '--link', runpath(), '--link', hide_runtime()], check=True)
# The Dyn runtime defines byte-at-a-time memcpy, memmove and memset in every
# executable. Exported, they would replace glibc's for every shared library in
# the process (SDL, FreeType, GPU drivers). Keep them local to the executable.
HIDE_RUNTIME = '{ local: memcpy; memmove; memset; };\n'
HIDE_RUNTIME_SCRIPT = 'VERSION { ' + HIDE_RUNTIME.strip() + ' }\n'
def hide_runtime():
    DEPS.mkdir(parents=True, exist_ok=True)
    (DEPS/'hide-runtime.map').write_text(HIDE_RUNTIME)
    return '--version-script=' + str(DEPS/'hide-runtime.map')
def static_libraries(support_object, flags):
    """Static archives plus linker scripts named like the shared libraries.
    Dyn's `#link("SDL3")` resolves libSDL3.so in DYN_LIBRARY_PATH; GNU ld reads
    these scripts and links the archives instead. Every script names the whole
    group, so link order between the three never matters and no archive member
    is linked twice. The Dyn runtime objects stay out of the archive: the
    executable already provides them."""
    import shlex
    static = DEPS/'static'
    static.mkdir(parents=True, exist_ok=True)
    archive = DEPS/'install/lib/libdna_native.a'
    archive.unlink(missing_ok=True)
    subprocess.run(['ar', 'rcs', str(archive), support_object], check=True)
    system = []
    # SDL's private libraries come from its static pkg-config entry; FreeType
    # and HarfBuzz stay ordinary shared system libraries.
    private = subprocess.check_output(['pkg-config', '--static', '--libs', 'sdl3'], text=True)
    shared = subprocess.check_output(['pkg-config', '--libs', 'freetype2', 'harfbuzz'], text=True)
    for flag in flags + shlex.split(private) + shlex.split(shared):
        if flag.startswith('-l') and flag not in ('-lSDL3', '-lSDL3_ttf') and flag not in system:
            system.append(flag)
    system += [flag for flag in ('-lutil', '-ldl', '-lpthread', '-lm') if flag not in system]
    # Dyn links with ld.lld directly, without the compiler driver's search
    # path, so system libraries are named by absolute path.
    def resolve(flag):
        found = subprocess.check_output(['cc', f'-print-file-name=lib{flag[2:]}.so'], text=True).strip()
        if found.startswith('/'):
            return _os.path.normpath(found)
        # glibc 2.34+ provides these from libc itself.
        if flag in ('-lutil', '-ldl', '-lpthread', '-lrt'):
            return None
        raise SystemExit(f'Cannot find the shared library for {flag}.')
    system = [path for path in map(resolve, system) if path]
    group = ' '.join(str(DEPS/f'install/lib/{name}') for name in ('libdna_native.a', 'libSDL3_ttf.a', 'libSDL3.a'))
    script = (f'/* Generated by scripts/deps.py: static DNA, SDL_ttf and SDL. */\nGROUP({group})\nINPUT(AS_NEEDED({" ".join(system)}))\n'
              + HIDE_RUNTIME_SCRIPT)
    for name in ('libSDL3.so', 'libSDL3_ttf.so', 'libdna_native.so'):
        (static/name).write_text(script)
    terminal_only(flags, resolve)
def terminal_only(flags, resolve):
    """The native library without SDL, for builds whose only frontend is the
    terminal: Dyn adapters with GUI stubs, and a linker script in build/deps/tui-static that names no
    SDL archive, SDL dependency or Fontconfig."""
    import shutil
    staged = DEPS/'native-dyn-tui'
    if staged.exists():
        shutil.rmtree(staged)
    shutil.copytree(ROOT/'src/native/dyn', staged)
    shutil.copyfile(ROOT/'modules/stubs/native_fonts.dyn', staged/'fonts.dyn')
    (staged/'memory_text.dyn').unlink()
    shutil.copyfile(ROOT/'modules/stubs/native_notify_gui.dyn', staged/'notify_gui.dyn')
    shutil.copyfile(ROOT/'modules/stubs/native_terminal_gui.dyn', staged/'terminal_gui.dyn')
    subprocess.run(['python3', str(ROOT/'scripts/compile.py'), _os.environ.get('DYN', 'dyn'),
                    'build', str(staged), '--shared', '--release',
                    '--emit-object', '--output', str(DEPS/'dna-support-tui.so')], check=True)
    support_object = str(DEPS/'dna-support-tui.so.o')
    archive = DEPS/'install/lib/libdna_native_tui.a'
    archive.unlink(missing_ok=True)
    subprocess.run(['ar', 'rcs', str(archive), support_object], check=True)
    system = []
    for flag in flags:
        if flag.startswith('-l') and not flag.startswith('-lSDL') and flag != '-lfontconfig' and flag not in system:
            system.append(flag)
    system += [flag for flag in ('-lutil', '-ldl', '-lpthread', '-lm') if flag not in system]
    system = [path for path in map(resolve, system) if path]
    directory = DEPS/'tui-static'
    directory.mkdir(parents=True, exist_ok=True)
    (directory/'libdna_native.so').write_text(
        f'/* Generated by scripts/deps.py: static DNA without SDL. */\nGROUP({archive})\nINPUT(AS_NEEDED({" ".join(system)}))\n'
        + HIDE_RUNTIME_SCRIPT)
build_sdl()
if ((DEPS/'install/lib/libSDL3_ttf.so').exists() and TTF_STAMP.exists()
        and TTF_STAMP.read_text().strip() == TTF_BUILD_ID):
    native()

    raise SystemExit(0)
DEPS.mkdir(parents=True, exist_ok=True)
archive = DEPS/f'SDL3_ttf-{VERSION}.tar.gz'
if not archive.exists():
    urllib.request.urlretrieve(f'https://github.com/libsdl-org/SDL_ttf/releases/download/release-{VERSION}/{archive.name}', archive)
if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
    raise SystemExit('SDL_ttf archive checksum mismatch')
with tarfile.open(archive) as source:
    source.extractall(DEPS, filter='data')
ttf_source = DEPS / f'SDL3_ttf-{VERSION}' / 'src/SDL_ttf.c'
text = ttf_source.read_text()
if text.count(TTF_OLD) != 1:
    raise SystemExit('SDL_ttf unwrapped-layout patch context changed; refusing an unverified build.')
text = text.replace(TTF_OLD, TTF_NEW)
for old, new in HB_PATCHES:
    if text.count(old) != 1:
        raise SystemExit('SDL_ttf shaping-buffer patch context changed; refusing an unverified build.')
    text = text.replace(old, new)
ttf_source.write_text(text)
renderer_source = DEPS / f'SDL3_ttf-{VERSION}' / 'src/SDL_renderer_textengine.c'
renderer_text = renderer_source.read_text()
if renderer_text.count(RENDER_POSITIONS) != 1 or renderer_text.count(RENDER_DRAW) != 1:
    raise SystemExit('SDL_ttf clipped-glyph patch context changed.')
renderer_source.write_text(renderer_text.replace(RENDER_POSITIONS, '').replace(RENDER_DRAW, RENDER_CULLED))
subprocess.run(['cmake','-S',str(DEPS/f'SDL3_ttf-{VERSION}'),'-B',str(DEPS/'ttf-build'),'-DCMAKE_BUILD_TYPE=Release','-DBUILD_SHARED_LIBS=ON','-DSDLTTF_SAMPLES=OFF','-DSDLTTF_VENDORED=OFF','-DSDLTTF_PLUTOSVG=OFF',f'-DCMAKE_PREFIX_PATH={DEPS}/install','-DCMAKE_INSTALL_LIBDIR=lib',f'-DCMAKE_INSTALL_PREFIX={DEPS}/install'],check=True)
subprocess.run(['cmake','--build',str(DEPS/'ttf-build'),'-j','2'],check=True)
subprocess.run(['cmake','--install',str(DEPS/'ttf-build')],check=True)
subprocess.run(['cmake','-S',str(DEPS/f'SDL3_ttf-{VERSION}'),'-B',str(DEPS/'ttf-static-build'),'-DCMAKE_BUILD_TYPE=Release','-DBUILD_SHARED_LIBS=OFF','-DCMAKE_POSITION_INDEPENDENT_CODE=ON','-DSDLTTF_SAMPLES=OFF','-DSDLTTF_VENDORED=OFF','-DSDLTTF_PLUTOSVG=OFF',f'-DCMAKE_PREFIX_PATH={DEPS}/install','-DCMAKE_INSTALL_LIBDIR=lib',f'-DCMAKE_INSTALL_PREFIX={DEPS}/install'],check=True)
subprocess.run(['cmake','--build',str(DEPS/'ttf-static-build'),'-j','2'],check=True)
subprocess.run(['cmake','--install',str(DEPS/'ttf-static-build')],check=True)
TTF_STAMP.write_text(TTF_BUILD_ID + '\n')

native()
