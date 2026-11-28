"""Keep tests off the developer's desktop display.

Importing this module removes the display variables from os.environ, so tests
and every process they start see no X11 or Wayland display. Test windows,
clipboard traffic and nested compositors on a live session have crashed the
desktop's X server bridge (xwayland-satellite), and every X application died
with it. Tests that need a window print SKIP when available() is false.

Set DNA_TEST_DISPLAY=private only when DISPLAY or WAYLAND_DISPLAY name private
servers, such as the headless weston that CI starts. Runners that start their
own private compositor set it for their children.
"""
import os
import sys

VARIABLES = ('DISPLAY', 'WAYLAND_DISPLAY', 'WAYLAND_SOCKET', 'NIRI_SOCKET')


def isolate():
    if os.environ.get('DNA_TEST_DISPLAY') == 'private':
        return
    for name in VARIABLES:
        os.environ.pop(name, None)


def available():
    """Whether native windows can open without touching the desktop display."""
    # macOS and Windows windows never go through an X11 or Wayland server.
    if not sys.platform.startswith('linux'):
        return True
    return bool(os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY'))


isolate()
