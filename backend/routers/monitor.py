import json
import random
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from agents.bias_detector import get_feature_contributions, run_bias_analysis
from agents.drift_agent import detect_drift
from agents.explainer_agent import generate_explanation
from agents.fix_agent import generate_fixes
from database import get_db
from models import Alert, BiasReport, ModelRegistry, Prediction

router = APIRouter(tags=["monitor"])
MONITOR_ANALYSIS_INTERVAL = 25


class PredictionItem(BaseModel):
    timestamp: Optional[datetime] = None
    input_features: Dict[str, Any] = Field(default_factory=dict)
    output_decision: int = Field(ge=0, le=1)
    group_label: Union[str, Dict[str, str]]
    true_label: Optional[int] = Field(default=None, ge=0, le=1)


class PredictionBatchRequest(BaseModel):
    model_id: int
    predictions: List[PredictionItem] = Field(min_length=1)


class MonitorPredictionRequest(BaseModel):
    timestamp: Optional[datetime] = None
    prediction: int = Field(ge=0, le=1)
    label: int = Field(ge=0, le=1)
    features: Dict[str, Any] = Field(default_factory=dict)
    sensitive: Dict[str, Any] = Field(default_factory=dict)


def _serialize_group_label(group_label: Union[str, Dict[str, str]]) -> str:
    if isinstance(group_label, dict):
        normalized = {str(key): str(value) for key, value in group_label.items()}
        return json.dumps(normalized, sort_keys=True)

    if isinstance(group_label, str):
        try:
            parsed = json.loads(group_label)
            if isinstance(parsed, dict):
                normalized = {str(key): str(value) for key, value in parsed.items()}
                return json.dumps(normalized, sort_keys=True)
        except json.JSONDecodeError:
            pass
        return group_label

    return "{}"


def _run_full_pipeline(model_id: int, db: Session) -> Dict[str, Any]:
    analysis = run_bias_analysis(model_id=model_id, window_size=100, db=db)
    feature_contributions = get_feature_contributions(model_id=model_id, db=db, window_size=100)
    fix_suggestions = generate_fixes(analysis, feature_contributions)
    explanation = generate_explanation(analysis, feature_contributions, fix_suggestions)

    created_reports: List[BiasReport] = []
    report_timestamp = datetime.utcnow()

    for item in analysis.get("reports", []):
        report = BiasReport(
            model_id=model_id,
            timestamp=report_timestamp,
            metric_name=item["metric_name"],
            group_a=item["group_a"],
            group_b=item["group_b"],
            disparity_score=float(item["disparity_score"]),
            severity=item.get("severity", "green"),
            explanation=explanation,
            feature_contributions=feature_contributions,
            metric_meaning=item.get("metric_meaning", ""),
            fix_suggestions=fix_suggestions,
            monitoring_type="batch_window_100",
        )
        db.add(report)
        created_reports.append(report)

    if created_reports:
        db.commit()
        for report in created_reports:
            db.refresh(report)

    drift_result = detect_drift(model_id=model_id, db=db)

    return {
        "analysis": analysis,
        "feature_contributions": feature_contributions,
        "fix_suggestions": fix_suggestions,
        "explanation": explanation,
        "created_reports": created_reports,
        "drift": drift_result,
    }


def _resolve_model(db: Session, model_id: Optional[int]) -> ModelRegistry:
    if model_id is not None:
        model = db.query(ModelRegistry).filter(ModelRegistry.id == model_id).first()
        if model is None:
            raise HTTPException(status_code=404, detail="Model not found.")
        return model

    latest_model = db.query(ModelRegistry).order_by(ModelRegistry.created_at.desc()).first()
    if latest_model is None:
        raise HTTPException(status_code=404, detail="No registered model found.")
    return latest_model


def _normalize_sensitive_value(attribute: str, value: Any) -> str:
    key = str(attribute or "").strip().lower()
    raw = str(value).strip().lower()

    if key == "gender":
        if raw in {"1", "true", "male", "m"}:
            return "male"
        if raw in {"0", "false", "female", "f"}:
            return "female"

    if key == "race":
        if raw in {"1", "true", "white"}:
            return "white"
        if raw in {"0", "false", "non-white", "non_white", "other", "black", "asian", "amer-indian-eskimo"}:
            return "non-white"

    return str(value)


