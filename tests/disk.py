#!/usr/bin/env python3
import ctypes as c, tempfile, time
from pathlib import Path
root=Path(__file__).resolve().parents[1];lib=c.CDLL(str(root/'build/deps/install/lib/libdna_native.so'))
lib.dna_disk_open.restype=c.c_void_p
lib.dna_disk_watch.argtypes=[c.c_void_p,c.c_uint,c.c_uint64,c.c_char_p,c.c_void_p,c.c_size_t]
lib.dna_disk_pending.argtypes=[c.c_void_p,c.c_uint,c.c_uint64];lib.dna_disk_pending.restype=c.c_long
lib.dna_disk_take.argtypes=[c.c_void_p,c.c_uint,c.c_uint64,c.c_void_p,c.c_size_t]
lib.dna_disk_close.argtypes=[c.c_void_p]
with tempfile.TemporaryDirectory() as d:
    path=Path(d)/'file';path.write_bytes(b'original');p=lib.dna_disk_open();assert p
    def take(status,expected=None,identity=1):
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            n=lib.dna_disk_pending(p,0,identity)
            if n:
                buf=c.create_string_buffer(max(1,n));actual=lib.dna_disk_take(p,0,identity,buf,len(buf))
                # Writers truncate before writing; the watcher may report that
                # intermediate state first. Wait for the expected final content.
                if actual==status and (expected is None or buf.value==expected):
                    return
            time.sleep(.005)
        raise AssertionError('disk event deadline')
    try:
        lib.dna_disk_watch(p,0,1,str(path).encode(),b'original',8);take(5)
        with path.open('wb') as writer:
            writer.write(b'changed');writer.flush();take(1,b'changed')
        temp=Path(d)/'new';temp.write_bytes(b'replaced');temp.replace(path);take(1,b'replaced')
        path.unlink();take(2)
        path.symlink_to('/dev/zero');take(3)
        path.unlink();path.write_bytes(b'original');take(5)
        time.sleep(.4);assert lib.dna_disk_pending(p,0,1)==0,'unchanged baseline repeatedly notified'
        lib.dna_disk_watch(p,0,2,str(path).encode(),b'original',8);take(5,identity=2)
        assert lib.dna_disk_pending(p,0,1)==0
        # Watches follow parent directories, and must recover after replacement.
        parent=Path(d)/'nested';parent.mkdir();nested=parent/'file';nested.write_bytes(b'original')
        lib.dna_disk_watch(p,0,3,str(nested).encode(),b'original',8);take(5,identity=3)
        parent.rename(Path(d)/'old-parent');take(2,identity=3)
        parent.mkdir();nested.write_bytes(b'recreated');take(1,b'recreated',identity=3)

    finally:lib.dna_disk_close(p)
print('PASS background file changes, atomic replacement, deletion, symlink refusal, slot reuse')

lib.dna_path_watch_open.argtypes=[c.c_char_p];lib.dna_path_watch_open.restype=c.c_void_p
lib.dna_path_watch_poll.argtypes=[c.c_void_p]
lib.dna_path_watch_close.argtypes=[c.c_void_p]
with tempfile.TemporaryDirectory() as directory:
    parent=Path(directory)/'config';parent.mkdir();path=parent/'settings'
    watcher=lib.dna_path_watch_open(str(path).encode())
    # Forced inotify failure is separately checked by disk_idle.py.
    if watcher:
        try:
            assert lib.dna_path_watch_poll(watcher)==0
            path.write_text('font_size = 18')
            assert lib.dna_path_watch_poll(watcher)==1
            assert lib.dna_path_watch_poll(watcher)==0
            parent.rename(Path(directory)/'moved')
            assert lib.dna_path_watch_poll(watcher)==-1
        finally:lib.dna_path_watch_close(watcher)
        parent.mkdir();watcher=lib.dna_path_watch_open(str(path).encode());assert watcher
        lib.dna_path_watch_close(watcher)
        print('PASS config watch create, drain, parent invalidation and recreation')
