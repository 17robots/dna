#!/usr/bin/env python3
"""Golden, refusal, CLI safety, and real old/new compiler semantic tests."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/migrate_casts.py'
spec = importlib.util.spec_from_file_location('cast_migrator', SCRIPT)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
bytecode_setting = sys.dont_write_bytecode
sys.dont_write_bytecode = True
try:
    spec.loader.exec_module(m)
finally:
    sys.dont_write_bytecode = bytecode_setting


class MigrationTests(unittest.TestCase):
    def test_goldens(self):
        cases = [
            ('#cast(i64) a + b', '#cast(i64, a) + b'),
            ('#bitcast(u32) f * 3', '#bitcast(u32, f) * 3'),
            ('#cast(i64) #cast(i32) value', '#cast(i64, #cast(i32, value))'),
            ('#cast(i64) -!~&x.f(1, 2)[a..b].*.z', '#cast(i64, -!~&x.f(1, 2)[a..b].*.z)'),
            ('(#cast(*u8) memory)[..count]', '(#cast(*u8, memory))[..count]'),
            ('#cast(i32) (a + b).f()[..][0]', '#cast(i32, (a + b).f()[..][0])'),
            ('#cast( fn(i32, [2]u8) (i32, i64)) f', '#cast( fn(i32, [2]u8) (i32, i64), f)'),
            ('#cast([#sizeof(fn(i32, i64))]u8) x', '#cast([#sizeof(fn(i32, i64))]u8, x)'),
            ('#cast(i32) #sizeof(fn(i32, i64)) + 2', '#cast(i32, #sizeof(fn(i32, i64))) + 2'),
            ('#cast(i32) #alignof([2]u64)', '#cast(i32, #alignof([2]u64))'),
            ('#cast(i32) f(#cast(i8) x, a[#cast(usize) n])', '#cast(i32, f(#cast(i8, x), a[#cast(usize, n)]))'),
            ('#cast(i32, x) + #bitcast(u32, y)', '#cast(i32, x) + #bitcast(u32, y)'),
            ('#cast(i32, #cast(i8) x)', '#cast(i32, #cast(i8, x))'),
            ('#cast /*type*/ (i32 /*end*/) /*value*/ x /*tail*/ + y', '#cast /*type*/ (i32 /*end*/, /*value*/ x) /*tail*/ + y'),
            ('#cast(i32) // hello\n x // tail\n + y', '#cast(i32, // hello\n x) // tail\n + y'),
            ('"#cast(i32) x" // #cast(i32) x\n/* #bitcast(u32) x */', '"#cast(i32) x" // #cast(i32) x\n/* #bitcast(u32) x */'),
            ('''#cast(i32) '\\'' + #cast(i32) "a\\\"(,]"''', '''#cast(i32, '\\'') + #cast(i32, "a\\\"(,]")'''),
            ('#cast(f64) .25e-2 + #cast(i64) 0xff', '#cast(f64, .25e-2) + #cast(i64, 0xff)'),
            ('if x > #cast(i64) y { return }', 'if x > #cast(i64, y) { return }'),
        ]
        for old, expected in cases:
            with self.subTest(old=old):
                actual, _ = m.convert(old.encode())
                self.assertEqual(actual, expected.encode())
                self.assertEqual(m.convert(actual), (actual, 0))

    def test_binary_boundaries(self):
        for op in ('+', '-', '*', '/', '%', '&', '|', '^', '&&', '||', '==', '!=', '<', '>', '<=', '>=', '<<', '>>', '..'):
            with self.subTest(op=op):
                self.assertEqual(m.convert(f'#cast(i64) x {op} y'.encode())[0], f'#cast(i64, x) {op} y'.encode())

    def test_exact_bytes(self):
        old = b'// \xff\r\n\tx := #cast(i32) /*\xfe*/ f("\xc3\xa9")[0]\r\n'
        self.assertEqual(m.convert(old)[0], old.replace(b'(i32)', b'(i32,').replace(b'[0]', b'[0])'))

    def test_refusals(self):
        for source in ('#cast(i32)', '#cast(i32) + x', '#cast(i32) ;', '#cast(i32) return', '#cast(i32)\nx := 1', '#cast(i32) x.', '#cast(i32) #unknown(x)', '#cast() x', '#cast i32 x', '#cast(i32) ()', '#cast(i32) [1,2]', '#cast(i32) Foo{x: 1}', '#cast(i32) x {}', '#cast(i32) (x]', '/* nope', '"nope', '#cast(i32) ' + '-' * 220 + 'x'):
            with self.subTest(source=source[:80]):
                with self.assertRaises(m.MigrationError):
                    m.convert(source.encode())

    def cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, timeout=10)

    def test_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            good = root / 'a.dyn'
            bad = root / 'b.dyn'
            ignored = root / 'ignore.txt'
            good.write_bytes(b'x := #cast(i32) value\r\n')
            original = good.read_bytes()
            ignored.write_bytes(b'#cast(i32) broken')
            self.assertEqual(self.cli(root).returncode, 1)
            self.assertEqual(good.read_bytes(), original)
            bad.write_bytes(b'#cast(i32)')
            self.assertEqual(self.cli('--write', root).returncode, 2)
            self.assertEqual(good.read_bytes(), original)
            bad.unlink()
            self.assertEqual(self.cli('--write', root).returncode, 0)
            self.assertEqual(good.read_bytes(), b'x := #cast(i32, value)\r\n')
            self.assertEqual(self.cli(root).returncode, 0)
            self.assertEqual(self.cli(root / 'missing').returncode, 2)
            link = root / 'link.dyn'
            link.symlink_to(good)
            self.assertEqual(self.cli('--write', link).returncode, 2)

    def test_compiler_semantic_oracle(self):
        old_path = os.environ.get('OLD_DYN')
        if not old_path:
            self.skipTest('set OLD_DYN for the optional legacy-compiler oracle')
        old = Path(old_path)
        new = Path(os.environ.get('NEW_DYN', ROOT.parent / 'dyn/compiler/build/dyn-release'))
        sdk = Path(os.environ.get('NEW_DYN_SDK', ROOT.parent / 'dyn/compiler'))
        if not old.is_file() or not new.is_file():
            self.skipTest('old/new compilers unavailable; set OLD_DYN and NEW_DYN')
        source = b'''fn require(ok: bool) { if !ok { #panic("cast migration semantic oracle") } }
fn next(count: *i32) i32 { count.* += 1
  return 7 }
struct Box { value: i32 }
fn main() {
  count: i32 = 0
  a := #cast(i64) next(&count) + 3
  require(a == 10 && count == 1)
  b := #cast(i64) #cast(i16) -next(&count) * 2
  require(b == -14 && count == 2)
  box := Box{value: 13}
  p := &box
  c := #cast(i64) p.*.value + #cast(i64) (&box).*.value
  require(c == 26)
  values: [3]i32 = [4, 5, 6]
  d := #cast(i64) values[1..][0] + 2
  require(d == 7)
  require(#cast(i64) #sizeof(i32) + #cast(i64) #alignof(i32) == 8)
  number: f32 = 1.0
  bits := #bitcast(u32) number
  require(bits == 1065353216)
}
'''
        migrated, count = m.convert(source)
        self.assertGreater(count, 8)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for label, compiler, content in (('old', old, source), ('new', new, migrated)):
                project = root / label
                project.mkdir()
                (project / 'main.dyn').write_bytes(content)
                env = dict(os.environ)
                env.pop('DYN_SDK', None)
                if label == 'new':
                    env['DYN_SDK'] = str(sdk)
                executable = root / (label + '-oracle')
                built = subprocess.run([str(compiler), 'build', '--no-cache', '--output', str(executable), str(project)], env=env, capture_output=True, timeout=60)
                self.assertEqual(built.returncode, 0, built.stderr.decode(errors='replace'))
                ran = subprocess.run([str(executable)], capture_output=True, timeout=10)
                self.assertEqual(ran.returncode, 0, ran.stderr.decode(errors='replace'))


if __name__ == '__main__':
    unittest.main()
