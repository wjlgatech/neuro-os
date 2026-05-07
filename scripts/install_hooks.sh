#!/usr/bin/env bash
# Install the local git hooks for this repo.
#
# Run once after cloning:
#
#   bash scripts/install_hooks.sh
#
# This points git at .githooks/ for this repo only (via core.hooksPath
# in the local config — no global git config is touched). To uninstall:
#
#   git config --unset core.hooksPath
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
HOOK_DIR="$REPO_ROOT/.githooks"

if [[ ! -d "$HOOK_DIR" ]]; then
    echo "✗ $HOOK_DIR not found — are you in the neuro-os repo root?" >&2
    exit 1
fi

# Make hooks executable (Windows / archive extraction sometimes loses +x).
chmod +x "$HOOK_DIR"/* 2>/dev/null || true

git config core.hooksPath "$HOOK_DIR"

cat <<EOF
✓ Installed git hooks from $HOOK_DIR

Active hooks:
  - commit-msg → enforces the What/Why/Validation message format (Law 9)
  - pre-commit → runs tests/test_engineering_principles.py before each commit

To bypass for a one-off:
  - skip msg format:   git commit --no-verify
  - skip enforcer:     FOUNDER_LOOP_SKIP_HOOKS=1 git commit ...

To uninstall:
  git config --unset core.hooksPath
EOF
