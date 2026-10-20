#!/usr/bin/env python3
"""Lexically migrate Dyn prefix casts. Exit 1: changes needed; 2: unsafe input.

Only .dyn files are discovered in directories. Explicit files may have any suffix.
Trivia and original bytes survive; only the type ')' and a closing ')' change.
This is a boundary recognizer, not a Dyn validator. Balanced group contents are
opaque except that casts inside them are migrated too. Aggregate operands and
unknown directives are deliberately refused. A following empty brace or a brace
starting with name-colon is ambiguous and refused (including control blocks).
Unary/cast recursion is limited to 200. Delimiters are checked file-wide, but
types and group contents are not validated. No files are written on parse error.
Writes preserve file modes, but are not a filesystem transaction on I/O failure.
"""
import argparse
from dataclasses import dataclass
from pathlib import Path
import sys


class MigrationError(ValueError):
    pass


@dataclass(frozen=True)
class Token:
    value: bytes
    start: int
    end: int
    kind: str = 'punct'


def lex(source):
    tokens = []
    i = 0
    n = len(source)
    def alpha(c):
        return 65 <= c <= 90 or 97 <= c <= 122 or c == 95
    while i < n:
        start = i
        c = source[i]
        if c in b' \t\r\n\v\f':
            i += 1
            continue
        if source.startswith(b'//', i):
            end = source.find(b'\n', i + 2)
            i = n if end < 0 else end
            continue
        if source.startswith(b'/*', i):
            end = source.find(b'*/', i + 2)
            if end < 0:
                raise MigrationError(f'byte {i}: unterminated comment')
            i = end + 2
            continue
        kind = 'punct'
        if c in (34, 39):
            kind = 'literal'
            i += 1
            while i < n and source[i] != c:
                if source[i] in (10, 13):
                    raise MigrationError(f'byte {start}: newline in literal')
                i += 2 if source[i] == 92 else 1
            if i >= n:
                raise MigrationError(f'byte {start}: unterminated literal')
            i += 1
        elif alpha(c) or c == 35:
            kind = 'name' if c != 35 else 'directive'
            i += 1
            while i < n and (alpha(source[i]) or 48 <= source[i] <= 57):
                i += 1
        elif 48 <= c <= 57 or c == 46 and i + 1 < n and 48 <= source[i + 1] <= 57:
            kind = 'literal'
            if source[i:i+2] in (b'0x', b'0b', b'0o'):
                i += 2
                while i < n and source[i] in b'0123456789abcdefABCDEF_':
                    i += 1
            else:
                i += 1
                while i < n and source[i] in b'0123456789_':
                    i += 1
                if c != 46 and i < n and source[i] == 46 and not source.startswith(b'..', i):
                    i += 1
                    while i < n and source[i] in b'0123456789_':
                        i += 1
                if i < n and source[i] in b'eE':
                    exponent = i
                    i += 1
                    if i < n and source[i] in b'+-':
                        i += 1
                    digits = i
                    while i < n and source[i] in b'0123456789_':
                        i += 1
                    if i == digits:
                        i = exponent
        else:
            pair = source[i:i+2]
            i += 2 if pair in (b'.*', b'..', b'&&', b'||', b'==', b'!=', b'<=', b'>=', b'<<', b'>>', b':=', b'->', b'+=', b'-=', b'*=', b'/=', b'&=', b'|=') else 1
        tokens.append(Token(source[start:i], start, i, kind))
    return tokens


