set shell := ["bash", "-euo", "pipefail", "-c"]
export DYN := env("DYN", "dyn")
export LD_LIBRARY_PATH := justfile_directory() / "build/deps/install/lib"
deps:
    python3 scripts/deps.py
build mode="debug": deps
    mkdir -p build
    "$DYN" build src --{{mode}} --output build/dna-{{mode}} --link "$PWD/build/deps/install/lib/libSDL3_ttf.so"
run file="": (build "debug")
    ./build/dna-debug {{quote(file)}}
test:
    python3 scripts/test.py
smoke: deps test
    mkdir -p build
    cc -std=c11 -Wall -Wextra -Werror $(pkg-config --cflags sdl3) -Ibuild/deps/install/include tests/abi.c -o build/abi-check
    ./build/abi-check
    just build debug
    just build release
    python3 scripts/smoke.py

# Exercise the user's direct command without inheriting this recipe's paths.
smoke-direct: deps
    env -u DYN_LIBRARY_PATH -u LD_LIBRARY_PATH SDL_VIDEODRIVER=dummy DYN_EDITOR_SMOKE=1 mise exec -- "$DYN" run src --no-cache
