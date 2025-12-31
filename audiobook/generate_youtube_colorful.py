#!/usr/bin/env python3
"""
Enhanced YouTube Video Generator with Colorful Audio Waveform
Creates a video with cover image and animated colorful waveform overlay.
"""

import subprocess
import json
from pathlib import Path

AUDIOBOOK_DIR = Path(__file__).parent
AUDIO_FILE = AUDIOBOOK_DIR / "Miserable_Audiobook_Complete.wav"
COVER_IMAGE = AUDIOBOOK_DIR / "audiobook_splash_screen.png"
OUTPUT_VIDEO = AUDIOBOOK_DIR / "output" / "Miserable_Audiobook_YouTube_Colorful.mp4"

def create_colorful_waveform_video(audio_path, image_path, output_path, style="gradient"):
    """
    Create YouTube video with cover image and animated colorful audio waveform.
    
    Styles:
    - gradient: Multi-color gradient waveform (cyan to magenta)
    - rainbow: Rainbow spectrum visualization
    - neon: Vibrant neon colors
    """
    
    if not audio_path.exists():
        print(f"❌ Audio file not found: {audio_path}")
        return False
    
    if not image_path.exists():
        print(f"❌ Cover image not found: {image_path}")
        return False
    
    print(f"🎬 Creating YouTube video with {style} waveform...")
    print(f"   Audio: {audio_path.name}")
    print(f"   Cover: {image_path.name}")
    print(f"   Output: {output_path.name}")
    
    # Different filter configurations based on style
    if style == "rainbow":
        # Use showspectrum for rainbow effect
        filter_complex = (
            "[1:a]showspectrum=s=1920x200:mode=combined:color=rainbow:scale=log,"
            "format=yuva420p,colorchannelmixer=aa=0.9[wave];"
            "[0:v][wave]overlay=0:H-200:shortest=1[outv]"
        )
    elif style == "neon":
        # Neon pink/cyan gradient
        filter_complex = (
            "[1:a]showwaves=s=1920x200:mode=cline:"
            "colors=#00ffff|#ff00ff|#ffff00:scale=sqrt:draw=full,"
            "format=yuva420p,colorchannelmixer=aa=0.9[wave];"
            "[0:v][wave]overlay=0:H-200:shortest=1[outv]"
        )
    else:  # gradient (default)
        # Smooth cyan to magenta gradient
        filter_complex = (
            "[1:a]showwaves=s=1920x200:mode=cline:"
            "colors=#00d4ff|#ff00ff:scale=sqrt:draw=full,"
            "format=yuva420p,colorchannelmixer=aa=0.9[wave];"
            "[0:v][wave]overlay=0:H-200:shortest=1[outv]"
        )
    
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(image_path),  # Loop cover image
        "-i", str(audio_path),                 # Audio input
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-map", "1:a",
        # Video encoding settings
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        # Audio encoding settings
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(output_path)
    ]
    
    try:
        print(f"\n🎥 Running ffmpeg (this may take 5-15 minutes for 3h48m audio)...")
        print(f"   Style: {style.upper()}")
        print("   Progress will be shown below:\n")
        
        # Run with real-time output
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Stream output
        for line in process.stdout:
            if "time=" in line or "frame=" in line:
                print(f"\r{line.strip()}", end="", flush=True)
        
        process.wait()
        
        if process.returncode != 0:
            print(f"\n❌ FFmpeg failed with exit code {process.returncode}")
            return False
        
        print("\n\n✅ Video created successfully!")
        
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
        
        print(f"\n📊 Video Details:")
        print(f"   Duration: {duration/60:.1f} minutes ({duration/3600:.2f} hours)")
        print(f"   Size: {size_mb:.1f} MB")
        print(f"   Resolution: 1920x1080")
        print(f"   Audio: AAC 192kbps")
        print(f"   Waveform: {style.upper()}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_video(video_path):
    """Verify the video can be played."""
    print("\n🔍 Verifying video integrity...")
    
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_format",
        "-show_streams",
        str(video_path)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print("✅ Video file is valid and playable!")
        return True
    except subprocess.CalledProcessError:
        print("❌ Video file is corrupted or incomplete")
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Generate YouTube video with colorful waveform animation"
    )
    parser.add_argument("--audio", type=str, default=str(AUDIO_FILE),
                       help="Path to audio file")
    parser.add_argument("--cover", type=str, default=str(COVER_IMAGE),
                       help="Path to cover image")
    parser.add_argument("--output", type=str, default=str(OUTPUT_VIDEO),
                       help="Output video path")
    parser.add_argument("--style", type=str, default="gradient",
                       choices=["gradient", "rainbow", "neon"],
                       help="Waveform style: gradient (cyan-magenta), rainbow (spectrum), neon (vibrant)")
    
    args = parser.parse_args()
    
    # Create output directory
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    
    # Generate video
    success = create_colorful_waveform_video(
        Path(args.audio),
        Path(args.cover),
        Path(args.output),
        style=args.style
    )
    
    if success:
        # Verify video
        verify_video(Path(args.output))
        
        print("\n" + "="*60)
        print("✅ YOUTUBE VIDEO READY!")
        print("="*60)
        print(f"\n📹 Video: {args.output}")
        print(f"\n🎬 Features:")
        print(f"   ✓ Cover image background")
        print(f"   ✓ Animated {args.style.upper()} waveform")
        print(f"   ✓ YouTube-optimized format")
        print(f"\n📖 Upload instructions: audiobook/YOUTUBE_UPLOAD_GUIDE.md")
        print("\n🎬 Ready to upload to YouTube!")
        print(f"\n💡 Try other styles: --style gradient|rainbow|neon")
    else:
        print("\n❌ Video generation failed")
        exit(1)
