#!/bin/bash
set -e

# Deep Trip - Setup & Run Script
# Installs dependencies and builds/runs the TEN framework app on the host.

REPO_ROOT="$(cd "$(dirname "$0")"; pwd)"
GO_VERSION="1.23.6"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()   { echo -e "${RED}[ERROR]${NC} $1"; }

# ---------------------------------------------------------------
# Step 0: Pre-flight checks
# ---------------------------------------------------------------
preflight() {
    info "Checking prerequisites..."

    if ! command -v curl &>/dev/null; then
        err "curl is required but not installed."
        exit 1
    fi
    if ! command -v unzip &>/dev/null; then
        err "unzip is required but not installed."
        exit 1
    fi
    if ! command -v docker &>/dev/null; then
        err "docker is required (for OpenClaw integration)."
        exit 1
    fi

    info "Prerequisites OK."
}

# ---------------------------------------------------------------
# Step 1: Install Go
# ---------------------------------------------------------------
install_go() {
    if command -v go &>/dev/null; then
        info "Go already installed: $(go version)"
        return
    fi

    info "Installing Go ${GO_VERSION}..."
    local arch
    arch=$(uname -m)
    case "$arch" in
        x86_64)  arch="amd64" ;;
        aarch64) arch="arm64" ;;
        *)       err "Unsupported arch: $arch"; exit 1 ;;
    esac

    local tarball="go${GO_VERSION}.linux-${arch}.tar.gz"
    curl -fSL -o "/tmp/${tarball}" "https://go.dev/dl/${tarball}"
    sudo rm -rf /usr/local/go
    sudo tar -C /usr/local -xzf "/tmp/${tarball}"
    rm -f "/tmp/${tarball}"

    export PATH="/usr/local/go/bin:$PATH"
    info "Go installed: $(go version)"
}

# ---------------------------------------------------------------
# Step 2: Install task (Taskfile runner)
# ---------------------------------------------------------------
install_task() {
    if command -v task &>/dev/null; then
        info "task already installed: $(task --version 2>&1 | head -1)"
        return
    fi

    info "Installing task (Taskfile runner)..."
    sudo sh -c "$(curl -fsSL https://taskfile.dev/install.sh)" -- -d -b /usr/local/bin
    info "task installed: $(task --version 2>&1 | head -1)"
}

# ---------------------------------------------------------------
# Step 3: Install tman (TEN package manager)
# ---------------------------------------------------------------
install_tman() {
    if command -v tman &>/dev/null; then
        info "tman already installed: $(tman --version 2>&1 | head -1)"
        return
    fi

    info "Installing tman..."
    bash "${REPO_ROOT}/ten-framework/tools/tman/install_tman.sh"
    info "tman installed."
}

# ---------------------------------------------------------------
# Step 4: Symlink the deep_trip extension
# ---------------------------------------------------------------
setup_extension() {
    info "Setting up deep_trip extension symlink..."
    bash "${REPO_ROOT}/setup_extension.sh"
}

# ---------------------------------------------------------------
# Step 5: Sync .env into TEN framework ai_agents
# ---------------------------------------------------------------
sync_env() {
    local src="${REPO_ROOT}/.env"
    local dst="${REPO_ROOT}/ten-framework/ai_agents/.env"

    if [ ! -f "$src" ]; then
        warn ".env not found at ${src}"
        warn "Copy .env.example to .env and fill in your API keys first."
        cp "${REPO_ROOT}/.env.example" "$src"
        warn "Created .env from .env.example - please edit it with your keys."
        exit 1
    fi

    # Merge deep_trip-specific vars into the TEN .env (preserving existing TEN config)
    info "Syncing environment variables..."

    # Source our .env to get the values
    set -a
    source "$src"
    set +a

    # Update key values in the TEN .env
    if [ -f "$dst" ]; then
        # Update existing keys if present, otherwise append
        for var in AGORA_APP_ID AGORA_APP_CERTIFICATE DEEPGRAM_API_KEY \
                   OPENAI_API_KEY MINIMAX_TTS_API_KEY MINIMAX_TTS_GROUP_ID \
                   OPENCLAW_HOST SYSTEM_PROMPT; do
            val="${!var}"
            if [ -n "$val" ]; then
                if grep -q "^${var}=" "$dst" 2>/dev/null; then
                    sed -i "s|^${var}=.*|${var}=${val}|" "$dst"
                else
                    echo "${var}=${val}" >> "$dst"
                fi
            fi
        done
        info "TEN .env updated with deep_trip values."
    else
        warn "TEN .env not found at ${dst}, copying from source."
        cp "$src" "$dst"
    fi
}

