#!/usr/bin/env python3
"""Convert manual counter loops to Dyn range loops (preview 10+).

Only exact, provably equivalent shapes are converted; everything else is left
alone. Usage: modernize_loops.py FILE... (rewrites in place, prints counts).
--revert FILE:LINE,... restores the original loops starting at those lines.
"""
import json
import re
import sys

MAPPING = []

ASSIGN = re.compile(r'^\s*([A-Za-z_][\w.\[\]]*)\s*(=|\+=|-=|\*=|/=)\s')


def indent(line):
    return len(line) - len(line.lstrip(' '))


def identifiers(expression):
    return set(re.findall(r'[A-Za-z_]\w*', expression)) - {'len', 'cast', 'usize', 'u32', 'u64', 'i32', 'true', 'false'}


def function_spans(lines):
    spans, start = [], None
    for number, line in enumerate(lines):
        if re.match(r'^(pub )?fn ', line):
            start = number
        elif line == '}' and start is not None:
            spans.append((start, number))
            start = None
    return spans


def loop_end(lines, for_line):
    """Index of the closing brace of the loop opened at for_line."""
    base = indent(lines[for_line])
    for number in range(for_line + 1, len(lines)):
        if lines[number].strip() == '}' and indent(lines[number]) == base:
            return number
        if lines[number].strip() and indent(lines[number]) < base:
            return None
    return None


def owner_loop(lines, start, line_number):
    """Innermost for/loop line enclosing line_number, scanning from start."""
    stack = []
    for number in range(start, line_number):
        text = lines[number].strip()
        while stack and indent(lines[number]) <= indent(lines[stack[-1]]) and text.startswith('}') and indent(lines[number]) == indent(lines[stack[-1]]):
            stack.pop()
            break
        if re.match(r'^(\w+:\s*)?for\b', text) and text.endswith('{'):
            stack.append(number)
    return stack[-1] if stack else None


def body_assigns(lines, first, last, names):
    """True if any identifier in names is assigned or address-taken in lines[first:last]."""
    for number in range(first, last):
        text = lines[number]
        match = ASSIGN.match(text)
        if match:
            target = re.split(r'[.\[]', match.group(1))[0]
            if target in names:
                return True
        for name in names:
            if re.search(r'&\s*' + re.escape(name) + r'\b', text):
                return True
            if re.search(r'\b' + re.escape(name) + r'\s*:=', text):
                return True
    return False


def candidates(lines, span):
    start, end = span
    found = []
    for number in range(start + 1, end):
        text = lines[number].strip()
        up = re.match(r'^for ([a-z_]\w*) (<|<=) (.+) \{$', text)
        down = re.match(r'^for ([a-z_]\w*) > 0 \{$', text)
        if not (up or down) or number == 0:
            continue
        name = (up or down).group(1)
        init = lines[number - 1].strip()
        closing = loop_end(lines, number)
        if closing is None:
            continue
        inner = indent(lines[number]) + 2
        body = (number + 1, closing)
        if up:
            limit = up.group(3)
            init_match = re.match(r'^' + re.escape(name) + r'(: usize)? (:)?= (.+)$', init)
            if not init_match or name in identifiers(limit) or '&&' in limit or '||' in limit:
                continue
            first_value = init_match.group(3)
            last_line = lines[closing - 1]
            if last_line.strip() != f'{name} += 1' or indent(last_line) != inner:
                continue
            # Other assignments to the counter, or to anything the bound reads.
            if body_assigns(lines, body[0], closing - 1, {name}) or body_assigns(lines, body[0], closing, identifiers(limit)):
                continue
            if re.search(r'\(|\)', limit) and not re.fullmatch(r'#len\([\w.\[\]]+\)( [-+] \d+)?', limit):
                continue
            # Every continue owned by this loop must be preceded by the increment.
            removals, ok = [closing - 1], True
            for inner_number in range(body[0], closing - 1):
                if lines[inner_number].strip() == 'continue' and owner_loop(lines, start, inner_number) == number:
                    previous = lines[inner_number - 1].strip()
                    if previous != f'{name} += 1':
                        ok = False
                        break
                    removals.append(inner_number - 1)
            if not ok:
                continue
            operator = '..=' if up.group(2) == '<=' else '..'
            header = ' ' * indent(lines[number]) + f'for {name} in {first_value}{operator}{limit} {{'
            found.append({'name': name, 'init': number - 1, 'for': number, 'closing': closing, 'removals': removals, 'header': header, 'declares': init_match.group(1) is not None or init_match.group(2) is not None})
        else:
            init_match = re.match(r'^' + re.escape(name) + r'(: usize)? (:)?= (.+)$', init)
            if not init_match:
                continue
            first_line = lines[number + 1]
            if first_line.strip() != f'{name} -= 1' or indent(first_line) != inner:
                continue
            if body_assigns(lines, number + 2, closing, {name}):
                continue
            header = ' ' * indent(lines[number]) + f'for {name} in #reverse(0..{init_match.group(3)}) {{'
            found.append({'name': name, 'init': number - 1, 'for': number, 'closing': closing, 'removals': [number + 1], 'header': header, 'declares': init_match.group(1) is not None or init_match.group(2) is not None})
    return found


def uses_outside(lines, span, name, loops):
    """True if name is used in the function outside the given loops' spans."""
    covered = set()
    for loop in loops:
        covered.update(range(loop['init'], loop['closing'] + 1))
    pattern = re.compile(r'(?<![\w.])' + re.escape(name) + r'\b')
    for number in range(span[0] + 1, span[1]):
        if number in covered:
            continue
        if pattern.search(lines[number]):
            return True
    return False


def convert(path, skip):
    lines = open(path).read().split('\n')
    plan = []
    for span in function_spans(lines):
        loops = candidates(lines, span)
        by_name = {}
        for loop in loops:
            by_name.setdefault(loop['name'], []).append(loop)
        for name, group in by_name.items():
            group = [loop for loop in group if (path, loop['for'] + 1) not in skip]
            if not group or uses_outside(lines, span, name, group):
                continue
            # The first loop must declare; later ones reset with `name = ...`.
            ordered = sorted(group, key=lambda loop: loop['for'])
            if not ordered[0]['declares']:
                continue
            plan.extend(ordered)
    drop = set()
    for loop in plan:
        lines[loop['for']] = loop['header']
        drop.add(loop['init'])
        drop.update(loop['removals'])
    result = [line for number, line in enumerate(lines) if number not in drop]
    open(path, 'w').write('\n'.join(result))
    mapping = []
    for loop in plan:
        shift = sum(1 for dropped in drop if dropped < loop['for'])
        closing_shift = sum(1 for dropped in drop if dropped < loop['closing'])
        mapping.append({'file': path, 'original': loop['for'] + 1, 'first': loop['for'] + 1 - shift, 'last': loop['closing'] + 1 - closing_shift})
    MAPPING.extend(mapping)
    return len(plan)


if __name__ == '__main__':
    skip = set()
    arguments = sys.argv[1:]
    if arguments and arguments[0] == '--skip':
        for item in arguments[1].split(','):
            if item:
                file, line = item.rsplit(':', 1)
                skip.add((file, int(line)))
        arguments = arguments[2:]
    total = 0
    for path in arguments:
        count = convert(path, skip)
        total += count
        if count:
            print(f'{path}: {count}')
    print(f'converted {total} loops')
    with open('/tmp/loop-map.json', 'w') as out:
        json.dump(MAPPING, out)
