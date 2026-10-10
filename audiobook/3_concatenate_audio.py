import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import book_manifest as bm

# Paths
AUDIOBOOK_DIR = Path(__file__).parent
OUTPUT_DIR = bm.OUTPUT_DIR
BACKGROUND_MUSIC = AUDIOBOOK_DIR / "background.mp3" # User can place a "background.mp3" here

def format_timestamp(seconds):
    """Format seconds into HH:MM:SS or MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def collect_parts(book):
    """Ordered list of (title, wav_path) for one book: intro, chapters (manifest order), outro."""
    parts = []
    intro = OUTPUT_DIR / bm.intro_wav_name(book)
    if intro.exists():
        parts.append(("Introduction", intro))

    entries = bm.load_manifest(book)
    if not entries:
        print(f"⚠️  No manifest entries for book {book}; run Stage 1 first.")
    for e in entries:
        wav = bm.audio_path(e["key"])
        if wav.exists() and wav.stat().st_size > 1000:
            if not bm.audio_is_current(e):
                print(f"⚠️  {e['key']}: audio was made from an older version of the source; re-run Stage 2")
            parts.append((e["title"], wav))
        else:
            print(f"⚠️  Missing audio for {e['key']} ({e['title']}); skipping")

    outro = OUTPUT_DIR / bm.outro_wav_name(book)
    if outro.exists():
        parts.append(("Conclusion", outro))
    return parts

def concatenate_audiobook(book=1):
    """Concatenate chapters, generate timestamps, and apply mastering."""
    import torch
    import torchaudio as ta
    from tqdm import tqdm

    final_unmastered = OUTPUT_DIR / f"GelezinioVilkoSaga_Book{book}_Unmastered.wav"
    final_mastered = AUDIOBOOK_DIR / bm.master_wav_name(book)
    timestamps_file = OUTPUT_DIR / bm.timestamps_name(book)

    print(f"🎧 Stage 3: Concatenating and Mastering Audiobook (book {book})...")

    parts = collect_parts(book)
    if not parts:
        print("❌ No chapter files found!")
        return

    print(f"\n📚 Found {len(parts)} segments to merge")

    all_audio = []
    sample_rate = None
    timestamps = []
    current_time = 0.0

    for title, wav_file in tqdm(parts, desc="Processing chapters"):
        try:
            waveform, sr = ta.load(str(wav_file))

            # Verify sample rate consistency
            if sample_rate is None:
                sample_rate = sr
            elif sr != sample_rate:
                resampler = ta.transforms.Resample(sr, sample_rate)
                waveform = resampler(waveform)

            # Add 3 seconds of silence between chapters (before the timestamp is taken)
            if all_audio:
                silence_frames = int(sample_rate * 3.0)
                all_audio.append(torch.zeros((waveform.shape[0], silence_frames), dtype=waveform.dtype))
                current_time += 3.0

            # Record timestamp at the true start of this chapter
            timestamps.append(f"{format_timestamp(current_time)} {title}")
            current_time += waveform.shape[1] / sample_rate
            all_audio.append(waveform)

        except Exception as e:
            print(f"❌ Error loading {wav_file.name}: {e}")

    if not all_audio:
        print("❌ No audio could be loaded!")
        return

    # 1. Save Timestamps
    with open(timestamps_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(timestamps))
    print(f"📍 Timestamps generated: {timestamps_file.name}")

    # 2. Concatenate
    print("\n🔗 Joining segments...")
    final_audio = torch.cat(all_audio, dim=1)
    ta.save(str(final_unmastered), final_audio, sample_rate)
    
    # 3. Mastering with FFmpeg (Normalizing ONLY)
    print("\n🔊 Starting Professional Mastering Phase...")
    
    loudnorm_filter = "loudnorm=I=-14:TP=-1.5:LRA=11"
    
    print("ℹ️  Normalizing narration to EBU R128 standard.")
    cmd = [
        "ffmpeg", "-y",
        "-i", str(final_unmastered),
        "-af", loudnorm_filter,
        "-ar", str(sample_rate),   # loudnorm upsamples internally; restore the original rate
        "-c:a", "pcm_s16le",
        str(final_mastered)
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        print("✅ Mastering complete! (EBU R128 Normalized)")
    except subprocess.CalledProcessError as e:
        print(f"❌ Mastering failed: {e.stderr.decode()}", flush=True)
        # Fallback: copy unmastered
        import shutil
        shutil.copy(final_unmastered, final_mastered)
    
    print(f"\n✨ FINAL OUTPUT: {final_mastered}", flush=True)
    print(f"📊 Duration: {format_timestamp(current_time)}", flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage 3: concatenate chapter audio into the master file")
    parser.add_argument("--book", type=int, default=1, help="Book number (default 1)")
    args = parser.parse_args()
    concatenate_audiobook(book=args.book)
