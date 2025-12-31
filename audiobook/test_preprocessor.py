import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

# Import the new async logic
preprocess_mod = __import__('1_preprocess_with_ollama')
MCPManager = preprocess_mod.MCPManager
preprocess_chapter = preprocess_mod.preprocess_chapter
load_quarto_config = preprocess_mod.load_quarto_config
get_ordered_chapters = preprocess_mod.get_ordered_chapters
build_context_summary = preprocess_mod.build_context_summary
NarrationMemory = preprocess_mod.NarrationMemory

async def test_agent():
    mcp_manager = MCPManager(Path('mcp.json'))
    await mcp_manager.connect_all()
    
    try:
        config = load_quarto_config()
        all_chapters = get_ordered_chapters(config)
        memory = NarrationMemory()
        
        # Test Chapter 1: Circadian Shuffle
        i = 0
        file, name = all_chapters[i]
        print(f"\n--- Testing ReAct Agent on Index {i}: {name} ({file}) ---")
        
        # Force ignore cache for testing
        cache_file = Path(f"cache/{name}.txt")
        if cache_file.exists():
            cache_file.unlink()
            
        prev_context, next_context = build_context_summary(all_chapters, i, window=1)
        
        text = await preprocess_chapter(
            file, 
            name, 
            mcp_manager, 
            previous_context=prev_context, 
            next_context=next_context, 
            memory=memory
        )
        
        if text:
            print(f"\n✅ Final Narration Output (excerpt):\n{text[:500]}...")
        else:
            print("\n❌ Failed: No narration returned")
            
    finally:
        await mcp_manager.disconnect_all()

if __name__ == "__main__":
    asyncio.run(test_agent())
