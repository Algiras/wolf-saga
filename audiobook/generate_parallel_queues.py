# Geležinio Vilko Saga Parallel Queue Pipeline
# Streams chapters through Preprocessing -> Audio -> Captions simultaneously.
# Chapters are identified by stable keys (b1_03_gintaro_sapnas); see book_manifest.py.

import subprocess
import threading
import queue
import time
import sys
from pathlib import Path

# Add current dir to path
sys.path.insert(0, str(Path(__file__).parent))

import book_manifest as bm
from tts_helpers import generate_long_audio

# These are imported inside workers to avoid conflicts / heavy imports at startup
# (modules whose names start with a digit need __import__):
# from 1_preprocess_with_ollama import preprocess_book
# from 4_generate_youtube_video import generate_captions

AUDIOBOOK_DIR = Path(__file__).parent
OUTPUT_DIR = bm.OUTPUT_DIR
PREPROCESSED_DIR = bm.PREPROCESSED_DIR
TRANSCRIPTS_DIR = bm.TRANSCRIPTS_DIR

# Silence 3_concatenate_audio.py inserts between segments (keep in sync)
CHAPTER_GAP_SECONDS = 3.0


def wav_duration(path):
    """Duration in seconds via ffprobe (no torch needed)."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out)


class PipelineManager:
    def __init__(self, reference_audio=None, book=1, skip_video=False, skip_preprocessing=False,
                 only=None, force=False):
        self.reference_audio = Path(reference_audio) if reference_audio else None
        self.book = book
        self.skip_video = skip_video
        self.skip_preprocessing = skip_preprocessing
        self.only = only
        self.force = force
        self.tts_queue = queue.Queue()
        self.caption_queue = queue.Queue()
        self.done_queue = queue.Queue()
        self.stop_signal = threading.Event()
        self.total_chapters = 0

        # Directories
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        PREPROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

    async def preprocessor_worker_async(self):
        """Stage 1: LLM Preprocessing (Sequential due to RAG)"""
        try:
            if self.skip_preprocessing:
                # Reuse whatever Stage 1 already produced; do not touch the LLM.
                print("⏭️  Preprocessor: --skip-preprocessing, using existing preprocessed text.", flush=True)
                entries = bm.build_manifest_entries(self.book)
                bm.save_manifest(self.book, entries)
                self.total_chapters = len(entries)
                for entry in entries:
                    if self.only and entry["key"] not in self.only and entry["key"].split(f"b{self.book}_", 1)[-1] not in self.only:
                        continue
                    if bm.is_ready(entry):
                        self.tts_queue.put(entry)
                    else:
                        print(f"   ⚠️ Preprocessor: {entry['key']} has no up-to-date narration text; skipping", flush=True)
            else:
                # Use __import__ for modules starting with numbers
                preprocess_mod = __import__('1_preprocess_with_ollama')
                self.total_chapters = len(bm.discover_chapters(self.book))
                print(f"📖 Preprocessor: Starting work on {self.total_chapters} chapters...", flush=True)
                failures = await preprocess_mod.preprocess_book(
                    self.book,
                    only=self.only,
                    force=self.force,
                    on_chapter_ready=self.tts_queue.put,
                )
                for key in failures:
                    print(f"   ⚠️ Preprocessor: {key} failed", flush=True)
        finally:
            # Always release the TTS worker, even when Stage 1 crashes
            self.tts_queue.put(None)
            print("✅ Preprocessor: Finished.", flush=True)

    def preprocessor_worker(self):
        """Wrapper for async worker."""
        import asyncio
        try:
            asyncio.run(self.preprocessor_worker_async())
        except BaseException as e:  # keep the other workers alive-and-draining
            print(f"❌ Preprocessor crashed: {e}", flush=True)

    def audio_worker(self):
        """Stage 2: TTS Generation (Sequential to save VRAM)"""
        print("🎙️ Audio: Initializing Chatterbox-Turbo...", flush=True)
        import torch
        from chatterbox.tts_turbo import ChatterboxTurboTTS
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = None

        try:
            while not self.stop_signal.is_set():
                task = self.tts_queue.get()
                if task is None:
                    break  # End signal

                key = task['key']
                output_wav = bm.audio_path(key)

                if self.force and (self.only is None or key in self.only):
                    needs_audio = True
                else:
                    needs_audio = not bm.audio_is_current(task)

                if needs_audio:
                    if model is None:  # load lazily: nothing to narrate -> no model load
                        model = ChatterboxTurboTTS.from_pretrained(device=device)
                    print(f"🎵 Audio: Narrating {key} ({task['title']})...", flush=True)
                    try:
                        text = Path(task['file']).read_text(encoding='utf-8')
                        generate_long_audio(
                            text, model, output_wav,
                            chunk_size=250, silence_per_newline=0.3,
                            audio_prompt_path=self.reference_audio
                        )
                        bm.write_audio_meta(task, text)
                    except Exception as e:
                        print(f"❌ Audio Error {key}: {e}", flush=True)
                        self.tts_queue.task_done()
                        continue
                else:
                    print(f"   ✓ Audio: {key} already up to date.", flush=True)

                # Push to Captions
                self.caption_queue.put({'key': key, 'wav': str(output_wav)})
                self.tts_queue.task_done()
        finally:
            self.caption_queue.put(None)
            if model is not None:
                del model
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            print("✅ Audio: Finished all tasks.", flush=True)

    def caption_worker(self):
        """Stage 3: Whisper Transcription (Parallel with Audio)"""
        print("📝 Captioner: Waiting for audio files...", flush=True)
        video_mod = __import__('4_generate_youtube_video')
        generate_captions = video_mod.generate_captions

        while not self.stop_signal.is_set():
            task = self.caption_queue.get()
            if task is None:
                break

            key, wav = task['key'], Path(task['wav'])
            output_srt = bm.srt_path(key)

            # Re-transcribe when the SRT is missing or older than the audio
            if output_srt.exists() and output_srt.stat().st_mtime >= wav.stat().st_mtime:
                print(f"   ✓ Captioner: {key} already up to date.", flush=True)
            else:
                print(f"📝 Captioner: Transcribing {key}...", flush=True)
                generate_captions(wav, output_srt)

            self.done_queue.put(task)
            self.caption_queue.task_done()

        print("✅ Captioner: Finished all transcripts.", flush=True)

    def run(self):
        print("\n" + "🚀" * 30)
        print("SAGA PARALLEL STREAMING PIPELINE")
        print("🚀" * 30 + "\n")

        start_time = time.time()

        # Start workers
        t1 = threading.Thread(target=self.preprocessor_worker)
        t2 = threading.Thread(target=self.audio_worker)
        t3 = threading.Thread(target=self.caption_worker)

        t1.start()
        t2.start()
        t3.start()

        # Wait for all to finish
        t1.join()
        t2.join()
        t3.join()

        end_time = time.time()
        print(f"\n✨ Parallel Generation Complete in {(end_time - start_time)/60:.1f} minutes!")

        # Step 4: Combine Everything
        self.assemble_final_product()

    def assemble_final_product(self):
        print("\n" + "="*60)
        print("STAGE 4: FINAL ASSEMBLY (Concatenation" + ("" if self.skip_video else " & Video") + ")")
        print("="*60 + "\n")

        concat_mod = __import__('3_concatenate_audio')

        # 1. Concatenate Audio
        concat_mod.concatenate_audiobook(self.book)

        # 2. Merge SRTs
        self.merge_srt_files()

        master_audio = AUDIOBOOK_DIR / bm.master_wav_name(self.book)

        # 3. Build Video (Background mixing is already in Stage 4 script)
        if self.skip_video:
            print("⏭️  Skipping YouTube video (--skip-video).", flush=True)
        else:
            video_mod = __import__('4_generate_youtube_video')
            splash = bm.BOOKS_DIR / str(self.book) / "cover.png"
            video_out = OUTPUT_DIR / bm.video_name(self.book)

            if video_mod.generate_video(master_audio, splash, video_out):
                # 4. Burn in Captions
                final_srt = OUTPUT_DIR / bm.master_srt_name(self.book)
                captioned_video = OUTPUT_DIR / bm.video_name(self.book, captioned=True)
                video_mod.add_captions_to_video(video_out, final_srt, captioned_video)

        # 5. Technical Validation
        print("\n" + "="*60)
        print("STAGE 5: TECHNICAL VALIDATION (ACX/Audible Compliance)")
        print("="*60 + "\n")
        val_mod = __import__('5_technical_validation')
        val_mod.validate_audio(master_audio)

    def merge_srt_files(self):
        """Merges chapter SRTs into one master SRT, in manifest order, offset by the
        chapter durations plus the silence the concatenation stage inserts."""
        print("🔗 Merging chapter transcripts into master SRT...", flush=True)

        # (key-or-name, wav, srt) in listening order: intro, chapters, outro
        segments = []
        intro_wav = OUTPUT_DIR / bm.intro_wav_name(self.book)
        if intro_wav.exists():
            segments.append((intro_wav, TRANSCRIPTS_DIR / (intro_wav.stem + ".srt")))
        for e in bm.load_manifest(self.book):
            wav = bm.audio_path(e["key"])
            if wav.exists() and wav.stat().st_size > 1000:
                segments.append((wav, bm.srt_path(e["key"])))
        outro_wav = OUTPUT_DIR / bm.outro_wav_name(self.book)
        if outro_wav.exists():
            segments.append((outro_wav, TRANSCRIPTS_DIR / (outro_wav.stem + ".srt")))

        master_srt = OUTPUT_DIR / bm.master_srt_name(self.book)

        cumulative_offset = 0.0
        master_lines = []
        caption_index = 1

        for n, (wav_file, srt_file) in enumerate(segments):
            if n > 0:
                cumulative_offset += CHAPTER_GAP_SECONDS
            duration = wav_duration(wav_file)

            if srt_file.exists():
                content = srt_file.read_text(encoding='utf-8').strip()
                for block in (content.split('\n\n') if content else []):
                    lines = block.split('\n')
                    if len(lines) < 3:
                        continue

                    # Offset the time line: 00:00:01,000 --> 00:00:04,000
                    start_str, end_str = lines[1].split(' --> ')
                    new_start = self.offset_srt_time(start_str, cumulative_offset)
                    new_end = self.offset_srt_time(end_str, cumulative_offset)

                    master_lines.append(f"{caption_index}\n{new_start} --> {new_end}\n" + "\n".join(lines[2:]))
                    caption_index += 1

            cumulative_offset += duration

        master_srt.write_text("\n\n".join(master_lines), encoding='utf-8')
        print(f"✅ Master SRT saved: {master_srt.name}", flush=True)

    def offset_srt_time(self, time_str, offset_sec):
        # HH:MM:SS,mmm
        h, m, s_m = time_str.split(':')
        s, ms = s_m.split(',')
        total_ms = round((int(h)*3600 + int(m)*60 + int(s) + int(ms)/1000.0 + offset_sec) * 1000)

        nh, rem = divmod(total_ms, 3600 * 1000)
        nm, rem = divmod(rem, 60 * 1000)
        ns, nms = divmod(rem, 1000)
        return f"{nh:02d}:{nm:02d}:{ns:02d},{nms:03d}"

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-audio", type=str, default=None)
    parser.add_argument("--book", type=int, default=1, help="Book number (default 1)")
    parser.add_argument("--skip-preprocessing", action="store_true",
                        help="Do not call the LLM; narrate from existing preprocessed text")
    parser.add_argument("--skip-video", action="store_true", help="Do not build the YouTube video")
    parser.add_argument("--only", type=str, default=None, help="Comma-separated chapter keys")
    parser.add_argument("--force", action="store_true", help="Regenerate selected chapters even if unchanged")
    args = parser.parse_args()

    only = {k.strip() for k in args.only.split(",") if k.strip()} if args.only else None
    manager = PipelineManager(reference_audio=args.reference_audio, book=args.book,
                              skip_video=args.skip_video, skip_preprocessing=args.skip_preprocessing,
                              only=only, force=args.force)
    manager.run()
