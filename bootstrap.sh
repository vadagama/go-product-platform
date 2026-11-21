#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT="${1:-.}"
python3 "$ROOT/installer/gpp.py" install-cli
BIN="${GPP_BIN_DIR:-$HOME/.local/bin}/gpp"
if [ -t 0 ]; then
  "$BIN" wizard --project "$PROJECT"
else
  # ADE agent: non-interactive worktree initialization only; no global changes.
  "$BIN" init --project "$PROJECT" --offline
  printf '\nADE agent: read project manager skill and ask for global skills permission/selection in conversation.\n'
fi
