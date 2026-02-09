import os
import json
import uuid
import datetime
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai.errors import ServerError
from agent.runtime_config import (
    deterministic_timestamp,
    gemini_generation_config,
    is_deterministic,
    stable_run_id,
)

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

class Perception:
    def __init__(self, perception_prompt_path: str, api_key: str | None = None, model: str = "gemini-2.0-flash"):
        load_dotenv()
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found in environment or explicitly provided.")
        self.client = genai.Client(api_key=self.api_key)
        self.perception_prompt_path = perception_prompt_path

    def build_perception_input(self, raw_input: str, memory: list, current_plan = "", snapshot_type: str = "user_query", tool_performance_summary: dict | None = None, analysis_hint: str | None = None) -> dict:
        if memory:
            memory_excerpt = {
                f"memory_{i+1}": {
                    "query": res["query"],
                    "result_requirement": res["result_requirement"],
                    "solution_summary": res["solution_summary"]
                }
                for i, res in enumerate(memory)}
        else:
            memory_excerpt = {}

        deterministic = is_deterministic()
        run_id = stable_run_id(raw_input, snapshot_type, current_plan or "") if deterministic else str(uuid.uuid4())
        timestamp = deterministic_timestamp() if deterministic else datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"

        return {
            "run_id": run_id,
            "snapshot_type": snapshot_type,
            "raw_input": raw_input,
            "memory_excerpt": memory_excerpt,
            "tool_performance_summary": tool_performance_summary or {},
            "prev_objective": "",
            "prev_confidence": None,
            "timestamp": timestamp,
            "schema_version": 1,
            "current_plan" : current_plan or "Inain Query Mode, plan not created",
            "analysis_hint": analysis_hint or ""
        }
    
    def run(self, perception_input: dict) -> dict:
        """Run perception on given input using the specified prompt file."""
        prompt_template = Path(self.perception_prompt_path).read_text(encoding="utf-8")
        full_prompt = f"{prompt_template.strip()}\n\n```json\n{json.dumps(perception_input, indent=2)}\n```"

        try:
            response = self.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=full_prompt,
                config=gemini_generation_config()
            )
        except ServerError as e:
            print(f"🚫 Perception LLM ServerError: {e}")
            return {
                "step_index": 0,
                "description": "Perception model unavailable: server overload.",
                "type": "NOP",
                "code": "",
                "conclusion": "",
                "plan_text": ["Step 0: Perception model returned a 503. Exiting to avoid loop."],
                "raw_text": str(e)
            }

        raw_text = response.text.strip()

        def _coerce_bool(value, default: bool) -> bool:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                lowered = value.strip().lower()
                if lowered in {"true", "yes", "y", "1"}:
                    return True
                if lowered in {"false", "no", "n", "0"}:
                    return False
            if isinstance(value, (int, float)):
                return bool(value)
            return default

        def _coerce_float(value, default: float) -> float:
            try:
                return float(value)
            except (TypeError, ValueError):
                return default

        try:
            json_block = raw_text.split("```json")[1].split("```")[0].strip()

            # Minimal sanitization — no unicode decoding
            output = json.loads(json_block)

            # ✅ Patch missing fields for PerceptionSnapshot
            required_fields = {
                "entities": [],
                "result_requirement": "No requirement specified.",
                "original_goal_achieved": False,
                "reasoning": "No reasoning given.",
                "local_goal_achieved": False,
                "local_reasoning": "No local reasoning given.",
                "last_tooluse_summary": "None",
                "solution_summary": "No summary.",
                "confidence": "0.0"
            }

            for key, default in required_fields.items():
                output.setdefault(key, default)

            output["original_goal_achieved"] = _coerce_bool(
                output.get("original_goal_achieved"), False
            )
            output["local_goal_achieved"] = _coerce_bool(
                output.get("local_goal_achieved"), False
            )
            output["confidence"] = _coerce_float(output.get("confidence"), 0.0)

            return output

        except Exception as e:
            # Optional: log to disk for inspection
            import pdb; pdb.set_trace()

            print("❌ EXCEPTION IN PERCEPTION:", e)
            return {
                "entities": [],
                "result_requirement": "N/A",
                "original_goal_achieved": False,
                "reasoning": "Perception failed to parse model output as JSON.",
                "local_goal_achieved": False,
                "local_reasoning": "Could not extract structured information.",
                "solution_summary": "Not ready yet",
                "confidence": "0.0"
            }


