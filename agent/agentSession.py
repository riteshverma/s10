from dataclasses import dataclass, asdict
from typing import Any, Literal, Optional
import uuid
import time
import json

@dataclass
class ToolCode:
    tool_name: str
    tool_arguments: dict[str, Any]

    def to_dict(self):
        return {
            "tool_name": self.tool_name,
            "tool_arguments": self.tool_arguments
        }


@dataclass
class PerceptionSnapshot:
    entities: list[str]
    result_requirement: str
    original_goal_achieved: bool
    reasoning: str
    local_goal_achieved: bool
    local_reasoning: str
    last_tooluse_summary: str
    solution_summary: str
    confidence: str

@dataclass
class Step:
    index: int
    description: str
    type: Literal["CODE", "CONCLUDE", "NOOP"]
    code: Optional[ToolCode] = None
    conclusion: Optional[str] = None
    execution_result: Optional[str] = None
    error: Optional[str] = None
    perception: Optional[PerceptionSnapshot] = None
    confidence_delta: Optional[float] = None
    status: Literal["pending", "completed", "failed", "skipped"] = "pending"
    attempts: int = 0
    was_replanned: bool = False
    parent_index: Optional[int] = None

    def to_dict(self):
        return {
            "index": self.index,
            "description": self.description,
            "type": self.type,
            "code": self.code.to_dict() if self.code else None,
            "conclusion": self.conclusion,
            "execution_result": self.execution_result,
            "error": self.error,
            "perception": self.perception.__dict__ if self.perception else None,
            "confidence_delta": self.confidence_delta,
            "status": self.status,
            "attempts": self.attempts,
            "was_replanned": self.was_replanned,
            "parent_index": self.parent_index
        }


class AgentSession:
    def __init__(self, session_id: str, original_query: str):
        self.session_id = session_id
        self.original_query = original_query
        self.perception: Optional[PerceptionSnapshot] = None
        self.plan_versions: list[dict[str, Any]] = []
        self.plan_history: list[list[str]] = []
        self.step_history: dict[int, list[Step]] = {}
        self.state = {
            "original_goal_achieved": False,
            "final_answer": None,
            "confidence": 0.0,
            "reasoning_note": "",
            "solution_summary": ""
            
        }

    def add_perception(self, snapshot: PerceptionSnapshot):
        self.perception = snapshot

    def add_plan_version(self, plan_texts: list[str], steps: list[Step]):
        plan = {
            "plan_text": plan_texts,
            "steps": steps.copy()
        }
        self.plan_versions.append(plan)
        self.plan_history.append(plan_texts)
        for step in steps:
            self.add_step_revision(step)
        return steps[0] if steps else None  # ✅ fix: return first Step

    def add_step_revision(self, step: Step) -> None:
        self.step_history.setdefault(step.index, []).append(step)

    def get_step_history(self, step_index: int) -> list[Step]:
        return list(self.step_history.get(step_index, []))

    def _parse_confidence(self, value: Any) -> Optional[float]:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def get_last_confidence(self, step_index: int, exclude_current: bool = False) -> Optional[float]:
        history = self.step_history.get(step_index, [])
        if exclude_current and history:
            history = history[:-1]
        for step in reversed(history):
            if step.perception:
                conf = self._parse_confidence(step.perception.confidence)
                if conf is not None:
                    return conf
        return None

    def compute_confidence_delta(self, step: Step) -> Optional[float]:
        if not step.perception:
            return None
        current = self._parse_confidence(step.perception.confidence)
        if current is None:
            return None
        previous = self.get_last_confidence(step.index, exclude_current=True)
        if previous is None:
            return None
        step.confidence_delta = current - previous
        return step.confidence_delta

    def get_next_step_index(self) -> int:
        return sum(len(v["steps"]) for v in self.plan_versions)


    def to_json(self):
        return {
            "session_id": self.session_id,
            "original_query": self.original_query,
            "perception": asdict(self.perception) if self.perception else None,
            "plan_versions": [
                {
                    "plan_text": p["plan_text"],
                    "steps": [asdict(s) for s in p["steps"]]
                } for p in self.plan_versions
            ],
            "step_history": {
                str(k): [asdict(s) for s in v]
                for k, v in self.step_history.items()
            },
            "state_snapshot": self.get_snapshot_summary()
        }

    def get_snapshot_summary(self):
        return {
            "session_id": self.session_id,
            "query": self.original_query,
            "final_plan": self.plan_versions[-1]["plan_text"] if self.plan_versions else [],
           "final_steps": [
                    asdict(s)
                    for version in self.plan_versions
                    for s in version["steps"]
                    if s.status == "completed"
                ],
            "final_answer": self.state["final_answer"],
            "confidence": self.state["confidence"],
            "reasoning_note": self.state["reasoning_note"]
        }

    def mark_complete(self, perception: PerceptionSnapshot, final_answer: Optional[str] = None, fallback_confidence: float = 0.95):
        self.state.update({
            "original_goal_achieved": perception.original_goal_achieved,
            "final_answer": final_answer or perception.solution_summary,
            "confidence": perception.confidence or fallback_confidence,
            "reasoning_note": perception.reasoning,
            "solution_summary": perception.solution_summary
        })



    def simulate_live(self, delay: float = 1.2):
        print("\n=== LIVE AGENT SESSION TRACE ===")
        print(f"Session ID: {self.session_id}")
        print(f"Query: {self.original_query}")
        time.sleep(delay)

        if self.perception:
            print("\n[Perception 0] Initial ERORLL:")
            print(f"  {asdict(self.perception)}")
            time.sleep(delay)

        for i, version in enumerate(self.plan_versions):
            print(f"\n[Decision Plan Text: V{i+1}]:")
            for j, p in enumerate(version["plan_text"]):
                print(f"  Step {j}: {p}")
            time.sleep(delay)

            for step in version["steps"]:
                print(f"\n[Step {step.index}] {step.description}")
                time.sleep(delay / 1.5)

                print(f"  Type: {step.type}")
                if step.code:
                    print(f"  Tool → {step.code.tool_name} | Args → {step.code.tool_arguments}")
                if step.execution_result:
                    print(f"  Execution Result: {step.execution_result}")
                if step.conclusion:
                    print(f"  Conclusion: {step.conclusion}")
                if step.error:
                    print(f"  Error: {step.error}")
                if step.perception:
                    print("  Perception ERORLL:")
                    for k, v in asdict(step.perception).items():
                        print(f"    {k}: {v}")
                if step.confidence_delta is not None:
                    print(f"  Confidence Delta: {step.confidence_delta:+.2f}")
                print(f"  Status: {step.status}")
                if step.was_replanned:
                    print(f"  (Replanned from Step {step.parent_index})")
                if step.attempts > 1:
                    print(f"  Attempts: {step.attempts}")
                time.sleep(delay)

        print("\n[Session Snapshot]:")
        print(json.dumps(self.get_snapshot_summary(), indent=2))

    def render_plan_history(self) -> str:
        lines = ["Plan History:"]
        for i, version in enumerate(self.plan_versions, 1):
            lines.append(f"v{i}:")
            for step in version["steps"]:
                parent = f" (replan from {step.parent_index})" if step.was_replanned else ""
                delta = ""
                if step.confidence_delta is not None:
                    delta = f" Δconf={step.confidence_delta:+.2f}"
                lines.append(f"  - Step {step.index}: {step.description}{parent}{delta}")
        return "\n".join(lines)
