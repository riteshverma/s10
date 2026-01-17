## Architecture Overview

This document describes the current architecture of the S10Share agent system.

### High-Level Flow

1. User query enters `AgentLoop` in `agent/agent_loop2.py`.
2. Perception runs with memory + tool performance context.
3. Decision generates a plan and tool code.
4. Code executes in a sandbox and tools are called via MCP.
5. Results are re-perceived and steps can replan, conclude, or request U1.
6. Sessions and histories are persisted to disk.

### Core Components

- **Orchestrator**: `agent/agent_loop2.py`
  - Handles perception, decision, execution, replans, and limits.
  - Tracks plan history and step history.
  - Posts trace events to the blackboard.

- **Perception**: `perception/perception.py`
  - Builds structured inputs and parses JSON output.
  - Adds tool performance summary and memory excerpt.

- **Decision**: `decision/decision.py`
  - Builds planning prompts with tool descriptions.
  - Includes fallback JSON parsing for nonstandard LLM outputs.

- **Execution Sandbox**: `action/executor.py`
  - Runs tool code in a restricted environment.
  - Enforces function call limits and timeouts.

- **Tools + MCP**: `mcp_servers/multiMCP.py`
  - Discovers tools across MCP servers.
  - Logs tool performance and bans tools after repeated failures.

### Memory and Logging

- **Session logs**: `memory/session_logs/YYYY/MM/DD/<session_id>.json`
- **Tool performance**: `memory/tool_performance.jsonl`
- **Blackboard trace**: `memory/blackboard.py`

### Key Policies

- **Max steps**: 3 (`MAX_STEPS`)
- **Max retries**: 3 (`MAX_RETRIES`)
- **Auto-ban tools**: after 3 failures per tool in the same run
- **Low confidence trigger**: `confidence < 0.3` routes to CriticAgent
- **Off-topic detection**: step output with no query-term overlap triggers replan

### Files to Debug

- Planning/parsing issues: `decision/decision.py`
- Perception JSON issues: `perception/perception.py`
- Tool failures: `mcp_servers/multiMCP.py`
- Sandbox errors: `action/executor.py`
- Session history: `memory/session_logs/...`
