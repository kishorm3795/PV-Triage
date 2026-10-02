#!/usr/bin/env bash
set -euo pipefail

# Secret scanner for working tree and git history
# Detects: AIza..., sk-..., api_key=..., and Bearer tokens

HIT_COUNT=0

# Define regex patterns with split strings to prevent self-detection
P_AIZA="AI""za[0-9A-Za-z\-_]{35}"
P_SK="sk""-[a-zA-Z0-9]{20,}"
P_APIKEY="api""_key[[:space:]]*=[[:space:]]*['\"]?[a-zA-Z0-9_\-]{8,}"
P_BEARER="[Bb]""earer[[:space:]]+[a-zA-Z0-9_\-\.]{20,}"

PATTERN="($P_AIZA|$P_SK|$P_APIKEY|$P_BEARER)"

echo "==> Scanning working tree for secrets..."
# Search tracked and untracked files in working tree (excluding .git and the script itself)
WT_HITS=$(git grep -E -I -n "$PATTERN" -- ':!scripts/scan_secrets.sh' ':!scripts/install_hooks.sh' 2>/dev/null || true)

# Also check untracked files that might not be in git index yet
UNTRACKED=$(git ls-files --others --exclude-standard)
if [ -n "$UNTRACKED" ]; then
    for f in $UNTRACKED; do
        if [ "$f" != "scripts/scan_secrets.sh" ] && [ "$f" != "scripts/install_hooks.sh" ] && [ -f "$f" ]; then
            UNTRACKED_HITS=$(grep -E -I -n "$PATTERN" "$f" 2>/dev/null || true)
            if [ -n "$UNTRACKED_HITS" ]; then
                WT_HITS=$(printf "%s\n%s: %s" "$WT_HITS" "$f" "$UNTRACKED_HITS")
            fi
        fi
    done
fi

if [ -n "$(echo "$WT_HITS" | tr -d '[:space:]')" ]; then
    echo "ERROR: Potential secrets found in working tree:"
    echo "$WT_HITS"
    HIT_COUNT=$((HIT_COUNT + 1))
else
    echo "Working tree is clean."
fi

echo "==> Scanning git commit history for secrets..."
GIT_HITS=$(git log -E -I -p --all -G"$P_AIZA|$P_SK|$P_APIKEY|$P_BEARER" -- ':!scripts/scan_secrets.sh' ':!scripts/install_hooks.sh' 2>/dev/null || true)

if [ -n "$GIT_HITS" ]; then
    MATCHED_LINES=$(echo "$GIT_HITS" | grep -E "^\+[^+]" | grep -E "$PATTERN" || true)
    if [ -n "$MATCHED_LINES" ]; then
        echo "ERROR: Potential secrets found in git commit history:"
        echo "$MATCHED_LINES"
        HIT_COUNT=$((HIT_COUNT + 1))
    else
        echo "Git history is clean."
    fi
else
    echo "Git history is clean."
fi

if [ "$HIT_COUNT" -gt 0 ]; then
    echo "FAILED: Secret scan found $HIT_COUNT violation(s). Exiting with non-zero status."
    exit 1
fi

echo "SUCCESS: No secrets detected in working tree or git history."
exit 0
