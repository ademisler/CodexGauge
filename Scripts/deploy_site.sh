#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT_NAME="${PROJECT_NAME:-codexcontrol}"
BRANCH_NAME="${BRANCH_NAME:-main}"
SITE_DIR="$ROOT_DIR/site"

cd "$ROOT_DIR"
npx wrangler pages deploy "$SITE_DIR" --project-name "$PROJECT_NAME" --branch "$BRANCH_NAME"
