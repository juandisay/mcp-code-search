import logging
import os
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from core.dependencies import get_indexer
from core.job_manager import job_manager
from core.utils import run_background_indexing

logger = logging.getLogger(__name__)
router = APIRouter()

class IndexRequest(BaseModel):
    path: str

@router.get("/stats")
def get_stats():
    """Get code search index statistics and active jobs."""
    try:
        indexer = get_indexer()
        projects = indexer.list_projects()
        active_jobs = job_manager.get_active_jobs()
        return {
            "timestamp": datetime.now().isoformat(),
            "total_chunks": indexer.collection.count(),
            "projects": projects,
            "active_tasks": active_jobs
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/index")
def api_index_folder(request: IndexRequest, background_tasks: BackgroundTasks):
    """Initiate background indexing via REST."""
    if not os.path.isdir(request.path):
        raise HTTPException(status_code=400, detail=f"Path '{request.path}' is not a directory.")

    # Use Job Manager to prevent duplicate indexing
    if not job_manager.start_job(request.path):
        return {"status": "already_indexing", "path": request.path}

    background_tasks.add_task(run_background_indexing, request.path)
    return {
        "status": "started",
        "path": request.path,
        "detail": "Indexing started in the background."
    }

@router.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}
