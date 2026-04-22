import json
from itertools import combinations
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import shap
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sqlalchemy.orm import Session

from database import SessionLocal
from models import ModelRegistry, Prediction
from utils.metrics import (
    determine_severity,
    group_approval_rates,
    group_false_positive_rates,
    group_true_positive_rates,
    majority_group,
    pairwise_gaps,
    pairwise_ratios,
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
    if X.empty or y.empty:
        return np.empty((0, 0))

    if y.nunique() < 2:
        return np.zeros((len(X), len(X.columns)), dtype=float)

    if X.shape[1] > 8:
        model = RandomForestClassifier(n_estimators=120, random_state=42)
        model.fit(X, y)
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X)
    else:
        model = LogisticRegression(max_iter=1000)
        model.fit(X, y)
        explainer = shap.LinearExplainer(model, X)
        shap_values = explainer.shap_values(X)

    if isinstance(shap_values, list):
        matrix = np.asarray(shap_values[-1], dtype=float)
    else:
        matrix = np.asarray(shap_values, dtype=float)

    if matrix.ndim == 3:
        matrix = matrix[:, :, -1]

    return matrix


def get_feature_contributions(
    model_id: int,
    db: Optional[Session] = None,
    window_size: int = 100,
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
            }

        predictions = (
            db.query(Prediction)
            .filter(Prediction.model_id == model_id)
            .order_by(Prediction.timestamp.desc())
            .limit(window_size)
            .all()
        )

        if not predictions:
            return {
                "top_contributing_features": [],
                "proxy_warnings": [],
            }

        sensitive_attributes = list(model.sensitive_attributes or [])
        df = _extract_prediction_rows(predictions, sensitive_attributes)
        if df.empty:
            return {
                "top_contributing_features": [],
                "proxy_warnings": [],
            }

        excluded = {"output_decision", "true_label", *sensitive_attributes}
        candidate_features = [column for column in df.columns if column not in excluded]
        if not candidate_features:
            return {
                "top_contributing_features": [],
                "proxy_warnings": [],
            }

        X = pd.DataFrame({column: _series_to_numeric(df[column]) for column in candidate_features})
        X = X.fillna(X.median(numeric_only=True)).fillna(0)
        y = pd.to_numeric(df["output_decision"], errors="coerce").fillna(0).astype(int)

        shap_matrix = _compute_shap_values(X, y)
        if shap_matrix.size == 0:
            return {
                "top_contributing_features": [],
                "proxy_warnings": [],
            }

        feature_diffs = {feature: 0.0 for feature in candidate_features}
        for attribute in sensitive_attributes:
            if attribute not in df.columns:
                continue

            groups = [group for group in df[attribute].dropna().astype(str).unique().tolist() if group]
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
                    feature_diffs[feature] += float(diff[index])

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

        total_diff = sum(feature_diffs.values())
        ranked = sorted(feature_diffs.items(), key=lambda item: item[1], reverse=True)[:5]

        top_contributing_features = []
        for feature, score in ranked:
            pct = 0.0 if total_diff <= 0 else (float(score) / float(total_diff)) * 100.0
            top_contributing_features.append(
                {
                    "feature": feature,
                    "contribution_pct": round(pct, 2),
                    "proxy_risk": feature in proxy_risk_features,
                }
            )

        return {
            "top_contributing_features": top_contributing_features,
            "proxy_warnings": sorted(set(proxy_warnings)),
        }
    except Exception:
        return {
            "top_contributing_features": [],
            "proxy_warnings": [],
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
) -> Dict[str, Any]:
    return {
        "metric_name": metric_name,
        "attribute": attribute,
        "group_a": f"{attribute}:{group_a}",
        "group_b": f"{attribute}:{group_b}",
        "disparity_score": round(float(score), 4),
        "severity": determine_severity(float(score)),
        "details": {
            "group_a_value": round(float(value_a), 4),
            "group_b_value": round(float(value_b), 4),
        },
    }


def run_bias_analysis(
    model_id: int,
    window_size: int = 100,
    db: Optional[Session] = None,
    as_of: Optional[datetime] = None,
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
                "generated_at": datetime.utcnow().isoformat(),
                "reports": [],
                "summary": {"max_disparity": 0.0, "worst_metric": None, "status": "model_not_found"},
            }

        query = db.query(Prediction).filter(Prediction.model_id == model_id)
        if as_of is not None:
            query = query.filter(Prediction.timestamp <= as_of)

        predictions = (
            query.order_by(Prediction.timestamp.desc())
            .limit(window_size)
            .all()
        )

        if not predictions:
            return {
                "model_id": model_id,
                "window_size": 0,
                "generated_at": datetime.utcnow().isoformat(),
                "reports": [],
                "summary": {"max_disparity": 0.0, "worst_metric": None, "status": "no_predictions"},
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

            approval_rates = group_approval_rates(df, attribute)
            true_positive_rates = group_true_positive_rates(df, attribute)
            false_positive_rates = group_false_positive_rates(df, attribute)

            for group_a, group_b, score, value_a, value_b in pairwise_gaps(approval_rates, baseline):
                report_rows.append(
                    _metric_row(
                        "Demographic Parity Difference",
                        attribute,
                        group_a,
                        group_b,
                        score,
                        value_a,
                        value_b,
                    )
                )

            for group_a, group_b, score, value_a, value_b in pairwise_gaps(true_positive_rates, baseline):
                report_rows.append(
                    _metric_row(
                        "Equal Opportunity Difference",
                        attribute,
                        group_a,
                        group_b,
                        score,
                        value_a,
                        value_b,
                    )
                )

            for group_a, group_b, score, value_a, value_b in pairwise_ratios(approval_rates, baseline):
                report_rows.append(
                    _metric_row(
                        "Disparate Impact Ratio",
                        attribute,
                        group_a,
                        group_b,
                        score,
                        value_a,
                        value_b,
                    )
                )

            for group_a, group_b, score, value_a, value_b in pairwise_gaps(false_positive_rates, baseline):
                report_rows.append(
                    _metric_row(
                        "False Positive Rate Gap",
                        attribute,
                        group_a,
                        group_b,
                        score,
                        value_a,
                        value_b,
                    )
                )

        max_disparity = max((row["disparity_score"] for row in report_rows), default=0.0)
        worst_row = max(report_rows, key=lambda row: row["disparity_score"], default=None)

        return {
            "model_id": model_id,
            "window_size": len(predictions),
            "generated_at": datetime.utcnow().isoformat(),
            "reports": report_rows,
            "summary": {
                "max_disparity": round(float(max_disparity), 4),
                "worst_metric": worst_row["metric_name"] if worst_row else None,
                "status": "ok",
            },
        }
    finally:
        if owns_session and db is not None:
            db.close()
