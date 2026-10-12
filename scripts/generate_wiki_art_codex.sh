#!/usr/bin/env bash
# Generate wiki entity images with the Codex CLI's built-in image generation (same method as the covers).
# Prompts come from scripts/wiki_art_prompts.py (graph node + persona description + shared style block).
#
# Usage:  scripts/generate_wiki_art_codex.sh [IDS="a b c"] [TYPES="character place"] [JOBS=3]
#   IDS="vytautas trakai" scripts/generate_wiki_art_codex.sh      # just these
#   TYPES="character" JOBS=4 scripts/generate_wiki_art_codex.sh   # all characters
#   scripts/generate_wiki_art_codex.sh                            # every entity except books (existing images skipped)
#   FORCE=1 IDS=birute ...                                         # regenerate even if wiki/images/birute.jpg exists
#   DRY=1 ...                                                      # list what would be generated
# Raw model output: wiki/images/_raw/<id>.png (git-ignored). Final: wiki/images/<id>.jpg (cropped 3:4 portrait or 4:3
# landscape, <=1200 px long side, JPEG < 400 KB). Then: python3 scripts/build_wiki.py && quarto render wiki
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CODEX="${CODEX:-$(command -v codex || echo /Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex)}"
IDS="${IDS:-}"
TYPES="${TYPES:-}"
JOBS="${JOBS:-3}"
FORCE="${FORCE:-0}"
DRY="${DRY:-0}"
IMG="$ROOT/wiki/images"
RAW="$IMG/_raw"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$IMG" "$RAW"
[ "$DRY" = 1 ] || [ -x "$CODEX" ] || { echo "Codex CLI not found (set CODEX=/path/to/codex)"; exit 1; }

# One job per entity that still lacks an image.
jobs_file="$WORK/jobs.txt"; : > "$jobs_file"
while read -r id aspect; do
  [ -n "$id" ] || continue
  have=""
  for ext in jpg jpeg webp png; do [ -s "$IMG/$id.$ext" ] && have=1; done
  if [ -n "$have" ] && [ "$FORCE" != 1 ]; then echo "skip existing $id"; continue; fi
  python3 "$ROOT/scripts/wiki_art_prompts.py" prompt "$id" > "$WORK/$id.prompt.txt"
  echo "$id $aspect" >> "$jobs_file"
done < <(python3 "$ROOT/scripts/wiki_art_prompts.py" list --types "$TYPES" --ids "$IDS")

total=$(wc -l < "$jobs_file" | tr -d ' ')
if [ "$DRY" = 1 ]; then echo "Would generate $total image(s):"; cat "$jobs_file"; exit 0; fi

run_one() {
  local id="$1" aspect="$2" size
  if [ "$aspect" = portrait ]; then size="portrait 1024x1536 (it will be cropped to 3:4, keep the subject centred)"
  else size="landscape 1536x1024 (it will be cropped to 4:3, keep the subject in the central area)"; fi
  local rel="wiki/images/_raw/${id}.png"
  "$CODEX" exec -C "$ROOT" -s workspace-write --ephemeral \
    -o "$WORK/last_${id}.txt" \
    "Generate ONE image with your image generation tool, ${size}, from the prompt in the <stdin> block. It is an encyclopedia illustration: absolutely no text, letters, runes or watermark. Save/copy the resulting PNG into this workspace as ${rel}. Do not modify any other file. Reply only with the saved path." \
    < "$WORK/${id}.prompt.txt" > "$WORK/log_${id}.txt" 2>&1 \
    && [ -s "$ROOT/$rel" ] \
    && python3 "$ROOT/scripts/wiki_art_prompts.py" process "$ROOT/$rel" "$ROOT/wiki/images/${id}.jpg" "$aspect" >/dev/null \
    && echo "ok  wiki/images/${id}.jpg" \
    || echo "FAIL $id (see: $(tail -3 "$WORK/log_${id}.txt" | tr '\n' ' '))"
}
export -f run_one; export CODEX ROOT WORK

echo "Generating $total image(s) with $JOBS parallel Codex sessions..."
[ "$total" -eq 0 ] || xargs -P "$JOBS" -L 1 bash -c 'run_one "$@"' _ < "$jobs_file"
echo "Done. Rebuild: python3 scripts/build_wiki.py && quarto render wiki"
