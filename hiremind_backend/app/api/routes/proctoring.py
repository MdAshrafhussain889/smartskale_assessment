from uuid import UUID
from pathlib import Path
import base64
import binascii
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.user import ProctorEvent, AssessmentAttempt, Assessment
from app.schemas.schemas import ProctorEventRequest
from app.api.routes.websocket import broadcast_proctor_event

router = APIRouter(prefix="/api/proctor", tags=["Proctoring"])
MEDIA_ROOT = Path("media/proctor")

VIOLATION_WEIGHTS = {
    "tab_switch": 5,
    "face_missing": 10,
    "fullscreen_exit": 8,
    "multi_face": 15,
    "copy_paste": 12,
    "other": 3,
}


def _save_snapshot(attempt_id: UUID, frame_snapshot: str | None) -> str | None:
    if not frame_snapshot:
        return None

    raw = frame_snapshot
    if "," in raw:
        raw = raw.split(",", 1)[1]

    try:
        image_bytes = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="Invalid frame snapshot")

    if len(image_bytes) > 750_000:
        raise HTTPException(status_code=413, detail="Snapshot is too large")

    MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    # Use timestamp-like UUID for stable uniqueness without trusting user filenames.
    from uuid import uuid4
    filename = f"{attempt_id}_{uuid4().hex}.jpg"
    path = MEDIA_ROOT / filename
    path.write_bytes(image_bytes)
    return f"/media/proctor/{filename}"


@router.post("/event", status_code=201)
async def log_proctor_event(
    payload: ProctorEventRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Log a proctoring violation event."""
    attempt = db.query(AssessmentAttempt).filter(
        AssessmentAttempt.id == payload.session_id,
    ).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Session not found")
    if current_user.role == "candidate" and attempt.candidate_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    snapshot_url = _save_snapshot(attempt.id, payload.frame_snapshot)

    event = ProctorEvent(
        attempt_id=attempt.id,
        event_type=payload.event_type,
        timestamp=payload.timestamp,
        frame_snapshot_url=snapshot_url,
        metadata_=payload.metadata,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    response = {
        "event_id": str(event.id),
        "session_id": str(attempt.id),
        "event_type": event.event_type,
        "severity_weight": VIOLATION_WEIGHTS.get(payload.event_type, 3),
        "timestamp": event.timestamp.isoformat(),
        "snapshot_url": event.frame_snapshot_url,
        "metadata": event.metadata_ or {},
    }
    await broadcast_proctor_event(str(attempt.id), response)
    return response


@router.get("/session/{attempt_id}/summary")
def get_session_summary(
    attempt_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("recruiter", "admin")),
):
    """Summarise all proctoring events for an attempt."""
    query = (
        db.query(AssessmentAttempt)
        .join(Assessment, AssessmentAttempt.assessment_id == Assessment.id)
        .filter(AssessmentAttempt.id == attempt_id)
    )
    if current_user.role != "admin":
        query = query.filter(Assessment.recruiter_id == current_user.id)
    attempt = query.first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Session not found")

    events = (
        db.query(ProctorEvent)
        .filter(ProctorEvent.attempt_id == attempt_id)
        .order_by(ProctorEvent.timestamp)
        .all()
    )

    counts: dict = {}
    total_penalty = 0
    for e in events:
        counts[e.event_type] = counts.get(e.event_type, 0) + 1
        total_penalty += VIOLATION_WEIGHTS.get(e.event_type, 3)

    risk_level = "low"
    if total_penalty >= 50:
        risk_level = "high"
    elif total_penalty >= 20:
        risk_level = "medium"

    return {
        "attempt_id": str(attempt_id),
        "total_events": len(events),
        "event_counts": counts,
        "total_penalty_score": total_penalty,
        "cheating_risk": risk_level,
        "events": [
            {
                "id": str(e.id),
                "type": e.event_type,
                "timestamp": e.timestamp.isoformat(),
                "snapshot_url": e.frame_snapshot_url,
                "metadata": e.metadata_ or {},
            }
            for e in events
        ],
    }
