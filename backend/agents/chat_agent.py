import json
import os
import re
from pathlib import Path
from typing import Any, Dict

from groq import Groq

from agents.fairness_summary import (
    build_fairness_snapshot,
    format_list,
    normalize_metric_score,
)

GREETING_WORDS = {"hello", "hi", "hey", "hii", "helo", "good morning", "good afternoon", "good evening"}
RELEVANT_KEYWORDS = {
    "model",
    "data",
    "fair",
    "fairness",
    "bias",
    "biased",
    "decision",
    "decisions",
    "impact",
    "explain",
    "explanation",
    "fix",
    "fixes",
    "deployment",
    "deploy",
    "affected",
    "groups",
    "root cause",
    "cause",
    "causing",
    "status",
}
CORE_RELEVANT_KEYWORDS = {
    "model",
    "data",
    "fair",
    "fairness",
    "bias",
    "decision",
    "decisions",
    "deployment",
    "deploy",
    "fix",
    "fixes",
    "affected",
    "groups",
}
VAGUE_RELEVANT_PHRASES = {
    "what does this mean",
    "what does it mean",
    "what does this tell us",
    "is this safe",
    "is it safe",
    "explain this",
    "explain about the data",
    "explain the data",
    "explain the model",
    "tell me about the data",
    "tell me about the model",
}
OFF_TOPIC_KEYWORDS = {
    "cooking",
    "recipe",
    "recipes",
    "sports",
    "movie",
    "movies",
    "cricket",
    "football",
    "basketball",
    "tennis",
    "weather",
    "music",
    "song",
    "songs",
    "celebrity",
    "travel",
    "joke",
    "poem",
}
UNRELATED_CHAT_PHRASES = {
    "how are you",
    "who are you",
    "what's up",
    "whats up",
    "tell me a joke",
    "tell me something fun",
}

OFF_TOPIC_RESPONSE = {
    "answer": "I can only help with AI fairness and model decisions.",
    "risk_level": "safe",
    "affected_groups": [],
    "recommended_action": "Ask about the model, data, bias, or deployment safety.",
}

