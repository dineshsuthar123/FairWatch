import json
import os
import re
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


def _sanitize_impact_text(text: Any) -> str:
    cleaned = str(text or "").strip()
    if not cleaned:
        return "Expected to reduce disparity after validation on fresh evaluation data."

    has_fake_precision = bool(
        re.search(r"(~\s*\d|\bfrom\s+\d|\bto\s+\d|\d+\.\d+|\d+\s*%)", cleaned.lower())
    )
    if has_fake_precision:
        return "Expected to reduce disparity, but exact impact must be validated on fresh evaluation data."

    return cleaned


def _sanitize_fix_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    fixes = payload.get("fixes", [])
    if not isinstance(fixes, list):
        payload["fixes"] = []
        return payload

    for fix in fixes:
        if not isinstance(fix, dict):
            continue
        fix["impact"] = _sanitize_impact_text(fix.get("impact"))

    if not payload.get("immediate_action"):
        payload["immediate_action"] = "Review fairness risks and validate mitigation before deployment."

    return payload


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
                    "action": "Increase sample weight for under-selected groups in training data",
                    "impact": "Expected to reduce demographic parity disparity after validation",
          "priority": "critical"
        }},
        {{
          "type": "remove_proxy",
                    "action": "Review and remove proxy-heavy features that closely track sensitive attributes",
                    "impact": "Reduces proxy-driven disparity risk",
          "priority": "high"
        }},
        {{
          "type": "threshold_tuning",
                    "action": "Tune decision thresholds using a fairness-constrained validation process",
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
        parsed = json.loads(clean)
        if not isinstance(parsed, dict):
            raise ValueError("LLM response is not a JSON object")
        return _sanitize_fix_payload(parsed)
    except Exception as exc:
        return {
            "fixes": [],
            "immediate_action": f"Fix generation unavailable: {exc}"
        }
