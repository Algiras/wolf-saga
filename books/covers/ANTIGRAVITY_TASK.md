# Task for the Antigravity agent: generate cover art

Paste everything below the line into Antigravity's agent chat, with this repository open as the workspace.

---

You are generating **textless cover art** for a six-book Lithuanian dark-fantasy series. Use your built-in image generation (Gemini image / "Nano Banana").

**Source of truth:** `books/covers/covers.yml`. For each entry under `books:` (numbers 1–6) it has:
- `art_prompt`: the portrait prompt (2:3)
- `art_wide_prompt`: the widescreen prompt (16:9)
- `art_negative`: things that must NOT appear (no text, letters, watermarks, logos, modern objects…)

**Do this for each book 1 → 6:**
1. Generate **3 portrait candidates** from `art_prompt` (append "Avoid: " + `art_negative`) at 2:3 portrait, the largest resolution available (target ≥ 2048×3072).
2. Generate **3 widescreen candidates** from `art_wide_prompt` (same negatives) at 16:9 (target ≥ 3840×2160, or the largest available).
3. Save them exactly as:
   `books/covers/art/candidates/book{N}_portrait_v{K}.png` and `books/covers/art/candidates/book{N}_wide_v{K}.png` (K = 1..3).
4. Check each image: reject and regenerate any that contain **any text or letter-like marks**, extra fingers or deformed hands, modern objects, or that ignore the composition notes (calm, dark space where the title goes). The giant mist/smoke/ember **wolf in the sky** must be visible in every image: it is the series motif.

**Rules:**
- Never add titles, names or any lettering: typography is added later by `scripts/make_covers.py`, because image models misspell Lithuanian (ą č ę ė į š ų ū ž).
- Keep the painterly, dark-realist style consistent across all six books (the shared style block opens every prompt).
- Don't edit any other file in the repository.

When finished, list the files you saved, and for each book say which candidate you think is strongest and why.

---

## After generation (back in the terminal)
```bash
# pick the winners (repeat per book and kind)
python3 scripts/generate_cover_art.py --select 1 portrait 2
python3 scripts/generate_cover_art.py --select 1 wide 1
# typeset all formats: ebook, square, video background, thumbnails, contact sheet
python3 scripts/make_covers.py all
python3 scripts/make_covers.py contact
```
