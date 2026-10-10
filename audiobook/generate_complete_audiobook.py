#!/usr/bin/env python3
"""
Master Audiobook Generation Pipeline
Orchestrates the complete audiobook generation process with voice cloning support.
"""

import subprocess
import sys
import argparse
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
import book_manifest as bm

# Delayed import for module starting with number
def generate_captions(*args, **kwargs):
    video_mod = __import__('4_generate_youtube_video')
    return video_mod.generate_captions(*args, **kwargs)

AUDIOBOOK_DIR = Path(__file__).parent

# Intro / outro text is book-aware: see bm.intro_text(book) and bm.outro_text(book).

def stream_subprocess(cmd, description):
    """Run a subprocess and stream its output to stdout with labels."""
    print(f"\n🚀 Starting {description} stage...", flush=True)
    process = subprocess.Popen(
        cmd,
        cwd=AUDIOBOOK_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    for line in process.stdout:
        print(f"[{description}] {line}", end="", flush=True)
    
    process.wait()
    if process.returncode != 0:
        print(f"\n❌ {description} stage failed with exit code {process.returncode}")
        return False
    print(f"\n✅ {description} stage complete!")
    return True

def run_stage(stage_number, script_name, description, extra_args=None):
    """Run a pipeline stage sequentially."""
    print(f"\n{'='*60}")
    print(f"STAGE {stage_number}: {description}")
    print(f"{'='*60}\n")
    
    script_path = AUDIOBOOK_DIR / script_name
    cmd = [sys.executable, str(script_path)]
    if extra_args:
        cmd.extend(extra_args)
    
    return stream_subprocess(cmd, description)

def generate_intro_outro(reference_audio=None, book=1):
    """Generate intro and outro with optional voice cloning and captions."""
    print("\n" + "="*60)
    print(f"STAGE 0: Audiobook Introduction & Outro ({bm.book_label(book)})")
    print("="*60 + "\n")
    
    # Handle reference audio
    reference_path = None
    if reference_audio:
        reference_path = Path(reference_audio)
        if not reference_path.exists():
            print(f"⚠️  Reference audio not found: {reference_audio}")
            print("   Using default voice")
            reference_path = None
        else:
            print(f"🎤 Using reference audio: {reference_path.name}")
    else:
        print("🎤 Using model default voice")
    
    try:
        import torch
        from chatterbox.tts_turbo import ChatterboxTurboTTS
        from tts_helpers import generate_long_audio

        intro_path = bm.OUTPUT_DIR / bm.intro_wav_name(book)
        outro_path = bm.OUTPUT_DIR / bm.outro_wav_name(book)
        intro_srt = bm.TRANSCRIPTS_DIR / (intro_path.stem + ".srt")
        outro_srt = bm.TRANSCRIPTS_DIR / (outro_path.stem + ".srt")
        intro_srt.parent.mkdir(parents=True, exist_ok=True)

        # Nothing to generate? Do not load the model at all.
        if intro_path.exists() and outro_path.exists():
            print(f"✓ Intro and outro already exist ({intro_path.name}, {outro_path.name})")
            if not intro_srt.exists():
                generate_captions(intro_path, intro_srt)
            if not outro_srt.exists():
                generate_captions(outro_path, outro_srt)
            return True

        print("🎙️  Loading Chatterbox-Turbo TTS...")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = ChatterboxTurboTTS.from_pretrained(device=device)
        
        bm.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        # Generate intro
        if not intro_path.exists():
            print(f"\n🎵 Generating introduction...")
            generate_long_audio(
                bm.intro_text(book), 
                model, 
                intro_path, 
                chunk_size=250,
                silence_per_newline=0.3,
                audio_prompt_path=reference_path
            )
        else:
            print(f"✓ Intro already exists: {intro_path.name}")
        
        # Generate intro captions
        if not intro_srt.exists():
            generate_captions(intro_path, intro_srt)
        
        # Generate outro
        if not outro_path.exists():
            print(f"\n🎵 Generating outro...")
            generate_long_audio(
                bm.outro_text(book), 
                model, 
                outro_path, 
                chunk_size=250,
                silence_per_newline=0.3,
                audio_prompt_path=reference_path
            )
        else:
            print(f"✓ Outro already exists: {outro_path.name}")
        
        # Generate outro captions
        if not outro_srt.exists():
            generate_captions(outro_path, outro_srt)
        
        print("\n✅ Intro & Outro complete!")
        # Clean up model to free VRAM for subprocesses
        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            
        return True
        
    except Exception as e:
        print(f"❌ Error generating intro/outro: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run the complete audiobook generation pipeline with parallelization."""
    parser = argparse.ArgumentParser(description="Generate complete audiobook")
    parser.add_argument("--book", type=int, default=1, help="Book number (default 1)")
    parser.add_argument("--reference-audio", type=str, default=None,
                       help="Path to reference audio for voice cloning (WAV, 5-30s)")
    parser.add_argument("--skip-preprocessing", action="store_true",
                       help="Skip the Gemini preprocessing stage and narrate from existing preprocessed text")
    parser.add_argument("--skip-video", action="store_true",
                       help="Skip YouTube video generation")
    parser.add_argument("--only", type=str, default=None,
                       help="Comma-separated chapter keys to process, e.g. b1_03_gintaro_sapnas")
    parser.add_argument("--force", action="store_true",
                       help="Regenerate the selected chapters even if their source is unchanged")
    args = parser.parse_args()

    book = args.book
    print("\n" + "🎙️" * 30)
    print(f"GELEZINIO VILKO SAGA – {bm.book_label(book).upper()}: {bm.book_title_en(book).upper()} (AUDIOBOOK PIPELINE)")
    print("🎙️" * 30 + "\n")

    # Stage 0: Generate intro & outro
    if not generate_intro_outro(reference_audio=args.reference_audio, book=book):
        print("\n⚠️  Warning: Intro/outro generation had issues, but continuing...")

    # Parallel Streaming Pipeline (skips unchanged chapters; assembly/video happen inside run())
    from generate_parallel_queues import PipelineManager

    only = {k.strip() for k in args.only.split(",") if k.strip()} if args.only else None
    manager = PipelineManager(
        reference_audio=args.reference_audio,
        book=book,
        skip_video=args.skip_video,
        skip_preprocessing=args.skip_preprocessing,
        only=only,
        force=args.force,
    )
    manager.run()

    print("\n" + "=" * 60)
    print("✅ COMPLETE PIPELINE FINISHED!")
    print("=" * 60)
    print(f"\n📁 FINAL AUDIOBOOK: {bm.master_wav_name(book)}")
    print(f"📍 YouTube Timestamps: output/{bm.timestamps_name(book)}")
    print(f"✅ Technical Validation: see output above")
    if not args.skip_video:
        print(f"📹 YouTube Video: output/{bm.video_name(book, captioned=True)}")

    print("\n💡 Tip: To add background ambiance, place a 'background.mp3' file in the")
    print("   audiobook directory and rerun the concatenation stage.")

if __name__ == "__main__":
    main()
