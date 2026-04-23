from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

SEVERITY_RANK = {"green": 1, "yellow": 2, "red": 3}
CONFIDENCE_RANK = {"low": 1, "medium": 2, "high": 3}


def safe_divide(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return float(numerator) / float(denominator)


def disparate_impact_ratio(unprivileged_rate: float, privileged_rate: float) -> float:
    priv = float(privileged_rate)
    unpriv = float(unprivileged_rate)

    if priv <= 0 and unpriv <= 0:
        return 1.0
    if priv <= 0 and unpriv > 0:
        return float("inf")

    return unpriv / priv


def determine_severity(score: float, metric_name: Optional[str] = None) -> str:
    score = float(score)

    if metric_name == "Disparate Impact Ratio":
        if 0.8 <= score <= 1.25:
            return "green"
        return "red"

    if score < 0.1:
        return "green"
    if score <= 0.2:
        return "yellow"
    return "red"


def confidence_from_sample_size(sample_size: int) -> str:
    size = int(sample_size)
    if size < 50:
        return "low"
    if size <= 200:
        return "medium"
    return "high"


def confidence_warning(confidence: str) -> str:
    if str(confidence).lower() == "low":
        return "Low confidence: results may be unstable"
    return ""


def majority_group(df: pd.DataFrame, group_col: str) -> Optional[str]:
    if df.empty or group_col not in df.columns:
        return None
    return str(df[group_col].value_counts(dropna=False).idxmax())


def group_sample_counts(df: pd.DataFrame, group_col: str) -> Dict[str, int]:
    if df.empty or group_col not in df.columns:
        return {}

    counts = df.groupby(group_col).size().to_dict()
    return {str(group): int(count) for group, count in counts.items()}


def _smoothed_binary_rate(series: pd.Series, alpha: float = 1.0) -> float:
    total = int(len(series))
    if total <= 0:
        return 0.0

    positives = float((pd.to_numeric(series, errors="coerce").fillna(0) == 1).sum())
    return (positives + alpha) / (total + (2.0 * alpha))


def group_approval_rates(
    df: pd.DataFrame,
    group_col: str,
    decision_col: str = "output_decision",
    alpha: float = 1.0,
) -> Dict[str, float]:
    if df.empty or group_col not in df.columns or decision_col not in df.columns:
        return {}

    rates: Dict[str, float] = {}
    for group, subset in df.groupby(group_col):
        rates[str(group)] = float(_smoothed_binary_rate(subset[decision_col], alpha=alpha))

    return rates


def group_true_positive_rates(
    df: pd.DataFrame,
    group_col: str,
    true_col: str = "true_label",
    decision_col: str = "output_decision",
    alpha: float = 1.0,
) -> Dict[str, float]:
    if df.empty or true_col not in df.columns:
        return {}
    positives = df[pd.to_numeric(df[true_col], errors="coerce").fillna(0) == 1]
    return group_approval_rates(
        positives,
        group_col=group_col,
        decision_col=decision_col,
        alpha=alpha,
    )


def group_false_positive_rates(
    df: pd.DataFrame,
    group_col: str,
    true_col: str = "true_label",
    decision_col: str = "output_decision",
    alpha: float = 1.0,
) -> Dict[str, float]:
    if df.empty or true_col not in df.columns or group_col not in df.columns or decision_col not in df.columns:
        return {}

    negatives = df[pd.to_numeric(df[true_col], errors="coerce").fillna(0) == 0]
    if negatives.empty:
        return {}

    rates: Dict[str, float] = {}
    for group, subset in negatives.groupby(group_col):
        rates[str(group)] = float(_smoothed_binary_rate(subset[decision_col], alpha=alpha))

    return rates


def pairwise_gaps(
    values: Dict[str, float],
    baseline_group: str,
    group_counts: Optional[Dict[str, int]] = None,
    min_group_size: int = 1,
) -> List[Tuple[str, str, float, float, float]]:
    if baseline_group not in values:
        return []

    baseline_value = float(values[baseline_group])
    rows: List[Tuple[str, str, float, float, float]] = []
    for group, value in values.items():
        if group == baseline_group:
            continue

        if group_counts is not None:
            if int(group_counts.get(group, 0)) < min_group_size:
                continue
            if int(group_counts.get(baseline_group, 0)) < min_group_size:
                continue

        group_value = float(value)
        score = abs(baseline_value - group_value)
        rows.append((baseline_group, group, score, baseline_value, group_value))

    return rows


def pairwise_ratios(
    values: Dict[str, float],
    baseline_group: str,
    group_counts: Optional[Dict[str, int]] = None,
    min_group_size: int = 1,
) -> List[Tuple[str, str, float, float, float]]:
    if baseline_group not in values:
        return []

    baseline_value = float(values[baseline_group])
    rows: List[Tuple[str, str, float, float, float]] = []
    for group, value in values.items():
        if group == baseline_group:
            continue

        if group_counts is not None:
            if int(group_counts.get(group, 0)) < min_group_size:
                continue
            if int(group_counts.get(baseline_group, 0)) < min_group_size:
                continue

        group_value = float(value)
        ratio = disparate_impact_ratio(group_value, baseline_value)
        rows.append((baseline_group, group, ratio, baseline_value, group_value))

    return rows


def metric_risk_distance(metric_name: str, value: float) -> float:
    value = float(value)
    if metric_name == "Disparate Impact Ratio":
        if value == float("inf"):
            return float("inf")
        return abs(1.0 - value)
    return abs(value)


def interpret_metric(
    metric_name: str,
    value: float,
    group_a: Optional[str] = None,
    group_b: Optional[str] = None,
    value_a: Optional[float] = None,
    value_b: Optional[float] = None,
) -> Dict[str, str]:
    value = float(value)
    severity = determine_severity(value, metric_name)

    group_a_label = str(group_a or "group A")
    group_b_label = str(group_b or "group B")

    if metric_name == "Demographic Parity Difference":
        gap = abs(value)
        if severity == "green":
            interpretation = f"DP = {gap:.2f} -> acceptable ({gap:.0%} approval gap)"
        elif severity == "yellow":
            near = " near high-disparity threshold" if gap >= 0.18 else ""
            interpretation = f"DP = {gap:.2f} -> moderate concern ({gap:.0%} approval gap{near})"
        else:
            interpretation = f"DP = {gap:.2f} -> high disparity ({gap:.0%} approval gap)"

    elif metric_name == "Equal Opportunity Difference":
        gap = abs(value)
        if severity == "green":
            interpretation = f"EO = {gap:.2f} -> acceptable ({gap:.0%} true-positive gap)"
        elif severity == "yellow":
            near = " near high-disparity threshold" if gap >= 0.18 else ""
            interpretation = f"EO = {gap:.2f} -> moderate concern ({gap:.0%} true-positive gap{near})"
        else:
            interpretation = f"EO = {gap:.2f} -> high disparity ({gap:.0%} true-positive gap)"

    elif metric_name == "False Positive Rate Gap":
        gap = abs(value)
        if severity == "green":
            interpretation = f"FPR = {gap:.2f} -> acceptable ({gap:.0%} false-positive gap)"
        elif severity == "yellow":
            near = " near high-disparity threshold" if gap >= 0.18 else ""
            interpretation = f"FPR = {gap:.2f} -> moderate concern ({gap:.0%} false-positive gap{near})"
        else:
            interpretation = f"FPR = {gap:.2f} -> high disparity ({gap:.0%} false-positive gap)"

    elif metric_name == "Disparate Impact Ratio":
        ratio = value
        if ratio == float("inf"):
            interpretation = (
                f"DI = inf -> high disparity ({group_b_label} receives far more approvals than {group_a_label})"
            )
        elif 0.8 <= ratio <= 1.25:
            imbalance = abs(1.0 - ratio)
            direction = "fewer" if ratio < 1.0 else "more"
            interpretation = (
                f"DI = {ratio:.2f} -> acceptable with mild imbalance "
                f"({group_b_label} receives {imbalance:.0%} {direction} approvals than {group_a_label})"
            )
        else:
            imbalance = abs(1.0 - ratio)
            direction = "fewer" if ratio < 1.0 else "more"
            interpretation = (
                f"DI = {ratio:.2f} -> high disparity "
                f"({group_b_label} receives {imbalance:.0%} {direction} approvals than {group_a_label})"
            )

    else:
        interpretation = f"{metric_name} = {value:.3f}"

    return {
        "severity": severity,
        "interpretation": interpretation,
    }


def summarize_decision(metrics: List[Dict[str, Any]], scope_label: str = "live_window") -> Dict[str, str]:
    if not metrics:
        return {
            "status": "safe",
            "confidence": "low",
            "reason": f"Safe - no {scope_label} fairness metrics are available yet",
        }

    ranked = sorted(
        metrics,
        key=lambda metric: (
            SEVERITY_RANK.get(str(metric.get("severity", "")).lower(), 0),
            metric_risk_distance(str(metric.get("metric_name", "")), float(metric.get("value", metric.get("disparity_score", 0.0)))),
        ),
        reverse=True,
    )

    worst = ranked[0]
    worst_severity = str(worst.get("severity", "green")).lower()

    if worst_severity == "red":
        status = "unsafe"
    elif worst_severity == "yellow":
        status = "risky"
    else:
        status = "safe"

    confidences = [str(metric.get("confidence", "low")).lower() for metric in metrics]
    min_confidence = min(confidences, key=lambda item: CONFIDENCE_RANK.get(item, 1)) if confidences else "low"

    reason = (
        f"{status.capitalize()} - {worst.get('metric_name', 'metric')} indicates "
        f"{worst_severity} disparity for {worst.get('group_b', 'monitored group')} "
        f"with {min_confidence} confidence"
    )

    affected_groups = []
    if status in ("unsafe", "risky") and "group_b" in worst:
        group_val = str(worst["group_b"]).split(":")[-1]
        if group_val:
            affected_groups.append(group_val)

    return {
        "status": status,
        "confidence": min_confidence,
        "reason": reason,
        "affected_groups": affected_groups,
    }
