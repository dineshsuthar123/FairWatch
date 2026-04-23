from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from agents.bias_detector import run_bias_analysis
from database import get_db
from models import BiasReport, Prediction
from routers.monitor import MONITOR_MIN_SAMPLES, MONITOR_WINDOW_SIZE, _run_full_pipeline
from utils.metrics import summarize_decision

router = APIRouter(prefix="/api/reports", tags=["reports"])

SEVERITY_RANK = {"green": 1, "yellow": 2, "red": 3}


def _serialize_report(report: BiasReport) -> Dict[str, Any]:
    return {
        "id": report.id,
        "model_id": report.model_id,
        "timestamp": report.timestamp,
        "metric": report.metric_name,
        "metric_name": report.metric_name,
        "metric_type": "live_window",
        "group_a": report.group_a,
        "group_b": report.group_b,
        "value": float(report.disparity_score),
        "disparity_score": float(report.disparity_score),
        "severity": report.severity,
        "interpretation": report.metric_meaning,
        "explanation": report.explanation,
        "feature_contributions": report.feature_contributions,
        "metric_meaning": report.metric_meaning,
        "fix_suggestions": report.fix_suggestions,
        "monitoring_type": report.monitoring_type,
    }


def _no_data_response(model_id: int, message: str) -> Dict[str, Any]:
    return {
        "status": "no_data",
        "model_id": model_id,
        "message": message,
        "reports": [],
        "metrics": [],
        "live_window_metrics": [],
        "aggregate_metrics": [],
        "decision_summary": summarize_decision([], "live_window"),
        "aggregate_decision_summary": summarize_decision([], "aggregate"),
    }


def _dual_scope_metrics(model_id: int, db: Session) -> Dict[str, Any]:
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

    return {
        "live_window_metrics": live_window_metrics,
        "aggregate_metrics": aggregate_metrics,
        "decision_summary": summarize_decision(live_window_metrics, "live_window"),
        "aggregate_decision_summary": summarize_decision(aggregate_metrics, "aggregate"),
    }


def _prediction_count(model_id: int, db: Session) -> int:
    return (
        db.query(Prediction)
        .filter(Prediction.model_id == model_id)
        .count()
    )


def _latest_report_batch(model_id: int, db: Session) -> List[BiasReport]:
    latest = (
        db.query(BiasReport)
        .filter(BiasReport.model_id == model_id)
        .order_by(BiasReport.timestamp.desc())
        .first()
    )
    if latest is None:
        return []

    return (
        db.query(BiasReport)
        .filter(BiasReport.model_id == model_id, BiasReport.timestamp == latest.timestamp)
        .order_by(BiasReport.metric_name.asc())
        .all()
    )


def get_report_from_store(model_id: int, db: Session) -> Dict[str, Any]:
    report_batch = _latest_report_batch(model_id=model_id, db=db)
    if not report_batch:
        return _no_data_response(model_id, "No monitoring data available")

    latest = report_batch[0]
    metric_sets = _dual_scope_metrics(model_id=model_id, db=db)
    live_window_metrics = metric_sets["live_window_metrics"]

    if live_window_metrics:
        top_severity = max(
            live_window_metrics,
            key=lambda metric: SEVERITY_RANK.get(str(metric.get("severity", "")).lower(), 0),
        ).get("severity", "green")
    else:
        top_severity = max(
            report_batch,
            key=lambda report: SEVERITY_RANK.get(report.severity, 0),
        ).severity

    return {
        "status": "ok",
        "model_id": model_id,
        "timestamp": latest.timestamp,
        "severity": top_severity,
        "explanation": latest.explanation,
        "feature_contributions": latest.feature_contributions,
        "fix_suggestions": latest.fix_suggestions,
        "monitoring_type": latest.monitoring_type,
        "metrics": live_window_metrics,
        "live_window_metrics": live_window_metrics,
        "aggregate_metrics": metric_sets["aggregate_metrics"],
        "decision_summary": metric_sets["decision_summary"],
        "aggregate_decision_summary": metric_sets["aggregate_decision_summary"],
        "reports": [_serialize_report(report) for report in report_batch],
    }


def generate_latest_report(model_id: int, db: Session) -> Dict[str, Any]:
    prediction_count = _prediction_count(model_id=model_id, db=db)
    if prediction_count < MONITOR_MIN_SAMPLES:
        return _no_data_response(
            model_id,
            f"Need at least {MONITOR_MIN_SAMPLES} monitoring samples before generating a report.",
        )

    print(
        f"[REPORTS] Generating latest report for model_id={model_id} "
        f"prediction_count={prediction_count}"
    )
    pipeline = _run_full_pipeline(model_id=model_id, db=db)

    if not pipeline.get("created_reports"):
        print(f"[REPORTS] No report rows generated for model_id={model_id}")
        return _no_data_response(
            model_id,
            "Monitoring data was stored, but fairness metrics are not ready yet.",
        )

    print(
        f"[REPORTS] Generated latest report for model_id={model_id} "
        f"rows={len(pipeline['created_reports'])}"
    )
    return get_report_from_store(model_id=model_id, db=db)


@router.get("/{model_id}")
def get_reports(model_id: int, db: Session = Depends(get_db)):
    reports = (
        db.query(BiasReport)
        .filter(BiasReport.model_id == model_id)
        .order_by(BiasReport.timestamp.asc())
        .all()
    )

    if not reports and _prediction_count(model_id=model_id, db=db) >= MONITOR_MIN_SAMPLES:
        generate_latest_report(model_id=model_id, db=db)
        reports = (
            db.query(BiasReport)
            .filter(BiasReport.model_id == model_id)
            .order_by(BiasReport.timestamp.asc())
            .all()
        )

    if not reports:
        return _no_data_response(model_id, "No monitoring data available")

    return {
        "status": "ok",
        "model_id": model_id,
        "reports": [_serialize_report(report) for report in reports],
    }


@router.get("/{model_id}/latest")
def get_latest_report(model_id: int, db: Session = Depends(get_db)):
    stored = get_report_from_store(model_id=model_id, db=db)
    if stored.get("status") == "ok":
        return stored

    if _prediction_count(model_id=model_id, db=db) >= MONITOR_MIN_SAMPLES:
        return generate_latest_report(model_id=model_id, db=db)

    return stored


@router.post("/{model_id}/latest/regenerate")
def regenerate_report(model_id: int, db: Session = Depends(get_db)):
    print(f"[REPORTS] Regenerate requested for model_id={model_id}")
    return generate_latest_report(model_id=model_id, db=db)
