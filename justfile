set shell := ["bash", "-euo", "pipefail", "-c"]
export DYN := env("DYN", "dyn")
export LD_LIBRARY_PATH := justfile_directory() / "build/deps/install/lib"
deps:
    python3 scripts/deps.py
build mode="debug": deps
    mkdir -p build
    "$DYN" build src --{{mode}} --output build/dna-{{mode}} --link "$PWD/build/deps/install/lib/libSDL3_ttf.so"
run: (build "debug")
    ./build/dna-debug
smoke:
    mkdir -p build
    cc -std=c11 -Wall -Wextra -Werror $(pkg-config --cflags sdl3) tests/abi.c -o build/abi-check
    ./build/abi-check
    just build debug
    SDL_VIDEODRIVER=dummy DYN_EDITOR_SMOKE=1 ./build/dna-debug
    just build release
    SDL_VIDEODRIVER=dummy DYN_EDITOR_SMOKE=1 ./build/dna-release
