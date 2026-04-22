from typing import Dict, List, Optional, Tuple

import pandas as pd


def safe_divide(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return float(numerator) / float(denominator)


def determine_severity(score: float) -> str:
    if score < 0.05:
        return "green"
    if score <= 0.1:
        return "yellow"
    return "red"


def majority_group(df: pd.DataFrame, group_col: str) -> Optional[str]:
    if df.empty or group_col not in df.columns:
        return None
    return str(df[group_col].value_counts(dropna=False).idxmax())


def group_approval_rates(
    df: pd.DataFrame,
    group_col: str,
    decision_col: str = "output_decision",
) -> Dict[str, float]:
    if df.empty or group_col not in df.columns:
        return {}

    grouped = df.groupby(group_col)[decision_col].mean().to_dict()
    return {str(group): float(rate) for group, rate in grouped.items()}


def group_true_positive_rates(
    df: pd.DataFrame,
    group_col: str,
    true_col: str = "true_label",
    decision_col: str = "output_decision",
) -> Dict[str, float]:
    if df.empty or true_col not in df.columns:
        return {}
    positives = df[df[true_col] == 1]
    return group_approval_rates(positives, group_col=group_col, decision_col=decision_col)


def group_false_positive_rates(
    df: pd.DataFrame,
    group_col: str,
    true_col: str = "true_label",
    decision_col: str = "output_decision",
) -> Dict[str, float]:
    if df.empty or true_col not in df.columns or group_col not in df.columns:
        return {}

    negatives = df[df[true_col] == 0]
    if negatives.empty:
        return {}

    rates: Dict[str, float] = {}
    for group, subset in negatives.groupby(group_col):
        rates[str(group)] = float((subset[decision_col] == 1).mean())

    return rates


def pairwise_gaps(
    values: Dict[str, float],
    baseline_group: str,
) -> List[Tuple[str, str, float, float, float]]:
    if baseline_group not in values:
        return []

    baseline_value = values[baseline_group]
    rows: List[Tuple[str, str, float, float, float]] = []
    for group, value in values.items():
        if group == baseline_group:
            continue
        score = abs(float(baseline_value) - float(value))
        rows.append((baseline_group, group, score, float(baseline_value), float(value)))

    return rows


def pairwise_ratios(
    values: Dict[str, float],
    baseline_group: str,
) -> List[Tuple[str, str, float, float, float]]:
    if baseline_group not in values:
        return []

    baseline_value = float(values[baseline_group])
    rows: List[Tuple[str, str, float, float, float]] = []
    for group, value in values.items():
        if group == baseline_group:
            continue

        group_value = float(value)
        raw_ratio = safe_divide(group_value, baseline_value)
        score = abs(1.0 - raw_ratio)
        rows.append((baseline_group, group, score, baseline_value, group_value))

    return rows


def interpret_metric(metric_name, score):
    thresholds = {
        "Demographic Parity Difference": [
            (0.05, "green", "Acceptable — groups treated nearly equally"),
            (0.10, "yellow", "Moderate imbalance — monitor closely"),
            (0.20, "red", "Severe imbalance — {score:.0%} gap in outcomes"),
        ],
        "Equal Opportunity Difference": [
            (0.05, "green", "Fair — qualified candidates treated equally"),
            (0.10, "yellow", "Warning — model misses some qualified candidates"),
            (0.20, "red", "Critical — model misses {score:.0%} of qualified minority candidates"),
        ],
        "Disparate Impact Ratio": [
            (0.20, "red", "Critical — minority group gets {score:.0%} of majority outcomes"),
            (0.40, "yellow", "Below 80% rule — legally actionable in many jurisdictions"),
            (1.00, "green", "Acceptable — near equal impact across groups"),
        ],
        "False Positive Rate Gap": [
            (0.05, "green", "Fair — false alarm rates equal across groups"),
            (0.10, "yellow", "Moderate — minority group flagged more often"),
            (1.00, "red", "Severe — {score:.0%} higher false alarm rate for minority group"),
        ],
    }

    levels = thresholds.get(metric_name, [])
    for threshold, severity, template in levels:
        if score <= threshold:
            return {
                "severity": severity,
                "meaning": template.format(score=score)
            }
    return {"severity": "red", "meaning": f"Score {score:.3f} exceeds all safe thresholds"}
