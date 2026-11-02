"""The Windows architecture that native test programs are built and run for.

Windows on ARM runs the x64 Dyn compiler under emulation; DNA_WINDOWS_TARGET
(set by the ARM64 CI job) makes every linked test program, and the SDK import
libraries it links against, ARM64 instead of the compiler's own x64.
"""
import os

TARGET = os.environ.get('DNA_WINDOWS_TARGET', 'x86_64-windows')
if TARGET not in ('x86_64-windows', 'aarch64-windows'):
    raise SystemExit('DNA_WINDOWS_TARGET must be x86_64-windows or aarch64-windows')
# Windows SDK library folder (Windows Kits/10/Lib/<version>/<um|ucrt>/<arch>).
SDK_ARCH = 'arm64' if TARGET == 'aarch64-windows' else 'x64'


def link_arguments():
    """Extra `dyn build` arguments for a program that links and runs here."""
    return ['--target', TARGET] if TARGET != 'x86_64-windows' else []


# Process-start deadlines stretch on slow runners (windows-11-arm takes ~17 s
# per Windows PowerShell start). Set by CI; 1 everywhere else.
TIME_SCALE = float(os.environ.get('DNA_TEST_TIME_SCALE', '1'))
