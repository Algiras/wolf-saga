# Audiobook → YouTube Pipeline Review

*Scope: everything in `audiobook/` plus `.github/workflows/render.yml`. Reviewed 2026-10-10 on branch `claude/book-story-review-ef2045`. Every script was read in full. Read-only checks only: `python3 -m py_compile` passes for all 23 scripts (syntax only), and I listed the output, cache and asset directories and checked whether secret files exist. I ran no TTS, made no paid API calls, uploaded nothing and read no secrets.*

> **Baseline note.** All file:line references are to the **committed HEAD (`09f5760`)**. While this review was being written (about 22:06–22:09 local time), another session began rewriting the audiobook scripts in this worktree. As of the end of this review, 17 audiobook files are modified and a new `audiobook/book_manifest.py` (stable chapter keys, manifest helpers) exists, all uncommitted. That work was not reviewed here. Line numbers may no longer match the working tree. Re-check each issue below against those edits before closing it. `book_manifest.py` already overlaps task T3 (manifest) in §9.

---

## 1. Summary verdict

**The current pipeline is not fit for a daily chapter series, and it should not be patched.** Replace it with a small, book-agnostic package, and salvage only a few ideas from the old code: the ffmpeg still-image encode, loudnorm, and reading chapter order from `_quarto.yml`.

The reasons, in order of how much they would hurt:

1. **It would publish another project's content.** `generate_chapter_videos.py`, the per-chapter video builder, puts the cover of *a different book* ("The Shadow of Extremism", `audiobook_splash_screen.png`) on every video. It also writes the description boilerplate of a third project ("Miserable: How to Fail at Life", miserable.cloud, a LinkedIn link, satire disclaimer) into every `description.txt`. Three more scripts default to `Miserable_Audiobook_Complete.wav`, and `mcp.json` mounts a directory from `the-shadow-of-extremism`.
2. **It loses text silently.** When a TTS chunk fails, the code logs the error, skips the chunk and still writes the WAV (`tts_helpers.py:140-154`). When an LLM chunk fails, the code writes a `[Error: Chunk N failed]` placeholder, and `clean_invalid_tags()` then deletes it as an "invalid tag" (`1_preprocess_with_ollama.py:566-571, 500`). Either way the listener hears a chapter with sentences missing, and nothing reports a failure.
3. **Revisions are never picked up.** Every stage skips a step when its output file already exists. The LLM cache is keyed by chapter *name*, not content (`1_preprocess_with_ollama.py:513-523`). The book is being revised right now, and a revised chapter would keep its old audio.
4. **Inserting a chapter renames everything after it.** Output files are named `{enumerate index}_{name}`. Adding `00_pradzia` (already in `_quarto.yml`) or `28b_krevos_sutartis` shifts every later index. The concatenator globs `output/*.wav` and would then splice old and new copies of the same chapters together (`3_concatenate_audio.py:39-46`).
5. **Lithuanian narration does not exist.** Stage 1 is an LLM *translation into English* (Gemini, despite the "ollama" filename). Its prompt strips the diacritics (lines 200–205). The TTS engine, Chatterbox-Turbo, is English-only.
6. **The upload path breaks YouTube's terms and has no state.** `youtube_uploader.py` drives YouTube Studio with Playwright: brittle CSS selectors, every video hard-coded to PRIVATE, no scheduling, no playlists, no captions, no thumbnails, and no record of what was uploaded, so a re-run uploads everything again. The YouTube ToS forbid automated access except through the API.
7. **Loudness and format are wrong for per-chapter uploads.** Each chapter is only peak-normalised; `loudnorm -14 LUFS` runs only on the concatenated whole book. The 1024×1024 square cover becomes a square video. There is no `+faststart` and no 48 kHz audio. The validator checks ACX levels (−23 to −18 dB RMS) that contradict the −14 LUFS master, against the wrong file, and the orchestrator prints "Technical Validation: Passed (ACX Compliant)" unconditionally (`generate_complete_audiobook.py:201`).

**Good news:** nothing has been generated or uploaded from this checkout. `output/`, `cache/`, `preprocessed/` and `transcripts/` hold only `.gitkeep`. No `.env`, `client_secret*.json`, `token*.json`, `voices/`, `reference_voice.wav` or `~/.playwright_youtube_session` exists. So there is no state to migrate, and a clean redesign costs nothing. One English full-book video from an earlier run is already public (`llms.txt` → `youtube.com/watch?v=7FTLqyPXSr0`). Section 8 says what to do with it.

**Recommended direction:**

- One deterministic, content-hashed pipeline: `manifest → extract → (translate) → script/markup → synth → master → render → publish`.
- Driven by `--book N --lang lt|en`.
- A global upload ledger.
- A **one-off scheduled batch upload with `publishAt`** per book and language, run as a rolling window while chapters are still being revised.
- Lithuanian on **ElevenLabs Eleven v3** (provisional; an A/B test decides), English on a *different* engine.
- Both fed from one neutral "emotion markup" script and the pronunciation lexicon.
- Book I as 30 daily parts of about 5–12 minutes.

---

## 2. Pipeline map (as found)

```
books/_quarto.yml ──► 1_preprocess_with_ollama.py  (Gemini 2.5 Flash via langchain; LLM translate LT→EN + "editor" rewrite)
                        │  cache/{chapter_name}.txt        ← keyed by NAME, never invalidated
                        │  preprocessed/{idx:02d}_{name}.txt + manifest.json   ← idx = enumerate position
                        │  (MCP servers + embeddings + "semantic memory" are built but never reach the prompt)
                        ▼
                     2_generate_audio.py  (Chatterbox-Turbo, English; voice_map of 28 hard-coded names → voices/*.wav)
                        │  output/{idx:02d}_{name}.wav     ← peak-normalised per file; skips if exists; loop never exits
                        ▼
                     3_concatenate_audio.py  (glob output/*.wav → one WAV, 3 s gaps, loudnorm −14 LUFS single pass)
                        │  GelezinioVilkoSaga_Book1_Complete.wav + output/timestamps.txt
                        ▼
                     4_generate_youtube_video.py  (cover.png 1024² still + optional bg music amix + optional
                        │                          faster-whisper "turbo" EN captions BURNED IN)
                        ▼
                     5_technical_validation.py  (ACX RMS/peak check on "Miserable_Audiobook_Complete.wav")

Per-chapter branch:  generate_chapter_videos.py  (output/*.wav → showwaves video on the WRONG BOOK's cover,
                        │                          description.txt with ANOTHER PROJECT's boilerplate)
                        ▼
                     youtube_uploader.py  (Playwright → studio.youtube.com, PRIVATE, no state)

Orchestrators:  generate_complete_audiobook.py → intro/outro (EN text) + generate_parallel_queues.PipelineManager
                generate_parallel.py (older; broken CLI args; never terminates)
Helpers/dev:    tts_helpers.py, normalize_voices.py, clean_tags.py, lint_book.py, debug_chapters.py,
                verify_english.py == verify_lithuanian.py (byte-identical), test_preprocessor.py, check_mcps.py,
                mcp.json, Dockerfile.mcp, download_voice_references.py (yt-dlp clips of YouTube videos),
                download_elevenlabs_voices.py, generate_youtube_waveform.py, generate_youtube_colorful.py
CI:             .github/workflows/render.yml renders the book and wiki only; there is no audiobook job (correct).
```

**Chapter discovery.** `load_quarto_config()` flattens `_quarto.yml` and *includes the part titles* ("Nuosmukis", "Pabėgimas", "Karas ir Tvarka") as pseudo-chapters (lines 255-256). They fail the file lookup and become LLM-narrated "Part:" stubs (lines 529-534). `sources.qmd` is narrated. `index.qmd` and `copyright.qmd` are skipped. The dict branch of `get_ordered_chapters()` (lines 706-718) is dead code, because the list is already flat. A stray `books/1/19_velnio_sandėris.qmd.tmp` exists; it is harmless under `_quarto.yml` discovery but would break a glob.

---

## 3. Issues ranked by severity

Severity scale: **S1** means wrong or harmful content would ship, or content is lost. **S2** means wrong output, or no idempotency or resumability. **S3** means quality loss. **S4** means hygiene.

### S1: blockers

