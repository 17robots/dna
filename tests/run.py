#!/usr/bin/env python3
"""Run DNA's checks in parallel stages.

usage: tests/run.py [test|smoke]

`test` runs TEST. `smoke` first runs BUILDS one at a time, because EDITOR
uses the editors they make, then runs TEST, CHECKS and EDITOR together. Steps
run in parallel (DNA_TEST_JOBS, default half the CPUs; 1 runs them in order),
then the steps that measure time or share a fixed build directory run one at a
time.
DNA_TEST_ONLY=a,b runs only the named steps (script stem, such as buffer_close).
DNA_TEST_TIMES=FILE appends each step's seconds to FILE.

The desktop display is hidden from every step; see tests/private_display.py.
"""
import concurrent.futures
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
import private_display  # hides the desktop display; see tests/private_display.py

ROOT = Path(__file__).resolve().parents[1]
JOBS = max(1, int(os.environ.get('DNA_TEST_JOBS', max(1, (os.cpu_count() or 2) // 2))))
ONLY = {name.strip() for name in os.environ.get('DNA_TEST_ONLY', '').split(',') if name.strip()}
TIMES = os.environ.get('DNA_TEST_TIMES')
# Steps that assert on time or bounded memory, or that reuse a fixed build
# directory another step in the same stage also uses: run after the parallel
# steps, one at a time.
ALONE = {
    'render_report_latency', 'native_clock', 'clipboard_deadline', 'background_worksets',
    'terminal_workset', 'picker_responsiveness', 'picker_progress', 'disk_idle', 'lsp_workset',
    'resource_cycles', 'native_memory', 'syntax_memory', 'lsp_storage', 'motion_policy',
    'presentation_policy', 'popup_surface_policy', 'surface_entrance_policy',
    'explorer_column_motion', 'disk', 'native_disk_dynamic', 'test_host threads --object-only',
}
TEST = [
    'tests/sdk_requirements.py',
    'tests/sdk_compat.py',
    'tests/process_macos.py',
    'tests/disk_macos.py',
    'tests/host_environment.py',
    'tests/platform_storage.py',
    'tests/darwin_errno.py',
    'tests/json_scratch.py',
    'tests/owned_arena.py',
    'tests/font_startup.py',
    'scripts/test.py',
]
# Smoke adds these to TEST.
CHECKS = [
    'scripts/test_host.py',
    'scripts/test_host.py filesystem',
    'scripts/test_host.py threads',
    'scripts/test_host.py bulk_memory',
    'tests/bulk_memory.py',
    'tests/build_guard.py',
    'tests/benchmark_cleanup.py',
    'tests/render_report_latency.py',
    'tests/static_native.py',
    'tests/dyn_support.py',
    'tests/native_fonts.py',
    'tests/native_text.py',
    'tests/clipboard_deadline.py',
    'tests/native_foundation.py',
    'tests/native_triangle_bounds.py',
    'tests/native_bitmap_raster.py',
    'tests/native_fill_spans.py',
    'tests/native_texture_raster.py',
    'tests/native_present_reuse.py',
    'tests/native_typing_frames.py',
    'tests/native_syntax_pending_frames.py',
    'tests/native_syntax_single_pass.py',
    'tests/native_syntax_settled_frames.py',
    'tests/native_syntax_idle.py',
    'tests/native_frame_sequence.py',
    'tests/ui_text_working_set.py',
    'tests/pane_storage.py',
    'tests/native_sync.py',
    'tests/native_clock.py',
    'tests/tui_storage.py',
    'tests/line_layout_reuse.py',
    'tests/motion_policy.py',
    'tests/surface_entrance_policy.py',
    'tests/popup_surface_policy.py',
    'tests/popup_surface_motion.py',
    'tests/surface_entrance.py',
    'tests/entrance_command_text.py',
    'tests/native_draw_opacity.py',
    'tests/completion_escape.py',
    'tests/completion_window.py',
    'tests/buffer_close.py',
    'tests/presentation_policy.py',
    'tests/status_focus.py',
    'tests/status_file_motion.py',
    'tests/explorer_column_motion.py',
    'tests/explorer_column_native.py',
    'tests/explorer_window_motion.py',
    'tests/theme_contrast.py',
    'tests/typography_metrics.py',
    'tests/picker_viewport.py',
    'tests/tree_search_navigation.py',
    'tests/background_worksets.py --expect bounded',
    'tests/process_transport.py',
    'tests/process_close.py',
    'tests/native_abi.py',
    'tests/native_desktop.py --object-only --editor-objects',
    'scripts/test_host.py threads --object-only',
    'tests/terminal_review.py',
    'tests/terminal_boundaries.py',
    'tests/terminal_workset.py --expect-bounded',
    'tests/rpc.py',
    'tests/jobs.py',
    'tests/server_install.py',
    'tests/disk.py',
    'tests/native_disk_dynamic.py',
    'tests/disk_idle.py',
    'tests/syntax_selection.py',
    'tests/textobject_queries.py',
    'tests/syntax_retire.py',
    'tests/native.py',
    'tests/project_search.py',
    'tests/recovery_faults.py',
    'tests/recovery_capture.py',
    'tests/save_failures.py',
    'tests/clone_save.py',
    'tests/save_completion.py',
    'tests/resource_cycles.py',
    'tests/native_memory.py',
    'tests/syntax_memory.py',
    'tests/syntax_changes.py',
    'tests/syntax_consistency.py',
    'tests/syntax_stream.py',
    'tests/syntax_dyn_fullfile.py',
    'tests/syntax_dyn_strings.py',
    'tests/thread_join.py',
    'tests/picker_index.py',
    'tests/picker_responsiveness.py',
    'tests/picker_progress.py',
    'tests/syntax_faults.py',
    'tests/recovery.py',
    'tests/plugins.py',
    'tests/lsp_storage.py',
    'tests/lsp_workset.py',
]
# Smoke builds these first; EDITOR uses them.
BUILDS = [
    'build: scripts/build_native.py --mode debug --output build/dna-debug',
    'build: scripts/build_native.py --mode release --output build/dna-release',
    'build: scripts/build_native.py --backend wayland --release',
    'build: scripts/build_native.py --backend x11 --release',
    'build: scripts/compile.py $DYN build examples/plugins/uppercase --debug --output examples/plugins/uppercase/uppercase',
    'build: scripts/build_smoke.py',
    'build: scripts/profile.py minimal release',
    'build: scripts/profile.py terminal release',
]
EDITOR = [
    'tests/tui_usability.py',
    'tests/tui_frames.py dna-debug',
    'tests/tui_frames.py dna-release',
    'tests/tui_frames.py dna-terminal',
    'tests/command_feedback.py dna-debug',
    'tests/command_feedback.py dna-release',
    'tests/keymap_features.py dna-debug',
    'tests/keymap_features.py dna-release',
    'tests/large_file.py',
    'tests/syntax_window.py',
    'tests/syntax_objects.py',
    'tests/lsp_large.py',
    'tests/lsp_symbols.py',
    'tests/git_gutter.py',
    'tests/version.py --binary build/dna-debug --binary build/dna-release',
    'tests/version.py --binary build/dna-minimal --binary build/dna-terminal',
    'DNA_SMOKE_TIMEOUT_SECONDS=${DNA_SMOKE_TIMEOUT_SECONDS:-90} scripts/smoke.py',
    'tests/launch.py',
    'DNA_NATIVE_BACKEND=wayland tests/native_platform.py',
    'DNA_NATIVE_BACKEND=wayland tests/native_gpu.py',
    'tests/native_shaping.py',
    'tests/native_selection.py',
    'tests/native_only.py --binary build/dna-debug --binary build/dna-release --binary build/dna-minimal --binary build/dna-terminal',
    'tests/tui_render.py terminal',
]


def expand(text):
    """$NAME and ${NAME}, plus the shell's ${NAME:-default}."""
    text = re.sub(r'\$\{(\w+):-([^}]*)\}', lambda match: os.environ.get(match[1]) or match[2], text)
    return os.path.expandvars(text)


class Step:
    def __init__(self, text):
        self.build = text.startswith('build: ')
        words = shlex.split(text.removeprefix('build: '))
        self.env = {}
        while '=' in words[0]:
            name, value = words.pop(0).split('=', 1)
            self.env[name] = expand(value)
        self.script = words[0]
        self.arguments = [expand(word) for word in words[1:]]
        self.name = Path(self.script).stem
        self.label = ' '.join([self.name, *self.arguments])
        self.alone = self.build or self.name in ALONE or self.label in ALONE


def execute(step):
    started = time.monotonic()
    command = [sys.executable, str(ROOT / step.script), *step.arguments]
    try:
        result = subprocess.run(command, cwd=ROOT, env=dict(os.environ, **step.env), stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=1800)
        status, output = result.returncode, result.stdout
    except subprocess.TimeoutExpired as error:
        status, output = 'timeout after 1800s', error.stdout or b''
    elapsed = time.monotonic() - started
    if TIMES:
        with open(TIMES, 'a') as out:
            out.write(f'{elapsed:.2f} {step.label}\n')
    return step, status, output, elapsed


failures = []


def report(step, status, output, elapsed):
    if status == 0:
        skipped = [line for line in output.decode(errors='replace').splitlines() if line.startswith('SKIP')]
        for line in skipped:
            print(f'  {step.label}: {line}', flush=True)
        print(f'PASS {step.label} ({elapsed:.1f}s)', flush=True)
        return
    failures.append(step.label)
    sys.stdout.write(output.decode(errors='replace'))
    print(f'FAIL {step.label}: {status} ({elapsed:.1f}s)', flush=True)


def stage(texts):
    steps = [Step(text) for text in texts]
    # A build always runs: later stages need its output.
    steps = [step for step in steps if step.build or not ONLY or step.name in ONLY]
    together = [step for step in steps if JOBS > 1 and not step.alone]
    alone = [step for step in steps if JOBS <= 1 or step.alone]
    with concurrent.futures.ThreadPoolExecutor(max_workers=JOBS) as pool:
        for future in concurrent.futures.as_completed([pool.submit(execute, step) for step in together]):
            report(*future.result())
    for step in alone:
        report(*execute(step))
        if step.build and failures:
            break


def main():
    suite = sys.argv[1] if len(sys.argv) > 1 else 'test'
    if suite not in ('test', 'smoke'):
        raise SystemExit('usage: tests/run.py [test|smoke]')
    started = time.monotonic()
    if suite == 'test':
        stage(TEST)
    else:
        # Builds first, one at a time; then every check together.
        stage(BUILDS)
        if not failures:
            stage(TEST + CHECKS + EDITOR)
    print(f'{suite}: {time.monotonic() - started:.0f}s with {JOBS} jobs', flush=True)
    if failures:
        raise SystemExit(f'FAIL {len(failures)} step(s): ' + ', '.join(failures))
    print(f'PASS DNA {suite}')


if __name__ == '__main__':
    main()
