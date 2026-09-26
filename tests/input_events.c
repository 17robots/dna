#define _GNU_SOURCE
#include <SDL3/SDL.h>
#include <SDL3_ttf/SDL_ttf.h>
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// Test-only interposer: exercise the application's actual SDL event loop.
// Burst counts are a work regression check, not human input-latency measurements.
static unsigned frames, titles, duplicate_titles;
static char previous_title[8192];
static Uint64 started;
static bool saw_complete_document;

static void queue_key(SDL_Keycode code, SDL_Keymod modifiers) {
    SDL_Event event = {0};
    event.type = SDL_EVENT_KEY_DOWN;
    event.key.key = code;
    event.key.mod = modifiers;
    event.key.down = true;
    if (!SDL_PushEvent(&event)) exit(1);
}

bool SDL_WaitEventTimeout(SDL_Event *event, int milliseconds) {
    static bool injected;
    if (!injected) {
        injected = true;
        started = SDL_GetTicksNS();
        queue_key(SDLK_I, 0);
        for (unsigned i = 0; i < 200; ++i) {
            queue_key(SDLK_A, 0);
            SDL_Event text = {0};
            text.type = SDL_EVENT_TEXT_INPUT;
            text.text.text = "a ";
            if (!SDL_PushEvent(&text)) exit(1);
        }
        queue_key(SDLK_ESCAPE, 0);
        queue_key(SDLK_Q, SDL_KMOD_CTRL);
        queue_key(SDLK_D, 0);
    }
    bool (*next)(SDL_Event *, int) = dlsym(RTLD_NEXT, "SDL_WaitEventTimeout");
    return next(event, milliseconds);
}

bool TTF_SetTextString(TTF_Text *text, const char *string, size_t length) {
    if (length == 400) {
        bool exact = true;
        for (size_t i = 0; i < length; ++i)
            if (string[i] != (i % 2 ? ' ' : 'a')) exact = false;
        if (exact) saw_complete_document = true;
    }
    bool (*next)(TTF_Text *, const char *, size_t) = dlsym(RTLD_NEXT, "TTF_SetTextString");
    return next(text, string, length);
}

bool SDL_SetWindowTitle(SDL_Window *window, const char *title) {
    ++titles;
    if (!strcmp(previous_title, title)) ++duplicate_titles;
    snprintf(previous_title, sizeof(previous_title), "%s", title);
    bool (*next)(SDL_Window *, const char *) = dlsym(RTLD_NEXT, "SDL_SetWindowTitle");
    return next(window, title);
}

bool SDL_RenderPresent(SDL_Renderer *renderer) {
    ++frames;
    bool (*next)(SDL_Renderer *) = dlsym(RTLD_NEXT, "SDL_RenderPresent");
    return next(renderer);
}

void SDL_Quit(void) {
    fprintf(stderr, "input burst: %u frames, %u titles, %u redundant titles, %.2f ms\n",
            frames, titles, duplicate_titles, (SDL_GetTicksNS() - started) / 1e6);
    if (!saw_complete_document || frames > 16 || duplicate_titles) {
        fprintf(stderr, "FAIL: lost input, excessive redraws, or redundant titles\n");
        exit(1);
    }
    void (*next)(void) = dlsym(RTLD_NEXT, "SDL_Quit");
    next();
}
