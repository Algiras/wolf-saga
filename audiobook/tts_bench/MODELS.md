# TTS engine shortlist for the Wolf Saga audiobook (Lithuanian and English)

Researched 2026-10-10 (the day of the review). Companion to `../VIDEO_PIPELINE_REVIEW.md` section 5. The bench harness in this folder (`bench.py`) is how the shortlist gets decided; this file says what to put in it and why.

**How to read the evidence tags.** `[V]` = checked this session against a vendor doc, model card, API response or release page. `[S]` = secondary source (blog, aggregator, press). `[E]` = my estimate, no source. Anything tagged `[S]` or `[E]` is a hypothesis, not a fact.

**What this ranking is, and is not.** It ranks engines on *documented* Lithuanian support, emotion control, character voices, pronunciation control, licence and cost. I found **no independent Lithuanian listening test, MOS score or sample page for any engine** (the only Lithuanian TTS literature I found is the Vilnius University VITS work on single-voice research models [S]). So "supports Lithuanian" below means "the vendor lists it", not "it sounds good". That is exactly what `bench.py` is for.

Cost basis for Book I: Lithuanian source = **197,491 characters / 29,603 words** (measured from `books/1`, story chapters 0-30, headings and attributes removed); English translation assumed ~185k characters [E]; narration ~3.5 h = ~12,700 s at 140 wpm [E]. All prices are list prices on 2026-10-10 and change; "retakes" budget is +50 %.

---

## 1. Bottom line

### Lithuanian, top 3

| # | Engine | Why | Main risk |
|---|---|---|---|
| 1 | **ElevenLabs Eleven v4** (`eleven_v4`; `eleven_v3` as comparison) | Lithuanian is on both the v3 (74 languages) and v4 (90+) lists `[V]`. Free-text audio tags (`[whispers]`, `[angry]`...), Text-to-Dialogue endpoint, inline IPA `/.../` on v4, pronunciation dictionaries, commercial licence on every paid plan `[V]`. The only option that ticks emotion + dialogue + IPA at once. | Lithuanian *quality* unverified. v4 has no SSML breaks and no speed control. Cost ~US$16-24 per book at list price. |
| 2 | **Gemini 3.8 Flash TTS** (`gemini-3.8-flash-tts`, Gemini API) | Lithuanian is in its language table (the Flash-Lite variant is not) `[V]`. Natural-language direction per line, inline tags, 30 studio voices plus a voice library, 2 speakers per request `[V]`. Cheapest by far: ~US$3 per book `[V]` (price doubles on 2027-01-01). | No phoneme/lexicon control documented, so names depend on the model. Google's Cloud TTS page still lists `lt-LT` as **Preview** for the Gemini models, and the 3.8 models are Gemini-API / Gemini-Enterprise only `[V]`. Style prompts in English on Lithuanian text: untested. |
| 3 | **Higgs TTS 3** (`bosonai/higgs-tts-3-4b`, self-hosted) | Lithuanian is in its "WER/CER under 5 -- polished" tier `[V]`. 43 control tokens: 21 emotions (anger, fear, sadness, helplessness, bitterness...), whispering/shouting, pauses, sfx; zero-shot cloning `[V]`. **Creator Use Grant lets monetised videos use it free with a credit line** `[V]`. Cost: GPU rental only. | Needs a CUDA GPU server (sglang-omni / vLLM-Omni); **no documented Apple-silicon path** `[V]`. 4.65B params (~9.3 GB weights). Research/non-commercial licence outside the Creator grant. No IPA input. |