# ---------------------------------------------------------------
# Step 6: Install TEN dependencies and build
# ---------------------------------------------------------------
build_app() {
    info "Installing TEN dependencies for tenapp..."
    cd "${REPO_ROOT}/tenapp"

    # Install dependencies via tman
    tman --verbose install

    # IMPORTANT: TEN runtime's Python addon loader links against libpython3.10.
    # All pip installs MUST use Python 3.10 to match. Using a different version
    # (e.g. 3.12 via pyenv) causes ModuleNotFoundError at runtime.
    local PIP="python3.10 -m pip"
    if ! python3.10 --version &>/dev/null; then
        warn "python3.10 not found, falling back to pip (may cause version mismatch)"
        PIP="pip"
    fi

    # Install Python requirements for all extensions
    info "Installing Python requirements (using Python 3.10)..."
    if [ -d "ten_packages/extension" ]; then
        for ext in ten_packages/extension/*/; do
            if [ -f "${ext}requirements.txt" ]; then
                info "  pip install for $(basename "$ext")"
                $PIP install -r "${ext}requirements.txt" 2>&1 | tail -1
            fi
        done
    fi
    if [ -d "ten_packages/system" ]; then
        for sys in ten_packages/system/*/; do
            if [ -f "${sys}requirements.txt" ]; then
                info "  pip install for $(basename "$sys")"
                $PIP install -r "${sys}requirements.txt" 2>&1 | tail -1
            fi
        done
    fi

    # Build Go app
    info "Building Go app..."
    if [ -f "ten_packages/system/ten_runtime_go/tools/build/main.go" ]; then
        go run ten_packages/system/ten_runtime_go/tools/build/main.go --verbose
    else
        err "ten_runtime_go build tool not found. Did tman install complete?"
        exit 1
    fi

    info "Build complete."
}

# ---------------------------------------------------------------
# Step 7: Run
# ---------------------------------------------------------------
run_app() {
    cd "${REPO_ROOT}/tenapp"

    local bin="./bin/main"
    if [ ! -f "$bin" ]; then
        # Try alternate locations
        bin=$(find . -name "main" -path "*/bin/*" -type f 2>/dev/null | head -1)
    fi

    if [ -z "$bin" ] || [ ! -f "$bin" ]; then
        err "Built binary not found. Build may have failed."
        exit 1
    fi

    # Load env vars (set -a exports them so the TEN runtime can read them)
    set -a
    source "${REPO_ROOT}/.env"
    set +a

    # CRITICAL: The TEN runtime's embedded Python needs these paths to find
    # system packages (ten_ai_base, ten_runtime) and native libraries (Agora SDK).
    # Without these, extensions fail with ModuleNotFoundError or dlopen errors.
    export PYTHONPATH="${REPO_ROOT}/tenapp/ten_packages/system/ten_ai_base/interface:${REPO_ROOT}/tenapp/ten_packages/system/ten_runtime_python/interface:${PYTHONPATH:-}"
    export LD_LIBRARY_PATH="${REPO_ROOT}/tenapp/ten_packages/system/agora_rtc_sdk/lib:${REPO_ROOT}/tenapp/ten_packages/extension/agora_rtc/lib:${LD_LIBRARY_PATH:-}"

    info "============================================"
    info "  Starting Deep Trip"
    info "============================================"
    info ""
    info "Tailscale access:"
    if command -v tailscale &>/dev/null; then
        local ts_ip
        ts_ip=$(tailscale ip -4 2>/dev/null || echo "unknown")
        info "  https://${ts_ip}:3000  (Web UI)"
    fi
    info ""
    info "Local access:"
    info "  https://localhost:3000  (Web UI)"
    info ""
    info "Press Ctrl+C to stop."
    info ""

    exec "$bin" --property "${REPO_ROOT}/tenapp/property.json"
}

# ---------------------------------------------------------------
# Main
# ---------------------------------------------------------------
usage() {
    cat <<EOF
Usage: $(basename "$0") [COMMAND]

Commands:
  install   Install all tools (go, task, tman) and build the app
  build     Build the TEN app only (assumes tools are installed)
  run       Run the app (assumes already built)
  all       Install + build + run (default)

EOF
}

main() {
    local cmd="${1:-all}"

    case "$cmd" in
        install)
            preflight
            install_go
            install_task
            install_tman
            setup_extension
            sync_env
            info "All tools installed. Run '$0 build' next."
            ;;
        build)
            sync_env
            build_app
            info "Build complete. Run '$0 run' to start."
            ;;
        run)
            run_app
            ;;
        all)
            preflight
            install_go
            install_task
            install_tman
            setup_extension
            sync_env
            build_app
            run_app
            ;;
        -h|--help|help)
            usage
            ;;
        *)
            err "Unknown command: $cmd"
            usage
            exit 1
            ;;
    esac
}

main "$@"
