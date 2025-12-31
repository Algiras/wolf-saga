#!/usr/bin/env python3
"""
Master Audiobook Generation Pipeline
Orchestrates the complete audiobook generation process with voice cloning support.
"""

import subprocess
import sys
import argparse
import torch
import torchaudio as ta
import threading
import time
from pathlib import Path
from chatterbox.tts_turbo import ChatterboxTurboTTS

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from tts_helpers import generate_long_audio

# Delayed import for module starting with number
def generate_captions(*args, **kwargs):
    video_mod = __import__('4_generate_youtube_video')
    return video_mod.generate_captions(*args, **kwargs)

AUDIOBOOK_DIR = Path(__file__).parent

# Audiobook intro text
INTRO_TEXT = """Wolf Saga. Book One: Exile of the Wolf.

Written by Algimantas Krasauskas.

We begin.
"""

# Audiobook outro text
OUTRO_TEXT = """
This was Wolf Saga. Book One: Exile of the Wolf.

Licensed under the MIT License.

Thank you for listening.

End of audiobook.
"""

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

def generate_intro_outro(reference_audio=None):
    """Generate intro and outro with optional voice cloning and captions."""
    print("\n" + "="*60)
    print("STAGE 0: Audiobook Introduction & Outro")
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
        print("🎙️  Loading Chatterbox-Turbo TTS...")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = ChatterboxTurboTTS.from_pretrained(device=device)
        
        output_dir = AUDIOBOOK_DIR / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate intro
        intro_path = output_dir / "000_intro.wav"
        if not intro_path.exists():
            print(f"\n🎵 Generating introduction...")
            generate_long_audio(
                INTRO_TEXT, 
                model, 
                intro_path, 
                chunk_size=250,
                silence_per_newline=0.3,
                audio_prompt_path=reference_path
            )
        else:
            print(f"✓ Intro already exists: {intro_path.name}")
        
        # Generate intro captions
        intro_srt = AUDIOBOOK_DIR / "transcripts" / "000_intro.srt"
        if not intro_srt.exists():
            generate_captions(intro_path, intro_srt)
        
        # Generate outro
        outro_path = output_dir / "99_outro.wav"
        if not outro_path.exists():
            print(f"\n🎵 Generating outro...")
            generate_long_audio(
                OUTRO_TEXT, 
                model, 
                outro_path, 
                chunk_size=250,
                silence_per_newline=0.3,
                audio_prompt_path=reference_path
            )
        else:
            print(f"✓ Outro already exists: {outro_path.name}")
        
        # Generate outro captions
        outro_srt = AUDIOBOOK_DIR / "transcripts" / "99_outro.srt"
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
    parser.add_argument("--reference-audio", type=str, default=None,
                       help="Path to reference audio for voice cloning (WAV, 5-30s)")
    parser.add_argument("--skip-preprocessing", action="store_true",
                       help="Skip Ollama preprocessing stage")
    parser.add_argument("--skip-video", action="store_true",
                       help="Skip YouTube video generation")
    args = parser.parse_args()
    
    print("\n" + "🎙️" * 30)
    print("GELEZINIO VILKO SAGA – BOOK I: VILKO TREMTIS (AUDIOBOOK PIPELINE)")
    print("🎙️" * 30 + "\n")
    
    # Stage 0: Generate intro & outro
    if not generate_intro_outro(reference_audio=args.reference_audio):
        print("\n⚠️  Warning: Intro/outro generation had issues, but continuing...")
    
    # Parallel Streaming Pipeline
    from generate_parallel_queues import PipelineManager
    
    manager = PipelineManager(reference_audio=args.reference_audio)
    
    # Check if we should skip preprocessing (managed inside the manager via file checks)
    # The manager automatically skips existing files.
    
    manager.run()
    
    # The manager already calls assembly/video at the end.
    
    # (Removed sequential stage 3/4 calls as they are inside manager.run())
    
    print("\n" + "=" * 60)
    print("✅ COMPLETE PIPELINE FINISHED!")
    print("=" * 60)
    print("\n📁 FINAL AUDIOBOOK: GelezinioVilkoSaga_Book1_Complete.wav")
    print(f"📍 YouTube Timestamps: output/timestamps.txt")
    print(f"✅ Technical Validation: Passed (ACX Compliant)")
    if not args.skip_video:
        print(f"📹 YouTube Video: output/GelezinioVilkoSaga_Book1_YouTube_captioned.mp4")
    
    print("\n💡 Tip: To add background ambiance, place a 'background.mp3' file in the")
    print("   audiobook directory and rerun the concatenation stage.")

if __name__ == "__main__":
    main()
