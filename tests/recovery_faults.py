#!/usr/bin/env python3
import ctypes as c, os, subprocess, tempfile, time
from pathlib import Path
root=Path(__file__).resolve().parents[1]
if not os.environ.get('DNA_FAULT_CHILD'):
    probe=root/'build/recovery-faults.so'
    subprocess.run(['python3', str(root/'scripts/native_test.py'), 'recovery_faults', str(probe)], check=True)
    subprocess.run(['python3',__file__],env=dict(os.environ,DNA_FAULT_CHILD='1',LD_PRELOAD=str(probe)),check=True,timeout=15)
    raise SystemExit
lib=c.CDLL(str(root/'build/deps/install/lib/libdna_native.so'))
lib.dna_recovery_open.argtypes=[c.c_char_p];lib.dna_recovery_open.restype=c.c_void_p
lib.dna_recovery_submit.argtypes=[c.c_void_p,c.c_char_p,c.c_size_t]
lib.dna_recovery_error.argtypes=[c.c_void_p];lib.dna_recovery_close.argtypes=[c.c_void_p]
def wait(predicate):
    deadline=time.monotonic()+3
    while time.monotonic()<deadline:
        if predicate():return
        time.sleep(.005)
    raise AssertionError('recovery deadline')
with tempfile.TemporaryDirectory() as d:
    directory=Path(d)/'recovery';directory.write_text('blocked by file')
    state=lib.dna_recovery_open(os.fsencode(directory));assert state
    try:
        assert lib.dna_recovery_submit(state,b'first',5)
        wait(lambda:lib.dna_recovery_error(state)!=0)
        directory.unlink()
        assert lib.dna_recovery_submit(state,b'first',5)
        wait(lambda:any(p.suffix!='.tmp' and p.read_bytes()==b'first' for p in directory.glob('session-*')))
        path=next(p for p in directory.glob('session-*') if p.suffix!='.tmp')
        os.environ['DNA_TEST_FAIL_FSYNC']='1'
        assert lib.dna_recovery_submit(state,b'failed',6)
        wait(lambda:lib.dna_recovery_error(state)!=0)
        assert path.read_bytes()==b'first';assert not list(directory.glob('*.tmp'))
        del os.environ['DNA_TEST_FAIL_FSYNC']
        assert lib.dna_recovery_submit(state,b'retried',7)
        wait(lambda:path.read_bytes()==b'retried')
    finally:lib.dna_recovery_close(state)
# A crash while the worker flushes a replacement must leave the previous record.
with tempfile.TemporaryDirectory() as d:
    pid=os.fork()
    if pid==0:
        state=lib.dna_recovery_open(os.fsencode(d));lib.dna_recovery_submit(state,b'committed',9)
        wait(lambda:any(p.suffix!='.tmp' and p.read_bytes()==b'committed' for p in Path(d).glob('session-*')))
        os.environ['DNA_TEST_STOP_FSYNC']='1';lib.dna_recovery_submit(state,b'interrupted',11)
        time.sleep(10);os._exit(1)
    import signal
    deadline=time.monotonic()+5
    while time.monotonic()<deadline:
        result,status=os.waitpid(pid,os.WNOHANG|os.WUNTRACED)
        if result and os.WIFSTOPPED(status):break
        time.sleep(.005)
    else:
        os.kill(pid,signal.SIGKILL);os.waitpid(pid,0);raise AssertionError('writer never reached flush')
    os.kill(pid,signal.SIGKILL);os.waitpid(pid,0)
    records=[p for p in Path(d).glob('session-*') if p.suffix!='.tmp']
    assert len(records)==1 and records[0].read_bytes()==b'committed', [(p.name,p.read_bytes()) for p in Path(d).glob('*')]
print('PASS recovery setup failure, failed flush, retry, interrupted replacement')
