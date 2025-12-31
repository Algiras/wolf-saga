import json
import torchaudio as ta
import torch
import subprocess
from pathlib import Path
from tqdm import tqdm

# Paths
AUDIOBOOK_DIR = Path(__file__).parent
OUTPUT_DIR = AUDIOBOOK_DIR / "output"
# Final filenames aligned to Gelezinio Vilko Saga, Book I: Vilko Tremtis
FINAL_UNMASTERED = OUTPUT_DIR / "GelezinioVilkoSaga_Book1_Unmastered.wav"
FINAL_MASTERED = AUDIOBOOK_DIR / "GelezinioVilkoSaga_Book1_Complete.wav"
TIMESTAMPS_FILE = OUTPUT_DIR / "timestamps.txt"
BACKGROUND_MUSIC = AUDIOBOOK_DIR / "background.mp3" # User can place a "background.mp3" here

def format_timestamp(seconds):
    """Format seconds into HH:MM:SS or MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def concatenate_audiobook():
    """Concatenate chapters, generate timestamps, and apply mastering."""
    print("🎧 Stage 3: Concatenating and Mastering Audiobook...")
    
    # Load manifest to get proper titles
    manifest_path = AUDIOBOOK_DIR / "preprocessed" / "manifest.json"
    chapter_titles = {}
    if manifest_path.exists():
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
            chapter_titles = {f"{c['index']:02d}_{c['name']}.wav": c['name'].replace('-', ' ').title() for c in manifest}
    
    # Find all chapter WAV files
    wav_files = sorted(OUTPUT_DIR.glob("*.wav"))
    # Filter out intro/outro and ensure they are sorted correctly (00_intro, 01..., 99_outro)
    wav_files = [
        f for f in wav_files
        if f.name.endswith('.wav')
        and not f.name.startswith('ShadowOfExtremism')
        and not f.name.startswith('GelezinioVilkoSaga')
    ]
    
    if not wav_files:
        print("❌ No chapter files found!")
        return
    
    print(f"\n📚 Found {len(wav_files)} chapters to merge")
    
    all_audio = []
    sample_rate = None
    timestamps = []
    current_time = 0.0
    
    for wav_file in tqdm(wav_files, desc="Processing chapters"):
        try:
            waveform, sr = ta.load(str(wav_file))
            
            # Map filename to human readable title
            title = chapter_titles.get(wav_file.name, wav_file.stem.replace('_', ' ').title())
            if "Intro" in title: title = "Introduction"
            if "Outro" in title: title = "Conclusion"
            
            # Record timestamp
            timestamps.append(f"{format_timestamp(current_time)} {title}")
            
            # Update cumulative time
            duration = waveform.shape[1] / sr
            current_time += duration
            
            # Verify sample rate consistency
            if sample_rate is None:
                sample_rate = sr
            elif sr != sample_rate:
                resampler = ta.transforms.Resample(sr, sample_rate)
                waveform = resampler(waveform)
            
            all_audio.append(waveform)
            
        except Exception as e:
            print(f"❌ Error loading {wav_file.name}: {e}")
    
    if not all_audio:
        print("❌ No audio could be loaded!")
        return

    # 1. Save Timestamps
    with open(TIMESTAMPS_FILE, 'w') as f:
        f.write("\n".join(timestamps))
    print(f"📍 Timestamps generated: {TIMESTAMPS_FILE.name}")

    # 2. Concatenate
    print("\n🔗 Joining segments...")
    final_audio = torch.cat(all_audio, dim=1)
    ta.save(str(FINAL_UNMASTERED), final_audio, sample_rate)
    
    # 3. Mastering with FFmpeg (Normalizing + Optional Ambiance)
    print("\n🔊 Starting Professional Mastering Phase...")
    
    # Build FFmpeg command
    # Filter complex: 
    # 3. Mastering with FFmpeg (Normalizing ONLY)
    print("\n🔊 Starting Professional Mastering Phase...")
    
    loudnorm_filter = "loudnorm=I=-14:TP=-1.5:LRA=11"
    
    print("ℹ️  Normalizing narration to EBU R128 standard.")
    cmd = [
        "ffmpeg", "-y",
        "-i", str(FINAL_UNMASTERED),
        "-af", loudnorm_filter,
        "-c:a", "pcm_s16le",
        str(FINAL_MASTERED)
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        print("✅ Mastering complete! (EBU R128 Normalized)")
    except subprocess.CalledProcessError as e:
        print(f"❌ Mastering failed: {e.stderr.decode()}", flush=True)
        # Fallback: copy unmastered
        import shutil
        shutil.copy(FINAL_UNMASTERED, FINAL_MASTERED)
    
    print(f"\n✨ FINAL OUTPUT: {FINAL_MASTERED}", flush=True)
    print(f"📊 Duration: {format_timestamp(current_time)}", flush=True)

if __name__ == "__main__":
    concatenate_audiobook()
