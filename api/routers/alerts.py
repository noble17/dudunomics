from fastapi import APIRouter, Depends, HTTPException
from core.auth.deps import current_user, CurrentUser
from api.models import AlertIn, AlertOut, AlertEventOut, AlertTemplateIn, AlertTemplateOut
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


@router.get("/templates", response_model=list[AlertTemplateOut])
def list_alert_templates(user: CurrentUser = Depends(current_user)):
    return repo.list_alert_templates(user.id)


@router.post("/templates", response_model=AlertTemplateOut, status_code=201)
def create_alert_template(body: AlertTemplateIn, user: CurrentUser = Depends(current_user)):
    template_id = repo.create_alert_template(
        user_id=user.id,
        name=body.name,
        description=body.description,
        items=[item.model_dump() for item in body.items],
    )
    templates = repo.list_alert_templates(user.id)
    return next(template for template in templates if template["id"] == template_id)


@router.put("/templates/{template_id}", response_model=AlertTemplateOut)
def update_alert_template(template_id: int, body: AlertTemplateIn, user: CurrentUser = Depends(current_user)):
    updated = repo.update_alert_template(
        user_id=user.id,
        template_id=template_id,
        name=body.name,
        description=body.description,
        items=[item.model_dump() for item in body.items],
    )
    if not updated:
        raise HTTPException(status_code=404, detail="템플릿 없음 또는 권한 없음")
    templates = repo.list_alert_templates(user.id)
    return next(template for template in templates if template["id"] == template_id)


@router.delete("/templates/{template_id}", status_code=204)
def delete_alert_template(template_id: int, user: CurrentUser = Depends(current_user)):
    deleted = repo.delete_alert_template(user.id, template_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="템플릿 없음 또는 권한 없음")


@router.get("/events", response_model=list[AlertEventOut])
def get_alert_events(user: CurrentUser = Depends(current_user)):
    return repo.get_alert_events(user.id)


@router.get("/events/unread", response_model=list[AlertEventOut])
def get_unread_events(user: CurrentUser = Depends(current_user)):
    return repo.get_unread_alert_events(user.id)


@router.post("/events/read", status_code=204)
def mark_events_read(user: CurrentUser = Depends(current_user)):
    repo.mark_all_alert_events_read(user.id)


@router.delete("/{alert_id}", status_code=204)
def delete_alert(alert_id: int, user: CurrentUser = Depends(current_user)):
    deleted = repo.delete_user_alert(user.id, alert_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="알림 없음 또는 권한 없음")