| # | Where | Problem | Impact | Fix |
|---|---|---|---|---|
| 1 | `generate_chapter_videos.py:18-40`, `audiobook_splash_screen.png` | The cover is "The Shadow of Extremism". The description boilerplate is from "Miserable: How to Fail at Life" (miserable.cloud, LinkedIn, satire disclaimer, `#ReverseMaven`). `BLOG_DIR` points at a nonexistent `../blog`. | Every per-chapter video would carry another book's cover and another project's links. | Delete the script and the image. New render stage uses per-book art from the manifest. |
| 2 | `tts_helpers.py:136-154` | TTS exceptions are caught, printed and skipped (`continue`). The WAV is still written and later treated as done (`> 1000` bytes). | Silent missing sentences in published audio. | Fail the chapter on any segment error after retries. Write to a temp file, then rename atomically. Assert segment count equals utterance count. |
| 3 | `1_preprocess_with_ollama.py:566-571` + `500` | A failed LLM chunk becomes `[Error: Chunk N failed]`. `clean_invalid_tags` deletes bracketed text that is not a proper name or FX tag, so the placeholder vanishes. `is_error_text` only detects the whole-chapter error string. | Silent missing passages in the English text, which then get cached. | Raise on failure and never cache partial output. Validate that the translation covers every source paragraph (paragraph-count and length-ratio check). |
| 4 | `1_preprocess_with_ollama.py:513-523, 743-756`; `2_generate_audio.py:135`; `generate_parallel_queues.py:134,173` | Skip-if-exists everywhere. The LLM cache is keyed by `chapter_name`. | Revised chapters are never re-translated or re-voiced. Stale audio ships. | Content-addressed keys: `sha256(source text + stage version + engine + voice + settings)`. |
| 5 | `1_preprocess_with_ollama.py:740`, `generate_parallel_queues.py:66-76,95,132`, `3_concatenate_audio.py:39-46` | File names use the `enumerate` position. The concatenator globs `output/*.wav`. | Adding `00_pradzia` or `28b` renames every later file, so everything is re-voiced and old and new copies are both concatenated (duplicated chapters). | Stable part keys derived from chapter stems (`b1/03_gintaro_sapnas`). Release order lives only in the manifest. Never glob outputs. |
| 6 | `youtube_uploader.py` (whole file) | Playwright drives the Studio UI. Selectors such as `#create-icon` and `#text-item-0` are brittle. Every video is set to PRIVATE (line 65), with no `publishAt`, playlist, captions, thumbnail, language, licence or synthetic-media fields, and no state. A re-run uploads duplicates (lines 95-102). | Breaks YouTube ToS (automated access outside the API). Cannot schedule. Not idempotent. | Replace with the YouTube Data API v3 (`videos.insert` with `status.publishAt`) plus a ledger (§7). |
| 7 | `download_voice_references.py:17-26` | Clips ten YouTube videos with `yt-dlp` as voice-cloning references for named characters. | Cloning real people's voices without consent is a rights and YouTube-policy problem. It would also force the "altered or synthetic" disclosure. | Delete. Use the engine's licensed library or designed voices. Clone only consenting voices, for example the author's own. |
| 8 | `1_preprocess_with_ollama.py:200-205` | The prompt tells the model to transliterate ą/ę/į/ų/ū/ė → a/e/i/u/u/e and š/č/ž → sh/ch/zh. It contradicts itself: "zh for ž", yet the example is *Žemyna → Zemyna*. *ę* and *ė* (different vowels) merge, so the lexicon can no longer be matched reliably. | Wrong names in English narration. Nothing for a pronunciation step to work with. | Keep the original Lithuanian spelling of every name. Apply the lexicon after translation (§5). |

### S2: wrong output, broken flow, no resumability

| # | Where | Problem | Fix |
|---|---|---|---|
| 9 | `2_generate_audio.py:104-105, 119-163` | It waits forever for `manifest.json`. The main `while True` loop never exits. | Batch CLI that exits with a status code. |
| 10 | `generate_parallel.py:59` | Passes `--reference-audio` to `2_generate_audio.py`, which only accepts `--device`, so argparse exits with code 2. `MANIFEST_PATH` is wrong (line 17) and the final message names "Miserable" (line 159). | Delete (superseded). |
| 11 | `generate_complete_audiobook.py:168-171, 201` | `--skip-preprocessing` and `--skip-video` are parsed but ignored. It prints "Technical Validation: Passed (ACX Compliant)" whatever happened. Intro and outro text are English only (lines 29-45). | Replace with a CLI that reports real results. |
| 12 | `tts_helpers.py:166-170` | Per-file *peak* normalisation to 0.9. Only the whole-book master gets loudnorm (`3_concatenate_audio.py:119`). | Per-part two-pass loudnorm to −14 LUFS integrated, −1.5 dBTP (§4.3). |
| 13 | `4_generate_youtube_video.py:39-56` | The background music is mixed with `amix` *after* mastering. `amix` normalises by the input count, so narration drops about 6 dB and the loudness target is lost. | Mix any bed *before* the final loudnorm, with `amix=normalize=0` and a sidechain duck. Better still: no music bed under narration. |
| 14 | `5_technical_validation.py:13, 63-99` | Validates `Miserable_Audiobook_Complete.wav`. ACX RMS −23..−18 dB contradicts the −14 LUFS master. `volumedetect` mean is not LUFS. | Validate each part with `ebur128` and true peak against the YouTube target. |
| 15 | `1_preprocess_with_ollama.py:375-389, 543-546, 658-690, 726-727` | Previous/next and semantic context are computed (extra Gemini summary call plus embeddings per chapter) but never inserted into the prompt. MCP servers are connected but no tools are bound. | Remove. You pay for calls that change nothing. |
| 16 | `1_preprocess_with_ollama.py:549-550` | Chunks are split every 4,000 *characters*, mid-sentence or mid-word, each translated with no neighbouring context. | Split on paragraph boundaries, or send whole chapters (all chapters are under 12k characters). |
| 17 | `1_preprocess_with_ollama.py:405-430` | The editor prompt asks for `[Narrator]` and `[Character]` blocks, contradicting the "no tags" rule. `clean_invalid_tags` keeps capitalised tags, and `tts_helpers` uses them to switch voices. | Generate voice and speaker information in a separate structured markup step (§5.4), not inside free text. |
| 18 | `3_concatenate_audio.py:36` / `generate_chapter_videos.py:65-69` / `youtube_uploader.py:25-29` | Titles come from file stems (`Senasis_Sernas.Title()`) or from a "CHAPTER:" line, not from the `# Heading` in the `.qmd`. | Titles come from the manifest, which reads the headings once. |
| 19 | `4_generate_youtube_video.py:113-121`, `generate_parallel_queues.py:175` | Captions come from faster-whisper "turbo" with `language="en"`, so they misspell invented names, and the code would mis-transcribe Lithuanian audio. | Build captions from the script text and the segment timings (§4.5). No ASR needed. |
| 20 | `4_generate_youtube_video.py:158-177`, `generate_parallel_queues.py:236-238` | Captions are *burned in*, a second full encode. | Upload soft captions with `captions.insert` (accessible, searchable, can be turned off). |
| 21 | `lint_book.py:8-9` | Globs `../books/*.qmd`, which is only `index`, `copyright` and `sources`. It never lints `books/1/*.qmd`. Path depends on the current directory. | Lint the chapters listed in the manifest. Resolve paths from `__file__`. |
| 22 | `debug_chapters.py:5` | Opens `../book/_quarto.yml` (`book`, not `books`), so it crashes. | Delete (the manifest CLI replaces it). |

### S3: quality

| # | Where | Problem | Fix |
|---|---|---|---|
| 23 | `tts_helpers.py:15-59` | `chunk_text` splits only on `'. '`. It appends `.` to every piece, turning questions into statements. It ignores `?`, `!`, `…` and the Lithuanian quotes `„…“`. A long dash-joined sentence exceeds the limit. | Sentence segmentation that handles `?!…` and closing quotes, falling back to `;` `:` and ` — `. |
| 24 | `tts_helpers.py:87-100` | A flat 0.3 s per newline. Paragraph, scene-break and chapter-break pauses are indistinguishable. | Pause table: sentence ≈ engine default, paragraph 0.6 s, dialogue turn 0.35 s, scene break (`* * *` / `---`) 1.8 s, chapter seam in a merged part 3 s. |
| 25 | `1_preprocess_with_ollama.py:276-299` | Markdown stripping misses `{.unnumbered}` attributes, footnotes `[^1]`, and italics (`*„…“*`, the divine voice). It turns `#` into "Chapter:" and `>` into `Quote: "…"`, so the narrator would read "Chapter:" and "Quote:" aloud. | Parse with a proper Markdown parser (markdown-it-py), map italics to a `voice=divine/inner` markup attribute, and drop attributes. |
| 26 | (all) | No number normalisation. Lithuanian needs case-aware verbalisation (*1385 m.*, Roman numerals as in *Vilniaus Apgultis I*). | Extract stage flags digits and Roman numerals. Resolve them with a small rule table plus an LLM proposal that the author reviews (stored as overrides). |
| 27 | `4_generate_youtube_video.py:15,41-66` | 1024×1024 source gives a square video (pillarboxed), 25 fps implicit, no `+faststart`, AAC at the source rate (24 kHz from Chatterbox). | 1920×1080 card, `-tune stillimage`, H.264 High, `yuv420p`, AAC 48 kHz, `+faststart` (§4.4). |
| 28 | `generate_chapter_videos.py:94-98`, `generate_youtube_*.py` | `showwaves` 1920 px wide overlaid on a 1024 px base, encoded with `-preset medium` per frame. Slow and cropped. | A still image only. Waveforms add render time and nothing for a listener. |

### S4: hygiene

