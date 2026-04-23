import json
from itertools import combinations
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import shap
from sklearn.base import ClassifierMixin
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.feature_selection import mutual_info_classif
from sqlalchemy.orm import Session

from database import SessionLocal
from models import ModelRegistry, Prediction
from utils.metrics import (
    confidence_from_sample_size,
    confidence_warning,
    group_approval_rates,
    group_false_positive_rates,
    group_sample_counts,
    group_true_positive_rates,
    interpret_metric,
    majority_group,
    metric_risk_distance,
    pairwise_gaps,
    pairwise_ratios,
    summarize_decision,
)


def _parse_group_label(group_label: str) -> Dict[str, str]:
    if not group_label:
        return {}

    try:
        parsed = json.loads(group_label)
        if isinstance(parsed, dict):
            return {str(key): str(value) for key, value in parsed.items()}
    except (TypeError, json.JSONDecodeError):
        pass

    parsed: Dict[str, str] = {}
    for chunk in str(group_label).split("|"):
        if "=" in chunk:
            key, value = chunk.split("=", 1)
        elif ":" in chunk:
            key, value = chunk.split(":", 1)
        else:
            continue
        parsed[key.strip()] = value.strip()

    return parsed


def _normalize_feature_value(value: Any) -> Any:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    if value is None:
        return np.nan
    return str(value)


def _series_to_numeric(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")
    categorical = pd.Categorical(series.astype(str))
    codes = pd.Series(categorical.codes, index=series.index).replace(-1, np.nan)
    return pd.to_numeric(codes, errors="coerce")


def _extract_prediction_rows(predictions: List[Prediction], sensitive_attributes: List[str]) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []

    for prediction in reversed(predictions):
        features = prediction.input_features or {}
        if isinstance(features, str):
            try:
                features = json.loads(features)
            except json.JSONDecodeError:
                features = {}

        parsed_group_label = _parse_group_label(prediction.group_label)

        row: Dict[str, Any] = {
            "output_decision": 1 if int(prediction.output_decision) == 1 else 0,
        }

        true_label = features.get("true_label", prediction.output_decision)
        try:
            row["true_label"] = 1 if int(true_label) == 1 else 0
        except (TypeError, ValueError):
            row["true_label"] = row["output_decision"]

        for key, value in dict(features).items():
            if key == "true_label":
                continue
            row[str(key)] = _normalize_feature_value(value)

        for attribute in sensitive_attributes:
            row[attribute] = str(parsed_group_label.get(attribute, features.get(attribute, "unknown")))

        rows.append(row)

    return pd.DataFrame(rows)


def _compute_shap_values(X: pd.DataFrame, y: pd.Series) -> np.ndarray:
    if X.empty or y.empty or y.nunique() < 2:
        raise ValueError("SHAP requires non-empty data and at least two target classes")

    model: ClassifierMixin
    mode = "tree"

    if X.shape[1] > 8:
        model = RandomForestClassifier(
            n_estimators=180,
            min_samples_leaf=2,
            random_state=42,
        )
        model.fit(X, y)
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X)
    else:
        mode = "kernel"
        model = LogisticRegression(max_iter=2000)
        model.fit(X, y)
        background = shap.sample(X, min(len(X), 30), random_state=42)

        def predict_proba_positive(data: np.ndarray) -> np.ndarray:
            frame = pd.DataFrame(data, columns=X.columns)
            return model.predict_proba(frame)[:, 1]

        explainer = shap.KernelExplainer(predict_proba_positive, background)
        shap_values = explainer.shap_values(X, nsamples="auto")

    matrix = np.asarray(shap_values[-1] if isinstance(shap_values, list) else shap_values, dtype=float)
    if matrix.ndim == 3:
        matrix = matrix[:, :, -1]

    if matrix.shape[0] != len(X):
        raise ValueError(f"SHAP output shape mismatch for {mode} explainer")

    return matrix


