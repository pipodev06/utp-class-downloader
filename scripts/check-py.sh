#!/usr/bin/env bash
# Verifica un proyecto Python con salida mínima. Uso: scripts/check-py.sh <carpeta> [--fast]
#   --fast  fase de desarrollo: sin tests ni análisis lento
# Usa uv si hay uv.lock; si no, el python del entorno activo. ruff (lint + formato), mypy si está, pytest.
set -u
source "$(dirname "${BASH_SOURCE[0]}")/_check-lib.sh"
DIR="${1:?uso: $0 <carpeta> [--fast]}"
FAST=0; [ "${2:-}" = "--fast" ] && FAST=1
cd "$ROOT/$DIR" || exit 2
NAME="$DIR"; [ "$DIR" = . ] && NAME=app
RUN=""; [ -f uv.lock ] && RUN="uv run"
command -v python >/dev/null || python() { py "$@"; }
step "$NAME-ruff" 20 -- $RUN python -m ruff check .
step "$NAME-format" 10 -- $RUN python -m ruff format --check .
if [ "$FAST" -eq 0 ] && $RUN python -c "import mypy" 2>/dev/null; then step "$NAME-mypy" 20 -- $RUN mypy .; fi
if [ "$FAST" -eq 0 ]; then
step "$NAME-test" 25 -- $RUN pytest -q -rs
warn_skips "$NAME-test"
fi
finish
