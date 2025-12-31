# Geležinio Vilko Saga Parallel Queue Pipeline
# Streams chapters through Preprocessing -> Audio -> Captions simultaneously.

import threading
import queue
import time
import sys
import json
from pathlib import Path
from tqdm import tqdm
import torch

# Add current dir to path
sys.path.insert(0, str(Path(__file__).parent))

# Import logic from existing scripts
from tts_helpers import generate_long_audio
from chatterbox.tts_turbo import ChatterboxTurboTTS

# These will be imported inside workers to avoid conflicts
# from 1_preprocess_with_ollama import NarrationMemory, preprocess_chapter, load_quarto_config, get_chapters_from_config, build_context_summary
# from 4_generate_youtube_video import generate_captions

AUDIOBOOK_DIR = Path(__file__).parent
OUTPUT_DIR = AUDIOBOOK_DIR / "output"
PREPROCESSED_DIR = AUDIOBOOK_DIR / "preprocessed"
TRANSCRIPTS_DIR = AUDIOBOOK_DIR / "transcripts"

class PipelineManager:
    def __init__(self, reference_audio=None):
        self.reference_audio = Path(reference_audio) if reference_audio else None
        self.tts_queue = queue.Queue()
        self.caption_queue = queue.Queue()
        self.done_queue = queue.Queue()
        self.stop_signal = threading.Event()
        
        # Directories
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        PREPROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

    async def preprocessor_worker_async(self):
        """Stage 1: LLM Preprocessing (Sequential due to RAG)"""
        print("🧠 Preprocessor: Initializing ReAct Agent & MCP...", flush=True)
        # Use __import__ for modules starting with numbers
        preprocess_mod = __import__('1_preprocess_with_ollama')
        NarrationMemory = preprocess_mod.NarrationMemory
        MCPManager = preprocess_mod.MCPManager
        preprocess_chapter = preprocess_mod.preprocess_chapter
        load_quarto_config = preprocess_mod.load_quarto_config
        get_ordered_chapters = preprocess_mod.get_ordered_chapters
        build_context_summary = preprocess_mod.build_context_summary
        MCP_CONFIG_PATH = preprocess_mod.MCP_CONFIG_PATH
        
        config = load_quarto_config()
        all_chapters = get_ordered_chapters(config)
        self.total_chapters = len(all_chapters)
        
        # Initialize MCP and Memory
        mcp_manager = MCPManager(MCP_CONFIG_PATH)
        await mcp_manager.connect_all()
        memory = NarrationMemory()
        
        # Pre-generate manifest for Stage 3/4
        manifest_chapters = []
        for chapter_index, (chapter_file, chapter_name) in enumerate(all_chapters):
            output_file = PREPROCESSED_DIR / f"{chapter_index:02d}_{chapter_name}.txt"
            manifest_chapters.append({
                'index': chapter_index,
                'name': chapter_name,
                'file': str(output_file)
            })
        
        manifest_file = PREPROCESSED_DIR / "manifest.json"
        with open(manifest_file, 'w') as f:
            json.dump(manifest_chapters, f, indent=2)
            
        print(f"📖 Preprocessor: Starting work on {self.total_chapters} chapters...", flush=True)
        
        try:
            for i, (chapter_file, chapter_name) in enumerate(all_chapters):
                if self.stop_signal.is_set(): break
                
                prev_context, next_context = build_context_summary(all_chapters, i, window=2)
                narrated_text = await preprocess_chapter(
                    chapter_file, 
                    chapter_name, 
                    mcp_manager,
                    previous_context=prev_context, 
                    next_context=next_context, 
                    memory=memory
                )
                
                if narrated_text:
                    prepped_path = PREPROCESSED_DIR / f"{i:02d}_{chapter_name}.txt"
                    with open(prepped_path, 'w') as f:
                        f.write(narrated_text)
                    
                    # Push to TTS
                    self.tts_queue.put({
                        'index': i,
                        'name': chapter_name,
                        'file': str(prepped_path),
                        'text': narrated_text
                    })
                else:
                    print(f"   ⚠️ Preprocessor: Skipping {chapter_name} (Empty/Failed)", flush=True)
        finally:
            await mcp_manager.disconnect_all()
        
        # Signal TTS that we are done
        self.tts_queue.put(None)
        print("✅ Preprocessor: Finished all chapters.", flush=True)

    def preprocessor_worker(self):
        """Wrapper for async worker."""
        import asyncio
        asyncio.run(self.preprocessor_worker_async())

    def audio_worker(self):
        """Stage 2: TTS Generation (Sequential to save VRAM)"""
        print("🎙️ Audio: Initializing Chatterbox-Turbo...", flush=True)
        from chatterbox.tts_turbo import ChatterboxTurboTTS
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = ChatterboxTurboTTS.from_pretrained(device=device)
        
        while not self.stop_signal.is_set():
            task = self.tts_queue.get()
            if task is None: break # End signal
            
            i, name, text = task['index'], task['name'], task['text']
            output_wav = OUTPUT_DIR / f"{i:02d}_{name}.wav"
            
            if not output_wav.exists():
                print(f"🎵 Audio: Narrating Chapter {i}: {name}...", flush=True)
                try:
                    generate_long_audio(
                        text, model, output_wav, 
                        chunk_size=250, silence_per_newline=0.3,
                        audio_prompt_path=self.reference_audio
                    )
                except Exception as e:
                    print(f"❌ Audio Error {name}: {e}", flush=True)
            else:
                print(f"   ✓ Audio: {name} already exists.", flush=True)
            
            # Push to Captions
            self.caption_queue.put({
                'index': i,
                'name': name,
                'wav': str(output_wav)
            })
            self.tts_queue.task_done()
            
        self.caption_queue.put(None)
        del model
        if torch.cuda.is_available(): torch.cuda.empty_cache()
        print("✅ Audio: Finished all tasks.", flush=True)

    def caption_worker(self):
        """Stage 3: Whisper Transcription (Parallel with Audio)"""
        print("📝 Captioner: Waiting for audio files...", flush=True)
        video_mod = __import__('4_generate_youtube_video')
        generate_captions = video_mod.generate_captions
        
        while not self.stop_signal.is_set():
            task = self.caption_queue.get()
            if task is None: break
            
            i, name, wav = task['index'], task['name'], task['wav']
            output_srt = TRANSCRIPTS_DIR / f"{i:02d}_{name}.srt"
            
            if not output_srt.exists():
                print(f"📝 Captioner: Transcribing {name}...", flush=True)
                generate_captions(Path(wav), output_srt)
            else:
                print(f"   ✓ Captioner: {name} already exists.", flush=True)
                
            self.done_queue.put(task)
            self.caption_queue.task_done()
            
        print("✅ Captioner: Finished all transcripts.", flush=True)

    def run(self):
        print("\n" + "🚀" * 30)
        print("SAGA PARALLEL STREAMING PIPELINE")
        print("🚀" * 30 + "\n")
        
        start_time = time.time()
        
        # Start workers
        t1 = threading.Thread(target=self.preprocessor_worker)
        t2 = threading.Thread(target=self.audio_worker)
        t3 = threading.Thread(target=self.caption_worker)
        
        t1.start()
        t2.start()
        t3.start()
        
        # Wait for all to finish
        t1.join()
        t2.join()
        t3.join()
        
        end_time = time.time()
        print(f"\n✨ Parallel Generation Complete in {(end_time - start_time)/60:.1f} minutes!")
        
        # Step 4: Combine Everything
        self.assemble_final_product()

    def assemble_final_product(self):
        print("\n" + "="*60)
        print("STAGE 4: FINAL ASSEMBLY (Concatenation & Video)")
        print("="*60 + "\n")
        
        concat_mod = __import__('3_concatenate_audio')
        video_mod = __import__('4_generate_youtube_video')
        
        concatenate_audiobook = concat_mod.concatenate_audiobook
        generate_video = video_mod.generate_video
        add_captions_to_video = video_mod.add_captions_to_video
        
        # 1. Concatenate Audio
        concatenate_audiobook()
        
        # 2. Merge SRTs (This is new logic)
        self.merge_srt_files()
        
        # 3. Build Video (Background mixing is already in Stage 4 script)
        master_audio = AUDIOBOOK_DIR / "GelezinioVilkoSaga_Book1_Complete.wav"
        splash = AUDIOBOOK_DIR.parent / "books" / "1" / "cover.png"
        video_out = OUTPUT_DIR / "GelezinioVilkoSaga_Book1_YouTube.mp4"
        
        if generate_video(master_audio, splash, video_out):
            # 4. Burn in Captions
            final_srt = OUTPUT_DIR / "GelezinioVilkoSaga_Book1_Complete.srt"
            captioned_video = OUTPUT_DIR / "GelezinioVilkoSaga_Book1_YouTube_captioned.mp4"
            add_captions_to_video(video_out, final_srt, captioned_video)

        # 5. Technical Validation
        print("\n" + "="*60)
        print("STAGE 5: TECHNICAL VALIDATION (ACX/Audible Compliance)")
        print("="*60 + "\n")
        val_mod = __import__('5_technical_validation')
        val_mod.validate_audio(master_audio)

    def merge_srt_files(self):
        """Merges individual chapter SRTs into one, offset by chapter durations."""
        print("🔗 Merging chapter transcripts into master SRT...", flush=True)
        import torchaudio as ta
        
        srt_files = sorted(TRANSCRIPTS_DIR.glob("*.srt"))
        master_srt = OUTPUT_DIR / "GelezinioVilkoSaga_Book1_Complete.srt"
        
        cumulative_offset = 0.0
        master_lines = []
        caption_index = 1
        
        for srt_file in srt_files:
            # Get chapter duration for offset
            wav_file = OUTPUT_DIR / (srt_file.stem + ".wav")
            if not wav_file.exists(): continue
            
            waveform, sr = ta.load(str(wav_file))
            duration = waveform.shape[1] / sr
            
            # Parse and offset SRT
            with open(srt_file, 'r') as f:
                content = f.read().strip()
                if not content: continue
                
                blocks = content.split('\n\n')
                for block in blocks:
                    lines = block.split('\n')
                    if len(lines) < 3: continue
                    
                    # Offset the time line: 00:00:01,000 --> 00:00:04,000
                    timeline = lines[1]
                    start_str, end_str = timeline.split(' --> ')
                    
                    new_start = self.offset_srt_time(start_str, cumulative_offset)
                    new_end = self.offset_srt_time(end_str, cumulative_offset)
                    
                    master_lines.append(f"{caption_index}\n{new_start} --> {new_end}\n" + "\n".join(lines[2:]))
                    caption_index += 1
            
            cumulative_offset += duration
            
        with open(master_srt, 'w') as f:
            f.write("\n\n".join(master_lines))
        print(f"✅ Master SRT saved: {master_srt.name}", flush=True)

    def offset_srt_time(self, time_str, offset_sec):
        # HH:MM:SS,mmm
        h, m, s_m = time_str.split(':')
        s, ms = s_m.split(',')
        total_sec = int(h)*3600 + int(m)*60 + int(s) + int(ms)/1000.0
        total_sec += offset_sec
        
        nh = int(total_sec // 3600)
        nm = int((total_sec % 3600) // 60)
        ns = int(total_sec % 60)
        nms = int((total_sec % 1) * 1000)
        return f"{nh:02d}:{nm:02d}:{ns:02d},{nms:03d}"

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-audio", type=str, default=None)
    args = parser.parse_args()
    
    manager = PipelineManager(reference_audio=args.reference_audio)
    manager.run()
