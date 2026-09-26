#!/usr/bin/env python3
import ctypes as c, json, os, shlex, tempfile, time
from pathlib import Path
root=Path(__file__).resolve().parents[1]
lib=c.CDLL(str(root/'build/deps/install/lib/libdna_native.so'))
lib.dna_rpc_open.argtypes=[c.c_char_p,c.c_char_p];lib.dna_rpc_open.restype=c.c_void_p
lib.dna_rpc_send.argtypes=[c.c_void_p,c.c_void_p,c.c_size_t]
lib.dna_rpc_size.argtypes=[c.c_void_p];lib.dna_rpc_size.restype=c.c_long
lib.dna_rpc_take.argtypes=[c.c_void_p,c.c_void_p,c.c_size_t];lib.dna_rpc_take.restype=c.c_long
lib.dna_rpc_close.argtypes=[c.c_void_p]
def receive(p):
    deadline=time.monotonic()+3
    while time.monotonic()<deadline:
        n=lib.dna_rpc_size(p)
        if n<0:return None
        if n:
            buf=c.create_string_buffer(n+1);assert lib.dna_rpc_take(p,buf,n+1)==n
            return json.loads(buf.raw[:n])
        time.sleep(.001)
    raise AssertionError('RPC deadline')
p=lib.dna_rpc_open(('python3 '+shlex.quote(str(root/'tests/fake_lsp.py'))).encode(),b'/tmp');assert p
try:
    request=b'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
    assert lib.dna_rpc_send(p,request,len(request));assert receive(p)['result']['capabilities']['positionEncoding']=='utf-16'
    assert not lib.dna_rpc_send(p,b'x',8388609)
finally:lib.dna_rpc_close(p)
for frame in (b'Content-Length: 999999999\r\n\r\n',b'Content-Length: 2\r\nContent-Length: 2\r\n\r\n{}',b'X: y\r\n\r\n{}',b'x'*9000):
    cmd='python3 -c '+shlex.quote('import sys,time;sys.stdout.buffer.write('+repr(frame)+');sys.stdout.flush();time.sleep(3)')
    p=lib.dna_rpc_open(cmd.encode(),b'/tmp');assert p
    try:assert receive(p) is None
    finally:lib.dna_rpc_close(p)
print('PASS LSP framing, fragmented messages, queue bounds, malformed peers, cleanup')

# Exercise the same transport against an actual installed language server.
with tempfile.TemporaryDirectory() as directory:
    fixture=Path(directory)/'main.dyn';source='fn main() { value := 42 }\n';fixture.write_text(source)
    p=lib.dna_rpc_open((shlex.quote(os.environ.get('DYN','dyn'))+' lsp').encode(),os.fsencode(directory));assert p
    def send(message):
        data=json.dumps(dict(jsonrpc='2.0',**message)).encode();assert lib.dna_rpc_send(p,data,len(data))
    def response(ident):
        for _ in range(100):
            message=receive(p);assert message is not None
            if message.get('id')==ident:return message
        raise AssertionError('too many server notifications')
    try:
        send({'id':1,'method':'initialize','params':{'processId':None,'rootUri':Path(directory).as_uri(),'capabilities':{'general':{'positionEncodings':['utf-16']}}}})
        assert 'capabilities' in response(1)['result']
        send({'method':'initialized','params':{}})
        send({'method':'textDocument/didOpen','params':{'textDocument':{'uri':fixture.as_uri(),'languageId':'dyn','version':1,'text':source}}})
        send({'id':2,'method':'textDocument/hover','params':{'textDocument':{'uri':fixture.as_uri()},'position':{'line':0,'character':13}}})
        assert 'result' in response(2)
        send({'id':3,'method':'shutdown','params':None});assert 'result' in response(3)
        send({'method':'exit','params':None})
    finally:lib.dna_rpc_close(p)
print('PASS installed Dyn LSP initialize, open, hover and shutdown')
