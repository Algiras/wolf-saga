#!/usr/bin/env bash
# Generate textless cover-art candidates with the Codex CLI's built-in image generation.
# Prompts come from books/covers/covers.yml (via generate_cover_art.py --dry-run).
#
# Usage:  scripts/generate_cover_art_codex.sh [BOOKS="1 2 3 4 5 6"] [VERSIONS=2] [JOBS=4]
#   e.g.  BOOKS="2 5" VERSIONS=3 scripts/generate_cover_art_codex.sh
# Output: books/covers/art/candidates/book{N}_{portrait|wide}_v{K}.png (existing files are skipped)
# Then:   python3 scripts/generate_cover_art.py --select N portrait K ; python3 scripts/make_covers.py all
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CODEX="${CODEX:-$(command -v codex || echo /Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex)}"
BOOKS="${BOOKS:-1 2 3 4 5 6}"
VERSIONS="${VERSIONS:-2}"
JOBS="${JOBS:-4}"
OUT="$ROOT/books/covers/art/candidates"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$OUT"
[ -x "$CODEX" ] || { echo "Codex CLI not found (set CODEX=/path/to/codex)"; exit 1; }

# Build one job per (book, kind, version).
jobs_file="$WORK/jobs.txt"; : > "$jobs_file"
for b in $BOOKS; do
  for kind in portrait wide; do
    python3 "$ROOT/scripts/generate_cover_art.py" --dry-run --book "$b" --only "$kind" | tail -n +3 > "$WORK/b${b}_${kind}.txt"
    for v in $(seq 1 "$VERSIONS"); do
      target="$OUT/book${b}_${kind}_v${v}.png"
      [ -s "$target" ] && { echo "skip existing $(basename "$target")"; continue; }
      echo "$b $kind $v" >> "$jobs_file"
    done
  done
done

run_one() {
  local b="$1" kind="$2" v="$3" size
  if [ "$kind" = portrait ]; then size="portrait 1024x1536"; else size="landscape 1536x1024 (wide; it will be cropped to 16:9, so keep the subject inside the central 16:9 band)"; fi
  local rel="books/covers/art/candidates/book${b}_${kind}_v${v}.png"
  "$CODEX" exec -C "$ROOT" -s workspace-write --ephemeral \
    -o "$WORK/last_${b}_${kind}_${v}.txt" \
    "Generate ONE image with your image generation tool, ${size}, from the prompt in the <stdin> block. It is a textless book-cover illustration: absolutely no text, letters, runes or watermark. Variation ${v}: interpret the composition freshly. Save/copy the resulting PNG into this workspace as ${rel}. Do not modify any other file. Reply only with the saved path." \
    < "$WORK/b${b}_${kind}.txt" > "$WORK/log_${b}_${kind}_${v}.txt" 2>&1 \
    && [ -s "$ROOT/$rel" ] && echo "✓ $rel" || echo "✗ book${b} ${kind} v${v} (see log: $(tail -3 "$WORK/log_${b}_${kind}_${v}.txt" | tr '\n' ' '))"
}
export -f run_one; export CODEX ROOT WORK

total=$(wc -l < "$jobs_file" | tr -d ' ')
echo "Generating $total image(s) with $JOBS parallel Codex sessions…"
[ "$total" -eq 0 ] || xargs -P "$JOBS" -L 1 bash -c 'run_one "$@"' _ < "$jobs_file"
echo "Done. Candidates in books/covers/art/candidates/"
