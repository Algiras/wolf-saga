import json
import torch
import torchaudio as ta
import logging
import time
from pathlib import Path
from tqdm import tqdm
from chatterbox.tts_turbo import ChatterboxTurboTTS

# Force float32 globally to avoid CPU dtype mismatch (float != double)
torch.set_default_dtype(torch.float32)

PREPROCESSED_DIR = Path(__file__).parent / "preprocessed"
OUTPUT_DIR = Path(__file__).parent / "output"
LOG_FILE = Path(__file__).parent / "audio_generation.log"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def generate_audiobook(device="cpu"):
    """Generate the complete audiobook from preprocessed chapters with multi-voice support."""
    logger.info("🎙️  Initializing Multi-Voice Chatterbox-Turbo TTS...")
    
    # Check for GPU
    if torch.cuda.is_available():
        device = "cuda"
    else:
        logger.warning("⚠️  CUDA not available, falling back to CPU")
        device = "cpu"
    
    # Load model
    try:
        model = ChatterboxTurboTTS.from_pretrained(device=device)
        # Deep cast internal modules to float32 if on CPU
        if device == "cpu":
            for attr in ['t3', 've', 's3gen', 'vocoder']:
                if hasattr(model, attr):
                    getattr(model, attr).to(torch.float32)
        
        logger.info(f"✅ TTS Model loaded on {device}")
    except Exception as e:
        logger.error(f"❌ Failed to load TTS model: {e}")
        return
    
    # Voice Mapping
    VOICE_DIR = Path(__file__).parent / "voices"
    VOICE_DIR.mkdir(exist_ok=True)
    
    voice_map = {
        "Narrator": Path(__file__).parent / "reference_voice.wav",
        "Kęstutis": VOICE_DIR / "kestutis.wav",
        "Kestutis": VOICE_DIR / "kestutis.wav",
        "Vytautas": VOICE_DIR / "vytautas.wav",
        "Jogaila": VOICE_DIR / "jogaila.wav",
        "Skirgaila": VOICE_DIR / "skirgaila.wav",
        "Senior Envoy": VOICE_DIR / "envoy.wav",
        "Envoy": VOICE_DIR / "envoy.wav",
        "Pasiuntinys": VOICE_DIR / "envoy.wav",
        "Pasiuntiniai": VOICE_DIR / "envoy.wav",
        "Sargybinis": VOICE_DIR / "skirgaila.wav",
        "Guard": VOICE_DIR / "skirgaila.wav",
        "Kapitonas": VOICE_DIR / "skirgaila.wav",
        "Captain": VOICE_DIR / "skirgaila.wav",
        "Shadow-Seller": VOICE_DIR / "velnias.wav",
        "Amber Queen": VOICE_DIR / "zemyna.wav",
        "Perkūnas": VOICE_DIR / "perkunas.wav",
        "Perkunas": VOICE_DIR / "perkunas.wav",
        "Žemyna": VOICE_DIR / "zemyna.wav",
        "Zemyna": VOICE_DIR / "zemyna.wav",
        "Medeinė": VOICE_DIR / "medeine.wav",
        "Medeine": VOICE_DIR / "medeine.wav",
        "Velnias": VOICE_DIR / "velnias.wav",
        "Devil": VOICE_DIR / "velnias.wav",
        "Egle": VOICE_DIR / "medeine.wav",
        "Vaidilute": VOICE_DIR / "medeine.wav",
        "Birute": VOICE_DIR / "zemyna.wav",
        "Birutė": VOICE_DIR / "zemyna.wav",
    }
    
    # Filter only existing voice files
    active_voice_map = {}
    for name, path in voice_map.items():
        if path.exists():
            active_voice_map[name] = path
            logger.info(f"🎤 Loaded voice: {name} ({path.name})")
    
    default_voice = active_voice_map.get("Narrator")
    if not default_voice:
        logger.warning("⚠️  No Narrator voice found. Using default TTS voice.")

    # Load manifest
    manifest_path = PREPROCESSED_DIR / "manifest.json"
    chapters = []
    
    logger.info("📡 Waiting for manifest.json from Stage 1...")
    while not manifest_path.exists():
        time.sleep(5)
    
    try:
        with open(manifest_path, 'r') as f:
            chapters = json.load(f)
        logger.info(f"📋 Loaded manifest with {len(chapters)} chapters")
    except Exception as e:
        logger.error(f"❌ Error reading manifest: {e}")
        return
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    from tts_helpers import generate_long_audio
    
    while True:
        # Refresh manifest
        try:
            with open(manifest_path, 'r') as f:
                chapters = json.load(f)
        except:
            pass
            
        total_chapters = len(chapters)
        any_new = False
        completed_in_run = 0
        
        for chapter in chapters:
            output_path = OUTPUT_DIR / f"{chapter['index']:02d}_{chapter['name']}.wav"
            prepped_file = Path(chapter['file'])
            
            if output_path.exists() and output_path.stat().st_size > 1000:
                continue
                
            if not prepped_file.exists() or prepped_file.stat().st_size < 10:
                continue
            
            logger.info(f"\n📚 Narrating: {chapter['name']}")
            try:
                with open(prepped_file, 'r') as f:
                    text = f.read()
                
                generate_long_audio(
                    text, model, output_path,
                    voice_map=active_voice_map,
                    default_voice=default_voice
                )
                any_new = True
                completed_in_run += 1
            except Exception as e:
                logger.error(f"❌ Error generating {chapter['name']}: {e}")
        
        # Check progress
        current_wavs = list(OUTPUT_DIR.glob("*.wav"))
        completed_count = len([w for w in current_wavs if w.stat().st_size > 1000])
        
        # Continue waiting for more chapters
        if not any_new:
            logger.info(f"🕒 Waiting for more preprocessed chapters... ({completed_count}/{total_chapters})")
            time.sleep(15)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate audiobook from preprocessed chapters")
    parser.add_argument("--device", default="cpu", choices=["cuda", "cpu"], 
                       help="Device to use for TTS generation")
    args = parser.parse_args()
    
    generate_audiobook(device=args.device)
