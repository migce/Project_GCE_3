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
from datetime import datetime, timezone as dt_timezone

from django.utils import timezone

from ..models import TradingSystem, DataFile, DataIngestionStatus, ImportLog
from .datafile_collector import collect_for_system
from .bar_importer import import_datafile


class DataIngestionWorker:
    def __init__(self):
        self._active = False
        self._thread: Optional[threading.Thread] = None
        # Throttle 'no_change' logs: log every N cycles per file
        self._no_change_every: int = 12  # ~1 minute if scan_interval=5s
        self._no_change_counters: dict[int, int] = {}

    @property
    def active(self) -> bool:
        return self._active

    def start(self):
        # Start or revive the worker thread
        if self._thread is None or not self._thread.is_alive():
            self._active = True
            self._thread = threading.Thread(target=self._loop, name='DataIngestionWorker', daemon=True)
            self._thread.start()
        else:
            # Ensure active flag is set if thread already running
            self._active = True

    def stop(self):
        self._active = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def _loop(self):
        while self._active:
            try:
                status = DataIngestionStatus.get()
                status.active = True
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
                            # Import or re-import
                            try:
                                res = import_datafile(df)
                                total_imported += 1
                                total_rows += (res.bars_created or 0)
                                # Log successful import
                                ImportLog.objects.create(
                                    trading_system=df.trading_system,
                                    timeframe=df.timeframe,
                                    data_file=df,
                                    filename=df.filename,
                                    action='imported',
                                    rows_imported=(res.bars_created or 0),
                                    message=f"indicators={res.indicator_values_created}",
                                    file_size=st.st_size,
                                    file_modified=datetime.fromtimestamp(st.st_mtime, tz=dt_timezone.utc),
                                )
                            except Exception as imp_err:
                                # Log error and continue to next file
                                ImportLog.objects.create(
                                    trading_system=df.trading_system,
                                    timeframe=df.timeframe,
                                    data_file=df,
                                    filename=df.filename,
                                    action='error',
                                    rows_imported=0,
                                    message=str(imp_err),
                                    file_size=st.st_size,
                                    file_modified=datetime.fromtimestamp(st.st_mtime, tz=dt_timezone.utc),
                                )
                                raise
                        else:
                            # No change this cycle; throttle log frequency per file
                            cnt = self._no_change_counters.get(df.id, 0) + 1
                            self._no_change_counters[df.id] = cnt
                            if cnt % max(1, self._no_change_every) == 0:
                                ImportLog.objects.create(
                                    trading_system=df.trading_system,
                                    timeframe=df.timeframe,
                                    data_file=df,
                                    filename=df.filename,
                                    action='no_change',
                                    rows_imported=0,
                                    message='',
                                    file_size=st.st_size,
                                    file_modified=datetime.fromtimestamp(st.st_mtime, tz=dt_timezone.utc),
                                )
                    except Exception as file_err:
                        # record error but keep going
                        status.last_error = str(file_err)
                        continue

                status.files_scanned += total_scanned
                status.files_imported += total_imported
                status.rows_imported += total_rows
                status.last_run = now
                # clear stale error if this cycle succeeded
                status.last_error = ''
                status.save()
            except Exception as e:
                try:
                    status.last_error = str(e)
                    status.save()
                except Exception:
                    pass

            try:
                interval = DataIngestionStatus.get().scan_interval or 5
            except Exception:
                interval = 5
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



