from fastapi import APIRouter, Depends
from pydantic import BaseModel
from core.auth.deps import CurrentUser, current_user
import core.repository as repo

router = APIRouter(prefix="/api/workspace", tags=["workspace"])


class WorkspaceIn(BaseModel):
    layout: dict
    name: str = "default"


@router.get("")
def get_workspace(name: str = "default", user: CurrentUser = Depends(current_user)):
    return {"layout": repo.get_workspace(user.id, name), "name": name}


@router.put("")
def save_workspace(body: WorkspaceIn, user: CurrentUser = Depends(current_user)):
    repo.save_workspace(user.id, body.layout, body.name)
    return {"ok": True}