def _ingest_prediction(
    db: Session,
    model: ModelRegistry,
    *,
    timestamp: Optional[datetime],
    prediction: int,
    label: Optional[int],
    features: Dict[str, Any],
    sensitive: Dict[str, Any],
) -> Prediction:
    feature_payload = dict(features or {})
    if label is not None:
        feature_payload["true_label"] = int(label)

    normalized_sensitive: Dict[str, str] = {}
    candidate_keys = model.sensitive_attributes or list(sensitive.keys())
    for attribute in candidate_keys:
        if attribute in sensitive:
            normalized_sensitive[str(attribute)] = _normalize_sensitive_value(attribute, sensitive[attribute])
        elif attribute in feature_payload:
            normalized_sensitive[str(attribute)] = _normalize_sensitive_value(attribute, feature_payload[attribute])

    if not normalized_sensitive:
        normalized_sensitive = {
            str(key): _normalize_sensitive_value(str(key), value)
            for key, value in dict(sensitive or {}).items()
        }

    for key, value in normalized_sensitive.items():
        if key not in feature_payload:
            feature_payload[key] = value

    row = Prediction(
        model_id=model.id,
        timestamp=timestamp or datetime.utcnow(),
        input_features=feature_payload,
        output_decision=int(prediction),
        group_label=_serialize_group_label(normalized_sensitive),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.post("/api/predict")
def submit_predictions(payload: PredictionBatchRequest, db: Session = Depends(get_db)):
    model = _resolve_model(db, payload.model_id)

    prediction_rows: List[Prediction] = []
    for item in payload.predictions:
        features = dict(item.input_features or {})
        if item.true_label is not None:
            features["true_label"] = int(item.true_label)

        prediction_rows.append(
            Prediction(
                model_id=payload.model_id,
                timestamp=item.timestamp or datetime.utcnow(),
                input_features=features,
                output_decision=int(item.output_decision),
                group_label=_serialize_group_label(item.group_label),
            )
        )

    db.add_all(prediction_rows)
    db.commit()

    pipeline = _run_full_pipeline(model_id=payload.model_id, db=db)

    return {
        "model_id": payload.model_id,
        "saved_predictions": len(prediction_rows),
        "saved_reports": len(pipeline["created_reports"]),
        "analysis_summary": pipeline["analysis"].get("summary", {}),
        "drift": pipeline["drift"],
        "feature_contributions": pipeline["feature_contributions"],
        "fix_suggestions": pipeline["fix_suggestions"],
        "explanation": pipeline["explanation"],
    }


@router.post("/monitor")
def stream_prediction(
    payload: MonitorPredictionRequest,
    model_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    model = _resolve_model(db, model_id)
    prediction = _ingest_prediction(
        db=db,
        model=model,
        timestamp=payload.timestamp,
        prediction=payload.prediction,
        label=payload.label,
        features=payload.features,
        sensitive=payload.sensitive,
    )

    total_predictions = (
        db.query(Prediction)
        .filter(Prediction.model_id == model.id)
        .count()
    )
    should_run_pipeline = (
        total_predictions >= MONITOR_ANALYSIS_INTERVAL
        and total_predictions % MONITOR_ANALYSIS_INTERVAL == 0
    )

    response = {
        "status": "ingested",
        "model_id": model.id,
        "prediction_id": prediction.id,
        "total_predictions": total_predictions,
        "analysis_triggered": should_run_pipeline,
    }

    if should_run_pipeline:
        pipeline = _run_full_pipeline(model_id=model.id, db=db)
        response.update(
            {
                "saved_reports": len(pipeline["created_reports"]),
                "analysis_summary": pipeline["analysis"].get("summary", {}),
                "drift": pipeline["drift"],
            }
        )

    return response


@router.post("/api/demo/inject-bias")
async def inject_bias(model_id: int, db: Session = Depends(get_db)):
    """
    Injects 50 biased predictions to simulate bias drift for demo.
    Female approval rate drops to 25%. Black approval rate drops to 30%.
    Timestamps are set to NOW so graph shows real-time spike.
    """
    model = db.query(ModelRegistry).filter(ModelRegistry.id == model_id).first()
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found.")

    predictions: List[Prediction] = []
    for _ in range(50):
        gender = random.choice(["male", "female"])
        race = random.choice(["white", "black"])

        # Intentionally correlated demo features for visible root-cause behavior.
        income_base = 92000 if (gender == "male" and race == "white") else 56000
        income = max(18000, int(random.gauss(income_base, 12000)))
        employment_gap = round(random.uniform(0.0, 0.8), 2)
        if gender == "female":
            employment_gap = round(min(1.2, employment_gap + 0.22), 2)

        zip_code = "94110" if race == "white" else "94124"

        if gender == "female":
            decision = 1 if random.random() < 0.25 else 0
        elif race == "black":
            decision = 1 if random.random() < 0.30 else 0
        else:
            decision = 1 if random.random() < 0.80 else 0

        predictions.append(
            Prediction(
                model_id=model_id,
                timestamp=datetime.utcnow(),
                group_label=f"gender:{gender}|race:{race}",
                output_decision=decision,
                input_features={
                    "gender": gender,
                    "race": race,
                    "income": income,
                    "employment_gap": employment_gap,
                    "zip_code": zip_code,
                },
            )
        )

    db.add_all(predictions)
    db.commit()

    pipeline = _run_full_pipeline(model_id=model_id, db=db)

    return {
        "status": "bias injected",
        "predictions_added": 50,
        "alert_triggered": pipeline["drift"],
    }


@router.post("/api/demo/reset")
async def reset_demo(model_id: int, db: Session = Depends(get_db)):
    """Clears injected bias predictions, resets to baseline for demo restart"""
    db.query(Alert).filter(Alert.model_id == model_id).delete(synchronize_session=False)
    db.query(BiasReport).filter(BiasReport.model_id == model_id).delete(synchronize_session=False)
    db.commit()
    return {"status": "reset complete"}
