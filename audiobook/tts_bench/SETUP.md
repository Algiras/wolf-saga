# Bench setup: what to install, download or get a key for

**Nothing in this list has been installed, downloaded or paid for.** The harness runs today with `macOS say` (English) and `edge-tts` (Lithuanian + English, free, unofficial; needs `--allow-online`); everything else skips cleanly until you approve it below.

Sizes are the Hub's reported weights where I could read them; the Hub's `usedStorage` figure counts every file ever pushed, so I only quote it as an upper bound. "(approx)" = estimate.

```
cd audiobook/tts_bench
python3 bench.py --list           # who is ready, who skips and why
python3 bench.py --dry-run --allow-paid --allow-online   # what would run, chars, rough cost
```

## 0. Harness itself (already satisfied on this Mac)

`numpy`, `scipy`, `soundfile`, `requests`, `ffmpeg`/`ffprobe` on PATH. No PyYAML needed. Python 3.14 works for the harness; for the heavy local models use a separate 3.11/3.12 virtualenv so that torch wheels exist (`python3.12 -m venv ~/.venvs/tts-bench`), then run `bench.py` from that venv.

Cost of one full bench pass per engine: Lithuanian passages = **6,223 characters**, English = **6,843 characters** (~13k total, ~13 minutes of audio per engine). Rendered utterances are cached in `cache/` by hash, so re-running costs nothing; changing text, voice or emotion re-renders only what changed. `--max-chars` (default 20,000 per engine) refuses to start a paid run above that.

## 1. API engines (no downloads, a key each; plugins read env vars only)

Approve a key, export it in the shell you run the bench from (never write it into a file in the repo), then add `--allow-paid`.

| Engine id | Env vars | Account step | Bench cost (13k chars both languages) | Pip packages |
|---|---|---|---|---|
| `elevenlabs` | `ELEVENLABS_API_KEY`; optional `ELEVENLABS_MODEL=eleven_v4` (default) or `eleven_v3`; `ELEVENLABS_VOICE_NARRATOR` / `_MALE_OLD` / `_MALE_YOUNG` / `_FEMALE` / `_DIVINE` / `_EXTRA` to override the placeholder voice ids | A paid plan is required for a commercial licence (Starter US$6/mo and up). A free key can run the bench (10k credits = the Lithuanian half only, no commercial rights) | list US$0.08/1k chars: **~US$1.0 per model** (v4 promo US$0.022/1k until 12 Oct 2026). Run it twice (v4, v3) = ~US$2 | none (uses `requests`) |
| `gemini` | `GEMINI_API_KEY`; optional `GEMINI_TTS_MODEL` (default `gemini-3.8-flash-tts`) | Google AI Studio key (paid tier for production use; the free tier is free of charge for these models per the pricing page) | ~13 min audio = ~US$0.03 | `google-genai` (1.62.0 is already installed here) |
| `azure` | `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION` (e.g. `westeurope`) | Azure Speech resource, F0 free tier = 0.5M neural chars/month | free (inside F0) | none |
| `google_chirp` | `GOOGLE_TTS_API_KEY` (Cloud API key restricted to the Text-to-Speech API) | Cloud project with TTS API enabled | ~US$0.4 `[est.]` | none |
| `openai` | `OPENAI_API_KEY`; optional `OPENAI_TTS_MODEL` | OpenAI API key | ~US$0.2 | none |

Voice ids in `voices.json` are placeholders. For Lithuanian you will want to choose ElevenLabs library voices with a Lithuanian accent (or design them) and override via the `ELEVENLABS_VOICE_<ROLE>` env vars; the Gemini names (`Charon`, `Algenib`, `Alnilam`, `Gacrux`, `Vindemiatrix`) are guesses to be replaced after listening. For Chirp 3 HD, which of the ~30 voice names exist for `lt-LT` was not confirmed: list them via the `voices.list` REST call and edit `voices.json`.