def convert(source):
    """Return (converted bytes, number of old casts); raise on unsafe boundaries."""
    ts = lex(source)
    pairs = {}
    stack = []
    closes = {b')': b'(', b']': b'[', b'}': b'{'}
    for i, t in enumerate(ts):
        if t.value in closes.values():
            stack.append(i)
        elif t.value in closes:
            if not stack or ts[stack[-1]].value != closes[t.value]:
                raise MigrationError(f'byte {t.start}: unmatched delimiter')
            opening = stack.pop()
            pairs[opening] = i
    if stack:
        raise MigrationError(f'byte {ts[stack[-1]].start}: unclosed delimiter')
    edits = []
    ends = {}
    casts = (b'#cast', b'#bitcast')
    def fail(i, message):
        offset = ts[i].start if i < len(ts) else len(source)
        raise MigrationError(f'byte {offset}: {message}')
    def group(i):
        if i >= len(ts) or ts[i].value != b'(':
            fail(i, 'expected parenthesized type or builtin argument')
        return pairs[i]
    def cast(i, depth=0):
        if i in ends:
            return ends[i]
        close = group(i + 1)
        if close == i + 2:
            fail(i, 'empty cast type')
        j = i + 2
        while j < close:
            if ts[j].value == b',':
                ends[i] = close + 1
                return close + 1
            j = pairs[j] + 1 if j in pairs else j + 1
        end = unary(close + 1, depth + 1)
        edits.append((ts[close].start, ts[close].end, b','))
        edits.append((ts[end - 1].end, ts[end - 1].end, b')'))
        ends[i] = end
        return end
    def unary(i, depth=0):
        if depth > 200:
            fail(i, 'operand nesting exceeds 200')
        if i >= len(ts):
            fail(i, 'missing cast operand')
        t = ts[i]
        if t.value in (b'-', b'!', b'~', b'&'):
            return unary(i + 1, depth + 1)
        if t.value in casts:
            j = cast(i, depth + 1)
        elif t.value == b'(':
            j = pairs[i] + 1
            if j == i + 2:
                fail(i, 'empty operand group')
        elif t.kind == 'directive':
            if t.value not in (b'#sizeof', b'#alignof', b'#typeof', b'#offsetof', b'#load', b'#syscall', b'#wrap', b'#len'):
                fail(i, 'unsupported operand directive')
            j = group(i + 1) + 1
        elif t.kind in ('name', 'literal') and t.value not in (b'return', b'else', b'if', b'for', b'while', b'break', b'continue', b'fn', b'struct', b'enum', b'union', b'type', b'const', b'use', b'defer', b'match', b'case'):
            j = i + 1
        else:
            fail(i, 'missing or unsupported cast operand')
        while j < len(ts):
            v = ts[j].value
            if v == b'.*':
                j += 1
            elif v == b'.':
                if j + 1 >= len(ts) or ts[j + 1].kind != 'name':
                    fail(j, 'missing field name')
                j += 2
            elif v in (b'(', b'['):
                j = pairs[j] + 1
            else:
                break
        # A named aggregate and a following block cannot be distinguished here.
        if (j < len(ts) and ts[j].value == b'{'
                and (ts[j + 1].value == b'}' or
                     j + 2 < len(ts) and ts[j + 1].kind == 'name' and ts[j + 2].value == b':')):
            fail(j, 'ambiguous aggregate/block after cast; parenthesize operand')
        if j < len(ts) and ts[j].value in (b':=', b'=', b':'):
            fail(j, 'assignment/declaration after operand; possible missing operand')
        return j
    for i, t in enumerate(ts):
        if t.value in casts:
            cast(i)
    # Stable ordering preserves inner-before-outer closings at shared endpoints.
    result = bytearray()
    previous = 0
    for start, end, replacement in sorted(edits, key=lambda e: e[0]):
        result.extend(source[previous:start])
        result.extend(replacement)
        previous = end
    result.extend(source[previous:])
    return bytes(result), len(edits) // 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true', help='write only after every input passes')
    parser.add_argument('paths', nargs='+', type=Path)
    args = parser.parse_args(argv)
    pending = []
    try:
        files = set()
        for path in args.paths:
            if path.is_dir():
                files.update(p for p in path.rglob('*.dyn') if p.is_file())
            elif path.is_file():
                files.add(path)
            else:
                raise MigrationError(f'{path}: no such file or directory')
        for path in sorted(files):
            if path.is_symlink():
                raise MigrationError(f'{path}: refusing symbolic link')
            original = path.read_bytes()
            try:
                migrated, count = convert(original)
            except MigrationError as error:
                raise MigrationError(f'{path}: {error}') from error
            if count:
                pending.append((path, original, migrated, count))
        # Detect concurrent changes before starting writes.
        if args.write:
            for path, original, _, _ in pending:
                if path.read_bytes() != original:
                    raise MigrationError(f'{path}: changed during migration')
            for path, _, migrated, _ in pending:
                path.write_bytes(migrated)
        for path, _, _, count in pending:
            print(f'{path}: {count} casts' + (' migrated' if args.write else ' need migration'))
        return 0 if args.write or not pending else 1
    except (MigrationError, OSError, RecursionError) as error:
        print(f'migrate_casts: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
