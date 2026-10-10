# Audiobook Text Preprocessor using Gemini API
# Specialized for: Geležinio Vilko Saga
# Transforms book chapters into narrator-friendly text with natural flow.
#
# Chapters are discovered from books/_quarto.yml, filtered to one book (--book N),
# and identified by a STABLE KEY derived from the source file name
# (b1_03_gintaro_sapnas), never by their position in the list. The manifest
# (preprocessed/manifest.json) records book, key, order, title, source path and a
# sha256 of the source text so later stages can skip unchanged chapters.
#
# `--list-chapters` is a dry run: it prints the discovered chapters and exits
# without importing langchain or calling any API.

from __future__ import annotations

import os
import re
import sys
import json
from pathlib import Path
import asyncio
import logging
import time
from typing import List, Dict, Any, Optional, Callable, Awaitable
from contextlib import AsyncExitStack

sys.path.insert(0, str(Path(__file__).parent))
import book_manifest as bm

# Paths
BOOK_DIR = bm.BOOKS_DIR
OUTPUT_DIR = bm.PREPROCESSED_DIR
CACHE_DIR = bm.CACHE_DIR
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

# Gemini configuration (API-based). The key is only REQUIRED when an LLM call is
# about to be made (see _require_gemini_key), so the dry run works without it.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if GEMINI_API_KEY:
    os.environ.setdefault("GOOGLE_API_KEY", GEMINI_API_KEY)

# Prefer v1 defaults
GENERATION_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
EDITOR_MODEL = os.getenv("GEMINI_EDITOR_MODEL", GENERATION_MODEL)
EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "text-embedding-004")
LLM_TIMEOUT = int(os.getenv("GEMINI_TIMEOUT", "240"))
LLM_RETRIES = int(os.getenv("GEMINI_RETRIES", "3"))
LLM_RETRY_BACKOFF = float(os.getenv("GEMINI_RETRY_BACKOFF", "2.0"))

# Heavy third-party imports are deferred until the LLM stack is really needed.
ChatGoogleGenerativeAI = GoogleGenerativeAIEmbeddings = Document = InMemoryVectorStore = None
StructuredTool = HumanMessage = AIMessage = None
ClientSession = StdioServerParameters = stdio_client = None
aiohttp = None


def _require_gemini_key():
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY must be set for Gemini usage.")


def _load_llm_stack():
    """Import aiohttp / mcp / langchain on first use (never in --list-chapters)."""
    global ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings, Document, InMemoryVectorStore
    global StructuredTool, HumanMessage, AIMessage, ClientSession, StdioServerParameters, stdio_client, aiohttp
    if ChatGoogleGenerativeAI is not None:
        return
    import aiohttp as _aiohttp
    # aiohttp compatibility shim: some client stacks expect aiohttp.ClientConnectorDNSError
    if not hasattr(_aiohttp, "ClientConnectorDNSError"):
        try:
            from aiohttp.client_exceptions import ClientConnectorError as _CCE
        except Exception:
            _CCE = Exception
        class _ClientConnectorDNSError(_CCE):
            pass
        _aiohttp.ClientConnectorDNSError = _ClientConnectorDNSError
    aiohttp = _aiohttp

    from mcp import ClientSession as _CS, StdioServerParameters as _SSP
    from mcp.client.stdio import stdio_client as _stdio
    from langchain_google_genai import GoogleGenerativeAIEmbeddings as _Emb, ChatGoogleGenerativeAI as _Chat
    from langchain_core.documents import Document as _Doc
    from langchain_core.vectorstores import InMemoryVectorStore as _VS
    from langchain_core.tools import StructuredTool as _ST
    from langchain_core.messages import HumanMessage as _HM, AIMessage as _AM
    ClientSession, StdioServerParameters, stdio_client = _CS, _SSP, _stdio
    GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI = _Emb, _Chat
    Document, InMemoryVectorStore, StructuredTool = _Doc, _VS, _ST
    HumanMessage, AIMessage = _HM, _AM


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
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except (OSError, ValueError) as e:
            logger.warning(f"MCP config unavailable ({e}); continuing without MCP tools")
            return {}

    async def connect_all(self, retries=3):
        """Connect to all servers defined in the config with retries."""
        _load_llm_stack()
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

    def get_langchain_tools(self) -> list:
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


def extract_chapter_text(qmd_file):
    """Extract clean text from a Quarto markdown file (path relative to books/)."""
    with open(BOOK_DIR / qmd_file, 'r', encoding='utf-8') as f:
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
        _require_gemini_key()
        _load_llm_stack()
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

async def agent_reasoning_loop(text, mcp_manager, previous_context="", next_context="", semantic_context=""):
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
        _require_gemini_key()
        _load_llm_stack()
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




