#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-$ROOT_DIR/.venv/bin/python}"
DEFAULT_TARGET="https://www.example.com"
TARGET="${TARGET:-$DEFAULT_TARGET}"
OUT_DIR="${OUT_DIR:-$ROOT_DIR/reports/public-audit}"
ENGINE="${ENGINE:-stealth}"
CRAWL_DEPTH="${CRAWL_DEPTH:-2}"
MAX_URLS="${MAX_URLS:-250}"

for arg in "$@"; do
  case "$arg" in
    TARGET=*)
      TARGET="${arg#TARGET=}"
      ;;
    OUT_DIR=*)
      OUT_DIR="${arg#OUT_DIR=}"
      ;;
    ENGINE=*)
      ENGINE="${arg#ENGINE=}"
      ;;
    CRAWL_DEPTH=*)
      CRAWL_DEPTH="${arg#CRAWL_DEPTH=}"
      ;;
    MAX_URLS=*)
      MAX_URLS="${arg#MAX_URLS=}"
      ;;
    PYTHON=*)
      PYTHON="${arg#PYTHON=}"
      ;;
    *)
      if [[ "$TARGET" == "$DEFAULT_TARGET" ]]; then
        TARGET="$arg"
      fi
      ;;
  esac
done

if [[ "$TARGET" != *"://"* ]]; then
  TARGET="https://$TARGET"
fi

if [[ ! -x "$PYTHON" ]]; then
  echo "Missing Python interpreter: $PYTHON" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"

echo "Target: $TARGET"
echo "Out:    $OUT_DIR"

exec "$PYTHON" "$ROOT_DIR/main.py" "$TARGET" \
  --engine "$ENGINE" \
  --crawl-depth "$CRAWL_DEPTH" \
  --max-urls "$MAX_URLS" \
  --check-links \
  --check-api \
  --format both \
  --out "$OUT_DIR"
