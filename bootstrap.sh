#!/usr/bin/env bash
set -euo pipefail

FORCE=0
if [[ "${1:-}" == "--force" || "${1:-}" == "-f" ]]; then
  FORCE=1
fi

CONFIG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GEMINI_ROOT="$(dirname "$CONFIG_DIR")"

if command -v python3 >/dev/null 2>&1 && python3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
  PY_BIN="python3"
elif command -v python >/dev/null 2>&1 && python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
  PY_BIN="python"
else
  echo "ERROR: Python 3.10+ (python3 or python) is required on PATH." >&2
  exit 1
fi

GEMINI_SRC="$CONFIG_DIR/GEMINI.global.md"
GEMINI_DST="$GEMINI_ROOT/GEMINI.md"

if [[ -f "$GEMINI_SRC" ]]; then
  if [[ ! -f "$GEMINI_DST" || "$FORCE" -eq 1 ]]; then
    cp "$GEMINI_SRC" "$GEMINI_DST"
    echo "Installed GEMINI.md -> $GEMINI_DST"
  else
    echo "Skipped GEMINI.md (already exists; pass --force to overwrite)"
  fi
fi

HOOKS_SRC="$CONFIG_DIR/hooks.json.portable"
HOOKS_DST="$CONFIG_DIR/hooks.json"

if [[ -f "$HOOKS_SRC" ]]; then
  if [[ ! -f "$HOOKS_DST" || "$FORCE" -eq 1 ]]; then
    "$PY_BIN" - "$HOOKS_SRC" "$HOOKS_DST" "$PY_BIN" "$CONFIG_DIR" <<'PY'
import pathlib, sys
src, dst, py_bin, cfg_dir = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), sys.argv[3], sys.argv[4]
text = (
    src.read_text(encoding="utf-8")
    .replace("__PYTHON__", py_bin)
    .replace("__CONFIG_DIR__", cfg_dir)
)
dst.write_text(text, encoding="utf-8", newline="\n")
PY
    echo "Installed hooks.json ($PY_BIN, $CONFIG_DIR) -> $HOOKS_DST"
  else
    echo "Skipped hooks.json (already exists; pass --force to overwrite)"
  fi
fi

MCP_SRC="$CONFIG_DIR/mcp_config.portable.json"
MCP_DST="$CONFIG_DIR/mcp_config.json"

if [[ -f "$MCP_SRC" ]]; then
  if [[ ! -f "$MCP_DST" || "$FORCE" -eq 1 ]]; then
    cp "$MCP_SRC" "$MCP_DST"
    echo "Installed mcp_config.json -> $MCP_DST"
  else
    echo "Skipped mcp_config.json (already exists; pass --force to overwrite)"
  fi
fi

echo ""
echo "Running config unit tests..."
"$PY_BIN" -m unittest discover -s "$CONFIG_DIR/scripts/tests" -v
