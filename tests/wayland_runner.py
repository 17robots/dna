#!/usr/bin/env python3
"""Run DNA checks with private clipboard/input in a nested niri compositor.

Adapted from Dyn's tests/window-clipboard-wayland-live.py (MIT).
The virtual keyboard supplies a Shift pair to each newly focused test window,
allowing clipboard requests to use a real seat serial. No SDK checkout required.
"""
import argparse
import os
import json
import threading
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
XML='''<protocol name="virtual_keyboard_unstable_v1">
<interface name="zwp_virtual_keyboard_v1" version="1">
<request name="keymap"><arg name="format" type="uint"/><arg name="fd" type="fd"/><arg name="size" type="uint"/></request>
<request name="key"><arg name="time" type="uint"/><arg name="key" type="uint"/><arg name="state" type="uint"/></request>
<request name="modifiers"><arg name="depressed" type="uint"/><arg name="latched" type="uint"/><arg name="locked" type="uint"/><arg name="group" type="uint"/></request>
<request name="destroy" type="destructor"/>
</interface>
<interface name="zwp_virtual_keyboard_manager_v1" version="1">
<request name="create_virtual_keyboard"><arg name="seat" type="object" interface="wl_seat"/><arg name="id" type="new_id" interface="zwp_virtual_keyboard_v1"/></request>
</interface></protocol>'''
INJECT=r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
#include <wayland-client.h>
#include <xkbcommon/xkbcommon.h>
#include "virtual-keyboard-client-protocol.h"
static struct wl_seat *seat;
static struct zwp_virtual_keyboard_manager_v1 *manager;
static void global(void*p,struct wl_registry*r,uint32_t name,const char*interface,uint32_t version){
 (void)p;(void)version;
 if(!strcmp(interface,"wl_seat"))seat=wl_registry_bind(r,name,&wl_seat_interface,1);
 if(!strcmp(interface,"zwp_virtual_keyboard_manager_v1"))manager=wl_registry_bind(r,name,&zwp_virtual_keyboard_manager_v1_interface,1);
}
static void removed(void*p,struct wl_registry*r,uint32_t name){(void)p;(void)r;(void)name;}
static const struct wl_registry_listener listener={global,removed};
int main(void){
 struct wl_display *display=wl_display_connect(NULL);assert(display);
 struct wl_registry *registry=wl_display_get_registry(display);wl_registry_add_listener(registry,&listener,NULL);
 assert(wl_display_roundtrip(display)>=0&&seat&&manager);
 struct zwp_virtual_keyboard_v1 *keyboard=zwp_virtual_keyboard_manager_v1_create_virtual_keyboard(manager,seat);
 struct xkb_context *context=xkb_context_new(XKB_CONTEXT_NO_FLAGS);assert(context);
 struct xkb_rule_names names={.layout="us"};struct xkb_keymap *keymap=xkb_keymap_new_from_names(context,&names,XKB_KEYMAP_COMPILE_NO_FLAGS);assert(keymap);
 char *text=xkb_keymap_get_as_string(keymap,XKB_KEYMAP_FORMAT_TEXT_V1);assert(text);
 int fd=memfd_create("dyn-isolated-injector-keymap",MFD_CLOEXEC);assert(fd>=0);size_t size=strlen(text)+1;
 assert(write(fd,text,size)==(ssize_t)size);zwp_virtual_keyboard_v1_keymap(keyboard,WL_KEYBOARD_KEYMAP_FORMAT_XKB_V1,fd,(uint32_t)size);
 close(fd);free(text);xkb_keymap_unref(keymap);xkb_context_unref(context);
 /* The runner invokes this once per newly focused private window. */
 for(uint32_t tick=1;tick<2;tick++){
   zwp_virtual_keyboard_v1_key(keyboard,tick*50,42,WL_KEYBOARD_KEY_STATE_PRESSED);
   zwp_virtual_keyboard_v1_key(keyboard,tick*50+1,42,WL_KEYBOARD_KEY_STATE_RELEASED);
   if(wl_display_flush(display)<0)break;
   usleep(50000);
 }
 wl_display_disconnect(display);return 0;
}
'''
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--timeout', type=float, default=120)
parser.add_argument('--run', nargs=argparse.REMAINDER, required=True)
arguments = parser.parse_args()
if not arguments.run or not 0 < arguments.timeout <= 1800:
    parser.error('provide a command and timeout in (0, 1800]')
command = arguments.run
if not sys.platform.startswith('linux') or not shutil.which('niri'):
    raise SystemExit('Isolated Wayland tests require Linux and niri')
parent_display=os.environ.get('WAYLAND_DISPLAY')
parent_runtime=os.environ.get('XDG_RUNTIME_DIR')
if not parent_display or not parent_runtime:
    raise SystemExit('Isolated Wayland tests require a parent Wayland display')
with tempfile.TemporaryDirectory(prefix='dyn-wayland-live-') as directory:
    work=Path(directory);runtime=work/'runtime';runtime.mkdir(mode=0o700)
    (work/'config.kdl').write_text('')
    (work/'virtual-keyboard.xml').write_text(XML)
    for mode,output in [('client-header','virtual-keyboard-client-protocol.h'),('private-code','virtual-keyboard-protocol.c')]:
        subprocess.run(['wayland-scanner',mode,str(work/'virtual-keyboard.xml'),str(work/output)],check=True)
    flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','wayland-client','xkbcommon'],text=True))
    if command:
        (work/'inject.c').write_text(INJECT)
        subprocess.run(['cc','-std=c11','-D_GNU_SOURCE','-Wall','-Wextra','-Werror','-I'+str(work),str(work/'inject.c'),str(work/'virtual-keyboard-protocol.c'),*flags,'-o',str(work/'inject')],check=True,timeout=120)
    env=dict(os.environ);env['XDG_RUNTIME_DIR']=str(runtime);env['WAYLAND_DISPLAY']=str(Path(parent_runtime)/parent_display) if not parent_display.startswith('/') else parent_display
    env.pop('WAYLAND_SOCKET',None);env.pop('NIRI_SOCKET',None)
    log=(work/'compositor.log').open('w+')
    compositor=subprocess.Popen(['niri','-c',str(work/'config.kdl'),'--','sh','-c','printf "%s\\n" "$WAYLAND_DISPLAY" > "$XDG_RUNTIME_DIR/test-display"'],env=env,stdout=log,stderr=subprocess.STDOUT)
    try:
        deadline=time.monotonic()+10
        marker=runtime/'test-display'
        while not marker.exists() and compositor.poll() is None and time.monotonic()<deadline:time.sleep(.02)
        if not marker.exists():
            log.seek(0);raise RuntimeError('isolated compositor failed: '+log.read())
        child_env=dict(env);child_env['WAYLAND_DISPLAY']=marker.read_text().strip();child_env.pop('DISPLAY',None)
        if command:
            child_env['DNA_TEST_WAYLAND_INPUT']='1'
            sockets=list(runtime.glob('niri.*.sock'))
            assert len(sockets)==1
            child_env['NIRI_SOCKET']=str(sockets[0])
            stopped=threading.Event()
            failures=[]
            def supply_input():
                seen=set()
                try:
                    while not stopped.wait(.05):
                        result=subprocess.run(['niri','msg','-j','focused-window'],env=child_env,capture_output=True,text=True,check=True,timeout=3)
                        focused=json.loads(result.stdout)
                        if focused and focused['id'] not in seen:
                            subprocess.run([str(work/'inject')],env=child_env,check=True,timeout=3)
                            seen.add(focused['id'])
                except Exception as error:
                    failures.append(error)
            injector=threading.Thread(target=supply_input,daemon=True)
            injector.start()
            try:
                subprocess.run(command,env=child_env,check=True,timeout=arguments.timeout)
                if failures:raise failures[0]
            finally:
                stopped.set();injector.join(timeout=5)
    finally:
        compositor.terminate()
        try:compositor.wait(timeout=5)
        except subprocess.TimeoutExpired:compositor.kill();compositor.wait()
        log.close()
