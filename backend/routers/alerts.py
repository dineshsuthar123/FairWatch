from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Alert

router = APIRouter(tags=["alerts"])


def _serialize_alert(alert: Alert) -> Dict[str, Any]:
    return {
        "id": alert.id,
        "model_id": alert.model_id,
        "model_name": alert.model.name if alert.model else None,
        "triggered_at": alert.triggered_at,
        "message": alert.message,
        "severity": alert.severity,
        "resolved": bool(alert.resolved),
    }


@router.get("/api/alerts/{model_id}")
def get_unresolved_alerts(model_id: int, db: Session = Depends(get_db)):
    alerts = (
        db.query(Alert)
        .filter(Alert.model_id == model_id, Alert.resolved.is_(False))
        .order_by(Alert.triggered_at.desc())
        .all()
    )

    return {
        "model_id": model_id,
        "alerts": [_serialize_alert(alert) for alert in alerts],
    }


@router.post("/api/alerts/{alert_id}/resolve")
def resolve_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found.")

    alert.resolved = True
    db.commit()
    db.refresh(alert)

    return {
        "message": "Alert resolved.",
        "alert": _serialize_alert(alert),
    }
