"""Patch production source for a test build, failing when the text is gone.

str.replace silently does nothing when its pattern no longer matches, so a
renamed function or reformatted line would quietly turn a test probe off.
"""


def patched(text, old, new):
    if old not in text:
        raise AssertionError(f'source patch no longer matches: {old[:120]!r}')
    return text.replace(old, new)
