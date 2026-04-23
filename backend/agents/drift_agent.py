import json
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from scipy.stats import linregress
from sqlalchemy.orm import Session

from database import SessionLocal
from models import Alert, BiasReport


def _severity_from_slope(slope: float) -> str:
    if slope > 0.15:
        return "red"
    if slope > 0.08:
        return "yellow"
    return "yellow"


def _trend_phrase(slope: float) -> str:
    if slope > 0.15:
        return "increasing rapidly"
    if slope > 0.08:
        return "increasing steadily"
    if slope > 0.05:
        return "increasing slightly"
    return "stable"


def _log_webhook_alert(payload: Dict[str, Any]) -> None:
    print(f"[FAIRWATCH_WEBHOOK] {json.dumps(payload, default=str)}")


def detect_drift(model_id: int, db: Optional[Session] = None) -> Dict[str, Any]:
    owns_session = db is None
    if owns_session:
        db = SessionLocal()

    try:
        since = datetime.utcnow() - timedelta(days=30)
        reports = (
            db.query(BiasReport)
            .filter(BiasReport.model_id == model_id, BiasReport.timestamp >= since)
            .order_by(BiasReport.timestamp.asc())
            .all()
        )

        if len(reports) < 2:
            return {
                "triggered": False,
                "reason": "insufficient_reports",
                "trend_explanation": "Not enough report history to assess drift trend.",
            }

        origin = reports[0].timestamp
        x_values = [
            (report.timestamp - origin).total_seconds() / 86400.0
            for report in reports
        ]
        y_values = [float(report.disparity_score) for report in reports]

        # Right after demo reset, reports can share the same timestamp.
        # linregress cannot run with zero x-axis variance, so skip drift in that case.
        if len(set(round(value, 8) for value in x_values)) < 2:
            return {
                "triggered": False,
                "reason": "insufficient_temporal_variation",
                "trend_explanation": "Not enough timestamp variation to assess drift trend.",
            }

        try:
            slope, _, _, _, _ = linregress(x_values, y_values)
        except ValueError:
            return {
                "triggered": False,
                "reason": "regression_unavailable",
                "trend_explanation": "Trend regression is unavailable for current report history.",
            }
        slope = float(slope)

        if slope <= 0.05:
            return {
                "triggered": False,
                "reason": "slope_below_threshold",
                "trend_explanation": "Fairness disparity trend is stable or improving.",
            }

        severity = _severity_from_slope(slope)
        trend_phrase = _trend_phrase(slope)
        worst_report = max(reports, key=lambda report: float(report.disparity_score))

        message = (
            f"Bias drift detected in {worst_report.metric_name} for {worst_report.group_b}. "
            f"Disparity is {trend_phrase} over recent reports."
        )

        alert = Alert(
            model_id=model_id,
            message=message,
            severity=severity,
            resolved=False,
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)

        payload = {
            "alert_id": alert.id,
            "model_id": model_id,
            "severity": severity,
            "message": message,
            "slope": round(slope, 4),
            "triggered_at": alert.triggered_at,
        }
        _log_webhook_alert(payload)

        return {
            "triggered": True,
            "alert_id": alert.id,
            "severity": severity,
            "message": message,
            "trend_explanation": message,
        }
    finally:
        if owns_session and db is not None:
            db.close()
