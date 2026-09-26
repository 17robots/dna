set shell := ["bash", "-euo", "pipefail", "-c"]
export DYN := env("DYN", "dyn")
build mode="debug":
    mkdir -p build
    "$DYN" build src --{{mode}} --output build/dna-{{mode}}
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