| # | Where | Problem |
|---|---|---|
| 29 | `requirements.txt` | Missing `mcp`, `langgraph`, `langchain-core`, `faster-whisper`, `playwright`, `soundfile`, `scipy`, `numpy`. `google-generativeai` is unused. Nothing is pinned. |
| 30 | `README.md` | Describes Ollama/Ministral, a nonexistent `VOICE_CLONING.md`, `generate_audiobook.py` and a `--model` flag. Licence section says "part of The Shadow of Extremism … personal use only", which contradicts the book's CC BY-NC-SA. |
| 31 | `YOUTUBE_DESCRIPTION.md` | Says preprocessing used Ollama and that Lithuanian TTS "is not yet capable". The second claim is now outdated (§5). © 2025 only. |
| 32 | `verify_lithuanian.py` | Byte-identical to `verify_english.py`. It has no Lithuanian content. |
| 33 | `normalize_voices.py:95-123` | Overwrites files in place, uses paths relative to the current directory, and imports `shutil` inside a loop, so line 109 raises `NameError` when `voices/` is empty. |
| 34 | `clean_tags.py` | Strips *every* bracketed span except 9 FX tags (speaker tags included), in place, in `preprocessed/`. |
| 35 | `mcp.json:14`, `Dockerfile.mcp`, `check_mcps.py`, `test_preprocessor.py` | Unused MCP infrastructure. The memory volume points into `the-shadow-of-extremism`. The Dockerfile installs `server-wikipedia`, which `mcp.json` never references. |
| 36 | `download_elevenlabs_voices.py` | Generates ElevenLabs premade-voice samples to use as Chatterbox clone prompts. Check whether ElevenLabs terms permit using outputs as cloning references for another engine. If you adopt ElevenLabs, use the voices directly instead. |
| 37 | `generate_youtube_waveform.py`, `generate_youtube_colorful.py` | Duplicate video generators defaulting to the "Miserable" files. |
| 38 | `llms.txt` | "License: See repository details". It should state CC BY-NC-SA 4.0 and list the per-book playlists once they exist. |

---

## 4. Recommended target pipeline (book-agnostic)

### 4.1 Diagram

```
                       audiobook/config/series.yaml   (series names, templates, schedule, voices per lang)
                       audiobook/manifests/book{N}.yaml (parts → chapters → titles; committed, CI-checked vs _quarto.yml)
                                         │
   books/N/*.qmd ──► [1 extract] ──► build/bN/lt/src/<chapter>.txt  (+ flags: numbers, roman numerals, foreign words)
                                         │
                         lang=en ──► [2 translate] ──► audiobook/text/bN/en/<chapter>.md   (COMMITTED, human-reviewed;
                                         │                 key = sha(src + prompt_ver + model); diacritics kept)
                                         ▼
                                   [3 script/markup] ──► build/bN/<lang>/<part>/script.jsonl
                                         │   rules (dialogue dashes, italics, scene breaks) + LLM speaker/emotion
                                         │   + audiobook/overrides/bN/<chapter>.yaml ; fidelity validator
                                         ▼
           world_rules/pronunciation_lexicon.json ──► [lexicon] (per-engine: PLS / inline IPA / respelling)
                                         ▼
                                   [4 synth] ──► build/cache/tts/<sha>.wav   (content-addressed per utterance;
                                         │        engine adapters: elevenlabs | gemini | google | azure | chatterbox | kokoro)
                                         ▼
                                   [5 master] ──► build/bN/<lang>/<part>/{part.flac, part.m4a, part.srt, part.vtt, qc.json}
                                         │        intro + body (pause table) + outro/end-screen bed → 2-pass loudnorm
                                         ▼
                                   [6 render] ──► build/bN/<lang>/<part>/{card.png, thumb.jpg, part.mp4}
                                         ▼
                                   [7 publish] ◄──► audiobook/state/uploads.json   (global ledger, committed)
                                         │        dry-run by default; quota budget; publishAt; playlists; captions; thumbs
                                         ▼
                                   [8 verify] ── videos.list → ledger reconcile; report stale parts
```

One CLI, every command idempotent:

```
python -m wolfaudio manifest  --book 1 [--check]              # (re)generate / validate manifest against _quarto.yml
python -m wolfaudio build     --book 1 --lang lt [--part b1/03_gintaro_sapnas] [--until master|render]
python -m wolfaudio ab-test   --book 1 --lang lt --engines elevenlabs,gemini,google --scenes ab_scenes.yaml
python -m wolfaudio schedule  --book 1 --lang lt --start 2026-11-02 --time 18:00 --tz Europe/Vilnius [--print]
python -m wolfaudio publish   --book 1 --lang lt [--window 10] [--execute]       # default: dry run
python -m wolfaudio status    [--book 1] [--lang lt]                              # ledger vs disk vs YouTube
```

### 4.2 Stage contracts

| Stage | Input | Output | Cache key (always includes book and lang) | Failure rule |
|---|---|---|---|---|
| **0 manifest** | `books/_quarto.yml` (or a Quarto profile per book), `.qmd` `# headings` | `manifests/bookN.yaml`: ordered parts, each `{key, chapters[], section, title_lt, title_en, blurb_lt, blurb_en, label}` | n/a (committed file) | `--check` fails CI if a `.qmd` listed in `_quarto.yml` is in no part, in two parts, or missing |
| **1 extract** | `.qmd` | normalised text, paragraph list, flags | `sha(qmd bytes, extract_ver)` | Unknown Quarto syntax is an error, not silently passed |
| **2 translate** (en) | extract output | `text/bN/en/<ch>.md` (committed) | `sha(src, prompt_ver, model)` | Paragraph count must match the source (±0). Lithuanian names kept verbatim. Output is never cached on failure |
| **3 script** | lt source or en text, overrides | `script.jsonl` (§5.4 schema) | `sha(text, markup_ver, overrides)` | Fidelity: concatenated `text` fields must equal the input text after whitespace normalisation |
| **4 synth** | script, voice config, lexicon | one WAV per utterance | `sha(engine, model, voice_id, settings, rendered_text)` | Retry 3× with backoff, then fail the part. No partial part output |
| **5 master** | utterance WAVs, intro/outro templates | `part.flac` (archive), `part.m4a`, `part.srt/.vtt`, `qc.json` | `sha(utterance hashes, pause table, master_ver)` | QC gate: −14 ±0.5 LUFS, TP ≤ −1.5 dBTP, no silence over 4 s except planned, utterance count matches |
| **6 render** | `part.m4a`, card template, art | `card.png` 1920×1080, `thumb.jpg` 1280×720 under 2 MB, `part.mp4` | `sha(audio, card, encoder_ver)` | `ffprobe` asserts H.264/AAC 48 kHz, duration within ±0.5 s of audio |
| **7 publish** | render outputs, ledger, series config | YouTube video + playlist items + captions + thumbnail, ledger row | ledger row compares `content_hash` with `video_hash` | Stops cleanly when the quota budget is spent. Resumes on the next run. Dry run is the default |

**Why per-utterance caching matters.** When the author changes one paragraph, only the utterances in that paragraph are re-synthesised (cents, not a whole chapter). Mastering and rendering re-run in seconds. The ledger then marks the part stale (§7.5).

### 4.3 Audio mastering

- **Chain per part:** high-pass at 70 Hz, then concatenate utterances with the pause table, then two-pass `loudnorm=I=-14:TP=-1.5:LRA=11:linear=true` using the measured values, then resample to 48 kHz.
- **Why −14 LUFS:** YouTube's playback reference. YouTube only turns loud content down and never turns it up, so −14 keeps narration as loud as music videos.
- **Outputs:** keep `part.flac` as the archive and `part.m4a` (AAC 192k, 48 kHz) as the render input.
- **Music:** no music under narration. A 3–5 s sting in the intro and a quiet bed under the 20 s end screen are fine, mixed *before* loudnorm.

### 4.4 Video render (fast and cheap)

```
ffmpeg -y -loop 1 -framerate 1 -i card.png -i part.m4a \
  -c:v libx264 -tune stillimage -preset veryfast -profile:v high -crf 20 -pix_fmt yuv420p -r 24 -g 240 \
  -c:a aac -b:a 192k -ar 48000 -ac 2 -shortest -movflags +faststart part.mp4
```

- Render speed: about 10–20 s per 10-minute part on Apple silicon (estimate). Book I's 30 parts take a few minutes. You can also stream-copy (`-c:a copy`) if `part.m4a` is already AAC 48 kHz.
- **Card:** a 1920×1080 layout with the book art (`books/N/cover_art.png`) on the left. On the right: series title, "I knyga · Vilko tremtis", the chapter number and title, and the Quarto part name ("Nuosmukis"). A thin progress strip ("4 / 30") is optional. Render it with Pillow and a font that has full Lithuanian glyph coverage (DejaVu Serif is already used for the PDF).
- **Thumbnail:** the same template at 1280×720 with the chapter number very large and the title in 3–4 words. Per-book accent colour. Custom thumbnails need a phone-verified channel.
- **Intro, at most 8 s:** sting plus a spoken line, "Geležinio Vilko Saga. Pirma knyga: Vilko tremtis. Trečias skyrius: Gintaro sapnas." The first part of each Quarto section also announces "Antroji dalis: Pabėgimas". Part titles are never separate videos.
- **Outro and end screen, last 20 s:** a spoken line ("Kitas skyrius – rytoj…"), a quiet bed, and a card layout with empty space for two end-screen elements (next video and playlist). The Data API cannot set end screens. Add them in Studio with "Import from video" (about 15 s per video), or skip them.
- **Per-chapter art:** optional later. A static per-book card is the simplest robust choice. Waveform visualisers cost render time and add nothing.

