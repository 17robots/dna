#!/usr/bin/env python3
"""Check Dyn FFI layouts against external library headers.

The compiler reads a generated header probe from stdin. No maintained C
implementation is involved; C remains necessary to interpret dependency ABIs.
"""
import os
from pathlib import Path
import shlex
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT/'build/native-abi'
STAGE.mkdir(parents=True, exist_ok=True)
for directory in ('src', 'tests'):
    remaining = list((ROOT/directory).rglob('*.c')) + list((ROOT/directory).rglob('*.h'))
    assert not remaining, f'DNA-owned C sources remain: {remaining}'
# Dyn type, C type, C field:Dyn field mappings.
LAYOUTS = [
 ('NativeMutex', 'pthread_mutex_t', ''),
 ('NativeCondition', 'pthread_cond_t', ''),
 ('NativeTimespec', 'struct timespec', 'tv_sec:seconds tv_nsec:nanoseconds'),
 ('InstallStat', 'struct stat', 'st_dev:device st_ino:inode st_nlink:links st_mode:mode st_uid:uid st_gid:gid st_rdev:rdevice st_size:size st_blksize:block_size st_blocks:blocks st_atim.tv_sec:access_seconds st_atim.tv_nsec:access_nanos st_mtim.tv_sec:modify_seconds st_mtim.tv_nsec:modify_nanos st_ctim.tv_sec:change_seconds st_ctim.tv_nsec:change_nanos'),
 ('InstallEntry', 'struct dirent', 'd_ino:inode d_off:offset d_reclen:length d_type:kind d_name:name'),
 ('PollDescriptor', 'struct pollfd', 'fd events revents:returned'),
 ('SyntaxPoint', 'TSPoint', 'row column'),
 ('SyntaxEdit', 'TSInputEdit', 'start_byte old_end_byte new_end_byte start_point old_end_point new_end_point'),
 ('SyntaxSource', 'TSInput', 'payload read encoding decode'),
 ('SyntaxParseState', 'TSParseState', 'payload current_byte_offset:offset has_error:error'),
 ('SyntaxQueryState', 'TSQueryCursorState', 'payload current_byte_offset:offset'),
 ('SyntaxParseOptions', 'TSParseOptions', 'payload progress_callback:progress'),
 ('SyntaxQueryOptions', 'TSQueryCursorOptions', 'payload progress_callback:progress'),
 ('TsNode', 'TSNode', 'context id tree'),
 ('TsCapture', 'TSQueryCapture', 'node index'),
 ('TsMatch', 'TSQueryMatch', 'id pattern_index capture_count captures'),
 ('TsPredicateStep', 'TSQueryPredicateStep', 'type:kind value_id:id'),
 ('TermColor', 'VTermColor', 'type:kind rgb.red:red rgb.green:green rgb.blue:blue'),
 ('TermCell', 'VTermScreenCell', 'chars width attrs:attributes fg bg'),
 ('TermPos', 'VTermPos', 'row col'),
 ('TermCallbacks', 'VTermScreenCallbacks', 'damage moverect movecursor settermprop:property bell resize sb_pushline:pushline sb_popline:popline sb_clear:clear'),
]
HEADERS = '''#define _GNU_SOURCE
#define PCRE2_CODE_UNIT_WIDTH 8
#include <pthread.h>
#include <time.h>
#include <sys/stat.h>
#include <sys/epoll.h>
#include <sys/syscall.h>
#include <dirent.h>
#include <spawn.h>
#include <signal.h>
#include <poll.h>
#include <termios.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <tree_sitter/api.h>
#include <vterm.h>
#include <pcre2.h>
#include <SDL3/SDL.h>
#include <SDL3_ttf/SDL_ttf.h>
'''
# Opaque libc records and constants used by bindings, including original checks.
ASSERTS = [
 'SYS_pidfd_open==434',
 'sizeof(posix_spawn_file_actions_t)==80 && _Alignof(posix_spawn_file_actions_t)<=8',
 'sizeof(posix_spawnattr_t)==336 && _Alignof(posix_spawnattr_t)<=8',
 'sizeof(sigset_t)==128 && _Alignof(sigset_t)<=8',
 'sizeof(siginfo_t)==128 && offsetof(siginfo_t,si_pid)==16 && offsetof(siginfo_t,si_code)==8 && offsetof(siginfo_t,si_status)==24',
 'sizeof(pthread_t)==8', 'sizeof(struct epoll_event)==12 && offsetof(struct epoll_event,data)==4',
 'sizeof(struct termios)==60 && offsetof(struct termios,c_cc)==17 && offsetof(struct termios,c_ispeed)==52 && offsetof(struct termios,c_ospeed)==56',
 'sizeof(struct sigaction)==152 && offsetof(struct sigaction,sa_mask)==8 && offsetof(struct sigaction,sa_flags)==136 && offsetof(struct sigaction,sa_restorer)==144',
 '(PCRE2_UTF | PCRE2_UCP | PCRE2_NEVER_BACKSLASH_C)==0x001a0000',
 'sizeof(PCRE2_SIZE)==sizeof(size_t)',
 'sizeof(TTF_SubString)==36 && offsetof(TTF_SubString,rect)==20',
 'sizeof(SDL_Event)==128 && _Alignof(SDL_Event)==8',
 'sizeof(SDL_KeyboardEvent)==40 && offsetof(SDL_KeyboardEvent,key)==28',
 'sizeof(SDL_TextEditingEvent)==40 && offsetof(SDL_TextEditingEvent,start)==32',
 'sizeof(SDL_TextInputEvent)==32 && offsetof(SDL_TextInputEvent,text)==24',
 'sizeof(SDL_MouseButtonEvent)==40 && offsetof(SDL_MouseButtonEvent,x)==28',
 'sizeof(SDL_MouseMotionEvent)==48 && offsetof(SDL_MouseMotionEvent,x)==28',
 'SDL_EVENT_TEXT_EDITING==770 && SDL_EVENT_KEY_DOWN==768 && SDL_EVENT_TEXT_INPUT==771 && SDL_EVENT_WINDOW_CLOSE_REQUESTED==528',
 'SDLK_F1==1073741882 && SDL_PIXELFORMAT_RGBA8888==0x16462004u && SDL_TEXTUREACCESS_TARGET==2 && SDL_BLENDMODE_BLEND==1',
 'SDL_EVENT_MOUSE_MOTION==1024 && SDL_EVENT_MOUSE_BUTTON_DOWN==1025 && SDL_EVENT_MOUSE_BUTTON_UP==1026',
]
code = [HEADERS] + [f'_Static_assert({check}, "native ABI {i}");' for i, check in enumerate(ASSERTS)]
code += ['int main(void) {']
checks = []
for dyn, native, fields in LAYOUTS:
    code.append(f'printf("%zu ", sizeof({native}));')
    checks.append((f'#sizeof({dyn})', dyn+' size'))
    code.append(f'printf("%zu ", _Alignof({native}));')
    checks.append((f'#alignof({dyn})', dyn+' alignment'))
    for item in fields.split():
        native_field, _, dyn_field = item.partition(':')
        dyn_field = dyn_field or native_field
        code.append(f'printf("%zu ", offsetof({native},{native_field}));')
        checks.append((f'#cast(usize) &v{dyn}.{dyn_field} - #cast(usize) &v{dyn}', dyn+'.'+dyn_field))
