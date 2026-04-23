from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from agents.bias_detector import run_bias_analysis
from agents.chat_agent import handle_query
from database import get_db
from models import BiasReport
from routers.monitor import MONITOR_WINDOW_SIZE
from utils.metrics import summarize_decision

router = APIRouter(tags=["chat"])

SEVERITY_RANK = {"green": 1, "yellow": 2, "red": 3}

class ChatRequest(BaseModel):
    query: str

@router.post("/api/chat/{model_id}")
def chat_with_copilot(model_id: int, request: ChatRequest, db: Session = Depends(get_db)):
    latest = (
        db.query(BiasReport)
        .filter(BiasReport.model_id == model_id)
        .order_by(BiasReport.timestamp.desc())
        .first()
    )
    
    if latest is None:
        return {
            "answer": "No fairness monitoring data is available for this model yet.",
            "risk_level": "safe",
            "affected_groups": [],
            "recommended_action": "Wait for monitoring data to accumulate."
        }

    window_analysis = run_bias_analysis(
        model_id=model_id,
        window_size=MONITOR_WINDOW_SIZE,
        db=db,
        scope_label="live_window",
    )
    aggregate_analysis = run_bias_analysis(
        model_id=model_id,
        window_size=None,
        db=db,
        scope_label="aggregate",
    )

    live_window_metrics = window_analysis.get("reports", [])
    aggregate_metrics = aggregate_analysis.get("reports", [])

    if live_window_metrics:
        top_severity_rank = max(
            live_window_metrics,
            key=lambda metric: SEVERITY_RANK.get(str(metric.get("severity", "")).lower(), 0),
        ).get("severity", "green")
    else:
        report_batch = (
            db.query(BiasReport)
            .filter(BiasReport.model_id == model_id, BiasReport.timestamp == latest.timestamp)
            .order_by(BiasReport.metric_name.asc())
            .all()
        )
        top_severity_rank = max(
            report_batch,
            key=lambda report: SEVERITY_RANK.get(report.severity, 0),
        ).severity

    decision_summary = summarize_decision(live_window_metrics, "live_window")
    aggregate_decision_summary = summarize_decision(aggregate_metrics, "aggregate")
    
    context = {
        "model_id": model_id,
        "is_status_CRITICAL": top_severity_rank == "red",
        "overall_severity": top_severity_rank,
        "metrics": live_window_metrics,
        "live_window_metrics": live_window_metrics,
        "aggregate_metrics": aggregate_metrics,
        "decision_summary": decision_summary,
        "aggregate_decision_summary": aggregate_decision_summary,
        "feature_contributions": latest.feature_contributions,
        "fix_suggestions": latest.fix_suggestions,
        "explanation": latest.explanation,
        "monitoring_type": latest.monitoring_type,
    }

    try:
        copilot_response = handle_query(request.query, context)
        return copilot_response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
