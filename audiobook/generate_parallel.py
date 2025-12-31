#!/usr/bin/env python3
"""
Parallel Audiobook Generation
Runs text preprocessing and audio generation in parallel for faster completion.
"""

import subprocess
import threading
import queue
import time
from pathlib import Path
import json

AUDIOBOOK_DIR = Path(__file__).parent
PREPROCESSED_DIR = AUDIOBOOK_DIR / "preprocessed"
OUTPUT_DIR = AUDIOBOOK_DIR / "output"
MANIFEST_PATH = AUDIOBOOK_DIR / "manifest.json"

class ParallelAudiobookGenerator:
    def __init__(self, reference_audio=None):
        self.reference_audio = reference_audio
        self.text_queue = queue.Queue()
        self.errors = []
        
    def preprocess_worker(self):
        """Worker thread for text preprocessing."""
        print("🔄 Starting text preprocessing...")
        cmd = ["python3", "1_preprocess_with_ollama.py"]
        
        try:
            result = subprocess.run(
                cmd,
                cwd=AUDIOBOOK_DIR,
                capture_output=True,
                text=True,
                check=True
            )
            print("✅ Text preprocessing complete!")
            
            # Signal that preprocessing is done
            self.text_queue.put("DONE")
            
        except subprocess.CalledProcessError as e:
            error_msg = f"❌ Preprocessing error: {e}\n{e.stderr}"
            print(error_msg)
            self.errors.append(error_msg)
            self.text_queue.put("ERROR")
    
    def audio_worker(self):
        """Worker thread for audio generation."""
        print("⏳ Waiting for first chapters to be preprocessed...")
        
        # Wait for some chapters to be ready
        time.sleep(30)  # Give preprocessing a head start
        
        print("🎙️  Starting audio generation...")
        cmd = ["python3", "2_generate_audio.py"]
        if self.reference_audio:
            cmd.extend(["--reference-audio", str(self.reference_audio)])
        
        try:
            # Run audio generation (it will process chapters as they become available)
            result = subprocess.run(
                cmd,
                cwd=AUDIOBOOK_DIR,
                capture_output=False,  # Show output in real-time
                text=True,
                check=True
            )
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
        
        # Create threads
        preprocess_thread = threading.Thread(target=self.preprocess_worker)
        audio_thread = threading.Thread(target=self.audio_worker)
        
        # Start preprocessing first
        preprocess_thread.start()
        
        # Start audio generation after a delay
        audio_thread.start()
        
        # Wait for both to complete
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
        cmd = ["python3", "3_concatenate_audio.py"]
        
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
    parser.add_argument(
        "--reference-audio",
        type=str,
        help="Path to reference audio for voice cloning"
    )
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
    
    generator = ParallelAudiobookGenerator(reference_audio=reference_path)
    
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
    print(f"\n📁 Output: {OUTPUT_DIR / 'Miserable_Audiobook_Complete.wav'}")
    
    return 0

if __name__ == "__main__":
    exit(main())
