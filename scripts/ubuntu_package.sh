#!/bin/sh
# Build the Linux release package on Ubuntu 24.04 so it runs on glibc 2.39
# and newer (Ubuntu 24.04, Debian 13, Fedora 40, current Arch). Run it as
# root in a fresh ubuntu:24.04 container or GitHub's ubuntu-24.04 runner:
#
#   sh scripts/ubuntu_package.sh
#
# It installs build dependencies with apt, builds tree-sitter (Ubuntu's is
# older than DNA's 0.25 minimum), installs the pinned Dyn SDK from mise.toml,
# and writes build/packages/dna-preview-linux-x86_64.tar.gz.
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"

tree_sitter_version=0.26.9
tree_sitter_sha256=8e14780500933f43d86662fcaa1b0ce99ebe9c220f4680bc929dce09a0e0cfc6

sudo=
if [ "$(id -u)" -ne 0 ]; then
    sudo=sudo
fi

export DEBIAN_FRONTEND=noninteractive
$sudo apt-get update
$sudo apt-get install -y --no-install-recommends \
    build-essential ca-certificates clang lld curl git python3 pkg-config binutils \
    libvterm-dev libpcre2-dev libutf8proc-dev \
    libharfbuzz-dev libfribidi-dev libfreetype-dev libfontconfig-dev \
    libwayland-dev wayland-protocols libxkbcommon-dev \
    libx11-dev libxi-dev libxrandr-dev libxss-dev libxtst-dev libxext-dev libxcursor-dev \
    libgl-dev libegl-dev libgles-dev libasound2-dev fonts-dejavu-core desktop-file-utils \
    weston libgl1-mesa-dri

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

# tree-sitter >= 0.25, into /usr/local where pkg-config finds it.
curl --fail --location --retry 3 -o "$work/tree-sitter.tar.gz" \
    "https://github.com/tree-sitter/tree-sitter/archive/refs/tags/v$tree_sitter_version.tar.gz"
echo "$tree_sitter_sha256  $work/tree-sitter.tar.gz" | sha256sum --check
tar -xzf "$work/tree-sitter.tar.gz" -C "$work"
make -C "$work/tree-sitter-$tree_sitter_version" -j"$(nproc)"
$sudo make -C "$work/tree-sitter-$tree_sitter_version" install PREFIX=/usr/local
$sudo mkdir -p /usr/local/share/licenses/tree-sitter
$sudo cp "$work/tree-sitter-$tree_sitter_version/LICENSE" /usr/local/share/licenses/tree-sitter/LICENSE
$sudo ldconfig
# deps.py asks cc where each library is; cc does not search /usr/local/lib.
export LIBRARY_PATH="/usr/local/lib${LIBRARY_PATH:+:$LIBRARY_PATH}"
export PKG_CONFIG_PATH="/usr/local/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"

# The Dyn SDK pinned in mise.toml (version and Linux checksum).
dyn_version=$(sed -n 's/^version = "\(.*\)"/\1/p' mise.toml | head -n 1)
dyn_asset=$(sed -n 's/^linux-x64 = { asset_pattern = "\([^"]*\)".*/\1/p' mise.toml)
dyn_sha256=$(sed -n 's/^linux-x64 = .*checksum = "sha256:\([0-9a-f]*\)".*/\1/p' mise.toml)
test -n "$dyn_version" && test -n "$dyn_asset" && test -n "$dyn_sha256"
curl --fail --location --retry 3 -o "$work/dyn.tar.gz" \
    "https://github.com/17robots/dyn/releases/download/v$dyn_version/$dyn_asset"
echo "$dyn_sha256  $work/dyn.tar.gz" | sha256sum --check
mkdir -p "$work/dyn"
tar -xzf "$work/dyn.tar.gz" --strip-components=1 -C "$work/dyn"
export PATH="$work/dyn/bin:$PATH"

# package.py starts the packaged editor once; give it a headless display
# (the same software-rendered Weston the Arch CI job uses).
if [ -z "${WAYLAND_DISPLAY:-}" ]; then
    export XDG_RUNTIME_DIR="$work/runtime"
    mkdir -p "$XDG_RUNTIME_DIR"
    chmod 700 "$XDG_RUNTIME_DIR"
    export WAYLAND_DISPLAY=dna-package
    export LIBGL_ALWAYS_SOFTWARE=true GALLIUM_DRIVER=llvmpipe
    weston --backend=headless --renderer=pixman --socket="$WAYLAND_DISPLAY" --idle-time=0 --log="$work/weston.log" &
    weston_pid=$!
    trap 'kill "$weston_pid" 2>/dev/null; rm -rf "$work"' EXIT
    for attempt in $(seq 100); do
        [ -S "$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY" ] && break
        sleep 0.1
    done
    [ -S "$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY" ] || { cat "$work/weston.log"; exit 1; }
fi

# The same steps as `just package`, with the variables the justfile exports.
DYN=$(python3 scripts/dyn_path.py)
export DYN
export DYN_LIBRARY_PATH="$root/build/deps/install/lib"
export LD_LIBRARY_PATH="$root/build/deps/install/lib"
# The default 2048 MiB address-space cap intermittently fails editor builds
# here ("failed to create module-qualified compiler symbols"); 4096 does not.
export DNA_BUILD_MEMORY_MB="${DNA_BUILD_MEMORY_MB:-4096}"
python3 scripts/deps.py
python3 scripts/build_native.py --mode release --output build/dna-release
python3 scripts/build_native.py --backend wayland --release
python3 scripts/build_native.py --backend x11 --release
python3 scripts/compile.py "$DYN" build examples/plugins/uppercase --release --output examples/plugins/uppercase/uppercase
python3 scripts/package.py
python3 - <<'EOF'
import json, tarfile
with tarfile.open('build/packages/dna-preview-linux-x86_64.tar.gz') as archive:
    info = json.load(archive.extractfile('dna-preview-linux-x86_64/build-info.json'))
print('minimum glibc:', info['minimum_glibc'])
EOF
