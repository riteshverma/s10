import os
import uuid
import json
import datetime
from perception.perception import Perception
from decision.decision import Decision
from action.executor import run_user_code
from agent.agentSession import AgentSession, PerceptionSnapshot, Step, ToolCode
from memory.session_log import live_update_session
from memory.tool_performance import get_tool_performance_summary
from memory.memory_search import MemorySearch
from mcp_servers.multiMCP import MultiMCP
from agent.context import AgentContext
from agent.critic_agent import CriticAgent
from memory.blackboard import post_to_blackboard, get_blackboard


GLOBAL_PREVIOUS_FAILURE_STEPS = 3
MAX_STEPS = 3
MAX_RETRIES = 3

class AgentLoop:
    def __init__(self, perception_prompt_path: str, decision_prompt_path: str, multi_mcp: MultiMCP, strategy: str = "exploratory"):
        self.perception = Perception(perception_prompt_path)
        self.decision = Decision(decision_prompt_path, multi_mcp)
        self.multi_mcp = multi_mcp
        self.strategy = strategy
        self.blackboard = get_blackboard()
        self.critic_agent = CriticAgent()
        self.agent_name = "agent-loop"

    async def run(self, query: str):
        session = AgentSession(session_id=str(uuid.uuid4()), original_query=query)
        self.context = AgentContext(agent_name=self.agent_name, blackboard=self.blackboard)
        session_memory= []
        self.log_session_start(session, query)

        memory_results = self.search_memory(query)
        tool_perf_summary = get_tool_performance_summary()
        perception_result = self.run_perception(query, memory_results, memory_results, tool_perf_summary=tool_perf_summary)
        session.add_perception(PerceptionSnapshot(**perception_result))
        self.handle_low_confidence(perception_result, context=self.context)

        if perception_result.get("original_goal_achieved"):
            self.handle_perception_completion(session, perception_result)
            return session

        decision_output = self.make_initial_decision(query, perception_result, tool_perf_summary=tool_perf_summary)
        step = session.add_plan_version(decision_output["plan_text"], [self.create_step(decision_output)])
        live_update_session(session)
        print(f"\n[Decision Plan Text: V{len(session.plan_versions)}]:")
        for line in session.plan_versions[-1]["plan_text"]:
            print(f"  {line}")
        print(session.render_plan_history())

        steps_executed = 0
        retries = 0
        while step:
            step_result = await self.execute_step(step, session, session_memory)
            if step_result is None:
                break  # 🔐 protect against CONCLUDE/NOP cases
            steps_executed += 1
            if steps_executed >= MAX_STEPS:
                self.handle_max_steps(session, query)
                break
            step, retries = self.evaluate_step(step_result, session, query, retries)

        return session

    def log_session_start(self, session, query):
        print("\n=== LIVE AGENT SESSION TRACE ===")
        print(f"Session ID: {session.session_id}")
        print(f"Query: {query}")
        post_to_blackboard(self.agent_name, f"session_start: {session.session_id} | query={query}")

    def search_memory(self, query):
        print("Searching Recent Conversation History")
        searcher = MemorySearch()
        results = searcher.search_memory(query)
        if not results:
            print("❌ No matching memory entries found.\n")
        else:
            print("\n🎯 Top Matches:\n")
            for i, res in enumerate(results, 1):
                print(f"[{i}] File: {res['file']}\nQuery: {res['query']}\nResult Requirement: {res['result_requirement']}\nSummary: {res['solution_summary']}\n")
        return results

    def run_perception(self, query, memory_results, session_memory=None, snapshot_type="user_query", current_plan=None, tool_perf_summary=None):
        combined_memory = (memory_results or []) + (session_memory or [])
        perception_input = self.perception.build_perception_input(
            raw_input=query, 
            memory=combined_memory, 
            current_plan=current_plan, 
            snapshot_type=snapshot_type,
            tool_performance_summary=tool_perf_summary
        )
        perception_result = self.perception.run(perception_input)
        print("\n[Perception Result]:")
        print(json.dumps(perception_result, indent=2, ensure_ascii=False))
        post_to_blackboard(self.agent_name, f"perception: {perception_result.get('solution_summary', '')}")
        return perception_result

    def handle_perception_completion(self, session, perception_result):
        print("\n✅ Perception fully answered the query.")
        session.state.update({
            "original_goal_achieved": True,
            "final_answer": perception_result.get("solution_summary", "Answer ready."),
            "confidence": perception_result.get("confidence", 0.95),
            "reasoning_note": perception_result.get("reasoning", "Handled by perception."),
            "solution_summary": perception_result.get("solution_summary", "Answer ready.")
        })
        live_update_session(session)

    def make_initial_decision(self, query, perception_result, tool_perf_summary=None):
        decision_input = {
            "plan_mode": "initial",
            "planning_strategy": self.strategy,
            "original_query": query,
            "perception": perception_result,
            "tool_performance_summary": tool_perf_summary
        }
        decision_output = self.decision.run(decision_input)
        return decision_output

    def create_step(self, decision_output, was_replanned: bool = False, parent_index: int | None = None):
        return Step(
            index=decision_output["step_index"],
            description=decision_output["description"],
            type=decision_output["type"],
            code=ToolCode(tool_name="raw_code_block", tool_arguments={"code": decision_output["code"]}) if decision_output["type"] == "CODE" else None,
            conclusion=decision_output.get("conclusion"),
            was_replanned=was_replanned,
            parent_index=parent_index
        )

    async def execute_step(self, step, session, session_memory):
        print(f"\n[Step {step.index}] {step.description}")

        if step.type == "CODE":
            print("-" * 50, "\n[EXECUTING CODE]\n", step.code.tool_arguments["code"])
            executor_response = await run_user_code(step.code.tool_arguments["code"], self.multi_mcp)
            if executor_response.get("status") == "error":
                print("\n⚠️ Tool failed. Handing off to U1 in the loop.")
                human_answer = input("U1 in the loop: Please provide the answer for this step:\n> ").strip()
                executor_response = {
                    "status": "success",
                    "result": f"U1 in the loop: {human_answer}",
                    "human_in_loop": True,
                    "tool_error": executor_response.get("error", "Unknown tool error")
                }
                session_memory.append({
                    "query": step.description,
                    "result_requirement": "U1 in the loop",
                    "solution_summary": executor_response["result"][:300]
                })
                if len(session_memory) > GLOBAL_PREVIOUS_FAILURE_STEPS:
                    session_memory.pop(0)

            step.execution_result = executor_response
            if os.getenv("DEBUG_PDB") == "1":
                import pdb; pdb.set_trace()
            step.status = "completed"

            tool_perf_summary = get_tool_performance_summary()
            perception_result = self.run_perception(
                query=executor_response.get('result', 'Tool Failed'),
                memory_results=session_memory,
                current_plan=session.plan_versions[-1]["plan_text"],
                snapshot_type="step_result",
                tool_perf_summary=tool_perf_summary
            )
            if self.is_off_topic(session.original_query, executor_response.get("result", "")):
                perception_result = self.lower_confidence(perception_result, reason="Off-topic tool result detected")
            step.perception = PerceptionSnapshot(**perception_result)
            self.handle_low_confidence(perception_result, context=self.context)

            if not step.perception or not step.perception.local_goal_achieved:
                failure_memory = {
                    "query": step.description,
                    "result_requirement": "Tool failed",
                    "solution_summary": str(step.execution_result)[:300]
                }
                session_memory.append(failure_memory)

                if len(session_memory) > GLOBAL_PREVIOUS_FAILURE_STEPS:
                    session_memory.pop(0)

            live_update_session(session)
            return step

        elif step.type == "CONCLUDE":
            print(f"\n💡 Conclusion: {step.conclusion}")
            step.execution_result = step.conclusion
            step.status = "completed"

            tool_perf_summary = get_tool_performance_summary()
            perception_result = self.run_perception(
                query=step.conclusion,
                memory_results=session_memory,
                current_plan=session.plan_versions[-1]["plan_text"],
                snapshot_type="step_result",
                tool_perf_summary=tool_perf_summary
            )
            step.perception = PerceptionSnapshot(**perception_result)
            self.handle_low_confidence(perception_result, context=self.context)
            session.mark_complete(step.perception, final_answer=step.conclusion)
            live_update_session(session)
            return None

        elif step.type == "NOP":
            print(f"\n❓ Clarification needed: {step.description}")
            step.status = "clarification_needed"
            live_update_session(session)
            return None


    def evaluate_step(self, step, session, query, retries):
        if step.perception.original_goal_achieved:
            print("\n✅ Goal achieved.")
            session.mark_complete(step.perception)
            live_update_session(session)
            return None, retries
        elif step.perception.local_goal_achieved:
            return self.get_next_step(session, query, step, retries)
        else:
            print("\n🔁 Step unhelpful. Replanning.")
            confidence_delta = session.compute_confidence_delta(step)
            if confidence_delta is not None and confidence_delta < 0:
                post_to_blackboard(self.agent_name, f"confidence_decline: Δ={confidence_delta:+.2f}")
            retries += 1
            if retries >= MAX_RETRIES:
                self.handle_plan_failure(session, query, step, retries)
                return None, retries
            decision_output = self.decision.run({
                "plan_mode": "mid_session",
                "planning_strategy": self.strategy,
                "original_query": query,
                "current_plan_version": len(session.plan_versions),
                "current_plan": session.plan_versions[-1]["plan_text"],
                "completed_steps": [s.to_dict() for s in session.plan_versions[-1]["steps"] if s.status == "completed"],
                "current_step": step.to_dict(),
                "tool_performance_summary": get_tool_performance_summary()
            })
            step = session.add_plan_version(
                decision_output["plan_text"],
                [self.create_step(decision_output, was_replanned=True, parent_index=step.index)]
            )

            print(f"\n[Decision Plan Text: V{len(session.plan_versions)}]:")
            for line in session.plan_versions[-1]["plan_text"]:
                print(f"  {line}")
            post_to_blackboard(self.agent_name, "decision: replanned due to unhelpful step")
            print(session.render_plan_history())

            return step, retries

    def get_next_step(self, session, query, step, retries):
        next_index = step.index + 1
        total_steps = len(session.plan_versions[-1]["plan_text"])
        if next_index < total_steps:
            decision_output = self.decision.run({
                "plan_mode": "mid_session",
                "planning_strategy": self.strategy,
                "original_query": query,
                "current_plan_version": len(session.plan_versions),
                "current_plan": session.plan_versions[-1]["plan_text"],
                "completed_steps": [s.to_dict() for s in session.plan_versions[-1]["steps"] if s.status == "completed"],
                "current_step": step.to_dict(),
                "tool_performance_summary": get_tool_performance_summary()
            })
            step = session.add_plan_version(
                decision_output["plan_text"],
                [self.create_step(decision_output)]
            )

            print(f"\n[Decision Plan Text: V{len(session.plan_versions)}]:")
            for line in session.plan_versions[-1]["plan_text"]:
                print(f"  {line}")
            post_to_blackboard(self.agent_name, "decision: next step generated")
            print(session.render_plan_history())

            return step, retries

        else:
            print("\n✅ No more steps.")
            return None, retries

    def handle_plan_failure(self, session, query, step, retries):
        print(f"\n🧭 Plan failed after {retries} retries. U1 in the loop required.")
        post_to_blackboard(self.agent_name, f"plan_failure: retries={retries}")
        suggested_plan = [
            "U1 in the loop: Confirm missing requirements and constraints (reason: reduce ambiguity).",
            "Use the most relevant tool with precise inputs (reason: improve accuracy).",
            "Summarize findings and conclude the answer (reason: finalize the response)."
        ]
        print("\nSuggested Plan:")
        for i, line in enumerate(suggested_plan, 1):
            print(f"  {i}. {line}")

        human_plan_text = input("\nU1 in the loop: Provide a revised plan with reasons; separate steps with hyphen (-), or press Enter to accept:\n> ").strip()
        if human_plan_text:
            chosen_plan = [
                f"U1 in the loop: {p.strip()}"
                for p in human_plan_text.split("-")
                if p.strip()
            ]
        else:
            chosen_plan = suggested_plan

        session.add_plan_version(chosen_plan, [])
        live_update_session(session)
        print("✅ Agent updated the plan based on U1 in the loop input.")
        post_to_blackboard(self.agent_name, "u1_plan_updated: agent listened")

        human_answer = input("Agent in the loop: Provide the answer for the failed part:\n> ").strip()
        session.state.update({
            "original_goal_achieved": True,
            "final_answer": f"Agnt U1 in the loop: {human_answer}",
            "confidence": 0.95,
            "reasoning_note": "U1 in the loop used after plan failure.",
            "solution_summary": f"U1 in the loop: {human_answer}"
        })
        live_update_session(session)

    def handle_max_steps(self, session, query):
        print(f"\n🛑 Max steps ({MAX_STEPS}) reached. U1 in the loop required.")
        post_to_blackboard(self.agent_name, f"max_steps_reached: {MAX_STEPS}")
        human_answer = input("U1 in the loop: Provide the answer to conclude:\n> ").strip()
        session.state.update({
            "original_goal_achieved": True,
            "final_answer": f"U1 in the loop: {human_answer}",
            "confidence": 0.9,
            "reasoning_note": "U1 in the loop used after max steps.",
            "solution_summary": f"U1 in the loop: {human_answer}"
        })
        live_update_session(session)

    def handle_low_confidence(self, perception_result: dict, context: AgentContext) -> None:
        try:
            confidence = float(perception_result.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        if confidence < 0.3:
            self.critic_agent.critique(perception_result, context)

    def is_off_topic(self, query: str, result: str) -> bool:
        if not query or not result:
            return False
        query_terms = {t.lower() for t in query.split() if len(t) > 3}
        if not query_terms:
            return False
        result_lower = result.lower()
        hits = sum(1 for t in query_terms if t in result_lower)
        return hits == 0

    def lower_confidence(self, perception_result: dict, reason: str, penalty: float = 0.3) -> dict:
        try:
            current = float(perception_result.get("confidence", 0.0))
        except (TypeError, ValueError):
            current = 0.0
        new_conf = max(0.0, current - penalty)
        perception_result["confidence"] = str(round(new_conf, 2))
        perception_result["local_reasoning"] = (
            f"{perception_result.get('local_reasoning', '')} | {reason}"
        ).strip()
        return perception_result