code += ['VTermScreenCell cell = {0}; unsigned bits; cell.attrs.bold=1; memcpy(&bits,&cell.attrs,4); if(bits!=1)return 1;',
         'memset(&cell.attrs,0,4); cell.attrs.underline=3; memcpy(&bits,&cell.attrs,4); if(bits!=6)return 1;',
         'memset(&cell.attrs,0,4); cell.attrs.italic=1; memcpy(&bits,&cell.attrs,4); if(bits!=8)return 1;',
         'memset(&cell.attrs,0,4); cell.attrs.reverse=1; memcpy(&bits,&cell.attrs,4); if(bits!=32)return 1;',
         'return 0; }']
flags = shlex.split(subprocess.check_output(['pkg-config','--cflags','sdl3','tree-sitter','vterm'],text=True))
subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror',
                '-I'+str(ROOT/'build/deps/install/include'), *flags, '-x','c','-','-o',str(STAGE/'headers')],
               input='\n'.join(code), text=True, check=True)
values = subprocess.check_output([str(STAGE/'headers')],text=True).split()
assert len(values)==len(checks)
for source in (ROOT/'src/native/dyn').glob('*.dyn'):
    shutil.copyfile(source, STAGE/source.name)
main = ['fn main() {'] + [f'  v{name} := {name}{{}}' for name,_,fields in LAYOUTS if fields]
main += [f'  if {expression} != {value} {{ #panic("{label}") }}' for (expression,label),value in zip(checks,values)]
main += ['}']
(STAGE/'main.dyn').write_text('\n'.join(main)+'\n')
subprocess.run(['python3',str(ROOT/'scripts/compile.py'),os.environ.get('DYN','dyn'),'build',str(STAGE),'--debug','--output',str(STAGE/'check')],check=True)
subprocess.run([str(STAGE/'check')],check=True,timeout=10)
print('PASS native Dyn layouts, external constants and libvterm bitfields match headers')
