#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
HOOK_DIR="$REPO_ROOT/.git/hooks"
PRE_COMMIT_HOOK="$HOOK_DIR/pre-commit"

echo "==> Installing pre-commit hook in $PRE_COMMIT_HOOK..."
mkdir -p "$HOOK_DIR"

cat << 'EOF' > "$PRE_COMMIT_HOOK"
#!/usr/bin/env bash
set -e
echo "Running pre-commit secrets scan..."
bash "$(git rev-parse --show-toplevel)/scripts/scan_secrets.sh"
EOF

chmod +x "$PRE_COMMIT_HOOK"
chmod +x "$REPO_ROOT/scripts/scan_secrets.sh"
chmod +x "$REPO_ROOT/scripts/install_hooks.sh"

echo "SUCCESS: Pre-commit hook installed and executable."
