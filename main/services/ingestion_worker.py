"""
Lightweight data ingestion worker.

Every N seconds:
 - Scan trading system directories to sync DataFile metadata
 - For each DataFile, if mtime changed since last record, import file to DB
   (full re-import for correctness and recovery)
 - Track KPIs in DataIngestionStatus
"""
import os
import threading
import time
from typing import Optional

from django.utils import timezone

from ..models import TradingSystem, DataFile, DataIngestionStatus
from .datafile_collector import collect_for_system
from .bar_importer import import_datafile


class DataIngestionWorker:
    def __init__(self):
        self._active = False
        self._thread: Optional[threading.Thread] = None

    @property
    def active(self) -> bool:
        return self._active

    def start(self):
        if self._active:
            return
        self._active = True
        self._thread = threading.Thread(target=self._loop, name='DataIngestionWorker', daemon=True)
        self._thread.start()

    def stop(self):
        self._active = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def _loop(self):
        while self._active:
            status = DataIngestionStatus.get()
            status.active = True
            try:
                total_scanned = 0
                total_imported = 0
                total_rows = 0
                now = timezone.now()

                # 1) sync files from directories
                for system in TradingSystem.objects.filter(is_active=True):
                    collect_for_system(system)

                # 2) import changed files
                for df in DataFile.objects.all():
                    try:
                        if not df.file_path or not os.path.exists(df.file_path):
                            continue
                        st = os.stat(df.file_path)
                        total_scanned += 1
                        # If modified time changed or DB has fewer processed rows than file rows → reimport
                        mtime_changed = not df.file_modified or abs(st.st_mtime - (df.file_modified.timestamp() if hasattr(df.file_modified,'timestamp') else time.mktime(df.file_modified.timetuple()))) > 0.5
                        if (not df.status or df.status != 'completed') or mtime_changed:
                            res = import_datafile(df)
                            total_imported += 1
                            total_rows += (res.bars_created or 0)
                    except Exception as file_err:
                        # record error but keep going
                        status.last_error = str(file_err)
                        continue

                status.files_scanned += total_scanned
                status.files_imported += total_imported
                status.rows_imported += total_rows
                status.last_run = now
                status.save()
            except Exception as e:
                status.last_error = str(e)
                status.save()

            interval = DataIngestionStatus.get().scan_interval or 5
            time.sleep(interval)
        # Mark inactive
        status = DataIngestionStatus.get()
        status.active = False
        status.save()


_worker: Optional[DataIngestionWorker] = None


def get_worker() -> DataIngestionWorker:
    global _worker
    if _worker is None:
        _worker = DataIngestionWorker()
    return _worker


def start_ingestion():
    worker = get_worker()
    worker.start()


def stop_ingestion():
    worker = get_worker()
    worker.stop()



