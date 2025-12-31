# Audiobook Text Preprocessor using Gemini API
# Specialized for: Geležinio Vilko Saga
# Transforms book chapters into narrator-friendly text with natural flow.

import os
import re
import yaml
import json
from pathlib import Path
import asyncio
import logging
import time
from typing import List, Dict, Any, Optional
from contextlib import AsyncExitStack
import aiohttp
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# aiohttp compatibility shim: some client stacks expect aiohttp.ClientConnectorDNSError
if not hasattr(aiohttp, "ClientConnectorDNSError"):
    try:
        from aiohttp.client_exceptions import ClientConnectorError as _CCE
    except Exception:
        _CCE = Exception
    class _ClientConnectorDNSError(_CCE):
        pass
    aiohttp.ClientConnectorDNSError = _ClientConnectorDNSError

from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_core.tools import StructuredTool
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.prebuilt import create_react_agent
from tqdm import tqdm

# Paths
BOOK_DIR = Path(__file__).parent.parent / "books"
OUTPUT_DIR = Path(__file__).parent / "preprocessed"
CACHE_DIR = Path(__file__).parent / "cache"
MCP_CONFIG_PATH = Path(__file__).parent / "mcp.json"
LOG_FILE = Path(__file__).parent / "preprocessing.log"

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

# Gemini configuration (API-based)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if GEMINI_API_KEY:
    os.environ.setdefault("GOOGLE_API_KEY", GEMINI_API_KEY)
else:
    raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY must be set for Gemini usage.")

# Prefer v1 defaults
GENERATION_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
EDITOR_MODEL = os.getenv("GEMINI_EDITOR_MODEL", GENERATION_MODEL)
EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "text-embedding-004")
LLM_TIMEOUT = int(os.getenv("GEMINI_TIMEOUT", "240"))
LLM_RETRIES = int(os.getenv("GEMINI_RETRIES", "3"))
LLM_RETRY_BACKOFF = float(os.getenv("GEMINI_RETRY_BACKOFF", "2.0"))

class MCPManager:
    """Manages connections to multiple MCP servers defined in mcp.json."""
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.sessions = {}
        self.tools_map = {} # tool_name -> server_name
        self.ollama_tools = [] # Ollama format tool definitions
        self.exit_stack = AsyncExitStack()
        self.config = self._load_config()

    def _load_config(self):
        with open(self.config_path, 'r') as f:
            return json.load(f)

    async def connect_all(self, retries=3):
        """Connect to all servers defined in the config with retries."""
        for name, cfg in self.config.get("mcpServers", {}).items():
            for attempt in range(retries):
                try:
                    print(f"🔌 Connecting to MCP Server: {name} (Attempt {attempt+1})...", flush=True)
                    params = StdioServerParameters(
                        command=cfg["command"],
                        args=cfg["args"],
                        env={**os.environ, **cfg.get("env", {})}
                    )
                    
                    transport_ctx = stdio_client(params)
                    read, write = await self.exit_stack.enter_async_context(transport_ctx)
                    session = await self.exit_stack.enter_async_context(ClientSession(read, write))
                    
                    await asyncio.wait_for(session.initialize(), timeout=30.0)
                    self.sessions[name] = session
                    
                    # Discover tools
                    tools_result = await session.list_tools()
                    for tool in tools_result.tools:
                        full_tool_name = f"{name}_{tool.name}" if name != "memory" else tool.name
                        self.tools_map[full_tool_name] = (name, tool.name)
                        
                        # Convert to Ollama tool format
                        self.ollama_tools.append({
                            'type': 'function',
                            'function': {
                                'name': full_tool_name,
                                'description': tool.description,
                                'parameters': tool.inputSchema
                            }
                        })
                    
                    print(f"✅ Connected to {name} ({len(tools_result.tools)} tools)", flush=True)
                    break
                except Exception as e:
                    print(f"   ⚠️  Failed to connect to {name}: {e}", flush=True)
                    if attempt == retries - 1:
                        print(f"   ❌ Giving up on {name}.", flush=True)
                    else:
                        await asyncio.sleep(2)

    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Call a specific tool on a specific server."""
        if server_name not in self.sessions:
            return f"Error: Server {server_name} not connected."
        
        try:
            result = await self.sessions[server_name].call_tool(tool_name, arguments)
            # Flatten text content or handle results cleanly
            if hasattr(result, 'content'):
                content = [c.text for c in result.content if hasattr(c, 'text')]
                return "\n".join(content)
            return str(result)
        except Exception as e:
            return f"Error calling tool {tool_name}: {e}"

    async def disconnect_all(self):
        """Close all connections."""
        await self.exit_stack.aclose()

    def get_langchain_tools(self) -> List[StructuredTool]:
        """Wrap MCP tools as LangChain StructuredTools."""
        lc_tools = []
        for full_name, (srv_name, real_tool_name) in self.tools_map.items():
            # Closures in loops are tricky, capture srv and tool
            def make_tool_func(s, t):
                async def tool_func(**kwargs):
                    return await self.call_tool(s, t, kwargs)
                return tool_func

            # Find description from ollama_tools cache
            desc = f"Tool: {full_name}"  # Default description
            for ot in self.ollama_tools:
                if ot['function']['name'] == full_name:
                    desc = ot['function']['description'] or desc
                    break

            lc_tools.append(StructuredTool.from_function(
                coroutine=make_tool_func(srv_name, real_tool_name),
                name=full_name,
                description=desc
            ))
        return lc_tools

AGENT_SYSTEM_PROMPT = """You are a Master Storyteller, a keeper of oral traditions and a weaver of dark, epic sagas. Your voice is that of one who has witnessed the collision of gods and men in the ancient Baltic forests. Your goal is to translate the provided Lithuanian text into a gripping, atmospheric, and rhythmic English audiobook narration.