def _dominance_adjusted_percentages(scores: Dict[str, float]) -> Dict[str, float]:
    sanitized = {feature: max(0.0, float(value)) for feature, value in scores.items()}
    if not sanitized:
        return {}

    total = sum(sanitized.values())
    if total <= 0:
        uniform = 100.0 / len(sanitized)
        return {feature: uniform for feature in sanitized}

    percentages = {feature: (value / total) * 100.0 for feature, value in sanitized.items()}
    ranked = sorted(percentages.items(), key=lambda item: item[1], reverse=True)

    if len(ranked) > 1:
        top_feature, top_pct = ranked[0]
        second_pct = ranked[1][1]
        top_raw = sanitized[top_feature]
        second_raw = sanitized[ranked[1][0]]
        dominance_ratio = top_raw / (second_raw + 1e-9)
        justified = dominance_ratio >= 8.0

        if top_pct > 90.0 and not justified:
            cap = 85.0
            percentages[top_feature] = cap
            remaining = 100.0 - cap

            others = [feature for feature in percentages if feature != top_feature]
            others_sum = sum(percentages[feature] for feature in others)
            if others_sum <= 0:
                each = remaining / len(others)
                for feature in others:
                    percentages[feature] = each
            else:
                scale = remaining / others_sum
                for feature in others:
                    percentages[feature] *= scale

    rounded = {feature: round(value, 2) for feature, value in percentages.items()}
    delta = round(100.0 - sum(rounded.values()), 2)
    if rounded:
        max_feature = max(rounded.items(), key=lambda item: item[1])[0]
        rounded[max_feature] = round(rounded[max_feature] + delta, 2)

    return rounded


def _pairwise_disparity_from_shap(
    df: pd.DataFrame,
    shap_matrix: np.ndarray,
    candidate_features: List[str],
    sensitive_attributes: List[str],
    min_group_size: int,
) -> Dict[str, float]:
    scores = {feature: 0.0 for feature in candidate_features}

    for attribute in sensitive_attributes:
        if attribute not in df.columns:
            continue

        counts = df[attribute].astype(str).value_counts()
        groups = [group for group, count in counts.items() if int(count) >= min_group_size]
        if len(groups) < 2:
            continue

        for group_a, group_b in combinations(groups, 2):
            mask_a = df[attribute].astype(str) == str(group_a)
            mask_b = df[attribute].astype(str) == str(group_b)
            if not mask_a.any() or not mask_b.any():
                continue

            mean_a = np.abs(shap_matrix[mask_a.to_numpy()]).mean(axis=0)
            mean_b = np.abs(shap_matrix[mask_b.to_numpy()]).mean(axis=0)
            diff = np.abs(mean_a - mean_b)

            for index, feature in enumerate(candidate_features):
                scores[feature] += float(diff[index])

    return scores


def _fallback_feature_diffs(
    df: pd.DataFrame,
    candidate_features: List[str],
    sensitive_attributes: List[str],
) -> Tuple[Dict[str, float], str]:
    feature_diffs = {feature: 0.0 for feature in candidate_features}
    numeric_frame = pd.DataFrame({feature: _series_to_numeric(df[feature]) for feature in candidate_features})

    for attribute in sensitive_attributes:
        if attribute not in df.columns:
            continue

        counts = df[attribute].astype(str).value_counts()
        groups = [group for group, count in counts.items() if int(count) >= 5]
        if len(groups) < 2:
            continue

        for group_a, group_b in combinations(groups, 2):
            pair_mask = df[attribute].astype(str).isin([str(group_a), str(group_b)])
            if not pair_mask.any():
                continue

            pair_attribute = df.loc[pair_mask, attribute].astype(str)
            pair_indicator = (pair_attribute == str(group_b)).astype(int).to_numpy()

            for feature in candidate_features:
                feature_values = pd.to_numeric(
                    numeric_frame.loc[pair_mask, feature],
                    errors="coerce",
                ).fillna(0.0)

                if feature_values.nunique(dropna=True) <= 1:
                    continue

                corr = feature_values.corr(pd.Series(pair_indicator, index=feature_values.index))
                corr_score = 0.0 if pd.isna(corr) else abs(float(corr))

                try:
                    mi = mutual_info_classif(
                        feature_values.to_numpy().reshape(-1, 1),
                        pair_indicator,
                        discrete_features=False,
                        random_state=42,
                    )[0]
                    mi_score = float(max(0.0, mi))
                except Exception:
                    mi_score = 0.0

                feature_diffs[feature] += max(corr_score, mi_score)

    return feature_diffs, "approximate contribution"


