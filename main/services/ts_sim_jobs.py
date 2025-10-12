import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from django.utils import timezone

_jobs: Dict[str, "Job"] = {}
_lock = threading.Lock()
_TTL_SEC = 3600  # keep finished jobs for 1h


@dataclass
class Job:
    id: str
    created_at: float = field(default_factory=lambda: time.time())
    status: str = 'pending'  # pending|running|done|error|cancelled
    progress: int = 0
    message: str = ''
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


def _cleanup():
    now = time.time()
    with _lock:
        to_del = [jid for jid, j in _jobs.items() if j.status in ('done', 'error', 'cancelled') and (now - j.created_at) > _TTL_SEC]
        for jid in to_del:
            _jobs.pop(jid, None)


def create_job() -> Job:
    _cleanup()
    jid = uuid.uuid4().hex
    job = Job(id=jid)
    with _lock:
        _jobs[jid] = job
    return job


def get_job(jid: str) -> Optional[Job]:
    with _lock:
        return _jobs.get(jid)


def update_progress(jid: str, progress: int, message: str = ''):
    job = get_job(jid)
    if not job:
        return
    job.progress = max(0, min(100, int(progress)))
    if message:
        job.message = message


def complete_job(jid: str, result: Dict[str, Any]):
    job = get_job(jid)
    if not job:
        return
    job.result = result
    job.status = 'done'
    job.progress = 100


def fail_job(jid: str, err: str):
    job = get_job(jid)
    if not job:
        return
    job.status = 'error'
    job.error = err
    job.message = err


def start_ts_simulation(system_id: int, base_level: int, start_balance: float, lot_size: float, worker: Callable[[Callable[[int,str],None]], Dict[str, Any]]):
    """Start a background job to compute TS simulation.

    worker(progress_cb) must return result dict.
    """
    job = create_job()

    def run():
        try:
            j = get_job(job.id)
            if not j:
                return
            j.status = 'running'
            def cb(p:int, m:str=''):
                update_progress(job.id, p, m)
            update_progress(job.id, 1, 'Preparing')
            res = worker(cb)
            complete_job(job.id, res)
        except Exception as e:
            fail_job(job.id, str(e))

    t = threading.Thread(target=run, name=f"TS-Sim-{job.id[:6]}", daemon=True)
    t.start()
    return job.id