def apply_pronunciation_lexicon(text, lang="en"):
    """HOOK: respell names / loanwords so the TTS pronounces them correctly.

    Currently returns the text UNCHANGED. Called after cleaning, right before the
    narration is cached.

    TODO: implement from world_rules/pronunciation_lexicon.json (per-language
    respellings for Lithuanian names and terms) as part of the pronunciation and
    diacritics redesign. `lang` selects the lexicon section ("en" for the English
    narration produced by this stage).
    """
    return text


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

async def preprocess_chapter(chapter: Dict[str, Any], mcp_manager, previous_context="", next_context="",
                             memory: Optional[NarrationMemory] = None, force: bool = False) -> Optional[str]:
    """Preprocess a single chapter (a manifest-style dict from book_manifest).

    The cache is keyed by the stable chapter key and invalidated when the source
    text hash changes. Returns the narration text, or None if the chapter was
    skipped or the LLM failed (failures are never cached or written).
    """
    key = chapter['key']
    print(f"\n📖 Processing: {key} ({chapter['title']})", flush=True)

    # Check cache: must match the current source hash and not be an error placeholder
    cache_file = bm.cache_path(key)
    hash_file = bm.cache_hash_path(key)
    if not force and cache_file.exists():
        cached_text = cache_file.read_text(encoding='utf-8')
        cached_hash = hash_file.read_text().strip() if hash_file.exists() else None
        if is_error_text(cached_text):
            print(f"   ⚠️  Cached version invalid (error placeholder); reprocessing", flush=True)
        elif cached_hash != chapter['source_hash']:
            print(f"   ⚠️  Cache is stale (source changed or unhashed); reprocessing", flush=True)
        else:
            print(f"   ✓ Using cached version", flush=True)
            if memory:
                memory.add_chapter(key, cached_text)
            return cached_text

    # Extract text
    try:
        text = extract_chapter_text(chapter['source'])
    except FileNotFoundError:
        print(f"   ⚠️  Skipping (not found: {chapter['source']})", flush=True)
        return None

    if not text or len(text) < 50:
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
    failed = False
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
        except Exception as e:
            logger.error(f"   ❌ Error processing chunk {i+1}: {e}")
            failed = True
            break
        if is_error_text(narrated):
            logger.error(f"   ❌ Chunk {i+1} failed: {narrated[:200]}")
            failed = True
            break
        narrated_chunks.append(narrated)

    if failed:
        # Never cache or publish an error placeholder as narration.
        return None

    final_text = '\n\n'.join(narrated_chunks)
    final_text = clean_invalid_tags(final_text)

    # Comprehensive text cleaning for TTS
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

    # Pronunciation pass (currently a no-op hook; see apply_pronunciation_lexicon)
    final_text = apply_pronunciation_lexicon(final_text, "en")

    # Cache (with the source hash) and memorize
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(final_text, encoding='utf-8')
    hash_file.write_text(chapter['source_hash'])

    if memory:
        memory.add_chapter(key, final_text)

    return final_text

def build_context_summary(chapters, current_index, window=2):
    """Build context summary from surrounding chapters (manifest-style dicts)."""
    def summarize(ch):
        try:
            text = extract_chapter_text(ch['source'])
            summary = text[:300].strip() + "..." if len(text) > 300 else text.strip()
            return f"\n{ch['key']}:\n{summary}\n"
        except Exception:
            return f"\n{ch['key']}: (content unavailable)\n"

    prev_start = max(0, current_index - window)
    prev_parts = ["PREVIOUS CHAPTERS:"] + [summarize(chapters[i]) for i in range(prev_start, current_index)] \
        if prev_start < current_index else []

    next_end = min(len(chapters), current_index + window + 1)
    next_parts = ["UPCOMING CHAPTERS:"] + [summarize(chapters[i]) for i in range(current_index + 1, next_end)] \
        if current_index + 1 < next_end else []

    return "\n".join(prev_parts), "\n".join(next_parts)

def _resolve_only(book: int, only: Optional[List[str]], entries: List[Dict[str, Any]]) -> Optional[set]:
    """Accept full keys (b1_03_x) or bare stems (03_x); error on unknown names."""
    if not only:
        return None
    keys = {e['key'] for e in entries}
    resolved = set()
    for name in only:
        cand = name if name in keys else f"b{book}_{name}"
        if cand not in keys:
            raise SystemExit(f"Unknown chapter '{name}' for book {book}. Known keys: {', '.join(sorted(keys))}")
        resolved.add(cand)
    return resolved