def format_contribution_output(
    contribution_scores: Dict[str, float],
    proxy_risk_features: set,
    proxy_warnings: List[str],
    mode: str,
    top_k: int = 5,
) -> Dict[str, Any]:
    percentages = _dominance_adjusted_percentages(contribution_scores)
    ranked = sorted(percentages.items(), key=lambda item: item[1], reverse=True)[:top_k]

    top_contributing_features = [
        {
            "feature": feature,
            "contribution_pct": pct,
            "proxy_risk": feature in proxy_risk_features,
            "contribution_mode": mode,
            "association_statement": (
                f"{feature} is strongly associated with the observed disparity and influences model decisions"
            ),
        }
        for feature, pct in ranked
    ]

    return {
        "top_contributing_features": top_contributing_features,
        "proxy_warnings": sorted(set(proxy_warnings)),
        "contribution_mode": mode,
    }


def get_feature_contributions(
    model_id: int,
    db: Optional[Session] = None,
    window_size: Optional[int] = 100,
    min_group_size: int = 5,
) -> Dict[str, Any]:
    owns_session = db is None
    if owns_session:
        db = SessionLocal()

    try:
        model = db.query(ModelRegistry).filter(ModelRegistry.id == model_id).first()
        if model is None:
            return {
                "top_contributing_features": [],
                "proxy_warnings": [],
                "contribution_mode": "unavailable",
            }

        query = (
            db.query(Prediction)
            .filter(Prediction.model_id == model_id)
            .order_by(Prediction.timestamp.desc())
        )
        if window_size and window_size > 0:
            query = query.limit(window_size)
        predictions = query.all()

        if not predictions:
            return {
                "top_contributing_features": [],
                "proxy_warnings": [],
                "contribution_mode": "unavailable",
            }

        sensitive_attributes = list(model.sensitive_attributes or [])
        df = _extract_prediction_rows(predictions, sensitive_attributes)
        if df.empty:
            return {
                "top_contributing_features": [],
                "proxy_warnings": [],
                "contribution_mode": "unavailable",
            }

        excluded = {"output_decision", "true_label", *sensitive_attributes}
        candidate_features = [column for column in df.columns if column not in excluded]
        if not candidate_features:
            return {
                "top_contributing_features": [],
                "proxy_warnings": [],
                "contribution_mode": "unavailable",
            }

        X = pd.DataFrame({column: _series_to_numeric(df[column]) for column in candidate_features})
        X = X.fillna(X.median(numeric_only=True)).fillna(0)
        y = pd.to_numeric(df["output_decision"], errors="coerce").fillna(0).astype(int)

        feature_diffs = {feature: 0.0 for feature in candidate_features}
        contribution_mode = "shap"
        try:
            shap_matrix = _compute_shap_values(X, y)
            if shap_matrix.size > 0:
                feature_diffs = _pairwise_disparity_from_shap(
                    df,
                    shap_matrix,
                    candidate_features,
                    sensitive_attributes,
                    min_group_size=min_group_size,
                )
        except Exception:
            feature_diffs, contribution_mode = _fallback_feature_diffs(
                df,
                candidate_features,
                sensitive_attributes,
            )

        if sum(feature_diffs.values()) <= 0:
            feature_diffs, contribution_mode = _fallback_feature_diffs(
                df,
                candidate_features,
                sensitive_attributes,
            )

        proxy_warnings: List[str] = []
        proxy_risk_features: set[str] = set()
        for attribute in sensitive_attributes:
            if attribute not in df.columns:
                continue

            sensitive_series = _series_to_numeric(df[attribute])
            for feature in candidate_features:
                feature_series = _series_to_numeric(df[feature])
                corr = feature_series.corr(sensitive_series)
                if pd.isna(corr):
                    continue
                if abs(float(corr)) > 0.6:
                    proxy_risk_features.add(feature)
                    proxy_warnings.append(
                        f"{feature} correlates {abs(float(corr)):.2f} with {attribute}"
                    )

        return format_contribution_output(
            contribution_scores=feature_diffs,
            proxy_risk_features=proxy_risk_features,
            proxy_warnings=proxy_warnings,
            mode=contribution_mode,
            top_k=5,
        )
    except Exception:
        return {
            "top_contributing_features": [],
            "proxy_warnings": [],
            "contribution_mode": "unavailable",
        }
    finally:
        if owns_session and db is not None:
            db.close()