Close behind: **Inworld TTS-2** (Lithuanian in Tier 2, ~US$25 per 1M chars `[V]/[S]`) and **OmniVoice** (local, runs on the Mac's MPS, Lithuanian in its language list `[V]`, but **CC-BY-NC weights** conflict with a monetised channel). Azure and Chirp 3 HD are the "stable and flat" fallbacks.

### English, top 3

| # | Engine | Why | Main risk |
|---|---|---|---|
| 1 | **ElevenLabs Eleven v4** | Same tags/dialogue/IPA toolbox, strongest documented expressiveness of the API engines `[V]` (vendor claims "most emotive"; no independent comparison seen). Inline IPA gives exact control of the lexicon names. | Cost, same as Lithuanian. If the author wants *different* engines per language (review section 5.3), use #2 for English. |
| 2 | **Gemini 3.8 Flash TTS** | Direction-by-prompt suits grief/rage/whisper; designed voices; a few dollars per book `[V]`. A different engine from the Lithuanian primary, as the review asked. | No pronunciation lexicon: use the respelling plan (`lexicon_tts.py` mode `respell`). |
| 3 | **Higgs TTS 3** | English is a Tier-1-quality language; emotion tokens; cloning; free for monetised creators with credit `[V]`. Strongest *open* option for acted dialogue. | GPU server needed (see above). If that is a blocker: **Chatterbox** (MIT, local, already in the pipeline) is the Mac-friendly English fallback. |

Runner-ups worth a listen if the top 3 disappoint: **Hume Octave 2** (English, acting-style prompts; still "preview" `[V]`), **OpenAI gpt-4o-mini-tts** (instructions, strong English `[S]`), **Cartesia Sonic 3.5** (English strong; no Lithuanian `[V]`).

---

## 2. Lithuanian: ranked shortlist

Ranked for "emotional multi-character audiobook, published on YouTube". Lithuanian column states what is *verified*.

| Rank | Engine | Lithuanian support | Emotion control | Multi-speaker / cloning | Phoneme / lexicon | Licence, YouTube monetisation | Book I cost (197k chars) | Hardware / speed | Samples |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **ElevenLabs Eleven v4 / v3** (API) | **Yes** `[V]` v3: "Lithuanian (lit)" in 74-language list; v4: Lithuanian in 90+ list. Quality unverified. | Free-text audio tags `[whispers]`, `[sighs]`, `[angry]`, `[low, gravelly voice]`; tags may be read aloud or ignored by some voices; v4 follows them better than v3 `[V]` | Text-to-Dialogue API (v4 and v3); voice library, design, cloning (v4 from 10 s of audio `[S]`) `[V]` | **v4: inline IPA `/.../`** (varies by voice/phrase); pronunciation dictionaries (TXT/PLS); phoneme *tags* only on Flash v2 `[V]`. No SSML breaks on v3/v4 | Free plan: **no** commercial licence (attribution does not change that); **all paid plans: commercial licence**, excl. Beta features `[V]` | v3/v4 list **US$0.08 per 1k chars** (v4 promo US$0.022 until 12 Oct 2026) `[V]`: **~US$16** (promo ~US$4.4); with retakes + tags ~US$24. Creator plan US$22/mo = 1M credits `[V]` (credits per char on v3/v4 not verified) | API, nothing local. Char limit 5k (v3) / 10k (v4) per request `[V]` | [v3 launch page](https://elevenlabs.io/blog/eleven-v3), [models](https://elevenlabs.io/docs/overview/models) |
| 2 | **Gemini 3.8 Flash TTS** (Gemini API) | **Yes** `[V]` ("over 130 languages"; not in Flash-Lite). Cloud TTS page: `lt-LT` = **Preview** | `speech_metadata.style` per turn, inline English tags `<sigh>` `<laugh>` `<long pause>`, or "Say X:" prefix (used by the harness); docs advise English tags even for non-English text `[V]` | 2 speakers per request with prebuilt voices; designed/cloned voices need one request per turn; 30 studio voices + "hundreds" in a library `[V]` | **None documented** `[V]` | Paid-tier output; Gemini API terms for commercial use **not checked** `[U]` | Audio output US$9 per 1M tokens at 25 tok/s through 2026 `[V]`: 12.7k s = 317k tokens = **~US$2.9** (~US$5.8 from 2027); +retakes ~US$4-9 | API. 8,192-token input limit; ~655 s max audio per call (Cloud TTS page) `[V]` | [speech-generation docs](https://ai.google.dev/gemini-api/docs/speech-generation) |
| 3 | **Higgs TTS 3 4B** (open weights, self-host) | **Yes** `[V]` model card tier "WER/CER < 5, polished", 102 languages total | 21 emotion tokens, `whispering`, `shouting`, `singing`, speed/pitch/pause tokens, 9 sfx; sentence-level `<|emotion:sadness|>` `[V]` | Zero-shot cloning from a reference + transcript `[V]`; multi-speaker by separate calls per speaker `[U]` | None documented | Boson Higgs TTS 3 Research & Non-Commercial licence **+ Creator Use Grant: monetised podcasts/videos free if you credit "Boson AI's Higgs Audio" in the description**; no hosting-as-a-service, no embedding in a product; no cloning without consent `[V]` | GPU rental: ~3.5 h audio, RTF unknown on your GPU `[E]` ~US$2-10 | 4.65B BF16 (~9.3 GB) `[V]`; served via **sglang-omni / vLLM-Omni on CUDA** `[V]`; **no Apple-silicon route documented**; ~16-24 GB GPU `[E]` | [model card](https://huggingface.co/bosonai/higgs-tts-3-4b) |
| 4 | **Inworld TTS-2** (API) | **Yes, Tier 2** `[V]` (Tier 1 = 15 major languages; Tier 2 = 79 languages "fully supported, results vary"); they advise designing/cloning a voice *in the target language* | Not verified `[U]` (markup syntax not found) | Voice design / instant cloning `[V]` | Not verified `[U]` | Not checked `[U]` | List US$25 per 1M chars (cut from US$35 in June 2026) `[S]`: **~US$5** | API | [language list](https://docs.inworld.ai/tts/capabilities/multilingual), [playground](https://platform.inworld.ai/tts) |
| 5 | **OmniVoice 0.6B** (k2-fsa, local) | **Yes** `[V]` (`lt` in the model-card language list; the repo's language table gives lt a value of 2629.45, units not stated). Quality unverified | Non-verbal tags `[laughter]` `[sigh]`..., voice-design attributes incl. whisper (trained on zh/en only), speed/duration; cloning is "the most stable mode" `[V]` | Zero-shot cloning (same-language reference gives best accent), voice design `[V]` | English via CMU `[B EY1 S]`; Chinese pinyin; **nothing for Lithuanian** `[V]` | Code Apache-2.0 but **model weights CC-BY-NC** (training-data constraint) `[V]`: not safe for a monetised channel | Free | 0.6B params, ~3.3 GB; vendor RTF 0.025 on a datacentre GPU `[V]`; **MPS supported** (`device_map="mps"`) `[V]`; Mac speed `[E]` RTF 0.3-1 (not measured). Short clips unreliable without a reference `[V]` | [model card](https://huggingface.co/k2-fsa/OmniVoice), [HF Space](https://huggingface.co/spaces/k2-fsa/OmniVoice) |
| 6 | **Azure AI Speech Neural** `lt-LT-OnaNeural`, `lt-LT-LeonasNeural` | **Yes** `[V]`, two standard voices | **None**: no styles/roles for lt-LT; SSML prosody/break only `[V]` | 2 voices, one per `<voice>` | `<phoneme>` for lt-LT **not documented** `[V]`; `<sub alias>` works `[S]` | Commercial OK under Azure terms `[U]` (not re-read) | **0.5M chars/month free** (F0 tier) `[V]` covers Book I; paid ~US$16 per 1M chars `[E]`: ~US$3 | API; also free via `edge-tts` (unofficial) | [voice gallery](https://speech.microsoft.com/portal/voicegallery) |
| 7 | **Google Cloud Chirp 3: HD** | **Yes** (`lt-LT`) `[V]` | Pace control only (no styles) | One voice per request; ~30 personas | **Custom pronunciation: NOT supported for lt-LT; pause control: NOT supported for lt-LT** `[V]` | Commercial OK `[U]` | ~US$30 per 1M chars `[E]`: ~US$6 | API | [Chirp 3 HD docs](https://docs.cloud.google.com/text-to-speech/docs/chirp3-hd) |
| 8 | **OpenAI gpt-4o-mini-tts** | **Unverified** `[U]` (no vendor statement found; Whisper covers Lithuanian, the TTS voices are English-tuned `[S]`) | Free-text `instructions` | Preset voices, one per request | None | Commercial OK, disclose AI voice `[U]` | ~US$0.015/min `[S]`: ~US$3 | API | -- |
| 9 | **Piper `lt_LT-reginute1-medium`** (local) | **Yes** `[V]`: one studio actress, ~3 h of LIEPA corpus (CC-BY-4.0), stress-annotated | **None**; flat, "single short words hurried and thin" (model card) `[V]` | 1 voice | The voice ships its own stress dictionary + Lithuanian phonemizer (`lt_kirciai.tsv`) `[V]` | Data CC-BY-4.0; model lineage stated in the card `[V]` | Free | 63.5 MB model; fast on CPU `[E]`. **Needs piper1-gpl master (PR #296 merged 2026-09-15, after the v1.8.0 release 2026-09-04)**; `pip install piper-tts` 1.8.0 cannot run it `[V]` | [samples folder](https://huggingface.co/rhasspy/piper-voices/tree/main/lt/lt_LT/reginute1/medium/samples) |
| 10 | **Fish Audio S2 Pro** (open weights; S2.1 is API-only) | `lt` is in the "other languages" list `[V]` | Free-form `[whisper in small voice]`-style tags, "15,000+ unique tags" `[V]` | Cloning | None | **Fish Audio Research Licence; commercial use needs a separate licence** `[V]`: not usable for a monetised channel without a deal | -- | 5B params (4B slow-AR + 0.4B fast-AR); card quotes an H200 only `[V]` | [model card](https://huggingface.co/fishaudio/s2-pro) |
| -- | **neongeckocom/tts-vits-cv-lt** | Yes on paper (VITS on Common Voice lt, 2022) | None | `speaker_ids.json` | -- | BSD-3-clause; **empty README, "Invalid JSON for config.json" on the Hub** `[V]` | -- | -- | not worth the time |
| -- | **SpeechT5 VoxPopuli-lt fine-tunes** (e.g. `mahimairaja/speecht5_finetuned_voxpopuli_lithuanian`, MIT, 37 downloads) | Technically | None, robotic | single x-vector | -- | -- | -- | -- | research toys, skip |

### Lithuanian candidates I ruled out (no Lithuanian)

| Engine | Evidence |
|---|---|
| Meta MMS-TTS `lit` (the review's table lists `facebook/mms-tts-lit`) | **Does not exist.** `facebook/mms-tts-lit` returns 401 from the Hub API; the `facebook/mms-tts-l*` listing jumps from `lis` to `lje`, `ljp`... with `lav` and `lat` present and no `lit` `[V]`. Also CC-BY-NC-4.0. **Correct the review.** |
| Chatterbox Multilingual | HF model card's 23 languages: ar da de el en es fi fr he hi it ja ko ms nl no pl pt ru sv sw tr zh `[V]`. No `lt`. |
| XTTS-v2 | 17 languages, no Lithuanian; Coqui Public Model Licence (non-commercial) `[V]` |
| Qwen3-TTS (0.6B/1.7B, Apache-2.0) | 10 languages (en zh ja ko de fr ru pt es it) `[S]`. No `lt`. |
| Kokoro-82M | EN-US/GB, es, fr, hi, it, ja, pt, zh `[V]`. No `lt`. |
| Voxtral TTS (Mistral, CC-BY-NC-4.0) | en fr es pt it nl de ar hi `[V]` |
| MOSS-TTS v1.5 (Apache-2.0, 8.5B) | 31 languages; `lt` not in the HF language tags `[V]` |
| Cartesia Sonic 3 / 3.5 | 42 languages; list has no Lithuanian `[V]` |
| Hume Octave 2 | en ja ko es fr pt it de ru hi ar `[V]` |
| Inworld Tier 1 | The 15 major languages; Lithuanian is Tier 2, listed above |
| Amazon Polly | No Lithuanian voice found in AWS docs or announcements `[S]`; one aggregator claims Polly Lithuanian voices (Benas/Leonas/Ona), contradicted by AWS docs, treat as wrong `[S]` |
| MiniMax Speech 2.6 | ~40 languages; third-party lists show no Lithuanian `[S]` (not confirmed on MiniMax's own page) |
| Orpheus-3B-ft (en), Dia (en), Sesame CSM-1B (en), Spark-TTS (en/zh, CC-BY-NC-SA), IndexTTS-2 (en/zh), VibeVoice-Realtime-0.5B (en), Kyutai TTS (en/fr) | HF model-card language tags `[V]` |
| F5-TTS (weights CC-BY-NC-4.0), Zonos (Apache-2.0), Orpheus multilingual research release | F5: no Lithuanian fine-tune found (HF search returned only Malaysian-F5) `[V]`. Zonos card has no language tags; its en/ja/zh/fr/de list and Orpheus-multilingual's fr/de/ko/hi/zh/es/it are from memory `[U]` |

---

## 3. English: ranked shortlist

English support is not in question for any engine below, so the table is about *acting* quality and control. I have **no listening evidence**; ranking is by documented controls and licence.

| Rank | Engine | Emotion control | Multi-speaker / cloning | Pronunciation | Licence, monetisation | Book I cost (~185k chars) | Hardware | Notes |
|---|---|---|---|---|---|---|---|---|
| 1 | **ElevenLabs Eleven v4 / v3** | Audio tags | Text-to-Dialogue; library, design, cloning | **Inline IPA**, dictionaries | Paid plans: commercial `[V]` | ~US$15-22 (list) | API | see Lithuanian row; use IPA from `world_rules/pronunciation_lexicon.json` |
| 2 | **Gemini 3.8 Flash TTS** | Per-turn style + inline tags | 2-speaker requests, voice library | None (use respelling) | check Gemini terms `[U]` | ~US$2.7 | API | cheapest strong option |
| 3 | **Higgs TTS 3** | 21 emotions, style, prosody, sfx tokens | cloning (consented refs) | none | Creator Use Grant (credit line) `[V]` | GPU rental | CUDA server only | best open acting model I found |
| 4 | **Hume Octave 2** (API, preview) | Natural-language acting prompts, voice design `[S]` | voices by description | -- | -- | -- | API | English among 11 languages `[V]`; not verified for dialogue stability |
| 5 | **OpenAI gpt-4o-mini-tts** | `instructions` | 11-ish preset voices | none | commercial OK, disclose AI voice `[U]` | ~US$3 `[S]` | API | |
| 6 | **Cartesia Sonic 3 / 3.5** | volume/speed/emotion via API + SSML tags `[V]` | voice library, cloning | -- | -- | -- | API | very low latency (irrelevant for batch) |
| 7 | **Inworld TTS-2** | not verified `[U]` | design/cloning | -- | -- | ~US$4.6 `[S]` | API | English is Tier 1 `[V]` |
| 8 | **Chatterbox / Turbo** (Resemble, MIT) | `exaggeration`, `cfg_weight`, paralinguistic tags `[sigh]` `[laugh]` | zero-shot cloning (needs reference clip), Perth watermark | respelling only | MIT `[V]` | free | Mac MPS OK `[S]`; RTF ~1-3 `[E]` | already integrated (`tts_helpers.py`); weights ~4 GB `[S]` |
| 9 | **Orpheus-3B** (Canopy, Apache-2.0) | `<laugh>` `<sigh>` etc. `[S]` | preset voices, finetunable | -- | Apache `[V]` | free | 3.8B params; heavy on a Mac `[E]` | |
| 10 | **Dia-1.6B** (Nari, Apache-2.0) | `[S1]`/`[S2]` dialogue + non-verbal tags `[S]` | two speakers per pass | -- | Apache `[V]` | free | 1.6B; CUDA-first `[E]` | |
| 11 | **Sesame CSM-1B** (Apache-2.0) | context-conditioned prosody | speaker ids, context | -- | Apache `[V]` | free | 1.55B | |
| 12 | **Qwen3-TTS** 0.6B/1.7B (Apache-2.0) | voice description, 9 presets | cloning (conflicting reports `[S]`) | -- | Apache `[V]` | free | runs on Apple via MLX `[S]` | the author's `speak-skill` lists it as "qwen-tts" |
| 13 | **Fish Audio S2 Pro** | free-form tags | cloning | -- | research only `[V]` | -- | 5B | commercial licence needed |
| 14 | **VibeVoice-Realtime-0.5B** (MIT) | none | single voice | -- | MIT | free | tiny | status of the long-form multi-speaker 1.5B TTS unclear (code reportedly removed Sept 2025 `[S]`) |
| 15 | **Azure en-US/en-GB neural**, **Polly generative** | styles (`whispering`, `angry`, `sad` on some en-US voices) / none | -- | `<phoneme>` IPA | commercial | ~US$3 | API | clean but "reading", not acting |
| baseline | **Kokoro-82M** `af_heart` (Apache-2.0) | none | presets | respelling | Apache `[V]` | free | CPU/MPS, fast | the author's voice for notifications; proof-listening only |
| baseline | **macOS `say`** | rate only | -- | -- | n/a | free | built in | harness smoke test |

---

## 4. What I could and could not run here

* Installed and **rendered**: `edge-tts` 7.2.8 (free Microsoft Edge read-aloud voices: `lt-LT-OnaNeural`, `lt-LT-LeonasNeural`, and en-GB/en-US voices) and macOS `say` (English). Both are in `samples/` and `index.html`. `edge-tts` is an *unofficial* endpoint: sporadic HTTP 403 throttling (the plugin backs off), no SLA, and Microsoft's terms do not license production use; treat it as a free proxy for "what Azure lt-LT sounds like".
* Installed but **not usable**: Kokoro (the cached `mlx-community/Kokoro-82M-4bit` fails to load in `mlx-audio` 0.4.1 with a conv-weight shape mismatch; the speak-skill's `kokoro-js` directory `/tmp/kokoro-test` no longer exists), `piper-tts` 1.4.1 (no Lithuanian phonemizer, and no Lithuanian voice file present).
* Not installed: Chatterbox, OmniVoice, XTTS, F5, Higgs, and every API key (none are set in this environment, by design).

## 5. Corrections to `VIDEO_PIPELINE_REVIEW.md` section 5

1. `facebook/mms-tts-lit` does not exist (see section 2). Remove the MMS row.
2. ElevenLabs now has **Eleven v4** (`eleven_v4`, `eleven_v4_turbo`, 90+ languages, Lithuanian included, 10k chars/request, inline IPA in plain `/.../`, audio tags). The review recommends v3; v3 is the same price (US$0.08/1k) and a good A/B comparison, but v4 should be the lead candidate. The review says phoneme rules are honoured "on v3 and Flash v2 only": the current docs say phoneme *tags* work only on Flash v2, and inline IPA works on v4 `[V]`.
3. Gemini: the Gemini API lists `gemini-3.8-flash-tts` (Lithuanian yes) and `gemini-3.8-flash-lite-tts` (no), plus `gemini-3.1-flash-tts-preview`. The Cloud TTS product lists `lt-LT` as Preview and does not expose the 3.8 models. Use the Gemini API.
4. Chirp 3 HD: verified that **custom pronunciation and pause control are not available for lt-LT** (the review said "verify"). Pace only.
5. New viable Lithuanian engines the review missed: **Higgs TTS 3**, **Inworld TTS-2 (Tier 2)**, **OmniVoice**, **Piper `lt_LT-reginute1`**, **Fish S2 Pro** (licence-blocked).
6. Open-model licences matter for monetisation: OmniVoice weights CC-BY-NC, Fish Research Licence, Voxtral CC-BY-NC, F5 CC-BY-NC, XTTS CPML. Higgs has the Creator Use Grant; Chatterbox (MIT), Kokoro, Qwen3-TTS, Orpheus, Dia, CSM are permissive.
7. YouTube policy `[S]`: the July 2025 monetisation update targets "mass-produced, repetitive, inauthentic" content, not AI voices as such; a serialised audiobook of an original text with unique art is not that, but templated 30-video batches with identical still cards could be read that way. Check the current YPP "inauthentic content" help page before relying on monetisation.

## 6. Unverified, and open questions

* Lithuanian **quality** of every engine (stress, intonation, emotion in Lithuanian). Nothing independent found.
* ElevenLabs credits-per-character on v3/v4 and whether tags count as characters (assumed yes, +10 %).
* Gemini 3.8 `speech_metadata.style` request syntax (the harness uses the older "Say X:" prefix instead), and Gemini API commercial-use terms.
* Prices marked `[E]` (Azure, Chirp 3 HD, OpenAI): pricing pages did not render the numbers for me.
* Whether OmniVoice's `generate(language=...)` keyword exists (the README shows `language_id` only for batch/CLI); the plugin falls back if it is rejected. Untested because the package is not installed.
* Higgs on Apple silicon: no documented route; an unofficial transformers/MPS port may exist but I did not look for one.
* Inworld TTS-2 emotion/markup control and licence terms; Hume Octave 2 dialogue stability; Polly generative voices: not researched past the language lists.
* PlayHT: status after the 2025 Meta acquisition not verified, left out.
* Piper `lt_kirciai.tsv` download location (the model card says "from this repo", the voice repo name was not given).
* Whether the author wants one engine for both languages or a deliberately different engine per language.
