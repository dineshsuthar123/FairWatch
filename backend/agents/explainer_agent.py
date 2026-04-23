import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from groq import Groq

from agents.fairness_summary import (
    build_fairness_snapshot,
    format_list,
    normalize_metric_score,
)

SYSTEM_PROMPT = """You are an AI fairness auditor writing for non-technical business users.

Return STRICT JSON only:
{
  "headline": "...",
  "what_is_happening": "...",
  "why_it_is_happening": "...",
  "affected_groups": ["..."],
  "real_world_impact": "...",
  "recommended_action": "..."
}

Rules:
- Use only the supplied data
- Keep every field short and plain English
- Mention the strongest fairness metric with its number when available
- Mention the main root-cause features when available
- Mention the affected groups when available
- If the latest status is red or critical, the headline must clearly say the model is unsafe to deploy
- No markdown
- No extra commentary outside JSON
"""


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
client = Groq(api_key=os.environ.get("GROQ_API_KEY")) if os.environ.get("GROQ_API_KEY") else None


def _strip_code_fence(content: str) -> str:
    cleaned = content.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()


def _build_local_explanation(
    bias_report_dict: Dict[str, Any],
    feature_contributions: Dict[str, Any],
    fix_suggestions: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    metrics = bias_report_dict.get("reports") or bias_report_dict.get("metrics") or []
    snapshot = build_fairness_snapshot(
        metrics=metrics,
        feature_contributions=feature_contributions,
        fix_suggestions=fix_suggestions,
        decision_summary=bias_report_dict.get("decision_summary"),
    )

    top_metric = snapshot["top_metric"] or {}
    metric_name = str(top_metric.get("metric_name") or "fairness metric").strip()
    metric_score = normalize_metric_score(top_metric)
    groups_text = format_list(snapshot["affected_groups"][:3]) or "the compared groups"
    root_cause_text = format_list(snapshot["root_cause_details"][:3])
    proxy_warning = snapshot["proxy_warnings"][0] if snapshot["proxy_warnings"] else ""

    if snapshot["risk_level"] == "unsafe":
        headline = "Unsafe to deploy."
    elif snapshot["risk_level"] == "risky":
        headline = "Fairness risk needs action before deployment."
    else:
        headline = "No critical fairness issue detected."

    if snapshot.get("confidence") == "low":
        headline += " Low confidence"

    if top_metric:
        what_is_happening = (
            f"The strongest issue is {metric_name} at {metric_score:.4f}, and it is affecting {groups_text}."
        )
    else:
        what_is_happening = "No fairness metric details are available in the latest report."

    if root_cause_text:
        why_it_is_happening = f"The main bias drivers are {root_cause_text}."
        if proxy_warning:
            why_it_is_happening += f" A proxy warning was also flagged: {proxy_warning}."
    elif proxy_warning:
        why_it_is_happening = f"A proxy warning was flagged: {proxy_warning}."
    else:
        why_it_is_happening = "No clear root cause was recorded in the latest report."

    if snapshot["risk_level"] == "unsafe":
        real_world_impact = f"People in {groups_text} may receive unfair decisions. This model is unsafe to deploy."
    elif snapshot["risk_level"] == "risky":
        real_world_impact = f"People in {groups_text} may receive uneven decisions unless the model is fixed."
    else:
        real_world_impact = f"No critical deployment block is shown right now, but {groups_text} should still be monitored."

    if snapshot.get("confidence_warning"):
        real_world_impact += f" {snapshot['confidence_warning']}."

    return {
        "headline": headline,
        "what_is_happening": what_is_happening,
        "why_it_is_happening": why_it_is_happening,
        "affected_groups": snapshot["affected_groups"],
        "real_world_impact": real_world_impact,
        "recommended_action": snapshot["recommended_action"],
    }


def _validate_explanation(payload: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return fallback

    cleaned = {
        "headline": str(payload.get("headline") or "").strip() or fallback["headline"],
        "what_is_happening": str(payload.get("what_is_happening") or "").strip() or fallback["what_is_happening"],
        "why_it_is_happening": str(payload.get("why_it_is_happening") or "").strip() or fallback["why_it_is_happening"],
        "affected_groups": payload.get("affected_groups") if isinstance(payload.get("affected_groups"), list) else fallback["affected_groups"],
        "real_world_impact": str(payload.get("real_world_impact") or "").strip() or fallback["real_world_impact"],
        "recommended_action": str(payload.get("recommended_action") or "").strip() or fallback["recommended_action"],
    }

    cleaned["affected_groups"] = [
        str(group).strip() for group in cleaned["affected_groups"] if str(group).strip()
    ] or fallback["affected_groups"]

    if "unsafe" in fallback["headline"].lower() and "unsafe" not in cleaned["headline"].lower():
        cleaned["headline"] = fallback["headline"]

    return cleaned


def generate_explanation(
    bias_report_dict: Dict[str, Any],
    feature_contributions: Dict[str, Any],
    fix_suggestions: Optional[Dict[str, Any]] = None,
) -> str:
    fallback = _build_local_explanation(bias_report_dict, feature_contributions, fix_suggestions)

    if client is None:
        return json.dumps(fallback)

    prompt = (
        f"Bias data: {json.dumps(bias_report_dict)}\n"
        f"Root cause features: {json.dumps(feature_contributions)}\n"
        f"Recommended fixes: {json.dumps(fix_suggestions or {})}\n"
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        content = _strip_code_fence(response.choices[0].message.content or "")
        parsed = json.loads(content)
        return json.dumps(_validate_explanation(parsed, fallback))
    except Exception:
        return json.dumps(fallback)
