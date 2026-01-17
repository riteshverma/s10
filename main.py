import asyncio
import yaml
from pathlib import Path
from mcp_servers.multiMCP import MultiMCP

from dotenv import load_dotenv
# from agent.agent_loop import AgentLoop
from agent.agent_loop2 import AgentLoop
from pprint import pprint
BANNER = """
──────────────────────────────────────────────────────
🔸  Agentic Query Assistant  🔸
Type your question and press Enter.
Type 'exit' or 'quit' to leave.
──────────────────────────────────────────────────────
"""


async def interactive() -> None:
    print(BANNER)
    print("Loading MCP Servers...")
    # Get workspace root directory
    workspace_root = Path(__file__).parent.absolute()
    mcp_servers_dir = workspace_root / "mcp_servers"
    
    with open("config/mcp_server_config.yaml", "r") as f:
        profile = yaml.safe_load(f)
        mcp_servers_list = profile.get("mcp_servers", [])
        configs = list(mcp_servers_list)
        # Resolve paths relative to workspace root
        for config in configs:
            if "cwd" in config:
                # Convert to absolute path if relative, or keep absolute if already absolute
                cwd_path = Path(config["cwd"])
                if not cwd_path.is_absolute():
                    config["cwd"] = str(workspace_root / config["cwd"])
                else:
                    # If absolute path doesn't exist, use mcp_servers directory
                    if not cwd_path.exists():
                        config["cwd"] = str(mcp_servers_dir)
            else:
                config["cwd"] = str(mcp_servers_dir)

    # Initialize MCP + Dispatcher
    multi_mcp = MultiMCP(server_configs=configs)
    await multi_mcp.initialize()
    loop = AgentLoop(
        perception_prompt_path="prompts/perception_prompt.txt",
        decision_prompt_path="prompts/decision_prompt.txt",
        multi_mcp=multi_mcp,
        strategy="exploratory"
    )
    while True:

        query = input("🟢  You: ").strip()
        if query.lower() in {"exit", "quit"}:
            print("👋  Goodbye!")
            break


        response = await loop.run(query)
        # response = await loop.run("What is 4 + 4?")
        # pprint(f"🔵  Agent: {response.state['final_answer']}\n {response.state['reasoning_note']}\n")
        print(f"🔵 Agent: {response.state['solution_summary']}\n")

        follow = input("\n\nContinue? (press Enter) or type 'exit': ").strip()
        if follow.lower() in {"exit", "quit"}:
            print("👋  Goodbye!")
            break

if __name__ == "__main__":
    asyncio.run(interactive())
