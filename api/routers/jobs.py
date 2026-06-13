from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

import core.repository as repo
from api.models import JobOut, JobRunOut
from core.auth.deps import CurrentUser, current_user
from core.scheduler import get_bootstrap_job_definitions, get_job_definitions, run_bootstrap_jobs, run_registered_job

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("", response_model=list[JobOut])
def list_jobs(_user: CurrentUser = Depends(current_user)):
    latest = repo.get_latest_job_runs()
    return [
        {**job, "latest_run": latest.get(job["id"])}
        for job in get_job_definitions()
    ]


@router.get("/{job_id}/runs", response_model=list[JobRunOut])
def list_runs(
    job_id: str,
    limit: int = Query(50, ge=1, le=200),
    _user: CurrentUser = Depends(current_user),
):
    _require_job(job_id)
    return repo.list_job_runs(job_id, limit=limit)


@router.post("/bootstrap/run")
def run_bootstrap(background_tasks: BackgroundTasks, _user: CurrentUser = Depends(current_user)):
    jobs = get_bootstrap_job_definitions()
    background_tasks.add_task(run_bootstrap_jobs, "manual_bootstrap")
    return {"status": "started", "job_ids": [job["id"] for job in jobs]}


@router.post("/{job_id}/run")
def run_job(job_id: str, background_tasks: BackgroundTasks, _user: CurrentUser = Depends(current_user)):
    _require_job(job_id)
    background_tasks.add_task(run_registered_job, job_id, "manual")
    return {"status": "started", "job_id": job_id}


def _require_job(job_id: str) -> None:
    if job_id not in {job["id"] for job in get_job_definitions()}:
        raise HTTPException(status_code=404, detail="등록되지 않은 작업입니다.")
