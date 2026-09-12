#!/bin/bash
# Produce a clean deployment artifact for a student-facing target host.
#
# Uses `git archive`, which (a) only ever contains the current tree state --
# no .git directory, no commit history, no commit messages -- and (b) honors
# .gitattributes export-ignore, which excludes docs/, SECURITY.md, the two
# vulnerable/*/READMEs, and the instructor-facing README.md (see
# .gitattributes for the exact list and why). README.release.md is copied in
# as the deploy-facing README.md.
#
# Usage:
#   scripts/build_release.sh [output-dir]     (default: ./release)
#
# Ship the resulting directory to the target host (rsync/scp) instead of
# `git clone`-ing this repo there. Never run this against a dirty working
# tree you haven't reviewed -- it archives whatever HEAD currently points
# at, uncommitted changes included only if committed first.
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

OUT_DIR="${1:-./release}"

if [ -e "$OUT_DIR" ]; then
  echo "refusing to overwrite existing path: $OUT_DIR" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"
git archive HEAD | tar -x -C "$OUT_DIR"
cp README.release.md "$OUT_DIR/README.md"

# git archive still emits directory entries whose contents were fully
# export-ignored (e.g. docs/) -- harmless, but clean them up so the
# spot-check below only flags a real leak, not an empty leftover folder.
find "$OUT_DIR" -depth -type d -empty -delete

echo "== release build complete: $OUT_DIR =="
echo "spot-check: the following must NOT exist in $OUT_DIR:"
for path in .git docs SECURITY.md vulnerable/upload/README.md vulnerable/privilege_escalation/README.md; do
  if [ -e "$OUT_DIR/$path" ]; then
    echo "  LEAK: $path is present -- fix .gitattributes before deploying" >&2
  else
    echo "  ok: $path absent"
  fi
done
