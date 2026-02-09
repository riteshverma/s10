import os
import json
import yaml
import requests
from pathlib import Path
from google import genai
from agent.runtime_config import gemini_generation_config, get_llm_generation_settings
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent.parent
MODELS_JSON = ROOT / "config" / "models.json"
PROFILE_YAML = ROOT / "config" / "profiles.yaml"

class ModelManager:
    def __init__(self):
        self.config = json.loads(MODELS_JSON.read_text())
        self.profile = yaml.safe_load(PROFILE_YAML.read_text())

        self.text_model_key = self.profile["llm"]["text_generation"]
        self.model_info = self.config["models"][self.text_model_key]
        self.model_type = self.model_info["type"]

        # ✅ Gemini initialization (your style)
        if self.model_type == "gemini":
            api_key = os.getenv("GEMINI_API_KEY")
            self.client = genai.Client(api_key=api_key)

    async def generate_text(self, prompt: str) -> str:
        if self.model_type == "gemini":
            return self._gemini_generate(prompt)

        elif self.model_type == "ollama":
            return self._ollama_generate(prompt)

        raise NotImplementedError(f"Unsupported model type: {self.model_type}")

    def _gemini_generate(self, prompt: str) -> str:
        response = self.client.models.generate_content(
            model=self.model_info["model"],
            contents=prompt,
            config=gemini_generation_config()
        )

        # ✅ Safely extract response text
        try:
            return response.text.strip()
        except AttributeError:
            try:
                return response.candidates[0].content.parts[0].text.strip()
            except Exception:
                return str(response)

    def _ollama_generate(self, prompt: str) -> str:
        settings = get_llm_generation_settings()
        options = {
            "temperature": settings.get("temperature", 0.0),
            "top_p": settings.get("top_p", 1.0),
            "top_k": settings.get("top_k", 1),
        }
        if "seed" in settings:
            options["seed"] = settings.get("seed")
        response = requests.post(
            self.model_info["url"]["generate"],
            json={
                "model": self.model_info["model"],
                "prompt": prompt,
                "stream": False,
                "options": options
            }
        )
        response.raise_for_status()
        return response.json()["response"].strip()
