#!/usr/bin/env python3
"""Check development-UI SDK preflight for installed and source layouts."""
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from sdk_check import require_ui_sdk, window_builder

with tempfile.TemporaryDirectory(prefix='dna-sdk-requirements-') as directory:
    work = Path(directory)
    installed = work / 'installed/bin/dyn'
    installed.parent.mkdir(parents=True)
    installed.touch()
    try:
        require_ui_sdk(installed, {})
    except SystemExit as error:
        assert 'std/ui/box' in str(error)
        assert 'preview.27' in str(error)
        assert 'DYN_SDK=' in str(error)
    else:
        raise AssertionError('SDK without UI modules accepted')
    (work / 'installed/share/dyn/ui/box').mkdir(parents=True)
    require_ui_sdk(installed, {})
    source = work / 'source/build/dyn-release'
    source.parent.mkdir(parents=True)
    source.touch()
    (work / 'source/std/ui/box').mkdir(parents=True)
    require_ui_sdk(source, {})
    override = work / 'override/std/ui/box'
    override.mkdir(parents=True)
    other = work / 'other/bin/dyn'
    require_ui_sdk(other, {'DYN_SDK': str(work / 'override')})
print('PASS SDK preflight: missing UI diagnostic, installed/source layouts and DYN_SDK')

with tempfile.TemporaryDirectory(prefix='dna-window-builder-') as directory:
    work = Path(directory)
    compiler = work / 'bin/dyn'
    installed = work / 'share/dyn/vendor/window/native/build.py'
    installed.parent.mkdir(parents=True)
    installed.touch()
    assert window_builder(compiler) == installed
    installed.unlink()
    source = work / 'vendor/window/native/build.py'
    source.parent.mkdir(parents=True)
    source.touch()
    assert window_builder(compiler) == source
print('PASS window builder: installed and source layouts')
