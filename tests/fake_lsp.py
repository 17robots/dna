#!/usr/bin/env python3
"""Deterministic stdio LSP peer, including fragmented frames and Unicode."""
import json, sys
versions={}; texts={}; commands={}
def send(message):
    body=json.dumps(dict(jsonrpc='2.0',**message),ensure_ascii=False).encode()
    header=f'Content-Length: {len(body)}\r\n\r\n'.encode()
    # Exercise partial headers/bodies, not newline-delimited JSON.
    for part in (header[:8],header[8:],body[:3],body[3:]):
        sys.stdout.buffer.write(part);sys.stdout.buffer.flush()
def offset(text,position):
    """String index of an LSP position with UTF-16 character units."""
    at=0
    for _ in range(position['line']):
        at=text.index('\n',at)+1
    units=0
    while units<position['character']:
        assert at<len(text) and text[at]!='\n',(position,text[at-10:at+10])
        units+=2 if ord(text[at])>0xFFFF else 1;at+=1
    assert units==position['character'],position
    return at
def edit(new):return {'range':{'start':{'line':0,'character':0},'end':{'line':0,'character':2}},'newText':new}
while True:
    headers={}
    while True:
        line=sys.stdin.buffer.readline()
        if not line:sys.exit()
        if line==b'\r\n':break
        key,value=line.decode().split(':',1);headers[key.lower()]=value.strip()
    message=json.loads(sys.stdin.buffer.read(int(headers['content-length'])))
    method=message.get('method');params=message.get('params',{});ident=message.get('id')
    if method=='initialize':result={'capabilities':{'positionEncoding':'utf-16','textDocumentSync':{'openClose':True,'change':2,'save':{'includeText':True}},'completionProvider':{'triggerCharacters':['/', '😀']},'hoverProvider':True,'definitionProvider':True,'referencesProvider':True,'renameProvider':True,'codeActionProvider':True}}
    elif method in ('textDocument/didOpen','textDocument/didChange'):
        doc=params['textDocument'];uri=doc['uri'];versions[uri]=doc['version']
        if method.endswith('didOpen'):texts[uri]=doc['text']
        else:
            for change in params['contentChanges']:
                if 'range' in change:
                    old=texts[uri];start=offset(old,change['range']['start']);end=offset(old,change['range']['end'])
                    assert start<=end,change
                    texts[uri]=old[:start]+change['text']+old[end:]
                else:texts[uri]=change['text']
        send({'method':'textDocument/publishDiagnostics','params':{'uri':uri,'version':doc['version'],'diagnostics':[{'range':edit('')['range'],'severity':2,'message':'fixture diagnostic é😀'}]}})
        continue
    elif method=='textDocument/didSave':
        assert params['text']==texts[params['textDocument']['uri']]
        send({'method':'window/logMessage','params':{'type':3,'message':'fixture saved'}});continue
    elif method is None and ident in commands:
        assert isinstance(params,dict)
        send({'id':commands.pop(ident),'result':None});continue
    elif ident is None:continue
    elif method=='textDocument/signatureHelp':result={'signatures':[{'label':'example(value: int)', 'documentation':'fixture signature'}], 'activeSignature':0, 'activeParameter':0}
    elif method=='textDocument/formatting':
        assert params['options']['tabSize'] > 0
        result=[edit('formatted')]
    elif method=='textDocument/hover':result={'contents':{'kind':'markdown','value':'**fixture hover**'}}
    elif method=='textDocument/completion':
        context=params.get('context', {})
        if context.get('triggerKind')==2:
            character=context['triggerCharacter']
            text=texts[params['textDocument']['uri']]
            assert character in ('/', '😀') and text[:offset(text,params['position'])].endswith(character)
        prefix = texts[params['textDocument']['uri']][:params['position']['character']]
        result=[{'label':'alphabet','insertText':'alphabet','filterText':'alphabet' if 'alphabet'.startswith(prefix) else prefix}]
        if context.get('triggerKind')==2:
            result[0]['detail']='fixture trigger accepted'
    elif method in ('textDocument/definition','textDocument/references','textDocument/typeDefinition','textDocument/implementation'):
        result=[{'uri':params['textDocument']['uri'],'range':edit('')['range']}]
    elif method=='textDocument/rename':result={'changes':{params['textDocument']['uri']:[edit(params['newName'])]}}
    elif method=='textDocument/codeAction':
        uri=params['textDocument']['uri']
        result=[{'title':'Fixture fix','edit':{'changes':{uri:[edit('fixed')]}}},
                {'title':'Resolve fixture','data':{'uri':uri}},
                {'title':'Execute fixture','command':'fixture.apply','arguments':[uri]}]
    elif method=='codeAction/resolve':result=dict(params,edit={'changes':{params['data']['uri']:[edit('resolved')]}})
    elif method=='workspace/executeCommand':
        assert params['command']=='fixture.apply'
        commands[10000]=ident
        send({'id':10000,'method':'workspace/applyEdit','params':{'edit':{'changes':{params['arguments'][0]:[edit('command')]}}}});continue
    else:send({'id':ident,'error':{'code':-32601,'message':'unsupported fixture method'}});continue
    send({'id':ident,'result':result})
