#!/usr/bin/env sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if ! command -v python3 >/dev/null 2>&1; then
  echo 'Se requiere Python 3.10 o posterior. En Linux Mint: sudo apt install python3'
  exit 1
fi
exec python3 app.py "$@"
