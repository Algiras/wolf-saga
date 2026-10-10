#!/usr/bin/env python3
"""
Parallel Audiobook Generation
Runs text preprocessing (Stage 1) and audio generation (Stage 2) in parallel for
faster completion, then concatenates (Stage 3).

Stage 2 runs in --watch mode so it narrates chapters as Stage 1 finishes them and
exits once every chapter of the book has up-to-date audio.
"""

import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import book_manifest as bm

AUDIOBOOK_DIR = Path(__file__).parent
OUTPUT_DIR = bm.OUTPUT_DIR


class ParallelAudiobookGenerator:
    def __init__(self, reference_audio=None, book=1, only=None, force=False):
        self.reference_audio = reference_audio
        self.book = book
        self.only = only          # optional comma-separated chapter keys
        self.force = force
        self.errors = []
        self.preprocess_done = threading.Event()
        self.audio_proc = None

    def _stage_args(self):
        args = ["--book", str(self.book)]
        if self.only:
            args += ["--only", self.only]
        if self.force:
            args += ["--force"]
        return args

    def preprocess_worker(self):
        """Worker thread for text preprocessing."""
        print("🔄 Starting text preprocessing...")
        cmd = [sys.executable, "1_preprocess_with_ollama.py"] + self._stage_args()

        try:
            subprocess.run(cmd, cwd=AUDIOBOOK_DIR, check=True)  # stream output
            print("✅ Text preprocessing complete!")
        except subprocess.CalledProcessError as e:
            error_msg = f"❌ Preprocessing error: {e}"
            print(error_msg)
            self.errors.append(error_msg)
            # Stage 2 would otherwise wait for chapters that will never arrive
            if self.audio_proc and self.audio_proc.poll() is None:
                self.audio_proc.terminate()
        finally:
            self.preprocess_done.set()

    def audio_worker(self):
        """Worker thread for audio generation."""
        print("⏳ Waiting for first chapters to be preprocessed...")

        # Give preprocessing a head start (it writes the manifest almost immediately)
        time.sleep(30)

        print("🎙️  Starting audio generation...")
        cmd = [sys.executable, "2_generate_audio.py", "--watch"] + self._stage_args()
        if self.reference_audio:
            cmd.extend(["--reference-audio", str(self.reference_audio)])

        try:
            # Narrates chapters as they become available and exits when all are done
            self.audio_proc = subprocess.Popen(cmd, cwd=AUDIOBOOK_DIR)
            returncode = self.audio_proc.wait()
            if returncode != 0 and not (self.errors and returncode < 0):
                raise subprocess.CalledProcessError(returncode, cmd)
            if returncode == 0:
                print("✅ Audio generation complete!")
        except subprocess.CalledProcessError as e:
            error_msg = f"❌ Audio generation error: {e}"
            print(error_msg)
            self.errors.append(error_msg)

    def run_parallel(self):
        """Run preprocessing and audio generation in parallel."""
        print("="*60)
        print("🚀 PARALLEL AUDIOBOOK GENERATION")
        print("="*60)
        print("\nThis will run text preprocessing and audio generation")
        print("simultaneously for faster completion.\n")

        preprocess_thread = threading.Thread(target=self.preprocess_worker)
        audio_thread = threading.Thread(target=self.audio_worker)

        preprocess_thread.start()
        audio_thread.start()

        preprocess_thread.join()
        audio_thread.join()

        if self.errors:
            print("\n❌ Errors occurred:")
            for error in self.errors:
                print(error)
            return False

        print("\n✅ Parallel generation complete!")
        return True

    def concatenate(self):
        """Concatenate all audio files."""
        print("\n🔗 Concatenating audio files...")
        cmd = [sys.executable, "3_concatenate_audio.py", "--book", str(self.book)]

        try:
            subprocess.run(cmd, cwd=AUDIOBOOK_DIR, check=True)
            print("✅ Concatenation complete!")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Concatenation error: {e}")
            return False

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate audiobook with parallel text/audio processing"
    )
    parser.add_argument("--book", type=int, default=1, help="Book number (default 1)")
    parser.add_argument(
        "--reference-audio",
        type=str,
        help="Path to reference audio for voice cloning"
    )
    parser.add_argument("--only", type=str, default=None,
                        help="Comma-separated chapter keys, e.g. b1_03_gintaro_sapnas")
    parser.add_argument("--force", action="store_true",
                        help="Regenerate selected chapters even if their source is unchanged")
    parser.add_argument(
        "--skip-concatenate",
        action="store_true",
        help="Skip final concatenation step"
    )

    args = parser.parse_args()

    reference_path = Path(args.reference_audio) if args.reference_audio else None
    if reference_path and not reference_path.exists():
        print(f"❌ Reference audio not found: {reference_path}")
        return 1

    generator = ParallelAudiobookGenerator(reference_audio=reference_path, book=args.book,
                                           only=args.only, force=args.force)

    # Run parallel generation
    if not generator.run_parallel():
        return 1

    # Concatenate if requested
    if not args.skip_concatenate:
        if not generator.concatenate():
            return 1

    print("\n" + "="*60)
    print("✅ AUDIOBOOK GENERATION COMPLETE!")
    print("="*60)
    print(f"\n📁 Output: {AUDIOBOOK_DIR / bm.master_wav_name(args.book)}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