async def preprocess_book(book: int = 1, only: Optional[List[str]] = None, force: bool = False,
                          on_chapter_ready: Optional[Callable[[Dict[str, Any]], None]] = None) -> List[str]:
    """Preprocess one book. Returns the keys that failed.

    The manifest is written up front with every chapter (pending ones have
    preprocessed_hash=None) and updated after each chapter, so Stage 2 can start
    narrating while this stage is still running. on_chapter_ready(entry) is called
    for every chapter whose narration text is ready (freshly produced or reused).
    """
    _require_gemini_key()
    print(f"🤖 ReAct Agent initialized: {GENERATION_MODEL} (book {book})")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    entries = bm.build_manifest_entries(book)
    if not entries:
        raise SystemExit(f"No story chapters discovered for book {book} in books/_quarto.yml")
    selected = _resolve_only(book, only, entries)
    bm.save_manifest(book, entries)

    mcp_manager = MCPManager(MCP_CONFIG_PATH)
    await mcp_manager.connect_all()
    failures: List[str] = []

    try:
        memory = NarrationMemory()

        try:
            from tqdm import tqdm
            iterator = tqdm(list(enumerate(entries)), desc="Processing")
        except ImportError:
            iterator = list(enumerate(entries))

        for idx, entry in iterator:
            key = entry['key']
            if selected is not None and key not in selected:
                continue
            output_file = Path(entry['file'])

            # Skip when the narration exists, matches the current source, and is not an error placeholder
            if not force and bm.is_ready(entry):
                existing_text = output_file.read_text(encoding='utf-8')
                if not is_error_text(existing_text):
                    logger.info(f"✅ Skipping {key} (unchanged)")
                    memory.add_chapter(key, existing_text)
                    if on_chapter_ready:
                        on_chapter_ready(entry)
                    continue
                logger.info(f"⚠️  Reprocessing {key} (previous run failed)")

            prev_context, next_context = build_context_summary(entries, idx, window=2)

            try:
                narrated_text = await preprocess_chapter(
                    entry, mcp_manager,
                    previous_context=prev_context, next_context=next_context,
                    memory=memory, force=force
                )
            except Exception as e:
                logger.error(f"❌ Failed to process {key}: {e}")
                narrated_text = None

            if not narrated_text:
                failures.append(key)
                continue

            # Optional spoken part heading on the first chapter of each Quarto part
            heading = bm.spoken_part_heading(entry.get('part_number'), entry.get('part')) if entry.get('first_in_part') else None
            output_file.write_text(f"{heading}\n\n{narrated_text}" if heading else narrated_text, encoding='utf-8')
            entry['preprocessed_hash'] = entry['source_hash']
            bm.save_manifest(book, entries)
            if on_chapter_ready:
                on_chapter_ready(entry)
    finally:
        await mcp_manager.disconnect_all()

    if failures:
        logger.error(f"❌ Failed chapters: {', '.join(failures)}")
    return failures


def print_chapter_report(book: int) -> int:
    """Dry run: list discovered chapters without any API / model usage."""
    chapters, skipped = bm.discover_chapters_report(book)
    print(f"Book {book}: {len(chapters)} story chapters discovered from books/_quarto.yml")
    print(f"{'order':>5}  {'key':<34} {'sha256':<12}  title  [part / source]")
    for ch in chapters:
        part = f" | part {ch['part_number']}: {ch['part']}" + (" (spoken heading here)" if ch['first_in_part'] else "") if ch['part'] else ""
        print(f"{ch['order']:>5}  {ch['key']:<34} {ch['source_hash'][:12]}  {ch['title']}  [{ch['source']}{part}]")
    parts = []
    for ch in chapters:
        if ch['part'] and ch['part'] not in parts:
            parts.append(ch['part'])
    print(f"\nQuarto part titles (labels only, NOT narrated as chapters): {', '.join(parts) or '-'}")
    print("Excluded pages:")
    for source, reason in skipped:
        print(f"  {source:<40} {reason}")
    return 0 if chapters else 1


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Stage 1: preprocess book chapters into narrator text with Gemini")
    parser.add_argument("--book", type=int, default=1, help="Book number (books/<N>/), default 1")
    parser.add_argument("--list-chapters", action="store_true",
                        help="Dry run: print discovered chapters, keys, order and hashes, then exit (no API calls)")
    parser.add_argument("--only", type=str, default=None,
                        help="Comma-separated chapter keys to (re)process, e.g. b1_03_gintaro_sapnas or 03_gintaro_sapnas")
    parser.add_argument("--force", action="store_true", help="Ignore cache / existing output for the selected chapters")
    args = parser.parse_args()

    if args.list_chapters:
        sys.exit(print_chapter_report(args.book))

    only = [k.strip() for k in args.only.split(",") if k.strip()] if args.only else None
    failed = asyncio.run(preprocess_book(args.book, only=only, force=args.force))
    sys.exit(1 if failed else 0)