SYSTEM_PROMPT = """You are Fairness Copilot for FairWatch.

Use only the provided context. Accept any question that is even loosely related to:
... [trimmed system boundaries] ...

Output STRICT JSON only:
{
  "answer": "...",
  "risk_level": "safe | risky | unsafe",
  "affected_groups": ["..."],
  "recommended_action": "..."
}

Rules:
- No markdown
- No extra commentary outside JSON
- Must explain decisions in human terms
- Must mention who is affected and why the decision was blocked
- Must NOT output raw metrics first
- If the status is unsafe (blocked), answer clearly. Example: "This decision was blocked because the model favors male applicants. Female applicants were receiving fewer approvals."
- Keep the answer plain English
- If the user says hello or hi, reply with a short greeting
- Distinguish live window metrics from aggregate metrics when relevant
- For unrelated questions, return exactly:
  {"answer":"I can only help with AI fairness and model decisions.","risk_level":"safe","affected_groups":[],"recommended_action":"Ask about the model, data, bias, or deployment safety."}
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


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _is_greeting(normalized_query: str) -> bool:
    if normalized_query in GREETING_WORDS:
        return True
    words = normalized_query.split()
    return len(words) <= 2 and any(word in GREETING_WORDS for word in words)


def _has_relevant_signal(normalized_query: str) -> bool:
    if any(keyword in normalized_query for keyword in RELEVANT_KEYWORDS):
        return True
    if normalized_query in VAGUE_RELEVANT_PHRASES:
        return True
    return normalized_query in {"what does this mean?", "is this safe?", "what does this mean", "is this safe"}


def _is_vague_but_relevant(normalized_query: str) -> bool:
    words = normalized_query.split()
    if len(words) > 8:
        return False

    vague_terms = {"explain", "mean", "means", "safe", "unsafe", "why", "how", "what", "this", "it"}
    return any(word in vague_terms for word in words)


def _is_off_topic(normalized_query: str) -> bool:
    if normalized_query in UNRELATED_CHAT_PHRASES:
        return True
    has_core_signal = any(keyword in normalized_query for keyword in CORE_RELEVANT_KEYWORDS)
    if any(keyword in normalized_query for keyword in OFF_TOPIC_KEYWORDS) and not has_core_signal:
        return True
    return False


def _classify_query(query: str) -> str:
    normalized_query = _normalize_text(query)

    if _is_greeting(normalized_query):
        return "greeting"
    if _is_off_topic(normalized_query):
        return "off_topic"
    if "data" in normalized_query or "dataset" in normalized_query:
        return "data"
    if any(term in normalized_query for term in {"deploy", "deployment", "safe", "unsafe", "risk", "risky"}):
        return "safety"
    if any(term in normalized_query for term in {"fix", "fixes", "action", "actions", "improve"}):
        return "fix"
    if any(term in normalized_query for term in {"explain", "meaning", "mean", "means", "why", "what does"}):
        return "explain"
    if any(term in normalized_query for term in {"fairness", "bias", "decision", "impact", "model", "groups"}):
        return "fairness"
    if _has_relevant_signal(normalized_query) or _is_vague_but_relevant(normalized_query):
        return "explain"
    return "off_topic"


def _strip_code_fence(content: str) -> str:
    cleaned = content.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()


def _groups_text(snapshot: Dict[str, Any]) -> str:
    return format_list(snapshot["affected_groups"][:3])


def _root_cause_text(snapshot: Dict[str, Any]) -> str:
    details = snapshot["root_cause_details"][:3]
    if details:
        return format_list(details)
    if snapshot["proxy_warnings"]:
        return snapshot["proxy_warnings"][0]
    return ""


def _metric_text(snapshot: Dict[str, Any]) -> str:
    metric = snapshot["top_metric"]
    if not metric:
        return ""

    meaning = str(metric.get("interpretation") or metric.get("metric_meaning") or "").strip()
    if meaning:
        return meaning

    metric_name = str(metric.get("metric_name") or "fairness metric")
    score = normalize_metric_score(metric)
    return f"{metric_name} is {score:.4f} in the latest report."


def _build_local_response(intent: str, snapshot: Dict[str, Any]) -> Dict[str, Any]:
    risk_level = snapshot["risk_level"]
    groups_text = _groups_text(snapshot)
    root_cause_text = _root_cause_text(snapshot)
    metric_text = _metric_text(snapshot)
    confidence_warning = str(snapshot.get("confidence_warning") or "").strip()
    decision_reason = str(snapshot.get("decision_reason") or "").strip()

    if intent == "greeting":
        answer = "Hi. I can help explain the model's fairness status, affected groups, and deployment safety."
    elif intent == "data":
        answer = "The current data is driving fairness risk."
        if groups_text:
            answer += f" It is affecting {groups_text}."
        if root_cause_text:
            answer += f" Key drivers are {root_cause_text}."
        if risk_level == "unsafe":
            answer += " This model is unsafe to deploy."
    elif intent == "safety":
        if risk_level == "unsafe":
            answer = "No. This model is unsafe to deploy."
        elif risk_level == "risky":
            answer = "Not yet. This model is risky to deploy."
        else:
            answer = "The latest report does not show a critical fairness issue."

        if groups_text:
            answer += f" It is affecting {groups_text}."
        if root_cause_text:
            answer += f" Main drivers are {root_cause_text}."
        if confidence_warning:
            answer += f" {confidence_warning}."
    elif intent == "fix":
        answer = f"Start with {snapshot['recommended_action'].rstrip('.')}."
        if groups_text:
            answer += f" This targets {groups_text}."
        if root_cause_text:
            answer += f" The main drivers are {root_cause_text}."
        if confidence_warning:
            answer += f" {confidence_warning}."
    else:
        if risk_level == "unsafe":
            answer = "This model is unsafe to deploy."
        elif risk_level == "risky":
            answer = "The latest report shows fairness risk."
        else:
            answer = "The latest report does not show a critical fairness issue."

        if groups_text:
            answer += f" It is affecting {groups_text}."
        if root_cause_text:
            answer += f" Main drivers are {root_cause_text}."
        elif metric_text:
            answer += f" {metric_text}"

    if decision_reason:
        answer += f" Decision summary: {decision_reason}."
    if confidence_warning and confidence_warning.lower() not in answer.lower():
        answer += f" {confidence_warning}."

    return {
        "answer": answer.strip(),
        "risk_level": risk_level,
        "affected_groups": snapshot["affected_groups"],
        "recommended_action": snapshot["recommended_action"],
    }


def _build_prompt(query: str, intent: str, context: Dict[str, Any], snapshot: Dict[str, Any]) -> str:
    return (
        f"Query intent: {intent}\n"
        f"User query: {query}\n"
        f"Derived fairness summary: {json.dumps(snapshot)}\n"
        f"Full context: {json.dumps(context)}\n"
    )


def _validate_response(
    parsed: Dict[str, Any],
    fallback: Dict[str, Any],
    snapshot: Dict[str, Any],
    intent: str,
) -> Dict[str, Any]:
    answer = str(parsed.get("answer") or "").strip()
    if not answer:
        return fallback

    if intent != "off_topic" and "i can only help" in answer.lower():
        return fallback

    risk_level = str(parsed.get("risk_level") or "").strip().lower()
    if risk_level not in {"safe", "risky", "unsafe"}:
        risk_level = fallback["risk_level"]

    affected_groups = parsed.get("affected_groups")
    if not isinstance(affected_groups, list):
        affected_groups = fallback["affected_groups"]
    else:
        affected_groups = [str(group).strip() for group in affected_groups if str(group).strip()]

    recommended_action = str(parsed.get("recommended_action") or "").strip() or fallback["recommended_action"]

    if snapshot["risk_level"] == "unsafe" and "unsafe" not in answer.lower():
        return fallback

    return {
        "answer": answer,
        "risk_level": snapshot["risk_level"] if snapshot["risk_level"] == "unsafe" else risk_level,
        "affected_groups": affected_groups or fallback["affected_groups"],
        "recommended_action": recommended_action,
    }


def handle_query(query: str, context: Dict[str, Any]) -> Dict[str, Any]:
    intent = _classify_query(query)
    if intent == "off_topic":
        return OFF_TOPIC_RESPONSE

    snapshot = build_fairness_snapshot(
        metrics=context.get("metrics"),
        feature_contributions=context.get("feature_contributions"),
        fix_suggestions=context.get("fix_suggestions"),
        explicit_severity=context.get("overall_severity"),
        decision_summary=context.get("decision_summary"),
    )
    fallback = _build_local_response(intent, snapshot)

    if client is None or intent == "greeting":
        return fallback

    prompt = _build_prompt(query, intent, context, snapshot)

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
        )

        content = _strip_code_fence(response.choices[0].message.content or "")
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            return fallback
        return _validate_response(parsed, fallback, snapshot, intent)
    except Exception:
        return fallback