CRITICAL: THE NARRATION MUST BE IN ENGLISH. TRANSLATE THE SOURCE LITHUANIAN CONTENT INTO CINEMATIC ENGLISH.

You have access to research tools to verify historical facts about 14th-century Lithuania, the intricate details of Baltic mythology (Perkūnas's justice, Žemyna's warmth, Medeinė's wildness), and the geopolitical chess match of the era. Use these to enrich the world-building and sensory texture of your storytelling.

{narration_rules}

Current Chapter for transformation:
{text}
"""


NARRATION_RULES = """CRITICAL FORMATTING RULES:
1. SOLE NARRATOR MODE: The entire output must be formatted as plain, pure English text for a single, professional audiobook narrator. 
   - **NO TAGS**: Do NOT use any tags like `[Narrator]`, `[Kestutis]`, or `[Vytautas]`. 
   - **DIALOGUE CLARITY (CRITICAL)**: Because there is only one voice, it must be 100% clear to a LISTENER who is speaking. 
     - If the source uses dashes (—) and the speaker isn't explicitly named in that specific line, you MUST add a dialogue attribution (e.g., "said Kestutis," "he replied," "Vytautas whispered").
     - Ensure the flow sounds like a professional English novel. The listener should never be confused about who has the floor.
   
   CORRECT EXAMPLE:
   Kestutis sat in his heavy oak chair, his hands gnarled and scarred from years of battle. He looked up as his son entered.
   
   "Vytautas," he said, his voice like gravel. "Have the envoys arrived?"
   
   "They are at the gates, Father," Vytautas replied, his hand resting on his sword hilt.
   
   - **LANGUAGE: THE ENTIRE OUTPUT MUST BE IN ENGLISH.** Every single word must be translated into English.
   - **FAITHFUL TRANSLATION**: Maintain the original pacing, tone, and specific imagery of the Lithuanian text. Translate accurately, do not add filler.
2. USE ENGLISH NAMES: In your English translation, use common English versions of names and places where they exist (e.g., Vilnius, Lithuania). For all other Lithuanian names, you MUST transliterate them to English phonetic equivalents:
   - ą -> a, ę -> e, į -> i, ų -> u, ū -> u, ė -> e
   - š -> sh
   - č -> ch
   - zh for ž
   - Example: Kęstutis -> Kestutis, Žemyna -> Zemyna, Švitrigaila -> Shvitrigaila, Birutė -> Birute.
3. Each newline in your output = 0.3 seconds of silence in the final audio. Use them for dramatic effect (e.g., between paragraphs).
4. Use 2-3 blank lines between major cinematic scenes for longer pauses.
5. NO MARKDOWN: Do NOT use asterisks (*) or markdown bold/italics. Use plain text only.
"""


async def call_llm_with_retry(llm, messages, timeout: int) -> Any:
    """Call an async LLM with retries and backoff."""
    last_error = None
    for attempt in range(1, LLM_RETRIES + 1):
        try:
            return await asyncio.wait_for(llm.ainvoke(messages), timeout=timeout)
        except asyncio.TimeoutError as e:
            last_error = e
            logger.warning(f"⏳ LLM timeout on attempt {attempt}/{LLM_RETRIES}")
        except Exception as e:
            last_error = e
            logger.warning(f"⚠️  LLM error on attempt {attempt}/{LLM_RETRIES}: {e}")
        if attempt < LLM_RETRIES:
            await asyncio.sleep(LLM_RETRY_BACKOFF * attempt)
    raise last_error if last_error else RuntimeError("LLM call failed without exception")


def call_llm_sync_retry(llm, prompt: str) -> Any:
    """Call a sync LLM (invoke) with retries and backoff."""
    last_error = None
    for attempt in range(1, LLM_RETRIES + 1):
        try:
            return llm.invoke(prompt)
        except Exception as e:
            last_error = e
            logger.warning(f"⚠️  LLM sync error on attempt {attempt}/{LLM_RETRIES}: {e}")
        if attempt < LLM_RETRIES:
            time.sleep(LLM_RETRY_BACKOFF * attempt)
    raise last_error if last_error else RuntimeError("LLM sync call failed without exception")


def is_error_text(text: str) -> bool:
    return "Error: Failed to process chapter" in text


def flatten_chapters(chapters):
    """recursively flatten Quarto chapter list handling parts."""
    flat_list = []
    for item in chapters:
        if isinstance(item, str):
            flat_list.append(item)
        elif isinstance(item, dict):
            # Handle part content file if present
            if 'part' in item and isinstance(item['part'], str):
                flat_list.append(item['part'])
            
            # Handle chapters within the part
            if 'chapters' in item:
                flat_list.extend(flatten_chapters(item['chapters']))
    return flat_list

def load_quarto_config():
    """Load the Quarto book configuration to get chapter order."""
    config_path = BOOK_DIR / "_quarto.yml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return flatten_chapters(config['book']['chapters'])

def extract_chapter_text(qmd_file):
    """Extract clean text from a Quarto markdown file."""
    with open(BOOK_DIR / qmd_file, 'r') as f:
        content = f.read()
    
    # Remove YAML frontmatter
    content = re.sub(r'^---\n.*?\n---\n', '', content, flags=re.DOTALL)
    
    # Remove Quarto callout syntax
    content = re.sub(r'^::: \{\.callout-[^\}]+\}\n', '', content, flags=re.MULTILINE)
    content = re.sub(r'^:::\n', '', content, flags=re.MULTILINE)
    
    # Remove LaTeX commands
    content = re.sub(r'\\[a-zA-Z]+(\{[^}]*\})?', '', content)
    
    # Remove citations
    content = re.sub(r'\[@[^\]]+\]', '', content)
    
    # Convert markdown headers to natural text
    content = re.sub(r'^# (.+)$', r'Chapter: \1', content, flags=re.MULTILINE)
    content = re.sub(r'^## (.+)$', r'Section: \1', content, flags=re.MULTILINE)
    content = re.sub(r'^### (.+)$', r'\1', content, flags=re.MULTILINE)
    
    # Convert blockquotes to quoted text
    content = re.sub(r'^> (.+)$', r'Quote: "\1"', content, flags=re.MULTILINE)
    
    # Clean up extra whitespace
    content = re.sub(r'\n{3,}', '\n\n', content)
    
    return content.strip()

class NarrationMemory:
    """Manages semantic memory of the book narration using embeddings."""
    def __init__(self, model_name: str = EMBEDDING_MODEL):
        print(f"🧠 Initializing Semantic Memory (Gemini: {model_name})...", flush=True)
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model=model_name,
            google_api_key=GEMINI_API_KEY
        )
        self.vector_store = InMemoryVectorStore(self.embeddings)
        self.chapter_count = 0

    def add_chapter(self, chapter_name: str, text: str):
        """Add a processed chapter to memory, chunking if necessary to avoid embedding limits."""
        # Split into ~2000 character chunks for reliable embedding
        chunk_size = 3000
        chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
        
        docs = []
        for j, chunk in enumerate(chunks):
            docs.append(Document(
                page_content=chunk,
                metadata={
                    "chapter": chapter_name, 
                    "index": self.chapter_count,
                    "chunk": j
                }
            ))
            
        try:
            self.vector_store.add_documents(docs)
            self.chapter_count += 1
            print(f"   📥 Memorized: {chapter_name} ({len(chunks)} chunks)", flush=True)
        except Exception as e:
            print(f"   ⚠️  Failed to memorize {chapter_name}: {e}", flush=True)

    def get_semantic_context(self, text: str, k=3) -> str:
        """Retrieve relevant snippets from previous chapters using a thematic summary."""
        if self.chapter_count == 0:
            return "(No semantic memory yet - first chapter)"
        
    def get_semantic_context(self, text: str, k=3) -> str:
        """Retrieve relevant snippets from previous chapters using a thematic summary."""
        if self.chapter_count == 0:
            return "(No semantic memory yet - first chapter)"
        
        try:
            # 1. Generate a quick thematic summary for the query
            summary_prompt = f"Summarize the core themes and key terms of this text in 2 sentences for a vector search query:\n\n{text[:2000]}"
            
            summary_llm = ChatGoogleGenerativeAI(
                model=GENERATION_MODEL,
                temperature=0.1,
                google_api_key=GEMINI_API_KEY
            )
            response = call_llm_sync_retry(summary_llm, summary_prompt)
            query = response.content.strip()
            
            print(f"   🔍 Memory Query: {query[:60]}...", flush=True)
            
            # 2. Find similar themes in previous chapters
            docs = self.vector_store.similarity_search(query, k=k)
            
            context_parts = []
            for doc in docs:
                source = doc.metadata.get("chapter", "Unknown")
                # Provide a bit more context for the narrator
                content = doc.page_content[:600] + "..." if len(doc.page_content) > 600 else doc.page_content
                context_parts.append(f"FROM CHAPTER '{source}':\n{content}")
            
            return "\n\n".join(context_parts)
        except Exception as e:
            print(f"   ⚠️  Semantic memory search failed: {e}", flush=True)
            return "(Semantic search unavailable)"

async def agent_reasoning_loop(text, mcp_manager: MCPManager, previous_context="", next_context="", semantic_context=""):
    """Draft, Self-Review/Critique, and Editing/Refinement loop."""
    
    draft_prompt = f"""You are a master storyteller and translator.
Translate the following Lithuanian text into English narration.
Goal: Stay as similar to the source as possible. Use English names and transliterate Lithuanian letters.
CRITICAL: DO NOT USE ANY TAGS (like [Narrator] or [Character Name]). Just provide the pure translated text.
DO NOT USE ANY ASTERISKS (*) OR BOLD/ITALIC MARKDOWN. Use hyphens (-) for lists if needed.

Do not emit any XML-like parameter artifacts (e.g., <parameter name="filePath">).

{NARRATION_RULES}

SOURCE TEXT:
{text}"""

    try:
        llm = ChatGoogleGenerativeAI(
            model=GENERATION_MODEL,
            temperature=0.1,
            streaming=False,
            google_api_key=GEMINI_API_KEY
        )
        logger.info(f"🎙️ Generating initial draft ({len(text)} chars)...")
        draft_response = await call_llm_with_retry(
            llm, [HumanMessage(content=draft_prompt)], timeout=LLM_TIMEOUT
        )
        draft = draft_response.content

        # EDITING & REVIEW STEP
        review_prompt = f"""CRITICAL EDITOR REVIEW & REWRITE:
Compare your English DRAFT to the original Lithuanian SOURCE. 

You are now acting as a Senior Editor. You must identify any errors in the draft and REWRITE it to perfection.

CHECKLIST:
1. NO ASTERISKS: Did you use * anywhere? REMOVE THEM. Replace with - for list items.
2. 100% ENGLISH: Did you leave any Lithuanian words like (dalintis, teises)? TRANSLATE THEM ALL.
3. NAMES: Are names like Kęstutis correctly transliterated to Kestutis?
4. DIALOGUE SEPARATION: After each [Character] dialogue block, did you start a NEW [Narrator] block for descriptions? 
   NEVER put narration like "she said" or "he whispered" in the same block as dialogue.
5. FIDELITY: Is it still extremely faithful to the original Lithuanian imagery?

SOURCE:
{text}

DRAFT:
{draft}

First, list the specific edits needed (Critique). 
Then, provide the COMPLETELY EDITED AND FINAL version. YOU MUST wrap the final version with <FINAL_NARRATION> tags.
Example:
<FINAL_NARRATION>
[Narrator]
Your final edited text here...
</FINAL_NARRATION>"""

        logger.info("🔍 Senior Editor: Critiquing and rewriting draft...")
        llm_editor = ChatGoogleGenerativeAI(
            model=EDITOR_MODEL,
            temperature=0.1,
            streaming=False,
            google_api_key=GEMINI_API_KEY
        )
        review_response = await call_llm_with_retry(
            llm_editor,
            [
                HumanMessage(content=draft_prompt),
                AIMessage(content=draft),
                HumanMessage(content=review_prompt)
            ],
            timeout=LLM_TIMEOUT
        )
        
        final_output = review_response.content
        match = re.search(r"<FINAL_NARRATION>(.*?)</FINAL_NARRATION>", final_output, re.DOTALL)
        if match:
            return match.group(1).strip()
        elif "---FINAL---" in final_output:
            return final_output.split("---FINAL---")[-1].strip()
        else:
            return final_output.strip()
    except asyncio.TimeoutError:
        logger.error(f"❌ LLM Timeout after {LLM_TIMEOUT}s")
        return f"Error: Failed to process chapter. LLM call timed out after {LLM_TIMEOUT}s"
    except Exception as e:
        logger.error(f"❌ LLM Error: {e}")
        return f"Error: Failed to process chapter. {e}"




def clean_invalid_tags(text):
    """Clean and standardize speaker/paralinguistic tags for TTS."""
    # Valid paralinguistic tags
    supported_fx = {
        '[chuckle]', '[laugh]', '[sigh]', '[gasp]', 
        '[cough]', '[groan]', '[sniff]', '[clear throat]', '[shush]'
    }
    
    # 1. Standardize speaker tags (e.g., [Narrator], [Vytautas])
    # Ensure they are at the start of a line or after a newline
    text = re.sub(r'(\n|^)\[([^\]]+)\]', r'\1[\2]', text)
    
    # 2. Handle invalid tags (anything that isn't a likely name or supported FX)
    def validate_tag(match):
        tag_content = match.group(1).strip()
        full_tag = f"[{tag_content}]"
        
        # Keep if it's a known FX
        if full_tag.lower() in supported_fx:
            return full_tag
            
        # Keep if it looks like a Proper Name (Speaker Tag)
        # Proper Name: capitalized words, spaces allowed
        if re.match(r'^[A-Z][a-z]+(\s+[A-Z][a-z]+)*$', tag_content):
            return full_tag
            
        # Otherwise, check for "Narrator"
        if tag_content == "Narrator":
            return full_tag
            
        # If it looks like an emotion or direction (e.g. [scary voice]), remove it
        return ""

    text = re.sub(r'\[([^\]]+)\]', validate_tag, text)
    
    # Clean up whitespace
    text = re.sub(r' +', ' ', text)
    text = re.sub(r'\n{4,}', '\n\n\n', text)
    
    return text.strip()

async def preprocess_chapter(chapter_file, chapter_name, mcp_manager, previous_context="", next_context="", memory: Optional[NarrationMemory] = None):
    """Preprocess a single chapter using the ReAct agent loop."""
    print(f"\n📖 Processing: {chapter_name}", flush=True)
    
    # Check cache and ensure it is not an error placeholder
    cache_file = CACHE_DIR / f"{chapter_name}.txt"
    if cache_file.exists():
        with open(cache_file, 'r') as f:
            cached_text = f.read()
        if is_error_text(cached_text):
            print(f"   ⚠️  Cached version invalid (error placeholder); reprocessing", flush=True)
        else:
            print(f"   ✓ Using cached version", flush=True)
            if memory:
                memory.add_chapter(chapter_name, cached_text)
            return cached_text
    
    # Extract text
    try:
        text = extract_chapter_text(chapter_file)
    except FileNotFoundError:
        # Check if it's likely a Part divider without a content file
        special_sections = ["Nuosmukis", "Pabėgimas", "Karas ir Tvarka"] # Add others as needed
        if any(s in chapter_name for s in special_sections) or "Part" in chapter_name:
            print(f"   ✨ Generating announcement for Part: {chapter_name}", flush=True)
            text = f"Part: {chapter_name}"
        else:
            print(f"   ⚠️  Skipping (not found: {chapter_file})", flush=True)
            return None
    
    is_part = "Part:" in (text or "")
    if not text or (len(text) < 50 and not is_part):
        print(f"   ⚠️  Skipping ({'too short' if text else 'empty'})", flush=True)
        return None
    
    # Get semantic context if memory is available
    semantic_context = ""
    if memory:
        semantic_context = memory.get_semantic_context(text)
    
    # Split into chunks if too long
    max_chunk_size = 4000
    chunks = [text[i:i+max_chunk_size] for i in range(0, len(text), max_chunk_size)]
    
    narrated_chunks = []
    for i, chunk in enumerate(chunks):
        if len(chunks) > 1:
            logger.info(f"   🤖 Processing chunk {i+1}/{len(chunks)}...")
        
        try:
            narrated = await agent_reasoning_loop(
                chunk, 
                mcp_manager,
                previous_context=previous_context, 
                next_context=next_context,
                semantic_context=semantic_context
            )
            narrated_chunks.append(narrated)
        except Exception as e:
            logger.error(f"   ❌ Error processing chunk {i+1}: {e}")
            narrated_chunks.append(f"[Error: Chunk {i+1} failed]")
    
    final_text = '\n\n'.join(narrated_chunks)
    final_text = clean_invalid_tags(final_text)
    
    # Comprehensive text cleaning for TTS
    import re
    # Remove markdown formatting
    final_text = re.sub(r'\*\*(.+?)\*\*', r'\1', final_text)      # **bold**
    final_text = re.sub(r'\*(.+?)\*', r'\1', final_text)          # *italic*
    final_text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', final_text)   # [text](url) -> text
    final_text = re.sub(r'`(.+?)`', r'\1', final_text)            # `code` -> code
    final_text = re.sub(r'_{2,}', '', final_text)                 # underscores
    final_text = re.sub(r'#{1,6}\s+', '', final_text)             # headers
    # Remove horizontal rules
    final_text = re.sub(r'^[-=]{3,}$', '', final_text, flags=re.MULTILINE)
    final_text = re.sub(r'^---+$', '', final_text, flags=re.MULTILINE)
    # Clean whitespace
    final_text = re.sub(r'\n{3,}', '\n\n', final_text)
    final_text = re.sub(r' {2,}', ' ', final_text)
    # Strip any stray XML-like parameter artifacts
    final_text = re.sub(r'<parameter[^>]*>', '', final_text)
    final_text = re.sub(r'</parameter>', '', final_text)
    final_text = final_text.strip()
    
    # Add chapter announcement at the beginning
    # Try to extract the actual title from the source file
    chapter_title = None
    try:
        with open(BOOK_DIR / f"{chapter_name}.qmd", 'r') as f:
            for line in f:
                # Look for the first markdown header (# Title)
                match = re.match(r'^#\s+(.+?)(\s+\{[^}]*\})?\s*$', line)
                if match:
                    chapter_title = match.group(1).strip()
                    # Remove "Part" prefix if it's a part divider, keep the rest
                    # e.g., "Part I: Historical Foundation" stays as is
                    break
    except:
        pass
    
    # Fallback to filename-based title if extraction failed
    if not chapter_title:
        chapter_title = chapter_name.replace('-', ' ').replace('_', ' ').title()
        # Strip leading zeros from numbers (e.g., "01 Foundations" -> "1 Foundations")
        import re as re_module
        chapter_title = re_module.sub(r'\b0+(\d+)', r'\1', chapter_title)
    
    # 2. Add numbering for regular chapters if missing
    # Check if filename starts with a number (e.g., "01-foundations")
    import re as re_module
    num_match = re_module.match(r'^0*(\d+)-', chapter_name)
    if num_match and "Part" not in chapter_title and "Transition" not in chapter_title:
        chapter_num = num_match.group(1)
        # Only prepend if title doesn't already start with the number
        if not chapter_title.startswith(chapter_num):
            chapter_title = f"{chapter_num} {chapter_title}"

    # 3. Add "Chapter: " prefix CONDITIONALLY
    # Don't add "Chapter:" for special sections
    special_prefixes = ["part", "epigraph", "dedication", "acknowledgements", 
                       "preface", "introduction", "copyright", "appendix", 
                       "glossary", "bibliography", "about", "transition", 
                       "call to action", "conclusion", "source index", "support"]
    
    # Check lower case title for robusntess
    title_lower = chapter_title.lower()
    is_special = any(p in title_lower for p in special_prefixes)
    
    # Removed automatic Lithuanian title prepending. The LLM handles translated titles.
    # if is_special:
    #     final_text = f"{chapter_title}.\n\n{final_text}"
    # else:
    #     final_text = f"Chapter: {chapter_title}.\n\n{final_text}"
    
    # Cache and Memorize
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(cache_file, 'w') as f:
        f.write(final_text)
    
    if memory:
        memory.add_chapter(chapter_name, final_text)
        
    return final_text

def build_context_summary(chapter_files, current_index, window=2):
    """Build context summary from surrounding chapters with actual content."""
    context_parts = []
    
    # Get previous chapters
    prev_start = max(0, current_index - window)
    if prev_start < current_index:
        context_parts.append("PREVIOUS CHAPTERS:")
        for i in range(prev_start, current_index):
            chapter_file, chapter_name = chapter_files[i]
            try:
                # Extract first 300 chars as summary
                text = extract_chapter_text(chapter_file)
                summary = text[:300].strip() + "..." if len(text) > 300 else text.strip()
                context_parts.append(f"\n{chapter_name}:\n{summary}\n")
            except:
                context_parts.append(f"\n{chapter_name}: (content unavailable)\n")
    
    prev_context = "\n".join(context_parts) if context_parts else ""
    
    # Get next chapters
    context_parts = []
    next_end = min(len(chapter_files), current_index + window + 1)
    if current_index + 1 < next_end:
        context_parts.append("UPCOMING CHAPTERS:")
        for i in range(current_index + 1, next_end):
            chapter_file, chapter_name = chapter_files[i]
            try:
                # Extract first 300 chars as preview
                text = extract_chapter_text(chapter_file)
                summary = text[:300].strip() + "..." if len(text) > 300 else text.strip()
                context_parts.append(f"\n{chapter_name}:\n{summary}\n")
            except:
                context_parts.append(f"\n{chapter_name}: (content unavailable)\n")
    
    next_context = "\n".join(context_parts) if context_parts else ""
    
    return prev_context, next_context

def get_ordered_chapters(chapters):
    """Clean the chapter list and extract names/paths."""
    all_chapters = []
    for chapter_entry in chapters:
        if isinstance(chapter_entry, str):
            chapter_file = chapter_entry
            chapter_name = Path(chapter_file).stem
            
            # Skip non-content files
            if chapter_file in ['index.qmd', 'copyright.qmd', 'references.qmd'] or chapter_name.startswith('interlude'):
                continue
            
            all_chapters.append((chapter_file, chapter_name))
            
        elif isinstance(chapter_entry, dict):
            # Handle part entries with nested chapters
            if 'part' in chapter_entry and 'chapters' in chapter_entry:
                for nested_chapter in chapter_entry['chapters']:
                    if isinstance(nested_chapter, str):
                        chapter_file = nested_chapter
                        chapter_name = Path(chapter_file).stem
                        
                        # Skip non-content files
                        if chapter_file in ['index.qmd', 'references.qmd'] or chapter_name.startswith('interlude'):
                            continue
                        
                        all_chapters.append((chapter_file, chapter_name))
    return all_chapters

async def preprocess_book():
    """Preprocess the entire book as an async agent."""
    print(f"🤖 ReAct Agent initialized: {GENERATION_MODEL}")
    
    # Initialize MCP
    mcp_manager = MCPManager(MCP_CONFIG_PATH)
    await mcp_manager.connect_all()
    
    try:
        chapters = load_quarto_config()
        all_chapters = get_ordered_chapters(chapters)
        
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        all_chapters = get_ordered_chapters(chapters)
        
        memory = NarrationMemory()
        processed_chapters = []
        
        for chapter_index, (chapter_file, chapter_name) in enumerate(tqdm(all_chapters, desc="Processing")):
            output_file = OUTPUT_DIR / f"{chapter_index:02d}_{chapter_name}.txt"
            
            # Check for existing output; skip only if it isn't an error placeholder
            if output_file.exists() and output_file.stat().st_size > 100:
                with open(output_file, 'r') as f:
                    existing_text = f.read()
                if is_error_text(existing_text):
                    logger.info(f"⚠️  Reprocessing {chapter_name} (previous run failed)")
                else:
                    logger.info(f"✅ Skipping {chapter_name} (already exists)")
                    # Still add to memory for context
                    memory.add_chapter(chapter_name, existing_text)
                    processed_chapters.append({'name': chapter_name, 'file': str(output_file.absolute()), 'index': chapter_index})
                    # Update manifest incrementally
                    with open(OUTPUT_DIR / "manifest.json", 'w') as f:
                        json.dump(processed_chapters, f, indent=4)
                    continue

            prev_context, next_context = build_context_summary(all_chapters, chapter_index, window=2)
            
            try:
                narrated_text = await preprocess_chapter(
                    chapter_file, 
                    chapter_name, 
                    mcp_manager,
                    previous_context=prev_context, 
                    next_context=next_context, 
                    memory=memory
                )
                
                if narrated_text:
                    with open(output_file, 'w') as f:
                        f.write(narrated_text)
                    processed_chapters.append({'name': chapter_name, 'file': str(output_file.absolute()), 'index': chapter_index})
                    
                    # Update manifest incrementally
                    with open(OUTPUT_DIR / "manifest.json", 'w') as f:
                        json.dump(processed_chapters, f, indent=4)
            except Exception as e:
                logger.error(f"❌ Failed to process {chapter_name}: {e}")
    finally:
        await mcp_manager.disconnect_all()

if __name__ == "__main__":
    asyncio.run(preprocess_book())
