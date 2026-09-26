#include <stddef.h>
#include <SDL3/SDL.h>
_Static_assert(sizeof(SDL_Event) == 128, "event storage");
_Static_assert(_Alignof(SDL_Event) == 8, "event alignment");
_Static_assert(sizeof(SDL_KeyboardEvent) == 40, "keyboard storage");
_Static_assert(offsetof(SDL_KeyboardEvent, key) == 28, "key offset");
_Static_assert(sizeof(SDL_TextInputEvent) == 32, "text storage");
_Static_assert(offsetof(SDL_TextInputEvent, text) == 24, "text pointer offset");
_Static_assert(SDL_EVENT_KEY_DOWN == 768, "key event kind");
_Static_assert(SDL_EVENT_TEXT_INPUT == 771, "text event kind");
_Static_assert(SDL_EVENT_WINDOW_CLOSE_REQUESTED == 528, "close event kind");
_Static_assert(SDLK_F1 == 1073741882, "F1 keycode");
int main(void) { return 0; }
