#!/usr/bin/env python3
"""
Normalize all voice reference files to consistent loudness and remove background noise.
"""

import numpy as np
import soundfile as sf
from pathlib import Path
from scipy import signal

def normalize_audio(audio, target_rms_db=-20.0):
    """Normalize audio to target RMS level."""
    # Calculate current RMS
    rms = np.sqrt(np.mean(audio**2))
    
    if rms == 0:
        return audio
    
    # Convert target from dB to linear
    target_rms = 10 ** (target_rms_db / 20)
    
    # Calculate gain
    gain = target_rms / rms
    
    # Apply gain
    normalized = audio * gain
    
    # Prevent clipping
    peak = np.max(np.abs(normalized))
    if peak > 0.95:
        normalized = normalized * (0.95 / peak)
    
    return normalized

def remove_noise(audio, sr, noise_threshold=-40):
    """Simple noise gate to remove background noise."""
    # Calculate RMS in small windows
    window_size = int(sr * 0.02)  # 20ms windows
    hop_size = window_size // 2
    
    # Pad audio
    padded = np.pad(audio, (0, window_size), mode='constant')
    
    # Calculate windowed RMS
    rms_values = []
    for i in range(0, len(padded) - window_size, hop_size):
        window = padded[i:i+window_size]
        rms = np.sqrt(np.mean(window**2))
        rms_values.append(rms)
    
    # Convert to dB
    rms_db = 20 * np.log10(np.array(rms_values) + 1e-10)
    
    # Create gate mask
    gate_mask = rms_db > noise_threshold
    
    # Expand mask to match audio length
    mask = np.repeat(gate_mask, hop_size)[:len(audio)]
    
    # Apply smooth gate
    from scipy.ndimage import gaussian_filter1d
    smooth_mask = gaussian_filter1d(mask.astype(float), sigma=sr//100)
    
    return audio * smooth_mask

def process_voice_file(input_path, output_path, target_rms_db=-20.0):
    """Process a single voice file."""
    print(f"Processing: {input_path.name}")
    
    # Read audio
    audio, sr = sf.read(input_path)
    
    # Convert to mono if stereo
    if len(audio.shape) > 1:
        audio = np.mean(audio, axis=1)
    
    # Remove noise
    audio = remove_noise(audio, sr, noise_threshold=-45)
    
    # Normalize loudness
    audio = normalize_audio(audio, target_rms_db)
    
    # Calculate stats
    rms = np.sqrt(np.mean(audio**2))
    rms_db = 20 * np.log10(rms) if rms > 0 else -np.inf
    peak = np.max(np.abs(audio))
    peak_db = 20 * np.log10(peak) if peak > 0 else -np.inf
    
    print(f"  → RMS: {rms_db:.2f} dB | Peak: {peak_db:.2f} dB")
    
    # Write normalized audio
    sf.write(output_path, audio, sr)

def main():
    voices_dir = Path("voices")
    backup_dir = Path("voices_backup")
    
    # Create backup
    if not backup_dir.exists():
        print("📦 Creating backup of original voices...")
        backup_dir.mkdir()
        for voice_file in voices_dir.glob("*.wav"):
            import shutil
            shutil.copy2(voice_file, backup_dir / voice_file.name)
        
        # Backup reference voice too
        ref_voice = Path("reference_voice.wav")
        if ref_voice.exists():
            shutil.copy2(ref_voice, backup_dir / "reference_voice.wav")
        print("✅ Backup created in voices_backup/")
    
    print("\n🎙️ Normalizing voice references...\n")
    
    # Process all voice files
    target_rms = -20.0  # Target RMS level in dB
    
    for voice_file in sorted(voices_dir.glob("*.wav")):
        process_voice_file(voice_file, voice_file, target_rms)
    
    # Process reference voice
    ref_voice = Path("reference_voice.wav")
    if ref_voice.exists():
        process_voice_file(ref_voice, ref_voice, target_rms)
    
    print(f"\n✅ All voices normalized to {target_rms} dB RMS")
    print("📊 Backup saved in voices_backup/")

if __name__ == "__main__":
    main()
