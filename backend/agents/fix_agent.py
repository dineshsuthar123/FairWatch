import json
import os
from pathlib import Path
from typing import Any, Dict

from groq import Groq


def _load_local_env_file() -> None:
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
        return


_load_local_env_file()
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))


def generate_fixes(bias_report_dict, feature_contributions):
    if not os.environ.get("GROQ_API_KEY"):
        return {
            "fixes": [],
            "immediate_action": "Set GROQ_API_KEY to enable fix generation."
        }

    prompt = f"""
    You are an ML fairness engineer. Given this bias report and feature 
    contributions, generate ONLY concrete, specific, actionable fixes.
    
    Bias Report: {json.dumps(bias_report_dict)}
    Feature Contributions: {json.dumps(feature_contributions)}
    
    Respond ONLY in this exact JSON format, no extra text:
    {{
      "fixes": [
        {{
          "type": "reweight",
          "action": "Increase sample weight of female records by 1.8x in training data",
          "impact": "Expected to reduce DP difference from 0.34 to ~0.12",
          "priority": "critical"
        }},
        {{
          "type": "remove_proxy",
          "action": "Drop zip_code column — correlates 0.73 with race attribute",
          "impact": "Removes 18% of race-based disparity",
          "priority": "high"
        }},
        {{
          "type": "threshold_tuning",
          "action": "Lower decision threshold for group=female from 0.5 to 0.40",
          "impact": "Equalizes approval rates without retraining",
          "priority": "medium"
        }}
      ],
      "immediate_action": "Suspend model deployment until threshold is tuned"
    }}
    """

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )

        raw = response.choices[0].message.content
        # Strip markdown if present
        clean = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(clean)
    except Exception as exc:
        return {
            "fixes": [],
            "immediate_action": f"Fix generation unavailable: {exc}"
        }
