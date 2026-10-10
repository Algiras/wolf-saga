"""Stage 2: narrate preprocessed chapters with Chatterbox-Turbo.

Processes every chapter that is ready (preprocessed text matches the manifest hash)
and does not yet have up-to-date audio, then EXITS. Use --watch to keep polling
while Stage 1 is still producing chapters (generate_parallel.py does this).

Outputs are named by the stable chapter key: output/b1_03_gintaro_sapnas.wav, with a
sidecar output/<key>.meta.json recording the source hash the audio was made from.
"""
import argparse
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import book_manifest as bm

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


def build_voice_map(reference_audio=None):
    """Voice map for [Name] tags. Only voice files that exist are kept.

    reference_audio (optional) overrides the Narrator voice; otherwise
    reference_voice.wav next to this script is used when present.
    """
    base = Path(__file__).parent
    VOICE_DIR = base / "voices"
    VOICE_DIR.mkdir(exist_ok=True)

    narrator = Path(reference_audio) if reference_audio else base / "reference_voice.wav"

    voice_map = {
        "Narrator": narrator,
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

    active = {}
    for name, path in voice_map.items():
        if path.exists():
            active[name] = path
            logger.info(f"🎤 Loaded voice: {name} ({path.name})")
    return active


def select_pending(entries, only=None, force=False):
    """Chapters to narrate now, plus a status breakdown.

    A chapter is pending when its preprocessed text is ready and either there is
    no audio, the audio was made from an older source hash, or --force is given.
    """
    pending, waiting, done = [], [], []
    for e in entries:
        if only is not None and e["key"] not in only:
            continue
        if not bm.is_ready(e):
            waiting.append(e)          # Stage 1 has not produced current text yet
        elif not force and bm.audio_is_current(e):
            done.append(e)
        else:
            pending.append(e)
    return pending, waiting, done


def generate_audiobook(book=1, only=None, force=False, reference_audio=None,
                       watch=False, idle_timeout_min=30.0, device="cpu"):
    """Narrate the pending chapters of one book, then return (exit code semantics: True = ok)."""
    manifest_path = bm.MANIFEST_PATH
    if not manifest_path.exists():
        if not watch:
            logger.error("❌ No manifest.json found. Run Stage 1 first (1_preprocess_with_ollama.py).")
            return False
        logger.info("📡 Waiting for manifest.json from Stage 1...")
        while not manifest_path.exists():
            time.sleep(5)

    entries = bm.load_manifest(book)
    if not entries:
        logger.error(f"❌ No chapters for book {book} in the manifest.")
        return False

    if only is not None:
        known = {e["key"] for e in entries}
        resolved = set()
        for name in only:
            cand = name if name in known else f"b{book}_{name}"
            if cand not in known:
                logger.error(f"❌ Unknown chapter '{name}' for book {book}. Known: {', '.join(sorted(known))}")
                return False
            resolved.add(cand)
        only = resolved

    # Nothing to do? Avoid loading the model at all.
    pending, waiting, done = select_pending(entries, only, force)
    if not pending and not (watch and waiting):
        logger.info(f"✅ Nothing to narrate for book {book}: {len(done)} up to date, {len(waiting)} not yet preprocessed.")
        return True

    logger.info("🎙️  Initializing Multi-Voice Chatterbox-Turbo TTS...")
    import torch
    from chatterbox.tts_turbo import ChatterboxTurboTTS
    from tts_helpers import generate_long_audio

    # Force float32 globally to avoid CPU dtype mismatch (float != double)
    torch.set_default_dtype(torch.float32)

    if torch.cuda.is_available():
        device = "cuda"
    else:
        logger.warning("⚠️  CUDA not available, falling back to CPU")
        device = "cpu"

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
        return False

    active_voice_map = build_voice_map(reference_audio)
    default_voice = active_voice_map.get("Narrator")
    if not default_voice:
        logger.warning("⚠️  No Narrator voice found. Using default TTS voice.")

    bm.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    failed = set()
    last_progress = time.time()
    forced_done = set()  # with --force, narrate each selected chapter once per run

    while True:
        entries = bm.load_manifest(book)  # refresh: Stage 1 may still be writing it
        pending, waiting, done = select_pending(entries, only, force=False)
        if force:
            # --force: everything selected and ready is pending until done once this run
            pending = [e for e in entries
                       if (only is None or e["key"] in only) and bm.is_ready(e) and e["key"] not in forced_done]
        pending = [e for e in pending if e["key"] not in failed]

        for e in pending:
            key = e["key"]
            prepped = Path(e["file"])
            output_path = bm.audio_path(key)
            logger.info(f"\n📚 Narrating: {key} ({e.get('title', '')})")
            try:
                text = prepped.read_text(encoding="utf-8")
                generate_long_audio(
                    text, model, output_path,
                    voice_map=active_voice_map,
                    default_voice=default_voice,
                )
                bm.write_audio_meta(e, text)
                forced_done.add(key)
                last_progress = time.time()
            except Exception as ex:
                logger.error(f"❌ Error generating {key}: {ex}")
                failed.add(key)

        if not watch:
            break

        # Watch mode: stop when everything selected is narrated (or failed), or when idle too long
        remaining = [e for e in bm.load_manifest(book)
                     if (only is None or e["key"] in only) and e["key"] not in failed
                     and (not bm.is_ready(e) or (force and e["key"] not in forced_done)
                          or (not force and not bm.audio_is_current(e)))]
        if not remaining:
            break
        if time.time() - last_progress > idle_timeout_min * 60:
            logger.error(f"❌ No progress for {idle_timeout_min:.0f} min; giving up on: "
                         f"{', '.join(e['key'] for e in remaining)}")
            break
        if not pending:
            logger.info(f"🕒 Waiting for more preprocessed chapters... ({len(remaining)} remaining)")
            time.sleep(15)

    entries = bm.load_manifest(book)
    narrated = sum(1 for e in entries if bm.audio_is_current(e))
    logger.info(f"📊 Book {book}: {narrated}/{len(entries)} chapters have up-to-date audio"
                + (f"; failed: {', '.join(sorted(failed))}" if failed else ""))
    return not failed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate audiobook from preprocessed chapters")
    parser.add_argument("--book", type=int, default=1, help="Book number (default 1)")
    parser.add_argument("--device", default="cpu", choices=["cuda", "cpu"],
                        help="Device to use for TTS generation (CUDA is auto-detected)")
    parser.add_argument("--reference-audio", type=str, default=None,
                        help="Reference voice WAV for the Narrator (default: reference_voice.wav if present)")
    parser.add_argument("--only", type=str, default=None,
                        help="Comma-separated chapter keys to narrate, e.g. b1_03_gintaro_sapnas or 03_gintaro_sapnas")
    parser.add_argument("--force", action="store_true",
                        help="Re-narrate selected chapters even if up-to-date audio exists")
    parser.add_argument("--watch", action="store_true",
                        help="Keep polling for chapters Stage 1 is still producing; exit when all are narrated")
    parser.add_argument("--idle-timeout", type=float, default=30.0,
                        help="With --watch: give up after this many minutes without progress (default 30)")
    args = parser.parse_args()

    if args.reference_audio and not Path(args.reference_audio).exists():
        print(f"❌ Reference audio not found: {args.reference_audio}")
        sys.exit(1)

    only = [k.strip() for k in args.only.split(",") if k.strip()] if args.only else None
    ok = generate_audiobook(
        book=args.book, only=only, force=args.force, reference_audio=args.reference_audio,
        watch=args.watch, idle_timeout_min=args.idle_timeout, device=args.device,
    )
    sys.exit(0 if ok else 1)