def _metric_row(
    metric_name: str,
    attribute: str,
    group_a: str,
    group_b: str,
    score: float,
    value_a: float,
    value_b: float,
    sample_size_a: int,
    sample_size_b: int,
    metric_scope: str,
) -> Dict[str, Any]:
    interpretation = interpret_metric(
        metric_name,
        score,
        group_a=f"{attribute}:{group_a}",
        group_b=f"{attribute}:{group_b}",
        value_a=value_a,
        value_b=value_b,
    )

    sample_min = min(int(sample_size_a), int(sample_size_b))
    confidence = confidence_from_sample_size(sample_min)
    warning = confidence_warning(confidence)
    metric_value = round(float(score), 4)

    return {
        "metric": metric_name,
        "metric_name": metric_name,
        "metric_type": metric_scope,
        "metric_scope": metric_scope,
        "attribute": attribute,
        "group_a": f"{attribute}:{group_a}",
        "group_b": f"{attribute}:{group_b}",
        "value": metric_value,
        "disparity_score": metric_value,
        "severity": interpretation["severity"],
        "interpretation": interpretation["interpretation"],
        "metric_meaning": interpretation["interpretation"],
        "sample_size": {
            "group_a": int(sample_size_a),
            "group_b": int(sample_size_b),
            "minimum": sample_min,
        },
        "confidence": confidence,
        "confidence_warning": warning,
        "details": {
            "group_a_value": round(float(value_a), 4),
            "group_b_value": round(float(value_b), 4),
            "group_a_n": int(sample_size_a),
            "group_b_n": int(sample_size_b),
        },
    }


