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
                "slope": 0.0,
            }

        origin = reports[0].timestamp
        x_values = [
            (report.timestamp - origin).total_seconds() / 86400.0
            for report in reports
        ]
        y_values = [float(report.disparity_score) for report in reports]

        slope, intercept, r_value, p_value, std_err = linregress(x_values, y_values)
        slope = float(slope)

        if slope <= 0.05:
            return {
                "triggered": False,
                "reason": "slope_below_threshold",
                "slope": round(slope, 4),
                "r_value": round(float(r_value), 4),
            }

        severity = _severity_from_slope(slope)
        worst_report = max(reports, key=lambda report: float(report.disparity_score))

        message = (
            f"Bias drift detected in {worst_report.metric_name} for {worst_report.group_b}. "
            f"Current drift slope={slope:.4f}, latest disparity={worst_report.disparity_score:.4f}."
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
            "slope": round(slope, 4),
            "r_value": round(float(r_value), 4),
        }
    finally:
        if owns_session and db is not None:
            db.close()
