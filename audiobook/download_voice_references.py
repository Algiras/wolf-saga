#!/usr/bin/env python3
"""
Downloads and trims character voice reference samples from YouTube.
Uses yt-dlp and ffmpeg to extract specific segments as WAV.
"""

import os
import subprocess
import json
from pathlib import Path

VOICE_DIR = Path(__file__).parent / "voices"
VOICE_DIR.mkdir(exist_ok=True)

# Define voice references from implementation plan
VOICE_REFERENCES = [
    {"name": "narrator", "url": "https://www.youtube.com/watch?v=XrfLgD3Hu6M", "start": "00:00:45", "duration": "30"},
    {"name": "kestutis", "url": "https://www.youtube.com/watch?v=lR-Qx64jPrU", "start": "00:00:30", "duration": "30"},
    {"name": "vytautas", "url": "https://www.youtube.com/watch?v=SVQTZFlXYvk", "start": "00:01:10", "duration": "30"},
    {"name": "jogaila", "url": "https://www.youtube.com/watch?v=0Rb97M4Ymdw", "start": "00:05:00", "duration": "30"},
    {"name": "envoy", "url": "https://www.youtube.com/watch?v=LthvwXA183c", "start": "00:00:45", "duration": "30"},
    {"name": "perkunas", "url": "https://www.youtube.com/watch?v=QNrs0j-5eSw", "start": "00:03:00", "duration": "30"},
    {"name": "zemyna", "url": "https://www.youtube.com/watch?v=kS4nYwmw5fQ", "start": "00:02:00", "duration": "30"},
    {"name": "medeine", "url": "https://www.youtube.com/watch?v=ivVHmLq2TnA", "start": "00:00:20", "duration": "30"},
    {"name": "velnias", "url": "https://www.youtube.com/watch?v=YoVQ5bT1vrg", "start": "00:00:45", "duration": "30"},
    {"name": "skirgaila", "url": "https://www.youtube.com/watch?v=tg4Ks2qSg7U", "start": "00:10:00", "duration": "30"},
]

def download_voice(voice):
    name = voice["name"]
    url = voice["url"]
    start = voice["start"]
    duration = voice["duration"]
    output_wav = VOICE_DIR / f"{name}.wav"
    temp_mp3 = VOICE_DIR / f"{name}_temp.mp3"

    if output_wav.exists():
        print(f"✅ Voice already exists: {name}")
        return

    print(f"🎬 Downloading {name} voice from {url}...")
    
    # Use yt-dlp to get the audio URL and ffmpeg to trim directly
    # This avoids downloading the whole video
    try:
        # Get direct audio URL
        cmd_get_url = ["yt-dlp", "-f", "ba", "-g", url]
        direct_url = subprocess.check_output(cmd_get_url).decode().strip()
        
        # Trim and convert to 24kHz mono WAV (ideal for Chatterbox)
        cmd_ffmpeg = [
            "ffmpeg", "-y", "-ss", start, "-t", duration, 
            "-i", direct_url, 
            "-ar", "24000", "-ac", "1", 
            str(output_wav)
        ]
        subprocess.run(cmd_ffmpeg, check=True, capture_output=True)
        print(f"   ✨ Created {output_wav}")
    except Exception as e:
        print(f"   ❌ Failed to download {name}: {e}")

if __name__ == "__main__":
    for voice in VOICE_REFERENCES:
        download_voice(voice)
    print("\n🎉 Voice reference download complete!")
