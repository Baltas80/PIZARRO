#!/usr/bin/env bash
set -euo pipefail

SRC="${1:-.}"
DEST="${2:-./backups}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$DEST"
tar --exclude="$DEST" --exclude='.git' -czf "$DEST/pizarro-$STAMP.tar.gz" "$SRC"
printf '%s\n' "$DEST/pizarro-$STAMP.tar.gz"
