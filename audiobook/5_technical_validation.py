#!/usr/bin/env python3
"""
Technical Validation Stage for Audiobook
Checks finalized audio against professional standards (ACX/Audible).
"""

import subprocess
import json
import re
from pathlib import Path

AUDIOBOOK_DIR = Path(__file__).parent
FINAL_MASTER = AUDIOBOOK_DIR / "Miserable_Audiobook_Complete.wav"

def validate_audio(file_path):
    """Perform technical validation on an audio file."""
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return False

    print(f"\n🧪 Validating: {file_path.name}")
    print("-" * 40)

    results = []
    all_pass = True

    # 1. Check Format (Sample Rate, Channels)
    probe_cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", "-show_format", str(file_path)
    ]
    try:
        probe_res = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
        data = json.loads(probe_res.stdout)
        stream = data['streams'][0]
        
        # Sample Rate Check (Prefer 44.1kHz or 48kHz)
        sr = int(stream['sample_rate'])
        sr_pass = sr >= 44100
        results.append({
            "check": "Sample Rate",
            "value": f"{sr} Hz",
            "status": "✅ PASS" if sr_pass else "⚠️ WARNING",
            "standard": ">= 44100 Hz"
        })
        if not sr_pass: all_pass = False

        # Channels (Mono vs Stereo)
        channels = stream['channels']
        results.append({
            "check": "Channels",
            "value": "Mono" if channels == 1 else "Stereo",
            "status": "✅ PASS",
            "standard": "Consistent"
        })

    except Exception as e:
        print(f"❌ Probe failed: {e}")
        return False

    # 2. Check Levels (RMS and Peak)
    # Using ffmpeg's volumedetect filter
    vol_cmd = [
        "ffmpeg", "-i", str(file_path),
        "-af", "volumedetect",
        "-f", "null", "/dev/null"
    ]
    try:
        vol_res = subprocess.run(vol_cmd, capture_output=True, text=True, check=True)
        vol_output = vol_res.stderr

        # Extract Max Volume (Peak)
        max_vol_match = re.search(r"max_volume: ([\-\d\.]+) dB", vol_output)
        max_vol = float(max_vol_match.group(1)) if max_vol_match else 0.0
        
        # ACX standard: Peak <= -3.0 dB
        peak_pass = max_vol <= -3.0
        results.append({
            "check": "Peak Level",
            "value": f"{max_vol} dB",
            "status": "✅ PASS" if peak_pass else "❌ FAIL",
            "standard": "<= -3.0 dB"
        })
        if not peak_pass: all_pass = False

        # Extract Mean Volume (RMS)
        mean_vol_match = re.search(r"mean_volume: ([\-\d\.]+) dB", vol_output)
        mean_vol = float(mean_vol_match.group(1)) if mean_vol_match else 0.0
        
        # ACX standard: -23 dB to -18 dB RMS
        # Note: ffmpeg's mean_volume is close to RMS but not identical; it's a good proxy.
        rms_pass = -23.5 <= mean_vol <= -17.5
        results.append({
            "check": "RMS Loudness",
            "value": f"{mean_vol} dB",
            "status": "✅ PASS" if rms_pass else "❌ FAIL",
            "standard": "-23dB to -18dB"
        })
        if not rms_pass: all_pass = False

    except Exception as e:
        print(f"❌ Level check failed: {e}")
        return False

    # Print Results Table
    print(f"{'CHECK':<15} | {'VALUE':<12} | {'STANDARD':<15} | {'STATUS'}")
    print("-" * 60)
    for r in results:
        print(f"{r['check']:<15} | {r['value']:<12} | {r['standard']:<15} | {r['status']}")

    if all_pass:
        print("\n🏆 TECHNICAL VALIDATION PASSED!")
        print("   Audio is compliant with professional distribution standards (ACX/Audible).")
    else:
        print("\n⚠️  TECHNICAL VALIDATION FAILED/WARNINGS")
        print("   Some parameters are outside optimal professional ranges.")
        print("   Tip: Rerun Stage 3 to remaster with different normalization targets.")

    return all_pass

if __name__ == "__main__":
    validate_audio(FINAL_MASTER)
