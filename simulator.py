import asyncio
import os
import time
from pathlib import Path

import yaml

from agent.agent_loop2 import AgentLoop
from mcp_servers.multiMCP import MultiMCP


DEFAULT_QUERIES = [
    "Summarize the document about DLF policy.",
    "What is 12 * 12 + 5?",
    "Find the key points from the economic.md document.",
    "List the top 3 insights from the cricket.txt file.",
    "Give a short summary of Tesla motors innovation PDF.",
    "What are the main sections in the Experience Letter document?",
    "Provide a quick answer: 2^8 and log it.",
    "Summarize the DLF_13072023190044_BRSR.pdf document.",
    "Find the topic of the Canvas LMS guide.",
    "Explain the meaning of ERORLL in this agent."
    "Summarize client details from the client_details.txt file.",
]


async def run_simulation(total_runs: int, sleep_seconds: float) -> None:
    workspace_root = Path(__file__).parent.absolute()
    mcp_servers_dir = workspace_root / "mcp_servers"

    with open("config/mcp_server_config.yaml", "r", encoding="utf-8") as f:
        profile = yaml.safe_load(f)
        mcp_servers_list = profile.get("mcp_servers", [])
        configs = list(mcp_servers_list)
        for config in configs:
            if "cwd" in config:
                cwd_path = Path(config["cwd"])
                if not cwd_path.is_absolute():
                    config["cwd"] = str(workspace_root / config["cwd"])
                else:
                    if not cwd_path.exists():
                        config["cwd"] = str(mcp_servers_dir)
            else:
                config["cwd"] = str(mcp_servers_dir)

    multi_mcp = MultiMCP(server_configs=configs)
    await multi_mcp.initialize()

    loop = AgentLoop(
        perception_prompt_path="prompts/perception_prompt.txt",
        decision_prompt_path="prompts/decision_prompt.txt",
        multi_mcp=multi_mcp,
        strategy="exploratory"
    )

    queries = DEFAULT_QUERIES
    for i in range(total_runs):
        query = queries[i % len(queries)]
        print(f"\n=== Simulation Run {i + 1}/{total_runs} ===")
        print(f"Query: {query}")
        await loop.run(query)
        print(f"Sleeping {sleep_seconds}s to avoid rate limits.")
        await asyncio.sleep(sleep_seconds)


if __name__ == "__main__":
    total_runs = int(os.getenv("SIM_TESTS", "120"))
    sleep_seconds = float(os.getenv("SIM_SLEEP_SECONDS", "1.5"))
    asyncio.run(run_simulation(total_runs, sleep_seconds))
