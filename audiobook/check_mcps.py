import asyncio
import json
import os
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def test_single_server(name, cfg):
    print(f"🛰️  Testing {name}...", flush=True)
    params = StdioServerParameters(
        command=cfg["command"],
        args=cfg["args"],
        env={**os.environ, **cfg.get("env", {})}
    )
    
    try:
        # Use a longer timeout for npx download
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                print(f"   ⏳ Initializing {name}...", flush=True)
                await asyncio.wait_for(session.initialize(), timeout=60.0)
                
                print(f"   🔍 Listing tools for {name}...", flush=True)
                tools = await asyncio.wait_for(session.list_tools(), timeout=10.0)
                
                tool_names = [t.name for t in tools.tools]
                print(f"   ✅ {name} OK! Tools: {', '.join(tool_names)}")
                return True
    except asyncio.TimeoutError:
        print(f"   ❌ {name} TIMEOUT (Registry/Download too slow?)", flush=True)
    except Exception as e:
        print(f"   ❌ {name} ERROR: {e}", flush=True)
    return False

async def main():
    config_path = Path("mcp.json")
    if not config_path.exists():
        print("mcp.json not found!")
        return
        
    with open(config_path, "r") as f:
        config = json.load(f)
        
    servers = config.get("mcpServers", {})
    print(f"🕵️  Diagnostic: Checking {len(servers)} servers (Registry: https://registry.npmjs.org/)\n")
    
    for name, cfg in servers.items():
        await test_single_server(name, cfg)
        print("-" * 20)

if __name__ == "__main__":
    asyncio.run(main())
