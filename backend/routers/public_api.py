from fastapi import APIRouter, Depends, Header, HTTPException
from typing import Dict, Any
from sqlalchemy.orm import Session

from database import get_db
from routers.monitor import MonitorPredictionRequest, stream_prediction
from agents.bias_detector import run_bias_analysis
from agents.explainer_agent import generate_explanation

router = APIRouter(prefix="/api/v1", tags=["public"])
API_KEY = "dev_secret_key"


def verify_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _get_model_id(payload_or_id: Any) -> int:
    model_id = None
    if isinstance(payload_or_id, dict):
        model_id = payload_or_id.get("model_id", 1)
    else:
        model_id = payload_or_id

    if isinstance(model_id, str) and model_id.isdigit():
        return int(model_id)
    if isinstance(model_id, int):
        return model_id
    return 1


@router.post("/evaluate", dependencies=[Depends(verify_key)])
def evaluate(payload: Dict[str, Any], db: Session = Depends(get_db)):
    """
    Intercepts decision and returns block/allow response.
    """
    model_id = _get_model_id(payload)
    
    try:
        req = MonitorPredictionRequest(**payload)
        stream_prediction(req, model_id=model_id, db=db)
    except Exception:
        pass

    analysis = run_bias_analysis(model_id=model_id, window_size=100, db=db)
    result = analysis.get("decision_summary", {})

    decision = "blocked" if result.get("status") == "unsafe" else "allowed"

    return {
        "decision": decision,
        "status": result.get("status", "safe"),
        "reason": result.get("reason", "Bias detected"),
        "affected_groups": result.get("affected_groups", []),
        "confidence": result.get("confidence", "medium"),
        "action": "prevented" if decision == "blocked" else "allowed"
    }


@router.post("/monitor", dependencies=[Depends(verify_key)])
def monitor(payload: Dict[str, Any], db: Session = Depends(get_db)):
    """
    Logs prediction into monitoring pipeline.
    """
    model_id = _get_model_id(payload)
    try:
        req = MonitorPredictionRequest(**payload)
        stream_prediction(req, model_id=model_id, db=db)
    except Exception:
        pass

    analysis = run_bias_analysis(model_id=model_id, window_size=100, db=db)
    result = analysis.get("decision_summary", {})

    decision = "blocked" if result.get("status") == "unsafe" else "allowed"

    return {
        "decision": decision,
        "status": result.get("status", "safe"),
        "reason": result.get("reason", "Bias detected"),
        "affected_groups": result.get("affected_groups", []),
        "confidence": result.get("confidence", "medium"),
        "action": "prevented" if decision == "blocked" else "allowed"
    }


@router.get("/models/{model_id}/status", dependencies=[Depends(verify_key)])
def get_status(model_id: str, db: Session = Depends(get_db)):
    resolved_id = _get_model_id(model_id)
    analysis = run_bias_analysis(model_id=resolved_id, window_size=100, db=db)
    status = analysis.get("decision_summary", {})
    
    return {
        "status": status.get("status", "safe"),
        "confidence": status.get("confidence", "medium"),
        "summary": status.get("reason", ""),
        "metrics": status.get("metrics", {})
    }


@router.post("/explain", dependencies=[Depends(verify_key)])
def explain(payload: Dict[str, Any], db: Session = Depends(get_db)):
    model_id = _get_model_id(payload)
    analysis = run_bias_analysis(model_id=model_id, window_size=100, db=db)
    
    explanation_payload = {
        "model_id": model_id,
        "reports": analysis.get("reports", []),
        "summary": analysis.get("summary", {}),
        "live_window_metrics": analysis.get("reports", []),
        "decision_summary": analysis.get("decision_summary", {})
    }
    
    explanation = generate_explanation(explanation_payload, {"top_contributing_features": [], "proxy_warnings": []}, {})
    
    return {
        "explanation": explanation
    }


@router.get("/health")
def health():
    return {"status": "ok"}
