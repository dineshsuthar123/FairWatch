from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from agents.explainer_agent import generate_explanation
from database import get_db
from models import BiasReport

router = APIRouter(tags=["reports"])

SEVERITY_RANK = {"green": 1, "yellow": 2, "red": 3}


def _serialize_report(report: BiasReport) -> Dict[str, Any]:
    return {
        "id": report.id,
        "model_id": report.model_id,
        "timestamp": report.timestamp,
        "metric_name": report.metric_name,
        "group_a": report.group_a,
        "group_b": report.group_b,
        "disparity_score": float(report.disparity_score),
        "severity": report.severity,
        "explanation": report.explanation,
        "feature_contributions": report.feature_contributions,
        "metric_meaning": report.metric_meaning,
        "fix_suggestions": report.fix_suggestions,
        "monitoring_type": report.monitoring_type,
    }


@router.get("/api/reports/{model_id}")
def get_reports(model_id: int, db: Session = Depends(get_db)):
    reports = (
        db.query(BiasReport)
        .filter(BiasReport.model_id == model_id)
        .order_by(BiasReport.timestamp.asc())
        .all()
    )

    return {
        "model_id": model_id,
        "reports": [_serialize_report(report) for report in reports],
    }


@router.get("/api/reports/{model_id}/latest")
def get_latest_report(model_id: int, db: Session = Depends(get_db)):
    latest = (
        db.query(BiasReport)
        .filter(BiasReport.model_id == model_id)
        .order_by(BiasReport.timestamp.desc())
        .first()
    )
    if latest is None:
        raise HTTPException(status_code=404, detail="No bias reports found for this model.")

    report_batch = (
        db.query(BiasReport)
        .filter(BiasReport.model_id == model_id, BiasReport.timestamp == latest.timestamp)
        .order_by(BiasReport.metric_name.asc())
        .all()
    )

    top_severity = max(
        report_batch,
        key=lambda report: SEVERITY_RANK.get(report.severity, 0),
    ).severity

    return {
        "model_id": model_id,
        "timestamp": latest.timestamp,
        "severity": top_severity,
        "explanation": latest.explanation,
        "feature_contributions": latest.feature_contributions,
        "fix_suggestions": latest.fix_suggestions,
        "monitoring_type": latest.monitoring_type,
        "metrics": [_serialize_report(report) for report in report_batch],
    }


@router.post("/api/reports/{model_id}/latest/regenerate")
def regenerate_latest_explanation(model_id: int, db: Session = Depends(get_db)):
    latest = (
        db.query(BiasReport)
        .filter(BiasReport.model_id == model_id)
        .order_by(BiasReport.timestamp.desc())
        .first()
    )
    if latest is None:
        raise HTTPException(status_code=404, detail="No bias reports found for this model.")

    report_batch = (
        db.query(BiasReport)
        .filter(BiasReport.model_id == model_id, BiasReport.timestamp == latest.timestamp)
        .order_by(BiasReport.metric_name.asc())
        .all()
    )

    report_dict = {
        "model_id": model_id,
        "generated_at": latest.timestamp,
        "reports": [
            {
                "metric_name": report.metric_name,
                "group_a": report.group_a,
                "group_b": report.group_b,
                "disparity_score": float(report.disparity_score),
                "severity": report.severity,
            }
            for report in report_batch
        ],
    }
    feature_contributions = latest.feature_contributions or {
        "top_contributing_features": [],
        "proxy_warnings": [],
    }

    explanation = generate_explanation(report_dict, feature_contributions)

    for report in report_batch:
        report.explanation = explanation

    db.commit()

    return {
        "model_id": model_id,
        "timestamp": latest.timestamp,
        "explanation": explanation,
        "feature_contributions": latest.feature_contributions,
        "fix_suggestions": latest.fix_suggestions,
        "monitoring_type": latest.monitoring_type,
        "metrics": [_serialize_report(report) for report in report_batch],
    }