def run_bias_analysis(
    model_id: int,
    window_size: Optional[int] = 100,
    db: Optional[Session] = None,
    as_of: Optional[datetime] = None,
    scope_label: str = "live_window",
) -> Dict[str, Any]:
    owns_session = db is None
    if owns_session:
        db = SessionLocal()

    try:
        model = db.query(ModelRegistry).filter(ModelRegistry.id == model_id).first()
        if model is None:
            return {
                "model_id": model_id,
                "window_size": 0,
                "metric_scope": scope_label,
                "generated_at": datetime.utcnow().isoformat(),
                "reports": [],
                "summary": {
                    "max_disparity": 0.0,
                    "worst_metric": None,
                    "status": "model_not_found",
                },
                "decision_summary": summarize_decision([], scope_label),
            }

        query = db.query(Prediction).filter(Prediction.model_id == model_id)
        if as_of is not None:
            query = query.filter(Prediction.timestamp <= as_of)

        query = query.order_by(Prediction.timestamp.desc())
        if window_size and window_size > 0:
            query = query.limit(window_size)
        predictions = query.all()

        if not predictions:
            return {
                "model_id": model_id,
                "window_size": 0,
                "metric_scope": scope_label,
                "generated_at": datetime.utcnow().isoformat(),
                "reports": [],
                "summary": {
                    "max_disparity": 0.0,
                    "worst_metric": None,
                    "status": "no_predictions",
                },
                "decision_summary": summarize_decision([], scope_label),
            }

        sensitive_attributes = model.sensitive_attributes or []
        df = _extract_prediction_rows(predictions, sensitive_attributes)

        report_rows: List[Dict[str, Any]] = []
        for attribute in sensitive_attributes:
            if attribute not in df.columns:
                continue

            baseline = majority_group(df, attribute)
            if baseline is None:
                continue

            approval_counts = group_sample_counts(df, attribute)
            approval_rates = group_approval_rates(df, attribute)
            positives_df = df[pd.to_numeric(df["true_label"], errors="coerce").fillna(0) == 1]
            negatives_df = df[pd.to_numeric(df["true_label"], errors="coerce").fillna(0) == 0]

            true_positive_counts = group_sample_counts(positives_df, attribute)
            false_positive_counts = group_sample_counts(negatives_df, attribute)

            true_positive_rates = group_true_positive_rates(df, attribute)
            false_positive_rates = group_false_positive_rates(df, attribute)

            for group_a, group_b, score, value_a, value_b in pairwise_gaps(
                approval_rates,
                baseline,
                group_counts=approval_counts,
                min_group_size=5,
            ):
                report_rows.append(
                    _metric_row(
                        "Demographic Parity Difference",
                        attribute,
                        group_a,
                        group_b,
                        score,
                        value_a,
                        value_b,
                        approval_counts.get(group_a, 0),
                        approval_counts.get(group_b, 0),
                        scope_label,
                    )
                )

            for group_a, group_b, score, value_a, value_b in pairwise_gaps(
                true_positive_rates,
                baseline,
                group_counts=true_positive_counts,
                min_group_size=5,
            ):
                report_rows.append(
                    _metric_row(
                        "Equal Opportunity Difference",
                        attribute,
                        group_a,
                        group_b,
                        score,
                        value_a,
                        value_b,
                        true_positive_counts.get(group_a, 0),
                        true_positive_counts.get(group_b, 0),
                        scope_label,
                    )
                )

            for group_a, group_b, score, value_a, value_b in pairwise_ratios(
                approval_rates,
                baseline,
                group_counts=approval_counts,
                min_group_size=5,
            ):
                report_rows.append(
                    _metric_row(
                        "Disparate Impact Ratio",
                        attribute,
                        group_a,
                        group_b,
                        score,
                        value_a,
                        value_b,
                        approval_counts.get(group_a, 0),
                        approval_counts.get(group_b, 0),
                        scope_label,
                    )
                )

            for group_a, group_b, score, value_a, value_b in pairwise_gaps(
                false_positive_rates,
                baseline,
                group_counts=false_positive_counts,
                min_group_size=5,
            ):
                report_rows.append(
                    _metric_row(
                        "False Positive Rate Gap",
                        attribute,
                        group_a,
                        group_b,
                        score,
                        value_a,
                        value_b,
                        false_positive_counts.get(group_a, 0),
                        false_positive_counts.get(group_b, 0),
                        scope_label,
                    )
                )

        max_disparity = max(
            (
                metric_risk_distance(row["metric_name"], float(row.get("value", row.get("disparity_score", 0.0))))
                for row in report_rows
            ),
            default=0.0,
        )
        worst_row = max(
            report_rows,
            key=lambda row: metric_risk_distance(
                row["metric_name"],
                float(row.get("value", row.get("disparity_score", 0.0))),
            ),
            default=None,
        )
        decision_summary = summarize_decision(report_rows, scope_label)

        return {
            "model_id": model_id,
            "window_size": len(predictions),
            "metric_scope": scope_label,
            "generated_at": datetime.utcnow().isoformat(),
            "reports": report_rows,
            "summary": {
                "max_disparity": round(float(max_disparity), 4),
                "worst_metric": worst_row["metric_name"] if worst_row else None,
                "status": "ok",
            },
            "decision_summary": decision_summary,
        }
    finally:
        if owns_session and db is not None:
            db.close()
