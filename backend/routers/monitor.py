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
from utils.metrics import interpret_metric

router = APIRouter(tags=["monitor"])


class PredictionItem(BaseModel):
    timestamp: Optional[datetime] = None
    input_features: Dict[str, Any] = Field(default_factory=dict)
    output_decision: int = Field(ge=0, le=1)
    group_label: Union[str, Dict[str, str]]
    true_label: Optional[int] = Field(default=None, ge=0, le=1)


class PredictionBatchRequest(BaseModel):
    model_id: int
    predictions: List[PredictionItem] = Field(min_length=1)


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
    explanation = generate_explanation(analysis, feature_contributions)

    created_reports: List[BiasReport] = []
    report_timestamp = datetime.utcnow()

    for item in analysis.get("reports", []):
        interpretation = interpret_metric(item["metric_name"], float(item["disparity_score"]))
        report = BiasReport(
            model_id=model_id,
            timestamp=report_timestamp,
            metric_name=item["metric_name"],
            group_a=item["group_a"],
            group_b=item["group_b"],
            disparity_score=float(item["disparity_score"]),
            severity=interpretation["severity"],
            explanation=explanation,
            feature_contributions=feature_contributions,
            metric_meaning=interpretation["meaning"],
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


@router.post("/api/predict")
def submit_predictions(payload: PredictionBatchRequest, db: Session = Depends(get_db)):
    model = db.query(ModelRegistry).filter(ModelRegistry.id == payload.model_id).first()
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found.")

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
                input_features={"gender": gender, "race": race},
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
