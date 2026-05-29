from fastapi import APIRouter, Depends, HTTPException
from core.auth.deps import current_user, CurrentUser
from api.models import AlertIn, AlertOut, AlertEventOut
import core.repository as repo

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut])
def list_alerts(user: CurrentUser = Depends(current_user)):
    return repo.get_user_alerts(user.id)


@router.post("", response_model=AlertOut, status_code=201)
def create_alert(body: AlertIn, user: CurrentUser = Depends(current_user)):
    alert_id = repo.create_alert(
        user_id=user.id,
        ticker=body.ticker,
        condition_type=body.condition_type,
        condition_value=body.condition_value,
    )
    alerts = repo.get_user_alerts(user.id)
    return next(a for a in alerts if a["id"] == alert_id)


@router.delete("/{alert_id}", status_code=204)
def delete_alert(alert_id: int, user: CurrentUser = Depends(current_user)):
    deleted = repo.delete_user_alert(user.id, alert_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="알림 없음 또는 권한 없음")


@router.get("/events", response_model=list[AlertEventOut])
def get_alert_events(user: CurrentUser = Depends(current_user)):
    return repo.get_alert_events(user.id)


@router.get("/events/unread", response_model=list[AlertEventOut])
def get_unread_events(user: CurrentUser = Depends(current_user)):
    return repo.get_unread_alert_events(user.id)


@router.post("/events/read", status_code=204)
def mark_events_read(user: CurrentUser = Depends(current_user)):
    repo.mark_all_alert_events_read(user.id)
