#!/usr/bin/env python3
"""
Helper functions for TTS chunking
"""

import json
import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# torch / torchaudio are imported lazily inside generate_long_audio so that this
# module (and the loudness helper) can be used without loading the TTS stack.

# Per-chapter loudness target (EBU R128), matches the master's normalisation.
LOUDNORM_I = -14.0
LOUDNORM_TP = -1.5
LOUDNORM_LRA = 11.0


def _probe_sample_rate(path, default=24000):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=sample_rate", "-of", "default=nw=1:nk=1", str(path)],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return int(out)
    except Exception:
        return default


def loudnorm_wav(path, i=LOUDNORM_I, tp=LOUDNORM_TP, lra=LOUDNORM_LRA):
    """EBU R128 loudness-normalise a WAV in place (two-pass, falls back to one pass).

    Daily per-chapter uploads need consistent loudness, so every chapter output is
    normalised on its own. loudnorm upsamples internally, so the original sample
    rate is restored with -ar. Returns True on success; on any ffmpeg failure the
    original file is left untouched and False is returned.
    """
    path = Path(path)
    sr = _probe_sample_rate(path)
    base_filter = f"loudnorm=I={i}:TP={tp}:LRA={lra}"

    # Pass 1: measure
    measured = None
    try:
        res = subprocess.run(
            ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
             "-af", base_filter + ":print_format=json", "-f", "null", "-"],
            capture_output=True, text=True, check=True,
        )
        blocks = re.findall(r"\{[^{}]*\}", res.stderr, flags=re.DOTALL)
        if blocks:
            data = json.loads(blocks[-1])
            if all(k in data for k in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")) \
                    and data["input_i"] not in ("-inf", "inf"):
                measured = data
    except Exception as e:
        logger.warning(f"loudnorm measure pass failed for {path.name}: {e}")

    if measured:
        af = (f"{base_filter}:measured_I={measured['input_i']}:measured_TP={measured['input_tp']}"
              f":measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}"
              f":offset={measured['target_offset']}:linear=true")
    else:
        af = base_filter  # single-pass fallback

    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.stem + ".", suffix=".norm.wav")
    os.close(fd)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(path),
             "-af", af, "-ar", str(sr), "-c:a", "pcm_s16le", tmp],
            capture_output=True, text=True, check=True,
        )
        os.replace(tmp, path)
        logger.info(f"loudnorm ({'two' if measured else 'single'}-pass) applied: {path.name}")
        return True
    except Exception as e:
        logger.warning(f"loudnorm failed for {path.name}, keeping un-normalised audio: {e}")
        if os.path.exists(tmp):
            os.unlink(tmp)
        return False

def chunk_text(text, max_chars=250):
    """Split text into chunks at natural boundaries (paragraphs/sentences)."""
    chunks = []
    paragraphs = text.split('\n\n')
    
    current_chunk = []
    current_size = 0
    
    for para in paragraphs:
        para_size = len(para)
        
        # If single paragraph is too long, split by sentences
        if para_size > max_chars:
            sentences = para.split('. ')
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue
                    
                # Add period back if it was removed
                if not sentence.endswith('.') and not sentence.endswith('[pause]'):
                    sentence += '.'
                
                sent_size = len(sentence)
                
                if current_size + sent_size > max_chars and current_chunk:
                    chunks.append('\n\n'.join(current_chunk))
                    current_chunk = [sentence]
                    current_size = sent_size
                else:
                    current_chunk.append(sentence)
                    current_size += sent_size
        else:
            if current_size + para_size > max_chars and current_chunk:
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = [para]
                current_size = para_size
            else:
                current_chunk.append(para)
                current_size += para_size
    
    if current_chunk:
        chunks.append('\n\n'.join(current_chunk))
    
    return chunks

