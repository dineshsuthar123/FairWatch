from typing import Any, Dict, List, Optional

SEVERITY_RANK = {"green": 1, "yellow": 2, "red": 3}
RISK_BY_SEVERITY = {"green": "safe", "yellow": "risky", "red": "unsafe"}


def severity_to_risk_level(severity: Optional[str]) -> str:
    normalized = str(severity or "green").strip().lower()
    return RISK_BY_SEVERITY.get(normalized, "safe")


def deployment_status_line(risk_level: str) -> str:
    if risk_level == "unsafe":
        return "This model is unsafe to deploy."
    if risk_level == "risky":
        return "This model needs fixes before deployment."
    return "The latest report does not show a critical fairness issue."


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
    raw_score = metric.get("score", metric.get("disparity_score", 0.0))
    try:
        return float(raw_score)
    except (TypeError, ValueError):
        return 0.0


def top_metric(metrics: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not metrics:
        return None

    return max(
        metrics,
        key=lambda metric: (
            SEVERITY_RANK.get(str(metric.get("severity", "")).lower(), 0),
            normalize_metric_score(metric),
        ),
    )


def infer_affected_groups(metrics: List[Dict[str, Any]]) -> List[str]:
    if not metrics:
        return []

    ranked_metrics = sorted(
        metrics,
        key=lambda metric: (
            SEVERITY_RANK.get(str(metric.get("severity", "")).lower(), 0),
            normalize_metric_score(metric),
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

        pct = item.get("contribution_pct")
        try:
            pct_text = f"{float(pct):.2f}%"
        except (TypeError, ValueError):
            pct_text = ""

        if pct_text:
            feature_details.append(f"{feature_name} ({pct_text})")
        else:
            feature_details.append(feature_name)

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


def build_fairness_snapshot(
    metrics: Optional[List[Dict[str, Any]]],
    feature_contributions: Optional[Dict[str, Any]] = None,
    fix_suggestions: Optional[Dict[str, Any]] = None,
    explicit_severity: Optional[str] = None,
) -> Dict[str, Any]:
    metric_rows = list(metrics or [])
    worst_metric = top_metric(metric_rows)
    overall_severity = str(
        explicit_severity
        or (worst_metric or {}).get("severity")
        or "green"
    ).strip().lower()
    risk_level = severity_to_risk_level(overall_severity)
    root_cause_data = infer_root_causes(feature_contributions)

    return {
        "risk_level": risk_level,
        "overall_severity": overall_severity,
        "deployment_status": deployment_status_line(risk_level),
        "affected_groups": infer_affected_groups(metric_rows),
        "root_causes": root_cause_data["features"],
        "root_cause_details": root_cause_data["feature_details"],
        "proxy_warnings": root_cause_data["proxy_warnings"],
        "recommended_action": recommended_action(fix_suggestions),
        "top_metric": worst_metric,
    }
