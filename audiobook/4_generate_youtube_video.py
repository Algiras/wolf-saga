#!/usr/bin/env python3
"""
YouTube Video Generator for Audiobook
Creates a video from audio with static splash screen and optional captions.
"""

import subprocess
import json
import threading
import torch
from pathlib import Path

AUDIOBOOK_DIR = Path(__file__).parent
AUDIO_FILE = AUDIOBOOK_DIR / "GelezinioVilkoSaga_Book1_Complete.wav"
SPLASH_IMAGE = AUDIOBOOK_DIR.parent / "books" / "1" / "cover.png"
OUTPUT_VIDEO = AUDIOBOOK_DIR / "output" / "GelezinioVilkoSaga_Book1_YouTube.mp4"
BACKGROUND_MUSIC = AUDIOBOOK_DIR / "background.mp3"

def generate_video(audio_path, image_path, output_path, add_captions=False):
    """Generate YouTube video from audio and splash screen."""
    
    if not audio_path.exists():
        print(f"❌ Audio file not found: {audio_path}")
        print("   Run generate_complete_audiobook.py first!")
        return False
    
    if not image_path.exists():
        print(f"❌ Splash screen not found: {image_path}")
        print("   Generate the splash screen first!")
        return False
    
    print("🎬 Generating YouTube video...")
    print(f"   Audio: {audio_path.name}")
    print(f"   Image: {image_path.name}")
    print(f"   Output: {output_path.name}")
    
    # FFmpeg command to create video from audio + static image
    # We now also handle background music mixing here if it exists
    if BACKGROUND_MUSIC.exists():
        print(f"🎶 Mixing with background ambiance: {BACKGROUND_MUSIC.name}")
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", str(image_path),
            "-i", str(audio_path),
            "-stream_loop", "-1", "-i", str(BACKGROUND_MUSIC),
            "-filter_complex", 
            "[1:a]volume=1.0[narr];" +
            "[2:a]volume=0.04[bg];" + # Subtle background at 4%
            "[narr][bg]amix=inputs=2:duration=first:dropout_transition=2[outa]",
            "-map", "0:v",
            "-map", "[outa]",
            "-c:v", "libx264", "-tune", "stillimage",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p", "-shortest",
            str(output_path)
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", str(image_path),
            "-i", str(audio_path),
            "-c:v", "libx264", "-tune", "stillimage",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p", "-shortest",
            str(output_path)
        ]
    
    try:
        print("\n🎥 Running ffmpeg...")
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"\n✅ Video created: {output_path}")
        
        # Get video info
        probe_cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(output_path)
        ]
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
        info = json.loads(probe_result.stdout)
        
        duration = float(info['format']['duration'])
        size_mb = int(info['format']['size']) / (1024 * 1024)
        
        print(f"   Duration: {duration/60:.1f} minutes")
        print(f"   Size: {size_mb:.1f} MB")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"\n❌ FFmpeg error: {e}")
        print(f"   stderr: {e.stderr}")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

def generate_captions(audio_path, output_srt):
    """Generate SRT captions from audio using faster-whisper (Turbo)."""
    print("\n📝 Generating captions with faster-whisper (Turbo)...")
    
    try:
        from faster_whisper import WhisperModel
        
        print("   Loading faster-whisper turbo model...")
        # Auto-detect device (Mac: CPU/MPS, Linux: CUDA/CPU)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute_type = "float16" if device == "cuda" else "int8"
        
        model = WhisperModel("turbo", device=device, compute_type=compute_type)
        
        print(f"   Transcribing {audio_path.name}...")
        segments, info = model.transcribe(
            str(audio_path),
            beam_size=5,
            language="en",
            vad_filter=True,  # Voice activity detection for better accuracy
        )
        
        print(f"   Detected language: {info.language} (probability: {info.language_probability:.2f})")
        
        # Write SRT file
        with open(output_srt, 'w') as f:
            for i, segment in enumerate(segments, 1):
                start = format_timestamp(segment.start)
                end = format_timestamp(segment.end)
                text = segment.text.strip()
                
                f.write(f"{i}\n")
                f.write(f"{start} --> {end}\n")
                f.write(f"{text}\n\n")
        
        print(f"✅ Captions saved: {output_srt}")
        return True
        
    except ImportError:
        print("⚠️  faster-whisper not installed.")
        print("   Install with: pip install faster-whisper")
        print("   (Much faster than openai-whisper!)")
        return False
    except Exception as e:
        print(f"❌ Error generating captions: {e}")
        import traceback
        traceback.print_exc()
        return False

def format_timestamp(seconds):
    """Format seconds to SRT timestamp format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def add_captions_to_video(video_path, srt_path, output_path):
    """Burn captions into video."""
    print("\n🔥 Burning captions into video...")
    
    cmd = [
        "ffmpeg",
        "-i", str(video_path),
        "-vf", f"subtitles={srt_path}",
        "-c:a", "copy",
        "-y",
        str(output_path)
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"✅ Video with captions: {output_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error adding captions: {e}")
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate YouTube video from audiobook")
    parser.add_argument("--audio", type=str, default=str(AUDIO_FILE),
                       help="Path to audio file")
    parser.add_argument("--image", type=str, default=str(SPLASH_IMAGE),
                       help="Path to splash screen image")
    parser.add_argument("--output", type=str, default=str(OUTPUT_VIDEO),
                       help="Output video path")
    parser.add_argument("--captions", action="store_true",
                       help="Generate and add captions (requires faster-whisper)")
    parser.add_argument("--sequential", action="store_true",
                       help="Generate captions sequentially instead of parallel (slower)")
    
    args = parser.parse_args()
    
    caption_thread = None
    srt_path = Path(args.output).with_suffix('.srt')
    caption_result = [False]  # Use list to share state between threads
    
    # Start caption generation in parallel by default (unless --sequential)
    if args.captions and not args.sequential:
        print("🚀 Starting parallel caption generation...")
        def caption_worker():
            caption_result[0] = generate_captions(Path(args.audio), srt_path)
        
        caption_thread = threading.Thread(target=caption_worker)
        caption_thread.start()
    
    # Generate video
    success = generate_video(
        Path(args.audio),
        Path(args.image),
        Path(args.output),
        add_captions=args.captions
    )
    
    # Handle captions
    if success and args.captions:
        if not args.sequential:
            # Wait for parallel caption generation to complete
            print("\n⏳ Waiting for caption generation to complete...")
            caption_thread.join()
            
            if caption_result[0]:
                # Create version with burned-in captions
                captioned_output = Path(args.output).with_stem(
                    Path(args.output).stem + "_captioned"
                )
                add_captions_to_video(
                    Path(args.output),
                    srt_path,
                    captioned_output
                )
        else:
            # Sequential caption generation
            if generate_captions(Path(args.audio), srt_path):
                # Create version with burned-in captions
                captioned_output = Path(args.output).with_stem(
                    Path(args.output).stem + "_captioned"
                )
                add_captions_to_video(
                    Path(args.output),
                    srt_path,
                    captioned_output
                )
    
    if success:
        print("\n" + "="*60)
        print("✅ YOUTUBE VIDEO READY!")
        print("="*60)
        print(f"\n📹 Video: {args.output}")
        if args.captions and (caption_result[0] if not args.sequential else True):
            print(f"📝 Captions: {srt_path}")
            if Path(args.output).with_stem(Path(args.output).stem + "_captioned").exists():
                print(f"📹 With captions: {Path(args.output).with_stem(Path(args.output).stem + '_captioned')}")
        print("\n🎬 Ready to upload to YouTube!")