### 4.5 Captions

The pipeline synthesises one sentence or utterance at a time, so it knows the exact start and end time of every utterance. It writes SRT and VTT straight from `script.jsonl` plus the measured WAV durations, splitting long sentences into cues of at most 2×42 characters proportionally by character count.

The caption text is the *canonical* text: real spelling with diacritics, never the respelling sent to an English engine. Upload one track per language (`captions.insert`, `language=lt` or `en`, `name="Lietuvių"` / `"English"`). No Whisper is needed. When an engine returns word timestamps (ElevenLabs "with timestamps", Azure word-boundary events), the code can use them for finer cues.

### 4.6 Directory layout

```
audiobook/
  wolfaudio/                 # package: cli.py manifest.py extract.py translate.py markup.py lexicon.py
                             #          engines/{elevenlabs,gemini,google_tts,azure,chatterbox,kokoro}.py
                             #          master.py captions.py render.py publish.py schedule.py ledger.py
  config/series.yaml         # series names (lt/en), templates, release time/tz, voices per lang, quota budget
  manifests/book1.yaml       # committed
  voices/{lt,en}.yaml        # engine + voice IDs per role (narrator, Vytautas, Birutė, Jogaila, Henė, …)
  overrides/b1/<chapter>.yaml# speaker/emotion/number fixes, human-edited
  text/b1/en/<chapter>.md    # committed English translation (reviewable diff when the LT source changes)
  state/uploads.json         # committed ledger (video IDs are not secrets)
  build/                     # gitignored
    cache/tts/<sha>.wav
    b1/lt/<part_key>/{script.jsonl,part.flac,part.m4a,part.srt,part.vtt,qc.json,card.png,thumb.jpg,part.mp4,meta.json}
    b1/en/<part_key>/…
  legacy/                    # (or delete) the old scripts, untouched, for reference
~/.config/wolf-saga/         # OUTSIDE the repo, chmod 600: youtube_client_secret.json, youtube_token.json, .env with API keys
```

---

## 5. Voice engine selection and pronunciation plan

### 5.1 Inventory (current)

