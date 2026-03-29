import threading
import uuid
from typing import Dict, Optional


class IndexingJobManager:
    """Thread-safe registry for tracking active indexing jobs."""
    def __init__(self):
        self._lock = threading.Lock()
        self._active_jobs: Dict[str, str] = {} # folder_path -> status

    def start_job(self, folder_path: str) -> bool:
        """Returns True if job started, False if already running."""
        with self._lock:
            if folder_path in self._active_jobs:
                return False
            self._active_jobs[folder_path] = "Initializing..."
            return True

    def update_job(self, folder_path: str, status: str):
        """Update the status of an active job."""
        with self._lock:
            if folder_path in self._active_jobs:
                self._active_jobs[folder_path] = status

    def finish_job(self, folder_path: str):
        """Complete a job and remove it from the registry."""
        with self._lock:
            self._active_jobs.pop(folder_path, None)

    def get_active_jobs(self) -> Dict[str, str]:
        """Return a snapshot of all active jobs and their statuses."""
        with self._lock:
            return self._active_jobs.copy()

class PlanningJobManager:
    """Thread-safe registry for tracking asynchronous Mahaguru planning jobs."""
    def __init__(self):
        self._lock = threading.Lock()
        # job_id -> {"status": str, "result": Optional[str], "brief": str}
        self._jobs: Dict[str, dict] = {}

    def create_job(self, brief: str) -> str:
        """Register a new job and return a unique Job ID."""
        job_id = f"plan_{uuid.uuid4().hex[:8]}"
        with self._lock:
            self._jobs[job_id] = {
                "status": "Running",
                "result": None,
                "brief": (brief[:60] + "...") if len(brief) > 60 else brief
            }
        return job_id

    def complete_job(self, job_id: str, result: str):
        """Mark a job as completed and store the result."""
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["status"] = "Completed"
                self._jobs[job_id]["result"] = result

    def fail_job(self, job_id: str, error_msg: str):
        """Mark a job as failed and store the error."""
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["status"] = "Failed"
                self._jobs[job_id]["result"] = error_msg

    def check_status(self, job_id: str) -> Optional[dict]:
        """Peek at the job status without removing it."""
        with self._lock:
            return self._jobs.get(job_id)

    def pop_job(self, job_id: str) -> Optional[dict]:
        """Retrieve the job and remove it from the registry to free memory."""
        with self._lock:
            return self._jobs.pop(job_id, None)

    def get_active_jobs(self) -> Dict[str, str]:
        """Return a snapshot of running planning jobs."""
        with self._lock:
            return {jid: data["brief"] for jid, data in self._jobs.items() if data["status"] == "Running"}

# Singleton instances
job_manager = IndexingJobManager()
planning_job_manager = PlanningJobManager()
