import json
import os
from collections import defaultdict
from typing import Dict, List


SUCCESS_STATUSES = {"success", "completed"}
FAIL_STATUSES = {"failed", "error", "blocked", "pending"}


def load_json(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_tool_calls(session: Dict) -> List[Dict]:
    calls = []

    for plan in session.get("plan_versions", []):
        for step in plan.get("steps", []):
            code = step.get("code")
            if not code:
                continue

            tool_name = code.get("tool_name", "unknown")
            execution = step.get("execution_result")

            if execution is None:
                status = "incomplete"
            else:
                status = execution.get("status", "unknown")

            calls.append({
                "tool": tool_name,
                "status": status.lower()
            })

    return calls


def classify_session_outcome(session: Dict) -> str:
    perception = session.get("perception", {})
    state = session.get("state_snapshot", {})

    if perception.get("original_goal_achieved") is True:
        return "success"

    if state.get("final_answer") is not None:
        return "partial"

    return "failed"


def analyze_logs(log_dir: str):
    tool_stats = defaultdict(lambda: {"total": 0, "success": 0, "failure": 0})
    session_outcomes = defaultdict(int)

    for file in os.listdir(log_dir):
        if not file.endswith(".json"):
            continue

        session = load_json(os.path.join(log_dir, file))

        # ---- Session outcome ----
        outcome = classify_session_outcome(session)
        session_outcomes[outcome] += 1

        # ---- Tool usage ----
        tool_calls = extract_tool_calls(session)

        if not tool_calls:
            tool_stats["direct_reasoning"]["total"] += 1
            tool_stats["direct_reasoning"]["success"] += 1
            continue

        for call in tool_calls:
            tool = call["tool"]
            status = call["status"]

            tool_stats[tool]["total"] += 1

            if status in SUCCESS_STATUSES:
                tool_stats[tool]["success"] += 1
            else:
                tool_stats[tool]["failure"] += 1

    return tool_stats, session_outcomes


def print_table(tool_stats, session_outcomes):
    print("\n=== TOOL USAGE SUMMARY ===\n")
    header = f"{'Tool':30} {'Total':>6} {'Success':>8} {'Failure':>8} {'Pass %':>8}"
    print(header)
    print("-" * len(header))

    for tool, stats in tool_stats.items():
        total = stats["total"]
        success = stats["success"]
        failure = stats["failure"]
        pass_rate = (success / total * 100) if total else 0.0

        print(f"{tool:30} {total:6} {success:8} {failure:8} {pass_rate:7.1f}%")

    print("\n=== SESSION OUTCOMES ===\n")
    total_sessions = sum(session_outcomes.values())

    for outcome, count in session_outcomes.items():
        pct = (count / total_sessions * 100) if total_sessions else 0.0
        print(f"{outcome.capitalize():10}: {count:3} ({pct:5.1f}%)")

    print(f"\nTotal sessions analyzed: {total_sessions}")


if __name__ == "__main__":
    LOG_DIR = "./"  # <-- put all your JSON files here

    tool_stats, session_outcomes = analyze_logs(LOG_DIR)
    print_table(tool_stats, session_outcomes)
