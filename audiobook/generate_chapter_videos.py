#!/usr/bin/env python3
"""
Enhanced Batch Video Generator for Audiobook Chapters
Organizes videos into folders with accompanying YouTube metadata.
"""

import subprocess
import json
import os
import re
from pathlib import Path
from tqdm import tqdm

AUDIOBOOK_DIR = Path(__file__).parent
OUTPUT_DIR = AUDIOBOOK_DIR / "output"
UPLOADS_DIR = OUTPUT_DIR / "youtube_uploads"
BLOG_DIR = AUDIOBOOK_DIR.parent / "blog" / "src" / "content" / "blog"
COVER_IMAGE = AUDIOBOOK_DIR / "audiobook_splash_screen.png"

# Boilerplate for descriptions
BOILERPLATE_START = """🎧 Miserable: How to Fail at Life - The Complete Audiobook

This video is a chapter from the satirical guide to optimizing your existence for maximum despair.

Written and narrated by The Reverse Maven.
"""

BOILERPLATE_END = """
---
⚠️ DISCLAIMER: This audiobook is a work of satire. It is intended to reflect the absurdity of modern "grind culture" and toxic self-improvement. It is NOT actual advice. If you are struggling with your mental health, please reach out to professional services.

---
🌐 CONNECT & EXPLORE:
📝 Full Text & Blog: https://miserable.cloud/
📧 Contact: https://www.linkedin.com/in/asimplek/
🐦 Follow the Despair: Stay tuned for the Deluxe Edition.

📌 TAGS:
#Audiobook #Satire #SelfHelp #Comedy #Philosophy #ReverseMaven #MiserableCloud
"""

def get_blog_metadata(slug):
    """Attempt to find description from blog post."""
    # Find file matching the slug suffix
    matches = list(BLOG_DIR.glob(f"*{slug}.md"))
    if not matches:
        return None, None
    
    blog_file = matches[0]
    content = blog_file.read_text()
    
    # Extract title and description from frontmatter
    title_match = re.search(r'title: "(.*?)"', content)
    desc_match = re.search(r'description: "(.*?)"', content)
    
    title = title_match.group(1) if title_match else None
    desc = desc_match.group(1) if desc_match else None
    
    return title, desc

import shutil

def create_video_with_metadata(audio_path, image_path, chapter_dir):
    """Create video and description file in the chapter directory."""
    slug = audio_path.stem.split('_', 1)[-1] if '_' in audio_path.stem else audio_path.stem
    title, blog_desc = get_blog_metadata(slug)
    
    if not title:
        title = slug.replace('-', ' ').title()
    
    video_path = chapter_dir / f"{audio_path.stem}.mp4"
    desc_path = chapter_dir / "description.txt"
    old_video_path = OUTPUT_DIR / "chapter_videos" / f"{audio_path.stem}.mp4"
    
    # 1. Create Description
    full_desc = f"{BOILERPLATE_START}\n"
    if title:
        full_desc += f"📖 CHAPTER: {title}\n"
    if blog_desc:
        full_desc += f"\n{blog_desc}\n"
    full_desc += BOILERPLATE_END
    
    desc_path.write_text(full_desc)
    
    # 2. Handle Video
    if not video_path.exists():
        # Check if we can reuse an old video
        if old_video_path.exists():
            print(f"📦 Moving existing video: {old_video_path.name}")
            shutil.move(str(old_video_path), str(video_path))
            return True
        
        # Otherwise, Generate
        filter_complex = (
            "[1:a]showwaves=s=1920x150:mode=cline:colors=white:scale=sqrt:draw=full,"
            "format=yuva420p,colorchannelmixer=aa=0.8[wave];"
            "[0:v][wave]overlay=0:H-150:shortest=1[outv]"
        )
        
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", str(image_path),
            "-i", str(audio_path),
            "-filter_complex", filter_complex,
            "-map", "[outv]",
            "-map", "1:a",
            "-c:v", "libx264",
            "-preset", "faster",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(video_path)
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"\n❌ FFmpeg failed for {audio_path.name}: {e.stderr.decode()}")
            return False
    return True

def main():
    if not COVER_IMAGE.exists():
        print(f"❌ Cover image not found: {COVER_IMAGE}")
        return

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Get all chapter WAV files
    wav_files = sorted([f for f in OUTPUT_DIR.glob("*.wav") 
                       if any(f.name.startswith(s) for s in ["0", "1", "2", "3", "4", "5"]) or 
                          f.name == "99_outro.wav"])
    
    print(f"🎬 Processing {len(wav_files)} chapters for folder-based upload.")
    
    for wav_file in tqdm(wav_files, desc="Batch Processing Chapters"):
        chapter_slug = wav_file.stem
        chapter_dir = UPLOADS_DIR / chapter_slug
        chapter_dir.mkdir(parents=True, exist_ok=True)
        
        create_video_with_metadata(wav_file, COVER_IMAGE, chapter_dir)

    print(f"\n✅ All uploads ready in: {UPLOADS_DIR}")

if __name__ == "__main__":
    main()
