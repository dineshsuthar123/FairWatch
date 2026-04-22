from typing import Dict, List, Optional, Tuple

import pandas as pd


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
        if (0.7 <= score < 0.8) or (1.25 < score <= 1.4):
            return "yellow"
        return "red"

    if score < 0.1:
        return "green"
    if score <= 0.2:
        return "yellow"
    return "red"


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


def _severity_label(severity: str) -> str:
    if severity == "green":
        return "acceptable"
    if severity == "yellow":
        return "moderate concern"
    return "severe imbalance"


def interpret_metric(
    metric_name,
    score,
    group_a: Optional[str] = None,
    group_b: Optional[str] = None,
    value_a: Optional[float] = None,
    value_b: Optional[float] = None,
    sample_size_a: Optional[int] = None,
    sample_size_b: Optional[int] = None,
):
    score = float(score)
    severity = determine_severity(score, metric_name)
    label = _severity_label(severity)

    display_a = str(group_a or "group_a")
    display_b = str(group_b or "group_b")

    if metric_name == "Demographic Parity Difference":
        diff = score
        if value_a is not None and value_b is not None:
            delta = float(value_a) - float(value_b)
            direction = "fewer" if delta >= 0 else "more"
            detail = f"{display_b} receives {abs(delta):.0%} {direction} approvals than {display_a}"
        else:
            detail = "approval rates differ across groups"
        meaning = f"DP = {diff:.2f} -> {label} ({detail})"

    elif metric_name == "Equal Opportunity Difference":
        diff = score
        if value_a is not None and value_b is not None:
            delta = float(value_a) - float(value_b)
            direction = "less" if delta >= 0 else "more"
            detail = (
                f"qualified {display_b} applicants are approved {abs(delta):.0%} {direction} often than {display_a}"
            )
        else:
            detail = "true positive rates differ across groups"
        meaning = f"EO = {diff:.2f} -> {label} ({detail})"

    elif metric_name == "Disparate Impact Ratio":
        ratio = score
        if ratio == float("inf"):
            detail = f"{display_a} has near-zero favorable outcomes while {display_b} does not"
            meaning = f"DI ratio = inf -> severe imbalance ({detail})"
        else:
            detail = f"{display_b} receives {ratio:.0%} of {display_a} approvals"
            meaning = f"DI ratio = {ratio:.2f} -> {label} ({detail})"

    elif metric_name == "False Positive Rate Gap":
        diff = score
        if value_a is not None and value_b is not None:
            delta = float(value_b) - float(value_a)
            direction = "higher" if delta >= 0 else "lower"
            detail = f"{display_b} has {abs(delta):.0%} {direction} false-positive rate than {display_a}"
        else:
            detail = "false-positive rates differ across groups"
        meaning = f"FPR gap = {diff:.2f} -> {label} ({detail})"

    else:
        meaning = f"{metric_name} = {score:.3f} -> {label}"

    if sample_size_a is not None and sample_size_b is not None:
        if min(int(sample_size_a), int(sample_size_b)) < 10:
            meaning = (
                f"{meaning} [low sample size: {display_a}=n{int(sample_size_a)}, "
                f"{display_b}=n{int(sample_size_b)}]"
            )

    return {
        "severity": severity,
        "meaning": meaning,
    }