Not wired (no verified Lithuanian or no time): Inworld TTS-2 (`https://platform.inworld.ai/tts`, API key, ~US$25/1M chars), Hume Octave 2 (English only). Say if you want plugins; each is ~40 lines.

## 2. Local / self-hosted engines

### 2.1 OmniVoice 0.6B (Lithuanian + English, runs on the Mac)

```
python3.12 -m venv ~/.venvs/tts-bench && source ~/.venvs/tts-bench/bin/activate
pip install torch==2.8.0 torchaudio==2.8.0          # Apple-silicon line from the model card
pip install omnivoice soundfile scipy numpy requests
huggingface-cli download k2-fsa/OmniVoice           # ~3.3 GB (0.61B params, F32)
```

* Licence: code Apache-2.0, **model weights CC-BY-NC** (model card). Fine for a listening test, **not for a monetised channel**.
* Optional text normalisation on macOS needs `conda install -c conda-forge pynini`.
* For stable Lithuanian use cloning from a same-language reference clip: `export OMNIVOICE_REF_NARRATOR=/path/ref_lt.wav OMNIVOICE_REF_NARRATOR_TEXT="transcript of the clip"` (consenting speaker only). Without a reference the plugin uses voice design strings from `voices.json`, which the card says are trained on zh/en only.
* The plugin's `generate(language=...)` call is unverified against the package; it retries without the keyword if rejected.

### 2.2 Higgs TTS 3 4B (Lithuanian + English; needs a CUDA GPU server, not the Mac)

```
# on a rented Linux GPU box (>= 24 GB VRAM recommended, my estimate; weights are ~9.3 GB BF16)
docker pull lmsysorg/sglang-omni:dev
export HF_TOKEN=...            # per the model card
hf download bosonai/higgs-tts-3-4b                  # ~9.3 GB
sgl-omni serve --model-path bosonai/higgs-tts-3-4b --port 8000
# or vLLM-Omni: vllm-omni serve bosonai/higgs-tts-3-4b
# then on the Mac:
export HIGGS_TTS_URL=http://<gpu-host>:8000
```

* Licence: Boson Higgs TTS 3 Research & Non-Commercial; the **Creator Use Grant** allows monetised podcasts/videos for free *if the description credits "Boson AI's Higgs Audio"*. No hosting it as a service, no cloning without consent.
* Cloning references live on the server: `HIGGS_REF_<ROLE>=/server/path.wav`, `HIGGS_REF_<ROLE>_TEXT=...`.
* Prerequisite to approve: a GPU rental (hourly). The bench needs roughly 30 minutes of it.

### 2.3 Piper `lt_LT-reginute1-medium` (Lithuanian only, flat, offline)

```
# 1. a Piper that has PhonemeType.LITHUANIAN: piper1-gpl master after 2026-09-15 (PR #296)
#    (pip install piper-tts==1.8.0 is NOT enough; it predates the merge). Build per the repo README:
pip install "git+https://github.com/OHF-Voice/piper1-gpl.git"
# 2. the voice (from rhasspy/piper-voices, lt/lt_LT/reginute1/medium/):
mkdir -p ~/.local/share/piper && cd ~/.local/share/piper
huggingface-cli download rhasspy/piper-voices lt/lt_LT/reginute1/medium/lt_LT-reginute1-medium.onnx lt/lt_LT/reginute1/medium/lt_LT-reginute1-medium.onnx.json --local-dir .
# then move/symlink the two files to ~/.local/share/piper/ (or set PIPER_MODEL_LT)
# 3. the stress dictionary lt_kirciai.tsv from the voice's own repo (location NOT confirmed: the MODEL_CARD only says "from this repo"). Put it next to the .onnx.
```

Sizes: model 63.5 MB, config 5 KB. Data licence CC-BY-4.0 (LIEPA corpus, Vilnius University). Expect a flat single voice: it is a floor/reference, not a contender for emotional delivery.

### 2.4 Kokoro-82M (English baseline; the author's `af_heart`)