| | Lithuanian | English |
|---|---|---|
| Text | none (the pipeline always translates to English) | Gemini 2.5 Flash translate plus "editor" rewrite, diacritics stripped |
| TTS | none | Chatterbox-Turbo (ResembleAI, MIT, English-only), zero-shot cloning from `reference_voice.wav` / `voices/*.wav` (none present), tags `[sigh]`, `[laugh]` and others |
| Characters | — | `voice_map` with 28 hard-coded names. Voices were meant to come from YouTube clips or ElevenLabs samples (both problematic, see #7 and #36) |
| Captions | — | faster-whisper turbo, `language=en` |

### 5.2 Engines researched (Oct 2026; vendors publish language lists, so verify before you commit)

| Engine | Lithuanian? | Emotion / style control | Multi-voice dialogue | Pronunciation control | Licence for YouTube (monetised) | Approx. cost, Book I (~185k chars lt) | Where it runs |
|---|---|---|---|---|---|---|---|
| **ElevenLabs Eleven v3** | **Yes** (74-language list includes Lithuanian) | Inline free-text **audio tags** (`[whispers]`, `[angry]`, `[sighs]`, `[crying]`…), the strongest of the group | Text-to-Dialogue API, voice library, voice design | **Inline IPA `/…/`** and **pronunciation dictionaries with IPA phonemes** (phoneme rules honoured on v3 and Flash v2 only) | Commercial use on paid plans (free tier needs attribution) | Roughly 1 credit per character, so ~185k credits plus ~50 % retakes: a Pro-tier month, order of US$100 (verify current pricing) | API |
| ElevenLabs Multilingual v2 / Flash v2.5 | **No** | — | — | — | — | — | API |
| **Gemini TTS** (`gemini-3.8-flash-tts`) | **Yes** (listed for 3.8 Flash TTS, *not* Flash-Lite) | Natural-language `style` per turn ("whispered urgently") plus inline tags `<sigh>`, `<laugh>`, `<long pause>` | 2 speakers per request with prebuilt voices. Custom (designed or replicated) voices are synthesised turn by turn | No phoneme or SSML lexicon documented, so respelling or accent marks only | Paid API output usable commercially (check Gemini API terms) | Low: order of a few US$ per book (verify 3.8 pricing) | API |
| Google Cloud TTS **Chirp 3: HD** | **Yes** (lt-LT, GA) | Limited. Natural prosody, little explicit emotion | One voice per request, about 30 voice personas | Limited (verify custom pronunciations for lt-LT) | Commercial OK | About US$30 per 1M chars, so ~US$6 | API |
| **Azure Neural** lt-LT `OnaNeural`, `LeonasNeural` | **Yes** | **No styles or roles** for lt-LT. SSML prosody and breaks only | One voice per SSML `<voice>` element, 2 voices only | `<phoneme>` IPA **not documented for lt-LT** (absent from the phonetic-sets page). `<sub alias>` respelling works | Commercial OK | About US$15–16 per 1M chars, so ~US$3 | API |
| OpenAI `gpt-4o-mini-tts` | Supports Whisper's languages, which include Lithuanian (voices tuned for English, so expect an accent; verify) | Natural-language `instructions` | Several preset voices, one per request | None (respelling only) | Commercial OK, disclose AI voice | Low, a few US$ | API |
| Chatterbox-Turbo / Multilingual (current) | **No** (the multilingual 23-language list has no Lithuanian) | Paralinguistic tags, exaggeration and CFG settings, reference cloning | Clone per character | Respelling only | MIT. Outputs carry a Perth watermark | Free (GPU or CPU time) | Local |
| **Kokoro-82M** (`af_heart`, used locally by the author) | **No** (EN-US, EN-GB, es, fr, hi, it, ja, pt, zh) | **None.** No emotion control, no cloning | Preset voices only | espeak-based, respelling only | Apache-2.0 | Free, very fast on CPU | Local |
| XTTS-v2 | No (16 languages) | Cloning | Clone per character | — | Coqui CPML (non-commercial) | Free | Local |
| Qwen3-TTS | No (10 languages) | Description and cloning | — | — | Apache-2.0 | Free | Local |
| Fish Audio S2 | Claims 80+ languages; Lithuanian unconfirmed | Inline instructions | Cloning | — | Research licence on open weights (commercial use needs a separate licence) | — | Local / API |
| F5-TTS | No Lithuanian evaluation | Cloning | — | — | CC-BY-NC weights, so no monetisation | Free | Local |
| Meta MMS-TTS `lit` (VITS) | Yes (listed as `facebook/mms-tts-lit`; I could not open the model page, so verify) | None, flat | One voice | Character-based | CC-BY-NC-4.0, so no monetisation | Free | Local |
| LIEPA synthesiser (VU) / VU VITS research models | Yes | None | Few voices | Rule-based | Check per model | Free (compile from source) | Local |

**Conclusion on Lithuanian.** Today only three options combine real Lithuanian, controllable emotion and character voices: **ElevenLabs v3** (audio tags plus IPA plus dialogue), **Gemini 3.8 Flash TTS** (style prompts plus tags plus designed voices) and, much flatter, Chirp 3 HD and Azure. No open model gives expressive Lithuanian.

### 5.3 Recommendation (provisional, to be confirmed by the A/B test in §5.6)

| | Primary | Fallback | Draft / proof-listening |
|---|---|---|---|
| **lt** | **ElevenLabs Eleven v3**: best emotion (tags), dialogue API, IPA pronunciation dictionaries for the 351 lexicon entries | **Gemini 3.8 Flash TTS**: style per turn, designed character voices, far cheaper. Also the cost-saving option if v3 retakes get expensive | Chirp 3 HD lt-LT (stable, cheap, flat) |
| **en** | **Gemini 3.8 Flash TTS** (a different model from lt, as the author asked): natural-language direction suits dark-fantasy grief, rage and whisper; voice design for Vytautas, Birutė, Jogaila and Henė; cheap | **Chatterbox-Turbo** (local, MIT, already integrated, tags, cloning from *consented* or designed references) | **Kokoro `af_heart`** (local, instant): proof-listening of translations and bonus shorts. Not for final dialogue (no emotion, no character range) |

If the A/B test shows v3 English clearly ahead, swap en to v3 and keep Gemini as the en fallback. The adapter layer makes the swap a config change in `voices/en.yaml`.

**Voice cast (both languages):** Narrator (a mature, low male or female voice: open question), Vytautas, Kęstutis, Birutė (also the first-person frame in `00_pradzia`), Jogaila, Henė, Skirgaila, the divine and Amber Queen voice (italic `*„…“*` passages, possibly the narrator with a processed effect), plus 2–3 generic voices (envoy, guard, Order knight). Keep a single narrator for attributions. Character voices only voice dialogue text, never narration.

### 5.4 Emotion markup layer (engine-neutral)

**Step A, rule-based (deterministic), which suits the book's conventions:**

- **Dialogue:** a line starting with `— ` is dialogue. Inside it, a further ` — ` switches to the narrator's attribution and a third ` — ` switches back. Example: `— Praurime, pasigailėk... — norėjo surėkti ji, bet …` gives Birutė "Praurime, pasigailėk..." followed by the narrator "norėjo surėkti ji, bet…".
- **Divine and inner voice:** italic `*„…“*` gets `voice=divine` or `voice=inner`.
- **Scene breaks:** `* * *` and `---` become pauses. `# Heading` becomes the title announcement, not body text.
- **Counts:** 227 line-initial dialogue dashes in Book I (Ch. 2 alone has 38). Inner ` — ` is also used as a parenthetical in narration, so only line-initial dashes open dialogue.

**Step B, LLM-assisted:** for each dialogue utterance, propose the `speaker` (from a closed cast list in `voices/*.yaml`) and the `emotion` and `intensity`. The LLM **must not touch the text**. A validator rejects any record whose text differs from Step A.

**Step C, human overrides:** `overrides/b1/<chapter>.yaml` keyed by utterance id. These win over Step B and survive regeneration.

```jsonc
// script.jsonl — one record per utterance
{"id":"b1/03_gintaro_sapnas#041","kind":"dialogue","speaker":"birute","emotion":"anguish","intensity":3,
 "text":"Praurime, pasigailėk...","pause_after_ms":350,"lang":"lt"}
{"id":"b1/03_gintaro_sapnas#042","kind":"narration","speaker":"narrator","emotion":"neutral","intensity":1,
 "text":"norėjo surėkti ji, bet jos gerklė buvo užpildyta tiršto, sūraus jūros vandens.","pause_after_ms":600}
{"id":"b1/03_gintaro_sapnas#047","kind":"divine","speaker":"amber_queen","emotion":"solemn","intensity":2,
 "text":"Uždaryk akis, Birute. …","pause_after_ms":900}
```

The emotion vocabulary is a closed set: `neutral, tender, solemn, awe, fear, anguish, grief, rage, cold, contempt, sly, exhausted, whisper, shout`, with intensity 0–3.

**Renderers (one small function per engine):**

| Engine | How a record is rendered |
|---|---|
| ElevenLabs v3 | Maps to an audio tag prefix (`[whispers]`, `[angry]`, `[sorrowful]`) plus `voice_id`. Consecutive dialogue turns go to Text-to-Dialogue |
| Gemini | `style="grief-stricken, barely holding back tears"` per turn, inline `<long pause>`, designed voice per speaker |
| Azure / Chirp | SSML `<prosody rate pitch>` and `<break>` (no styles for lt) |
| Chatterbox | `exaggeration` / `cfg_weight` per intensity, plus `[sigh]` and other tags |

### 5.5 Pronunciation plan

The lexicon has 351 entries, 545 inflected `variants`, `ascii` forms on 168 entries, and **73 entries flagged `verify:true`**.

1. **Never strip diacritics.** Fix the English translation prompt: "Keep every Lithuanian personal name, place name and term in its original Lithuanian spelling with diacritics. Translate common nouns only." Use the `ascii` forms only to *match* legacy text, never to produce it.
2. **One matcher, many outputs** (`wolfaudio/lexicon.py`): build a case-sensitive, Unicode word-boundary regex from `text`, `variants` and `ascii`, longest match first (so *Šešėlių Pardavėjas* wins over *Pardavėjas*). Run it on the script text *after* markup. It returns spans, not rewritten text, so captions keep the canonical spelling.
3. **Per-engine rendering of those spans:**

   | Engine | lt voice | en voice |
   |---|---|---|
   | ElevenLabs v3 | Usually nothing: the Lithuanian voice reads Lithuanian. Use a pronunciation dictionary (IPA phoneme rules) only for entries whose stress the A/B test shows it gets wrong, and for `category: foreign` | Upload a generated PLS dictionary (IPA from `ipa`). If a dictionary rule fails, fall back to inline `/ipa/` |
   | Gemini, OpenAI, Chatterbox, Kokoro | Nothing (Gemini) / n/a | Substitute a respelling built from `respelling_en`, normalised for TTS: hyphens removed, CAPS lowered, stress shown by spelling (for example `VEE-tow-tahs` → `Veetowtahs`). Test that the engine does not spell CAPS out as letters |
   | Azure / Chirp | `<sub alias>` with accent-marked forms from §3 of the guide (`Kęstùtis`). Test whether the voice honours the accent marks | `<phoneme alphabet="ipa">` for en-US voices |

4. **Stress-moving names** (Kęstutis, Birutė, Eglė, Jonas, Kaunas, Palanga, Trakai): for a Lithuanian voice, only the case forms named in `stress_notes` need overrides. Generate dictionary rules per inflected form.
5. **`verify:true` rows:** the build prints a report of every occurrence in the parts being rendered. Before a part ships, either a native speaker confirms the row, or the engine's default is accepted explicitly in `overrides/`.
6. **QA:** produce a pronunciation reel per engine and voice: each lexicon entry in a carrier sentence ("Vardas: Výtautas."), about 351 × 3 s, so roughly 18 minutes. The author listens once and logs failures into a small `pronunciation_overrides.yaml` (engine, voice and entry give the fix). The reel doubles as a bonus video ("Kaip tarti sagos vardus").

### 5.6 A/B listening test (before committing to an engine)

- **Excerpts:** 60–90 s each, rendered by every candidate engine (lt: v3, Gemini 3.8, Chirp 3 HD; en: v3, Gemini 3.8, Chatterbox-Turbo, Kokoro as a baseline), all from the **same `script.jsonl`**:
  1. Ch. 3 *Gintaro sapnas*: Birutė's vision and the Amber Queen's italic voice (lines ~19–23), plus her blessing (author picks about 90 s).
  2. Ch. 9 *Paskutinė giesmė*: Kęstutis's death in the Krėva cell (lines ~27–49).
  3. Ch. 24 *Pasirinkimas*: the night of fire in the storehouse (lines ~3–25).
  4. Ch. 2 *Vilko perspėjimas*: a dialogue-dense exchange (character separation).
  5. A name-dense paragraph (pronunciation stress test, for example from `00_pradzia`).
- **Procedure:** loudness-match every clip to −16 LUFS, randomise labels (A/B/C…), and hide engine names (the `ab-test` command writes `key.json` separately). The author plus, ideally, two native listeners score 1–5 on Lithuanian naturalness, emotional fit, character distinctness, name pronunciation (count errors against the lexicon) and artefacts (glitches, skipped or repeated words).
- **Decision rule:** highest mean wins. **Veto** any engine with a skipped or repeated word, or more than 2 name errors per minute.
- **Cost:** about 5 excerpts × ~1,200 characters × 7 renders, roughly 40k characters. That is within free or entry tiers. Needs the author's approval and keys; agents must not run it unprompted.

---

## 6. Segmenting: what is a "small part"?

**Rule (Plan A, recommended):** one chapter = one part = one day.

- A chapter of 4 minutes or less **merges forward** with the next chapter in the same Quarto section.
- The two front-matter pieces (`prologue` + `00_pradzia`, 6.8 min together) form Day 1.
- `index.qmd` (Pratarmė) becomes a Day 0 trailer. `copyright.qmd` and `sources.qmd` are not narrated; their content goes into descriptions.

This gives 30 daily parts of about 5–12 minutes, a month-long habit, and a 1:1 mapping to chapters. Inserting a chapter later (28b) adds one part and touches nothing else.

**Plan B (only if mid-roll ads matter):** greedy merge to at least 8 minutes within each section (YouTube allows mid-rolls from 8 min, and you need YPP eligibility first). That gives 19 parts: `prologue+00`, `01`, `02`, `03`, `04+05`, `06+07`, `08`, `09+10`, `11+12`, `13+14`, `15+16`, `17`, `18+19`, `20+21`, `22+23`, `24+25`, `26+27`, `28+28b`, `29+30`. Monetisation is not available yet, so stay with Plan A and revisit for Book II.

Long chapters do not need splitting: the longest today is Ch. 3 at about 11.3 min. Split only above about 20 min, at a scene break.

**Estimates.** Words come from the current `.qmd` files (Markdown and attributes stripped) at 140 words/min. Book I has 27,040 words (excluding `index`, `copyright` and `sources`), about 3.2 h of narration, and about 3.4 h with `28b` at an estimated 1,400 words (the revision plan says 1,200–1,600). The video column adds about 0.6 min per part for intro, outro and end screen. Re-estimate after the R1–R6 revisions land: `wolfaudio manifest --book 1 --estimate`.

---

## 7. Publishing plan

### 7.1 Auth and secrets

- **OAuth "installed app" flow** (`google-auth-oauthlib`), scopes `youtube.upload` and `youtube.force-ssl` (needed for captions and playlists).
- Store client secret and token in `~/.config/wolf-saga/` with chmod 600, never in the repo. Add `client_secret*.json`, `*token*.json` and `.env*` to `.gitignore`.
- **Publish the OAuth consent screen ("In production").** Refresh tokens of apps left in "Testing" expire after 7 days, which would silently break any scheduled run. An unverified app is fine for the author's own channel; Google shows a warning screen once.
- Check whether the API project needs the YouTube API compliance audit. The current `videos.insert` docs say unverified projects are *not* restricted to private, but older guidance locked their uploads to private. Do one test upload (private, then delete) before the batch.

### 7.2 Quota (verified against the current quota table)

| Call | Units | Per part |
|---|---|---|
| `videos.insert` | **1, in a separate "Video Uploads" bucket, 100 calls/day** (older docs said 1,600) | 1 |
| `captions.insert` | 400 | 400 |
| `thumbnails.set` | 50 | 50 |
| `playlistItems.insert` | 50 | 100 (book playlist + series master) |
| `videos.update` (prev/next relink, localisations) | 50 | 50 |
| `videos.list` / `playlistItems.list` | 1 | ~2 |
| **Total** | | **~600 units → about 16 parts/day** on the default 10,000 |

Book I in one language (30 parts) fits in **2 days of uploading**; both languages in 4. Under the old 1,600-unit insert cost it would be about 2,200 units per part, or 4 per day. The publisher reads the budget from config, stops cleanly at the limit (quota resets at midnight Pacific) and resumes. The ledger makes this safe.

### 7.3 Scheduled batch (the core idea)

- **Upload settings:** each part is uploaded with `status.privacyStatus=private` and `status.publishAt=<UTC instant>`, which the schedule computes from the local release time with `zoneinfo`. Vilnius changes from EEST to EET on the last Sunday of October, so store local time and time zone, never a fixed offset.
- **Playlists:** the video is added to its book and language playlist and to the series master at once. Scheduled-private items stay hidden until they go public.
- **Rolling window while Book I is being revised:** `publish --window 10` keeps the next 10 days uploaded and scheduled. Run it weekly, by hand or with a weekly launchd job. Chapters revised before their slot are re-rendered and replaced (§7.5). Once the book text is frozen, run `publish` without `--window` to schedule the remainder in one go.
- **Relink pass:** after each batch, a relink pass fills "← Ankstesnis / Kitas →" links in descriptions (`videos.update`), now that the video IDs are known.

### 7.4 Automation options

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **One-off scheduled batch with `publishAt`** (rolling window during revisions) | YouTube does the daily release, reliably, with the laptop closed. A few runs per book. Easy to audit in Studio | Late edits need replace logic (§7.5). Needs 2–4 quota days per book | **Recommended** |
| Daily local cron / launchd that uploads that day's part as public | Edits land until the last minute | The Mac must be awake and online every day at release time. A missed day or token expiry means a missed release. No buffer | Not recommended (keep only a *weekly* reconcile job) |
| GitHub Actions with stored secrets | No local machine needed | TTS needs API keys or a GPU. Video files (about 50–150 MB each) aren't in git, so you'd need artifact storage. YouTube refresh token stored in CI. Long jobs | Not worth it. Keep CI for checks only (manifest consistency, unit tests) |

**Regenerating only revised chapters:** `wolfaudio build --book 1 --lang lt` recomputes hashes. Only utterances whose rendered text changed are synthesised; only the affected parts are re-mastered and re-rendered. `status` lists stale parts.

### 7.5 Ledger: `audiobook/state/uploads.json`

```jsonc
{
  "version": 1,
  "playlists": {
    "series/lt": "PLxxxxxxxx", "series/en": "PLyyyyyyyy",
    "b1/lt": "PL…", "b1/en": "PL…", "bonus/lt": "PL…"
  },
  "parts": {
    "b1/lt/03_gintaro_sapnas": {
      "chapters": ["1/03_gintaro_sapnas.qmd"],
      "order": 4,
      "content_hash": "sha256:…",            // hash of the master inputs (script + voices + master settings)
      "video_hash":   "sha256:…",            // hash of the part.mp4 actually uploaded
      "audio": "build/b1/lt/03_gintaro_sapnas/part.flac",
      "video": "build/b1/lt/03_gintaro_sapnas/part.mp4",
      "youtube_id": "AbCdEfGhIjk",
      "playlist_items": {"b1/lt": "UExf…", "series/lt": "UExg…"},
      "caption_ids": {"lt": "…"},
      "thumbnail_set": true,
      "title": "Geležinio Vilko Saga · I knyga · 3 skyrius: Gintaro sapnas",
      "publish_at": "2026-11-05T16:00:00Z",
      "status": "scheduled",                 // planned | uploaded | scheduled | public | stale | replaced
      "replaced_by": null,
      "history": [{"at": "2026-10-28T19:02:11Z", "action": "insert", "video_hash": "sha256:…"}]
    }
  },
  "quota": {"day": "2026-10-28", "pacific_units_used": 3550}
}
```

**When a part's `content_hash` differs from what was uploaded:**

| Video status | Action |
|---|---|
| `scheduled` (never public) | Delete and re-upload with the *same* `publishAt` and playlist position (`videos.delete` 50 + insert + captions + thumb, about 550 units). Seamless |
| `public`, metadata-only change | `videos.update` / `captions.update` |
| `public`, audio change | Upload the new video, swap the playlist item, set the old one to unlisted with "Atnaujinta versija → link" in its description, and mark the ledger `replaced`. YouTube does not allow replacing a video's file. Or flag it and leave it, which the author decides per case (`publish --replace-public` is opt-in) |

### 7.6 Playlists

| Playlist | Lithuanian title | Contents |
|---|---|---|
| Per book and language | "Geležinio Vilko Saga · I knyga: Vilko tremtis (garsinė knyga)" | Parts in order |
| Per book and language | "The Iron Wolf Saga · Book I: The Wolf's Exile (audiobook)" (English series name is an open question) | Parts in order |
| Series master per language | "Geležinio Vilko Saga · Visos knygos" | Every book's parts in order. Books are appended as they release |
| Bonus per language | "Sagos pasaulis" | Pronunciation reel, Atlas tours, legends, character shorts. Kept out of the main playlists so binge listening isn't interrupted |

### 7.7 Metadata templates (in `config/series.yaml`, parameterised by book, part and language)

**Titles (100 characters maximum; a validator truncates the title, never the series prefix):**

- lt: `Geležinio Vilko Saga · {book_roman} knyga · {chapter_label}: {title}`. Here `chapter_label` is `3 skyrius`, or `4–5 skyriai` for a merged part, or `Prologas ir Pradžia`. Example: **"Geležinio Vilko Saga · I knyga · 3 skyrius: Gintaro sapnas"**.
- en: `The Iron Wolf Saga · Book {book_roman} · Chapter {n}: {title_en}`.
- **Title case:** the `.qmd` headings are title-cased ("Gintaro Sapnas"). The template uses Lithuanian sentence case ("Gintaro sapnas"), stored per part in the manifest (`title_lt`) so no automatic lower-casing breaks proper nouns ("Kelionė į Vilnių").

**Description (lt). English mirrors it, and is also supplied as `localizations.en` on the Lithuanian video so international viewers see English metadata:**

```
{blurb_lt}                                   ← 1–2 sentence hook, from manifest (no spoilers beyond this part)

▶ Klausykite nuo pradžių: {playlist_url}
← Ankstesnis: {prev_url}   |   Kitas →: {next_url} (pasirodys {next_date})

📖 Skaityti tekstą: https://algiras.github.io/wolf-saga/{chapter_html_path}
🗺 Sagos pasaulis (wiki): https://algiras.github.io/wolf-saga/wiki/
🔊 Kaip tarti vardus: {pronunciation_video_url}
🤖 llms.txt: https://algiras.github.io/wolf-saga/llms.txt

{chapters_block}                             ← only for merged parts: 0:00 Įžanga / 0:08 4 skyrius: … / 3:20 5 skyrius: …

Įgarsinta dirbtinio intelekto balsu ({engine}). Tekstas: Algimantas Krasauskas.
Licencija: CC BY-NC-SA 4.0 — https://creativecommons.org/licenses/by-nc-sa/4.0/deed.lt
© 2025–2026 Algimantas Krasauskas

#GeležinioVilkoSaga #GarsinėKnyga #LietuviškaFantastika
```

- Check the `chapter_html_path` URLs against the rendered site (Quarto writes `books/_book/1/03_gintaro_sapnas.html`).
- YouTube shows only the first three hashtags above the title.

**Other API fields:**

| Field | Value | Why |
|---|---|---|
| `snippet.tags` | ≤ 500 chars, lt + en: saga name, *garsinė knyga*, audiobook, dark fantasy, Lithuania, Vytautas, Kęstutis, Birutė, Jogaila, Teutonic Order, Baltic mythology, plus chapter-specific names from the lexicon hits | |
| `categoryId` | `24` (Entertainment) | |
| `defaultLanguage` / `defaultAudioLanguage` | `lt` (or `en`) | |
| `status.selfDeclaredMadeForKids` | `false` | Violence, dark themes |
| `status.license` | **`youtube` (standard)**, not `creativeCommon` | YouTube's CC option is **CC BY**, which would grant commercial reuse and contradict NC-SA. State CC BY-NC-SA in the description instead |
| `status.embeddable` | `true` | |
| `status.containsSyntheticMedia` | `false` for designed or library AI voices narrating fiction, which is not "realistic altered content" | **Must be `true`** if any voice is cloned from a real person. The description always discloses AI narration. Final call is the author's (open question) |

### 7.8 Release calendar (multi-book)

- **Config:** `schedule.yaml` holds `{book, lang, start_date | after: <book>/<lang> + gap_days, time, tz, weekdays: all}`. Bonus items are pinned to dates or weekdays on the bonus playlist (for example Sundays) and never shift the main sequence. Bonus content stays off the main chain because it would break binge order.
- **Chaining:** Book II's `start = last(Book I) + gap_days` (default 14, with bonus shorts in the gap). Books II–IV exist only as outlines today, so in practice the gap will be months. The scheduler just needs the rule.
- **Two languages:** run them as separate chains. For example, lt daily at 18:00 Europe/Vilnius, with en either starting after lt ends or daily at 18:00 America/New_York (open question).
- **Compilation:** at the end of each book, a full-book compilation video built by concatenating the mastered parts, with chapter timestamps generated from part durations. It is cheap, good for search and serves binge listeners. It can replace the existing English full-book video (`7FTLqyPXSr0`), which predates the revisions: unlist it once the new English series exists, or keep it with a note.

---

## 8. Book I release calendar (Plan A, first concrete instance)

Release time: 18:00 Europe/Vilnius (placeholder). Date = Day 1 + (n−1). The "Est. narration" column is word count ÷ 140; video adds about 0.6 min.

| Day | Date | Part title (lt) | Source chapters | Est. narration (min) | Est. video (min) |
|---|---|---|---|---|---|
| 0 | Day 1 − 3 | Trailer: Pratarmė (bonus playlist + pinned) | `index.qmd` + series teaser | 1.9 | 2.5 |
| 1 | Day 1 | Prologas: Gintaro ašaros · Pradžia | `1/prologue.qmd`, `1/00_pradzia.qmd` | 6.8 | 7.4 |
| 2 | Day 1 + 1 | 1 skyrius: Senasis šernas *(announces "Pirmoji dalis: Nuosmukis")* | `1/01_senasis_sernas.qmd` | 10.7 | 11.3 |
| 3 | Day 1 + 2 | 2 skyrius: Vilko perspėjimas | `1/02_vilko_perspejimas.qmd` | 8.7 | 9.3 |
| 4 | Day 1 + 3 | 3 skyrius: Gintaro sapnas | `1/03_gintaro_sapnas.qmd` | 11.3 | 11.9 |
| 5 | Day 1 + 4 | 4–5 skyriai: Kelionė į Vilnių · Dvigubas veidas | `1/04_kelione_i_vilniu.qmd`, `1/05_dvigubas_veidas.qmd` | 9.9 | 10.5 |
| 6 | Day 1 + 5 | 6 skyrius: Geležiniai vartai | `1/06_geleziniai_vartai.qmd` | 6.9 | 7.5 |
| 7 | Day 1 + 6 | 7–8 skyriai: Tylos puota · Krėvos požemiai | `1/07_tylos_puota.qmd`, `1/08_krevos_pozemiai.qmd` | 11.9 | 12.5 |
| 8 | Day 1 + 7 | 9 skyrius: Paskutinė giesmė | `1/09_paskutine_giesme.qmd` | 5.9 | 6.5 |
| 9 | Day 1 + 8 | 10 skyrius: Šaltas rytas | `1/10_saltas_rytas.qmd` | 5.2 | 5.8 |
| 10 | Day 1 + 9 | 11 skyrius: Našlė *(announces "Antroji dalis: Pabėgimas")* | `1/11_nasle.qmd` | 5.7 | 6.3 |
| 11 | Day 1 + 10 | 12 skyrius: Gedulo skraistė | `1/12_gedulo_skraiste.qmd` | 4.9 | 5.5 |
| 12 | Day 1 + 11 | 13 skyrius: Keitimas | `1/13_keitimas.qmd` | 5.5 | 6.1 |
| 13 | Day 1 + 12 | 14 skyrius: Šešėlis naktyje | `1/14_seselis_naktyje.qmd` | 5.5 | 6.1 |
| 14 | Day 1 + 13 | 15 skyrius: Pabėgimas | `1/15_pabegimas.qmd` | 6.1 | 6.7 |
| 15 | Day 1 + 14 | 16 skyrius: Pelkės vaikai | `1/16_pelkes_vaikai.qmd` | 4.8 | 5.4 |
| 16 | Day 1 + 15 | 17 skyrius: Pasienis | `1/17_pasienis.qmd` | 8.4 | 9.0 |
| 17 | Day 1 + 16 | 18 skyrius: Geležinis magistras | `1/18_gelezinis_magistras.qmd` | 4.8 | 5.4 |
| 18 | Day 1 + 17 | 19 skyrius: Velnio sandėris | `1/19_velnio_sanderis.qmd` | 5.4 | 6.0 |
| 19 | Day 1 + 18 | 20 skyrius: Svetimi dievai *(announces "Trečioji dalis: Karas ir tvarka")* | `1/20_svetimi_dieviai.qmd` | 5.4 | 6.0 |
| 20 | Day 1 + 19 | 21 skyrius: Pirmoji kova | `1/21_pirmoji_kova.qmd` | 5.0 | 5.6 |
| 21 | Day 1 + 20 | 22 skyrius: Vilniaus apgultis I | `1/22_vilniaus_apgultis_i.qmd` | 5.2 | 5.8 |
| 22 | Day 1 + 21 | 23 skyrius: Ugnis ir pelenai | `1/23_ugnis_ir_pelenai.qmd` | 5.2 | 5.8 |
| 23 | Day 1 + 22 | 24 skyrius: Pasirinkimas | `1/24_pasirinkimas.qmd` | 4.2 | 4.8 |
| 24 | Day 1 + 23 | 25 skyrius: Išdavikų išdavikas | `1/25_isdaviku_isdavikas.qmd` | 4.8 | 5.4 |
| 25 | Day 1 + 24 | 26 skyrius: Susitikimas peleninėje | `1/26_susitikimas_pelenineje.qmd` | 5.4 | 6.0 |
| 26 | Day 1 + 25 | 27 skyrius: Gintaro auka | `1/27_gintaro_auka.qmd` | 5.1 | 5.7 |
| 27 | Day 1 + 26 | 28 skyrius: Nauja tvarka | `1/28_nauja_tvarka.qmd` | 5.1 | 5.7 |
| 28 | Day 1 + 27 | 28b skyrius: Krėvos sutartis *(label depends on renumbering, see Q8)* | `1/28b_krevos_sutartis.qmd` *(not yet written; 1,200–1,600 words planned)* | ~10.0 | ~10.6 |
| 29 | Day 1 + 28 | 29 skyrius: Krikštas | `1/29_krikstas.qmd` | 6.6 | 7.2 |
| 30 | Day 1 + 29 | 30 skyrius: Epilogas | `1/30_epilogas.qmd` | 5.7 | 6.3 |
| 31 | Day 1 + 30 | Visa knyga (compilation, chapter timestamps) | all of the above | ~196 | ~197 |

**Totals:** 30 daily parts, about 196 min (3.3 h) of narration. Bonus slots (separate playlist), for example Sundays: the pronunciation reel (from §5.5), "Kas yra kas" character shorts, an Atlas tour of Trakai, Vilnius and Krėva, and the legend of Birutė. The calendar must be regenerated after the R1–R6 revisions change word counts, and if 28b is renumbered.

---

## 9. Implementation tasks for follow-up agents

Every task runs **in dry-run, mock or local mode only**. Paid TTS calls, LLM calls and YouTube calls need the author's explicit go-ahead and keys. Each task ends with `python3 -m py_compile` and `pytest audiobook/tests -q` passing.

| # | Task | Files | Acceptance criteria | Tier |
|---|---|---|---|---|
| T1 | **Quarantine foreign and broken code** | Move every current script, `mcp.json`, `Dockerfile.mcp` and `audiobook_splash_screen.png` to `audiobook/legacy/` (or delete). Delete `download_voice_references.py`. Fix `.gitignore` (secrets, `build/`) | `grep -riE "miserable\|shadow of extremism\|reverse maven\|the-shadow-of-extremism" audiobook --exclude-dir=legacy` returns nothing. No active script references YouTube clip downloading | Haiku |
| T2 | **Package skeleton and CLI** | `audiobook/wolfaudio/{__init__,cli}.py`, `pyproject.toml` or pinned `requirements.txt`, `tests/` | `python -m wolfaudio --help` lists `manifest`, `build`, `ab-test`, `schedule`, `publish` and `status`. Dependencies pinned | Haiku |
| T3 | **Manifest** | `wolfaudio/manifest.py`, `manifests/book1.yaml`, `config/series.yaml` | Reads `_quarto.yml` and the headings. Applies the Plan A merge rule. Writes stable keys. `--check` fails if a chapter is unassigned or duplicated, or a file is missing. `--estimate` prints the §8 table. Adding a fake `28b` changes exactly one part | Sonnet |
| T4 | **Extract** | `wolfaudio/extract.py`, tests with fixtures from `books/1` | Strips YAML, divs and attributes. Maps italics to markers and scene breaks to pause markers. Flags digits and Roman numerals. Golden tests on `00_pradzia` and `03_gintaro_sapnas` | Sonnet |
| T5 | **Lexicon** | `wolfaudio/lexicon.py`, tests | Loads all 351 entries. Longest match first. Returns spans. Exports an ElevenLabs PLS (IPA), a respelling map and SSML. Lists `verify:true` hits per part. Test: *Šešėlių Pardavėjas* is matched before *Pardavėjas*; `Kestutis` (ascii) maps to *Kęstutis* | Sonnet |
| T6 | **Markup / script** | `wolfaudio/markup.py`, `overrides/b1/`, tests | Rule parser handles the `— … — attribution — …` pattern and italic divine voice. Pluggable LLM speaker and emotion step with a mock in tests. Fidelity validator rejects text drift. Overrides applied | Sonnet |
| T7 | **Engine adapters and TTS cache** | `wolfaudio/engines/*.py`, `wolfaudio/synth.py`, `voices/{lt,en}.yaml` | Common interface `synth(record) -> wav + meta`. Content-addressed cache. Retries, then hard failure. Mock engine for tests. Adapters for ElevenLabs v3, Gemini TTS, Google Chirp 3 HD, Azure, Chatterbox and Kokoro (real calls behind `--allow-network`) | Sonnet |
| T8 | **A/B harness** | `wolfaudio/abtest.py`, `ab_scenes.yaml` | Renders the §5.6 scenes per engine, loudness-matches them to −16 LUFS, writes blind `A.wav…` plus `key.json` and a scoring CSV. Dry run prints the character count and cost estimate | Haiku |
| T9 | **Master and captions** | `wolfaudio/master.py`, `wolfaudio/captions.py` | Pause table. Two-pass loudnorm to −14 LUFS / −1.5 dBTP at 48 kHz. SRT and VTT from segment timings with canonical text. `qc.json` gate as in §4.2. Unit test with synthetic tones | Sonnet |
| T10 | **Render** | `wolfaudio/render.py`, `assets/card_template/` | 1920×1080 card and 1280×720 thumbnail (under 2 MB) with Lithuanian glyphs. ffmpeg command from §4.4. `ffprobe` assertions. Renders a 10-minute part in under 60 s locally | Haiku |
| T11 | **Translate (en)** | `wolfaudio/translate.py`, `text/b1/en/` | Whole-chapter prompt that keeps diacritics and names. Hash cache. Paragraph-count check. Writes committed Markdown. Never caches failures | Sonnet |
| T12 | **Schedule** | `wolfaudio/schedule.py`, `config/schedule.yaml` | `zoneinfo` DST-correct UTC instants. Chains books with `after + gap_days`. Bonus slots on a separate playlist. Prints the §8 table. Tests across the late-October DST change | Haiku |
| T13 | **Publisher and ledger** | `wolfaudio/publish.py`, `wolfaudio/ledger.py`, `state/uploads.json` | OAuth installed-app flow with tokens in `~/.config/wolf-saga`. Dry run by default. `videos.insert` with private + `publishAt`, localisations, licence `youtube`, made-for-kids false, language fields. Captions, thumbnail, two playlist inserts, relink pass. Quota budget with clean stop and resume. Stale detection and replace rules (§7.5). Tests against a fake API client. A re-run makes zero calls when nothing has changed | Sonnet |
| T14 | **Status and verify** | `wolfaudio/status.py` | Table of parts: built, stale, uploaded, scheduled or public, compared against `videos.list` | Haiku |
| T15 | **CI checks** | `.github/workflows/render.yml` (new step, or a separate `audiobook-check.yml`) | Runs `wolfaudio manifest --check --book 1` and `pytest` with no network or secrets. No TTS or upload in CI | Haiku |
| T16 | **Pronunciation reel** | `wolfaudio/reel.py` | Carrier-sentence script for all entries, rendered per engine (mock in tests). Doubles as a bonus video part (`bonus/lt/pronunciation`) | Haiku |
| T17 | **Docs** | `audiobook/README.md`, `YOUTUBE_DESCRIPTION.md` (becomes the template source), `llms.txt` (licence, playlists) | Matches the new CLI. No mention of Ollama or other projects. Licence stated as CC BY-NC-SA 4.0 | Haiku |

**Suggested order:** T1 → T2 → T3 → T4 → T5 → T6 → T7 → T8 (author runs the A/B test and picks engines) → T9 → T10 → T12 → T13 → T14 → T15. T11, T16 and T17 can run in parallel once T2 exists.

---

## 10. Open questions for the author

1. **Language order:** Lithuanian first (recommended: it is the book's language and nothing Lithuanian exists yet), English first, or both in parallel? Same channel with separate playlists, or a separate English channel? YouTube's multi-language audio tracks (one video, lt and en audio) can only be added in Studio, not through the API. Is that worth the manual step?
2. **Narrator:** male or female, age and timbre? Should Birutė's first-person frame (`00_pradzia`) use her own voice rather than the narrator's?
3. **Full cast or narrator only?** A full cast (Vytautas, Kęstutis, Birutė, Jogaila, Henė, Skirgaila, the Amber Queen…) is more dramatic but costs more and needs more QA per chapter.
4. **Budget:** is a month of ElevenLabs Pro (order of US$100 for Book I in Lithuanian including retakes) acceptable, or should cost decide in favour of Gemini TTS?
5. **Release slot:** 18:00 Europe/Vilnius daily? Every day, or weekdays only? The English chain's time zone?
6. **Ship Book I now or after the R1–R6 revisions are frozen?** The rolling window handles late edits, but replacing *public* videos is clumsy.
7. **Already-public videos:** if a chapter changes after release, replace (new video, old one unlisted), update metadata only, or leave it?
8. **Chapter numbering:** will `28b` be renumbered (29 → 30, 30 → 31) before release? Titles show chapter numbers, and renaming after publication costs updates.
9. **English series name:** "The Iron Wolf Saga" (`llms.txt`) or "Wolf Saga" (old description)? And English chapter titles: who approves them?
10. **AI disclosure:** set `containsSyntheticMedia` = true anyway, for transparency, or only if a real person's voice is cloned? Do you want to use your own voice as a cloned narrator (consented)?
11. **The existing full English video** (`7FTLqyPXSr0`): keep, unlist, or replace with the new compilation at the end of the English run?
12. **Monetisation plans:** these decide Plan A (30 short parts) versus Plan B (19 parts of 8 min or more, mid-roll eligible).
13. **Pronunciation sign-off:** who confirms the 73 `verify:true` stress rows (a native-speaker reviewer, VLKK lookup)?

---

### Sources (web research, October 2026)

- ElevenLabs supported languages: https://elevenlabs.io/docs/help-center/other/what-languages-do-you-support
- ElevenLabs v3 prompting (inline IPA, audio tags): https://elevenlabs.io/docs/best-practices/prompting/eleven-v3
- ElevenLabs pronunciation dictionaries: https://elevenlabs.io/docs/eleven-api/guides/how-to/text-to-speech/pronunciation-dictionaries
- Gemini speech generation: https://ai.google.dev/gemini-api/docs/speech-generation
- Google Chirp 3 HD voices: https://docs.cloud.google.com/text-to-speech/docs/chirp3-hd
- Azure Speech language support: https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=tts
- Azure SSML phonetic sets: https://learn.microsoft.com/en-us/azure/ai-services/speech-service/speech-ssml-phonetic-sets
- Chatterbox Multilingual language list: https://huggingface.co/ResembleAI/chatterbox
- Kokoro voices: https://soniqo.audio/guides/kokoro
- LIEPA TTS: https://pypi.org/project/liepa-tts
- Qwen3-TTS: https://simonwillison.net/2026/Jan/22/qwen3-tts
- Fish Audio S2: https://fish.audio/s2/
- YouTube Data API quota costs: https://developers.google.com/youtube/v3/determine_quota_cost
- YouTube `videos.insert`: https://developers.google.com/youtube/v3/docs/videos/insert
- YouTube video resource (`publishAt`, `containsSyntheticMedia`, `license`): https://developers.google.com/youtube/v3/docs/videos
