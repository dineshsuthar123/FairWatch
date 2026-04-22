from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from agents.chat_agent import handle_query
from database import get_db
from models import BiasReport

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
    
    context = {
        "model_id": model_id,
        "is_status_CRITICAL": top_severity_rank == "red",
        "overall_severity": top_severity_rank,
        "metrics": [
            {
                "metric_name": r.metric_name,
                "score": float(r.disparity_score),
                "group_a": r.group_a,
                "group_b": r.group_b,
                "severity": r.severity,
                "metric_meaning": r.metric_meaning,
            } for r in report_batch
        ],
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
