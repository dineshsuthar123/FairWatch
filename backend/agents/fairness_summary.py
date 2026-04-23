from typing import Any, Dict, List, Optional

SEVERITY_RANK = {"green": 1, "yellow": 2, "red": 3}
RISK_BY_SEVERITY = {"green": "safe", "yellow": "risky", "red": "unsafe"}
CONFIDENCE_RANK = {"low": 1, "medium": 2, "high": 3}


def severity_to_risk_level(severity: Optional[str]) -> str:
    normalized = str(severity or "green").strip().lower()
    return RISK_BY_SEVERITY.get(normalized, "safe")


def risk_from_decision_status(status: str) -> str:
    normalized = str(status or "safe").strip().lower()
    if normalized in {"safe", "risky", "unsafe"}:
        return normalized
    return "safe"


def severity_from_risk_level(risk_level: str) -> str:
    if risk_level == "unsafe":
        return "red"
    if risk_level == "risky":
        return "yellow"
    return "green"


def deployment_status_line(risk_level: str, confidence: str) -> str:
    if risk_level == "unsafe":
        base = "This model is unsafe to deploy."
    elif risk_level == "risky":
        base = "This model needs fixes before deployment."
    else:
        base = "The latest report does not show a critical fairness issue."

    if str(confidence).lower() == "low":
        return f"{base} Confidence is low, so results may be unstable."

    return base


def format_list(items: List[str]) -> str:
    cleaned = [item for item in items if item]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    return f"{', '.join(cleaned[:-1])}, and {cleaned[-1]}"


def normalize_metric_score(metric: Dict[str, Any]) -> float:
    raw_score = metric.get("value", metric.get("score", metric.get("disparity_score", 0.0)))
    try:
        return float(raw_score)
    except (TypeError, ValueError):
        return 0.0


def metric_risk_distance(metric: Dict[str, Any]) -> float:
    metric_name = str(metric.get("metric_name") or metric.get("metric") or "")
    score = normalize_metric_score(metric)
    if metric_name == "Disparate Impact Ratio":
        return abs(1.0 - score)
    return abs(score)


def top_metric(metrics: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not metrics:
        return None

    return max(
        metrics,
        key=lambda metric: (
            SEVERITY_RANK.get(str(metric.get("severity", "")).lower(), 0),
            metric_risk_distance(metric),
        ),
    )


def infer_overall_confidence(metrics: List[Dict[str, Any]]) -> str:
    if not metrics:
        return "low"

    values = [str(metric.get("confidence", "low")).strip().lower() for metric in metrics]
    return min(values, key=lambda value: CONFIDENCE_RANK.get(value, 1))


def infer_affected_groups(metrics: List[Dict[str, Any]]) -> List[str]:
    if not metrics:
        return []

    ranked_metrics = sorted(
        metrics,
        key=lambda metric: (
            SEVERITY_RANK.get(str(metric.get("severity", "")).lower(), 0),
            metric_risk_distance(metric),
        ),
        reverse=True,
    )

    risky_metrics = [
        metric for metric in ranked_metrics if str(metric.get("severity", "")).lower() in {"yellow", "red"}
    ]
    source = risky_metrics or ranked_metrics

    groups: List[str] = []
    for metric in source:
        label = str(metric.get("group_b") or "").strip()
        if label and label not in groups:
            groups.append(label)

    return groups[:6]


def infer_root_causes(feature_contributions: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    feature_contributions = feature_contributions or {}
    ranked_features = feature_contributions.get("top_contributing_features") or []
    proxy_warnings = feature_contributions.get("proxy_warnings") or []

    features: List[str] = []
    feature_details: List[str] = []
    for item in ranked_features[:3]:
        feature_name = str(item.get("feature") or "").strip()
        if not feature_name:
            continue
        features.append(feature_name)

        association_statement = str(item.get("association_statement") or "").strip()
        if association_statement:
            feature_details.append(association_statement)
            continue

        pct = item.get("contribution_pct")
        try:
            pct_text = f"{float(pct):.1f}%"
        except (TypeError, ValueError):
            pct_text = ""

        if pct_text:
            feature_details.append(
                f"{feature_name} is strongly associated with the observed disparity ({pct_text} contribution)"
            )
        else:
            feature_details.append(
                f"{feature_name} is strongly associated with the observed disparity"
            )

    return {
        "features": features,
        "feature_details": feature_details,
        "proxy_warnings": [str(warning).strip() for warning in proxy_warnings if str(warning).strip()],
    }


def recommended_action(fix_suggestions: Optional[Dict[str, Any]]) -> str:
    if isinstance(fix_suggestions, dict):
        immediate_action = str(fix_suggestions.get("immediate_action") or "").strip()
        if immediate_action:
            return immediate_action

        for fix in fix_suggestions.get("fixes") or []:
            action = str(fix.get("action") or "").strip()
            if action:
                return action

    return "Review the flagged groups and fix the main bias drivers before deployment."


def confidence_warning(confidence: str) -> str:
    if str(confidence).lower() == "low":
        return "Low confidence: results may be unstable"
    return ""


def build_fairness_snapshot(
    metrics: Optional[List[Dict[str, Any]]],
    feature_contributions: Optional[Dict[str, Any]] = None,
    fix_suggestions: Optional[Dict[str, Any]] = None,
    explicit_severity: Optional[str] = None,
    decision_summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    metric_rows = list(metrics or [])
    worst_metric = top_metric(metric_rows)
    root_cause_data = infer_root_causes(feature_contributions)

    explicit_status = str((decision_summary or {}).get("status") or "").strip().lower()
    if explicit_status in {"safe", "risky", "unsafe"}:
        risk_level = risk_from_decision_status(explicit_status)
        overall_severity = severity_from_risk_level(risk_level)
    else:
        overall_severity = str(
            explicit_severity
            or (worst_metric or {}).get("severity")
            or "green"
        ).strip().lower()
        risk_level = severity_to_risk_level(overall_severity)

    overall_confidence = str(
        (decision_summary or {}).get("confidence") or infer_overall_confidence(metric_rows)
    ).strip().lower()
    decision_reason = str((decision_summary or {}).get("reason") or "").strip()

    return {
        "risk_level": risk_level,
        "overall_severity": overall_severity,
        "confidence": overall_confidence,
        "confidence_warning": confidence_warning(overall_confidence),
        "decision_reason": decision_reason,
        "deployment_status": deployment_status_line(risk_level, overall_confidence),
        "affected_groups": infer_affected_groups(metric_rows),
        "root_causes": root_cause_data["features"],
        "root_cause_details": root_cause_data["feature_details"],
        "proxy_warnings": root_cause_data["proxy_warnings"],
        "recommended_action": recommended_action(fix_suggestions),
        "top_metric": worst_metric,
    }
