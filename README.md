## Architecture Changes: S9 → S10Share

This README summarizes the architectural changes between the S9 project
('C:\Users\Monisha Srivastava\Downloads\S9') and the S10Share project
('C:\Users\Monisha Srivastava\Downloads\S10Share').

### Key Architecture Changes

- **Entry point and bootstrapping**  
  S9 runs from 'agent.py' and wires 'core.loop.AgentLoop' with
  'core.session.MultiMCP'. S10Share moves to 'main.py', loads MCP server
  configs from 'config/mcp_server_config.yaml', and instantiates
  'agent.agent_loop2.AgentLoop' with explicit perception/decision prompt
  paths.

- **Module organization**  
  S9 groups execution logic under 'core/' and 'modules/' (context/session/
  strategy separated from perception/decision/action/tools). S10Share
  promotes these into top-level packages ('perception/', 'decision/',
  'action/', 'memory/', 'agent/'), reducing the “core vs modules” split and
  making the pipeline stages first-class.

- **MCP server layout**  
  S9 keeps MCP server scripts in the root ('mcp_server_*.py') and
  constructs them from 'config/profiles.yaml'. S10Share consolidates MCP
  server logic into 'mcp_servers/' with 'multiMCP.py' and uses
  'config/mcp_server_config.yaml' for multi-server setup.

- **Session + memory flow**  
  S9 uses a 'core.context.AgentContext' and a loop with lifelines, then
  runs perception/decision/action via 'modules.*'. S10Share shifts to
  'AgentSession' + 'PerceptionSnapshot' tracking, logs sessions via
  'memory.session_log', and performs a memory search before perception as
  a structured step.

- **Agent loop refactor**  
  S10Share’s 'agent/agent_loop2.py' is a cleaner orchestration layer: it
  extracts helper methods (search, perception, decision, step eval),
  making the loop more modular and easier to extend than the S9 monolithic
  'core/loop.py'.

### Attribution and Provenance

See 'PROVENANCE.md' for source notes, human/LLM contributions, and change
history context.
