import json
import os
from pathlib import Path
from typing import Any, Dict

from groq import Groq

SYSTEM_PROMPT = (
    "You are an AI fairness auditor explaining bias reports to non-technical "
    "business managers. Be direct, specific, and use plain English. "
    "Never use jargon. Always state the real-world impact."
)


def _load_local_env_file() -> None:
    """Load key/value pairs from backend/.env into process env if missing."""
    env_file = Path(__file__).resolve().parents[1] / ".env"
    if not env_file.exists():
        return

    try:
        for raw_line in env_file.read_text(encoding="utf-8-sig").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            if line.startswith("export "):
                line = line[len("export "):].strip()

            if "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()

            if len(value) >= 2 and ((value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")):
                value = value[1:-1]

            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        # If reading .env fails, runtime falls back to normal environment variables.
        return


_load_local_env_file()
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))


def generate_explanation(bias_report_dict: Dict[str, Any], feature_contributions: Dict[str, Any]) -> str:
    if not os.environ.get("GROQ_API_KEY"):
        return "Groq API key is missing. Set GROQ_API_KEY to generate an AI-written fairness explanation."

    prompt = f"""
    You are an AI fairness auditor reporting to a non-technical executive.
    
    Rules:
    - Every claim MUST reference a specific number from the data
    - Explain root cause using feature names provided
    - State real-world consequences in plain English
    - Maximum 200 words
    - No jargon, no bullet hell — write in clear paragraphs
    - Never say "retrain the model" without saying exactly how
    
    Bias Data: {json.dumps(bias_report_dict)}
    Root Cause Features: {json.dumps(feature_contributions)}
    
    Structure your response as:
    
    WHAT IS HAPPENING (2 sentences with numbers)
    WHY IT IS HAPPENING (feature names causing it)  
    REAL WORLD IMPACT (specific consequences)
    IMMEDIATE ACTION (one concrete sentence)
    """

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return response.choices[0].message.content
    except Exception as exc:
        return (
            "FairWatch could not reach the explanation service right now. "
            f"The monitoring engine still detected disparity signals. Error: {exc}"
        )
