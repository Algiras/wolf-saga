#!/usr/bin/env python3
import torch
from pathlib import Path
from chatterbox.tts_turbo import ChatterboxTurboTTS
from tts_helpers import generate_long_audio

def verify():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    # Force float32 globally to avoid CPU dtype mismatch (float != double)
    torch.set_default_dtype(torch.float32)
    print(f"🎙️ Using device: {device}")
    model = ChatterboxTurboTTS.from_pretrained(device=device)
    
    # Deep cast internal modules to float32 if on CPU
    if device == "cpu":
        for attr in ['t3', 've', 's3gen', 'vocoder']:
            if hasattr(model, attr):
                getattr(model, attr).to(torch.float32)
    
    text_path = Path("preprocessed/01_prologue.txt")
    output_path = Path("output/verification_chapter1.wav")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if not text_path.exists():
        print(f"❌ Error: {text_path} not found")
        return
        
    with open(text_path, 'r') as f:
        lines = f.readlines()
        # Limit to first 10 lines for QUICK verification (includes Kęstutis dialogue)
        text = "".join(lines[:10])
        
    print(f"🎵 Generating quick audio for: {text_path.name}")
    generate_long_audio(
        text, 
        model, 
        output_path, 
        chunk_size=250,
        silence_per_newline=0.3
    )
    print(f"✅ Sample generated: {output_path}")

if __name__ == "__main__":
    verify()
