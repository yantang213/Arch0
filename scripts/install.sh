#!/bin/sh
set -eu

ARCH0_REPO_URL="${ARCH0_REPO_URL:-https://github.com/yantang213/Arch0.git}"
ARCH0_REF="${ARCH0_REF:-main}"
ARCH0_INSTALL_DIR="${ARCH0_INSTALL_DIR:-$HOME/.local/share/arch0/repo}"
ARCH0_BIN_DIR="${ARCH0_BIN_DIR:-$HOME/.local/bin}"
ARCH0_SKIP_SKILL_INSTALL="${ARCH0_SKIP_SKILL_INSTALL:-0}"
ARCH0_SKILL_SOURCE="${ARCH0_SKILL_SOURCE:-$ARCH0_REPO_URL}"

log() {
  printf '%s\n' "$*"
}

fail() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

have() {
  command -v "$1" >/dev/null 2>&1
}

require_command() {
  if ! have "$1"; then
    fail "missing required command: $1. Install $1, then rerun this installer."
  fi
}

require_node_20() {
  require_command node
  major="$(node -p "process.versions.node.split('.')[0]" 2>/dev/null || printf '0')"
  case "$major" in
    ''|*[!0-9]*) fail "could not detect Node.js version. Install Node.js 20 or newer." ;;
  esac
  if [ "$major" -lt 20 ]; then
    fail "Node.js 20 or newer is required. Current major version: $major."
  fi
}

checkout_repo() {
  if [ -d "$ARCH0_INSTALL_DIR/.git" ]; then
    log "Updating Arch0 repo at $ARCH0_INSTALL_DIR"
    git -C "$ARCH0_INSTALL_DIR" fetch --quiet origin "$ARCH0_REF"
    git -C "$ARCH0_INSTALL_DIR" checkout --quiet "$ARCH0_REF"
    git -C "$ARCH0_INSTALL_DIR" pull --ff-only --quiet origin "$ARCH0_REF"
    return
  fi

  if [ -e "$ARCH0_INSTALL_DIR" ]; then
    fail "$ARCH0_INSTALL_DIR exists but is not a git repo. Move it aside or set ARCH0_INSTALL_DIR."
  fi

  mkdir -p "$(dirname "$ARCH0_INSTALL_DIR")"
  log "Cloning Arch0 from $ARCH0_REPO_URL"
  git clone --quiet --branch "$ARCH0_REF" "$ARCH0_REPO_URL" "$ARCH0_INSTALL_DIR"
}

build_cli() {
  if [ ! -f "$ARCH0_INSTALL_DIR/cli/package.json" ]; then
    fail "CLI package not found at $ARCH0_INSTALL_DIR/cli/package.json."
  fi

  log "Installing Arch0 CLI dependencies"
  (cd "$ARCH0_INSTALL_DIR/cli" && npm install)

  log "Building Arch0 CLI"
  (cd "$ARCH0_INSTALL_DIR/cli" && npm run build)

  if [ ! -f "$ARCH0_INSTALL_DIR/cli/dist/index.js" ]; then
    fail "CLI build did not produce $ARCH0_INSTALL_DIR/cli/dist/index.js."
  fi
}

write_shim() {
  mkdir -p "$ARCH0_BIN_DIR"
  shim="$ARCH0_BIN_DIR/arch0"
  tmp="$shim.tmp.$$"

  cat >"$tmp" <<EOF
#!/bin/sh
exec node "$ARCH0_INSTALL_DIR/cli/dist/index.js" "\$@"
EOF
  chmod 755 "$tmp"
  mv "$tmp" "$shim"
  log "Installed arch0 shim at $shim"
}

install_skill() {
  if [ "$ARCH0_SKIP_SKILL_INSTALL" = "1" ]; then
    log "Skipping Arch0 Skill installation because ARCH0_SKIP_SKILL_INSTALL=1"
    return
  fi

  if ! have npx; then
    log "Skipping Arch0 Skill installation because npx was not found."
    log "After npm/npx is available, run:"
    log "  npx -y skills add \"$ARCH0_SKILL_SOURCE\" -y -g"
    return
  fi

  log "Installing Arch0 Skill"
  if ! npx -y skills add "$ARCH0_SKILL_SOURCE" -y -g; then
    log "Arch0 Skill installation failed."
    log "You can retry manually:"
    log "  npx -y skills add \"$ARCH0_SKILL_SOURCE\" -y -g"
  fi
}

print_path_hint() {
  case ":$PATH:" in
    *":$ARCH0_BIN_DIR:"*) ;;
    *)
      log ""
      log "PATH warning: $ARCH0_BIN_DIR is not on PATH."
      log "Add it to your shell profile, for example:"
      log "  export PATH=\"$ARCH0_BIN_DIR:\$PATH\""
      ;;
  esac
}

main() {
  require_command git
  require_command npm
  require_node_20

  checkout_repo
  build_cli
  write_shim
  install_skill
  print_path_hint

  log ""
  log "Arch0 CLI installed."
  log ""
  log "Next steps on a remote machine:"
  log "  arch0 setup remote"
  log "  arch0 status"
}

main "$@"