def generate_long_audio(text, model, output_path, chunk_size=250, silence_per_newline=0.3, voice_map=None, default_voice=None, audio_prompt_path=None, loudnorm=True):
    """Generate audio for long text by chunking and concatenating, with dynamic voice switching.
    
    Args:
        text: Text to generate audio for
        model: ChatterboxTurboTTS model
        output_path: Path to save output WAV file
        chunk_size: Maximum characters per chunk
        silence_per_newline: Seconds of silence per newline
        voice_map: Dictionary mapping [Name] to voice reference WAV files
        default_voice: Default voice path if no tag is present or found
        audio_prompt_path: Shortcut for a single reference voice (backward-compatible)
        loudnorm: Apply per-file EBU R128 normalisation (I=-14, TP=-1.5, LRA=11) after saving
    """
    import torch
    import torchaudio as ta

    # Force float32 for CPU stability
    torch.set_default_dtype(torch.float32)
    
    # Split text by newlines to insert silence
    lines = text.split('\n')
    
    logger.info(f"Processing {len(lines)} lines with silence insertion and voice switching")
    
    all_audio = []
    sample_rate = model.sr
    
    # Create silence tensor
    silence_samples = int(sample_rate * silence_per_newline)
    silence = torch.zeros(1, silence_samples, dtype=torch.float32)
    
    # Prefer explicit prompt if provided, otherwise fall back to legacy default voice
    current_voice = audio_prompt_path or default_voice
    voice_map = voice_map or {}
    
    for i, line in enumerate(lines):
        line = line.strip()
        
        # Skip empty lines but add silence for them
        if not line:
            if i > 0:
                all_audio.append(silence)
            continue
        
        # Detect voice switching tag: [Name]
        tag_match = re.match(r'^\[([^\]]+)\](.*)', line)
        if tag_match:
            voice_name = tag_match.group(1).strip()
            line = tag_match.group(2).strip()
            
            # Switch voice if in map
            if voice_name in voice_map:
                current_voice = voice_map[voice_name]
                logger.info(f"🎙️ Switching to voice: {voice_name}")
            else:
                # If not in map, maybe it's just a tag to skip or use default
                pass
            
            # If line is now empty (just a tag line), just update voice and continue
            if not line:
                continue
        else:
            # Fallback: treat a lone capitalized name (optionally with trailing colon) as a speaker cue
            name_only = re.match(r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*:?$' , line)
            if name_only:
                voice_name = name_only.group(1).strip()
                if voice_name in voice_map:
                    current_voice = voice_map[voice_name]
                    logger.info(f"🎙️ Switching to voice: {voice_name} (implicit tag)")
                    continue

        # Process the (possibly cleaned) line
        # If line is too long, chunk it
        if len(line) > chunk_size:
            chunks = chunk_text(line, max_chars=chunk_size)
            logger.info(f"Line {i+1} ({current_voice.name if hasattr(current_voice, 'name') else 'default'}): {len(chunks)} chunks")
            
            for j, chunk in enumerate(chunks):
                try:
                    wav = model.generate(chunk, audio_prompt_path=str(current_voice) if current_voice else None, norm_loudness=False)
                    all_audio.append(wav.to(torch.float32))
                except Exception as e:
                    import traceback
                    print(f"   ⚠️  Error on line {i+1}, chunk {j+1}: {e}")
                    traceback.print_exc()
                    continue
        else:
            # Generate audio for the line
            try:
                wav = model.generate(line, audio_prompt_path=str(current_voice) if current_voice else None, norm_loudness=False)
                all_audio.append(wav.to(torch.float32))
            except Exception as e:
                import traceback
                print(f"   ⚠️  Error on line {i+1}: {e}")
                traceback.print_exc()
                continue
        
        # Add silence after each line
        if i < len(lines) - 1:
            all_audio.append(silence)
    
    if not all_audio:
        raise Exception("No audio segments were generated successfully")
    
    # Concatenate all audio segments
    final_audio = torch.cat(all_audio, dim=1)
    
    # PEAK NORMALIZATION: Boost the signal so it is audible
    max_val = final_audio.abs().max()
    if max_val > 0:
        print(f"   🔊 Normalizing audio (current peak: {max_val.item():.4f})")
        final_audio = final_audio / max_val * 0.9
    else:
        print("   ⚠️  Warning: Generated audio is completely silent!")

    # Save as 16-bit PCM
    ta.save(str(output_path), final_audio, sample_rate, encoding="PCM_S", bits_per_sample=16)

    # Per-chapter loudness (the master is normalised again in stage 3)
    if loudnorm:
        loudnorm_wav(output_path)

    duration = final_audio.shape[1] / sample_rate
    print(f"   ✅ Generated {duration:.1f}s of audio with {len(all_audio)} segments")
    
    return final_audio
