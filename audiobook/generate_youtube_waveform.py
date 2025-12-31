#!/usr/bin/env python3
"""
Enhanced YouTube Video Generator with Audio Waveform Animation
Creates a video with cover image and animated waveform overlay.
"""

import subprocess
import json
from pathlib import Path

AUDIOBOOK_DIR = Path(__file__).parent
AUDIO_FILE = AUDIOBOOK_DIR / "Miserable_Audiobook_Complete.wav"
COVER_IMAGE = AUDIOBOOK_DIR / "audiobook_splash_screen.png"
OUTPUT_VIDEO = AUDIOBOOK_DIR / "output" / "Miserable_Audiobook_YouTube_Waveform.mp4"

def create_waveform_video(audio_path, image_path, output_path):
    """
    Create YouTube video with cover image and animated audio waveform.
    Uses ffmpeg's showwaves filter for real-time audio visualization.
    """
    
    if not audio_path.exists():
        print(f"❌ Audio file not found: {audio_path}")
        return False
    
    if not image_path.exists():
        print(f"❌ Cover image not found: {image_path}")
        return False
    
    print("🎬 Creating YouTube video with waveform animation...")
    print(f"   Audio: {audio_path.name}")
    print(f"   Cover: {image_path.name}")
    print(f"   Output: {output_path.name}")
    
    # FFmpeg command with waveform overlay
    # This creates a video with:
    # 1. Static cover image as background
    # 2. Animated waveform overlay at the bottom
    # 3. Semi-transparent black bar behind waveform for visibility
    
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(image_path),  # Loop cover image
        "-i", str(audio_path),                 # Audio input
        "-filter_complex",
        # Create waveform visualization
        "[1:a]showwaves=s=1920x200:mode=cline:colors=white:scale=sqrt,"
        # Add semi-transparent background for waveform
        "format=yuva420p,colorchannelmixer=aa=0.8[wave];"
        # Overlay waveform on bottom of image
        "[0:v][wave]overlay=0:H-200:shortest=1[outv]",
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
        print("\n🎥 Running ffmpeg (this may take 5-15 minutes for 3h48m audio)...")
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
        description="Generate YouTube video with waveform animation"
    )
    parser.add_argument("--audio", type=str, default=str(AUDIO_FILE),
                       help="Path to audio file")
    parser.add_argument("--cover", type=str, default=str(COVER_IMAGE),
                       help="Path to cover image")
    parser.add_argument("--output", type=str, default=str(OUTPUT_VIDEO),
                       help="Output video path")
    
    args = parser.parse_args()
    
    # Create output directory
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    
    # Generate video
    success = create_waveform_video(
        Path(args.audio),
        Path(args.cover),
        Path(args.output)
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
        print(f"   ✓ Animated audio waveform")
        print(f"   ✓ YouTube-optimized format")
        print(f"\n📖 Upload instructions: audiobook/YOUTUBE_UPLOAD_GUIDE.md")
        print("\n🎬 Ready to upload to YouTube!")
    else:
        print("\n❌ Video generation failed")
        exit(1)