Pick one (none present on this Mac in working form):

```
# a) kokoro-onnx (already pip-installed here as kokoro-onnx 0.4.7): two files from the GitHub release "model-files-v1.0"
mkdir -p ~/.cache/kokoro-onnx && cd ~/.cache/kokoro-onnx
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx   # 325.5 MB (int8: 92.4 MB, fp16: 177.5 MB)
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin    # 28.2 MB
# b) MLX: huggingface-cli download mlx-community/Kokoro-82M-bf16   # ~0.4 GB (the 4bit repo already cached fails to load)
# c) PyTorch: pip install kokoro ; huggingface-cli download hexgrad/Kokoro-82M   # ~0.3-1.2 GB
```

Licence Apache-2.0. English (and es/fr/hi/it/ja/pt/zh); no Lithuanian.

### 2.5 Chatterbox (English only, the current pipeline engine)

```
pip install chatterbox-tts
huggingface-cli download ResembleAI/chatterbox-turbo        # ~2-4 GB (Hub reports 4.0 GB incl. history)
export CHATTERBOX_REF_NARRATOR=/path/consented_ref.wav      # Turbo requires a reference clip; one per role
```

MIT licence, Perth watermark. No Lithuanian in the 23-language multilingual model.

### 2.6 Candidates not wired into the harness (English only or licence-blocked)

| Model | Repo id | Size | Licence | Why not wired |
|---|---|---|---|---|
| Qwen3-TTS 0.6B / 1.7B | `Qwen/Qwen3-TTS-12Hz-0.6B-Base` (2.5 GB), `...1.7B-Base` (4.5 GB) | | Apache-2.0 | no Lithuanian; English runner-up; MLX route per `speak-skill` |
| Orpheus-3B | `canopylabs/orpheus-3b-0.1-ft` | 3.8B params | Apache-2.0 | English, heavy |
| Dia-1.6B | `nari-labs/Dia-1.6B` | 1.6B | Apache-2.0 | English, CUDA-first |
| Sesame CSM-1B | `sesame/csm-1b` | 1.55B | Apache-2.0 | English |
| Fish Audio S2 Pro | `fishaudio/s2-pro` | 5B (~10 GB) | Fish Research Licence (commercial needs a deal) | licence |
| MOSS-TTS v1.5 | `OpenMOSS-Team/MOSS-TTS-v1.5` | 8.5B | Apache-2.0 | no Lithuanian |
| VibeVoice-Realtime | `microsoft/VibeVoice-Realtime-0.5B` | 1.0B | MIT | English single voice |

## 3. Suggested approval order (cheapest information first)

1. **Free, now:** `python3 bench.py --engines edge,say --allow-online` (done once; samples are in `samples/`). Listen to the Lithuanian edge samples to calibrate what "flat Azure neural" sounds like.
2. **Keys, about US$3 total:** `elevenlabs` (v4 then `ELEVENLABS_MODEL=eleven_v3`), `gemini`, and `azure` (F0 free). That already covers the review's top candidates for both languages.
3. **Optional free local:** OmniVoice (3.3 GB) for a Mac-native open Lithuanian data point, Piper if you want the offline floor.
4. **Only if 1-3 disappoint or you want an open stack:** a GPU-hour for Higgs TTS 3.

## 4. Pronunciation assets the bench can export

```
python3 bench.py --export-pls build/lexicon_lt.pls   # W3C PLS (IPA) with the 351 entries + inflected variants
python3 bench.py --write-schema markup_schema.json   # the neutral utterance-record JSON schema
python3 lexicon_tts.py                                # demo of every lexicon mode on one sentence
```

Lexicon modes per engine and language live in `lexicon_tts.POLICY`; override for an experiment with `--lexicon-mode lt_accent` (EXPERIMENTAL: stress marks derived from the `stress` field) or `ipa_slash` to test ElevenLabs inline IPA on Lithuanian text.
