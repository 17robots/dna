#!/usr/bin/env python3
"""Deterministic, logged stdio LSP traffic for the expanded benchmark only."""
import json
from pathlib import Path
import re
import sys
import time

LOG = Path(sys.argv[1])
texts = {}
completions = 0


def log(**event):
    with LOG.open('a') as stream:
        stream.write(json.dumps(dict(at_ns=time.monotonic_ns(), **event))+'\n')


def send(message):
    body = json.dumps(dict(jsonrpc='2.0', **message), ensure_ascii=False).encode()
    header = f'Content-Length: {len(body)}\r\n\r\n'.encode()
    for part in (header[:8], header[8:], body[:3], body[3:]):
        sys.stdout.buffer.write(part)
        sys.stdout.buffer.flush()


def position(text, value):
    at = 0
    for _ in range(value['line']):
        at = text.index('\n', at)+1
    units = 0
    while units < value['character']:
        units += 2 if ord(text[at]) > 0xffff else 1
        at += 1
    assert units == value['character']
    return at


while True:
    headers = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            raise SystemExit
        if line == b'\r\n':
            break
        key, value = line.decode().split(':', 1)
        headers[key.lower()] = value.strip()
    message = json.loads(sys.stdin.buffer.read(int(headers['content-length'])))
    method, params, ident = message.get('method'), message.get('params', {}), message.get('id')
    log(method=method, ident=ident)
    if method == 'initialize':
        send({'id': ident, 'result': {'capabilities': {'positionEncoding': 'utf-16',
            'textDocumentSync': {'openClose': True, 'change': 2}, 'completionProvider': {}}}})
    elif method in ('textDocument/didOpen', 'textDocument/didChange'):
        doc = params['textDocument']; uri = doc['uri']
        if method.endswith('didOpen'):
            texts[uri] = doc['text']
        else:
            for change in params['contentChanges']:
                if 'range' in change:
                    old = texts[uri]
                    start, end = position(old, change['range']['start']), position(old, change['range']['end'])
                    texts[uri] = old[:start]+change['text']+old[end:]
                else:
                    texts[uri] = change['text']
        send({'method': 'textDocument/publishDiagnostics', 'params': {'uri': uri,
            'version': doc['version'], 'diagnostics': [{'range': {'start': {'line': 0, 'character': 0},
            'end': {'line': 0, 'character': 2}}, 'severity': 2, 'message': 'BENCH_LSP_DIAGNOSTIC'}]}})
        log(event='diagnostic', version=doc['version'], text_bytes=len(texts[uri].encode()))
    elif method == 'textDocument/completion':
        completions += 1
        text = texts[params['textDocument']['uri']]
        prefix = text[:position(text, params['position'])]
        match = re.search(r'[A-Za-z0-9_]+$', prefix)
        token = match[0] if match else ''
        label = f'bench_complete_{completions:04}'
        send({'id': ident, 'result': [{'label': label, 'insertText': label, 'filterText': token}]})
    elif method == 'shutdown':
        send({'id': ident, 'result': None})
    elif method == 'exit':
        raise SystemExit
    elif ident is not None:
        send({'id': ident, 'error': {'code': -32601, 'message': 'unsupported benchmark fixture method'}})
