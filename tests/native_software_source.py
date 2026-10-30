"""Extract the production software branch for CPU-only raster oracles.

Direct GPU rendering is covered by native_gpu.py on a real GL context. These
oracles deliberately retain their small fake surfaces and frozen CPU references.
"""
def function(path, name):
    text=path.read_text()
    actual='native_text_cached_bitmap' if name=='native_text_bitmap' and 'pub fn native_text_cached_bitmap(' in text else name
    start=text.index(('pub ' if 'pub fn '+actual+'(' in text else '')+'fn '+actual+'(')
    end=text.index('{',start)+1;depth=1
    while depth:
        if text[end]=='{':depth+=1
        elif text[end]=='}':depth-=1
        end+=1
    body=text[start:end]
    marker='if native_gui.direct {'
    while marker in body:
        begin=body.index(marker);finish=body.index('{',begin)+1;depth=1
        while depth:
            if body[finish]=='{':depth+=1
            elif body[finish]=='}':depth-=1
            finish+=1
        body=body[:begin]+body[finish:]
    body=body.replace('    if !native_gui.direct {\n      native_texture_cpu(t)\n    }\n','').replace('  native_texture_cpu(t)\n','').replace('    t.dirty=true\n','')
    if actual!=name:
        body=body.replace('native_text_cached_bitmap(renderer:rawptr, key:u64,','native_text_bitmap(renderer:rawptr,')
    return body
