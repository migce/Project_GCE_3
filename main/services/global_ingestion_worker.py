"""
Global feed ingestion worker.

Every N seconds:
 - For each active TradingSystem, scan data directory via TF bindings and sync MarketDataFile
 - Import pending/changed MarketDataFile into MarketBar/MarketIndicator*
 - Optionally re-generate signals for the affected system
 - Track KPIs in DataIngestionStatus (reuse existing model)
"""
from __future__ import annotations

import os
import threading
import time
from typing import Optional
from datetime import datetime, timezone as dt_timezone

from django.utils import timezone

from ..models import TradingSystem, MarketDataFile, DataIngestionStatus, SignalEvent
from .global_feed_collector import collect_for_system as collect_global
from .global_importer import import_market_datafile
from .signal_engine import generate_signals_for_system


class GlobalIngestionWorker:
    def __init__(self):
        self._active = False
        self._thread: Optional[threading.Thread] = None

    @property
    def active(self) -> bool:
        return self._active

    def start(self):
        if self._thread is None or not self._thread.is_alive():
            self._active = True
            self._thread = threading.Thread(target=self._loop, name='GlobalIngestionWorker', daemon=True)
            self._thread.start()
        else:
            self._active = True

    def stop(self):
        self._active = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def _loop(self):
        while self._active:
            try:
                self._tick()
            except Exception:
                pass
            try:
                st = DataIngestionStatus.get()
                interval = st.scan_interval or 5
            except Exception:
                interval = 5
            time.sleep(interval)

    def _tick(self):
        status = DataIngestionStatus.get()
        status.active = True
        now = timezone.now()
        scanned = 0
        imported = 0
        rows = 0

        # 1) Collect files per system via TF bindings
        systems = TradingSystem.objects.filter(is_active=True)
        for sys in systems:
            try:
                collect_global(sys)
            except Exception:
                continue

        # 2) Import pending/changed MarketDataFile
        for mdf in MarketDataFile.objects.all():
            try:
                if not mdf.file_path or not os.path.exists(mdf.file_path):
                    continue
                st = os.stat(mdf.file_path)
                scanned += 1
                mtime_changed = (not mdf.file_modified) or abs(st.st_mtime - (mdf.file_modified.timestamp() if hasattr(mdf.file_modified,'timestamp') else time.mktime(mdf.file_modified.timetuple()))) > 0.5
                if (mdf.status != 'completed') or mtime_changed:
                    res = import_market_datafile(mdf)
                    imported += 1
                    rows += (res.bars_created or 0)
                    # Generate signals
                    try:
                        from ..models import TradingSystemTFBinding
                        bindings = list(mdf.feed.system_bindings.all())
                        for b in bindings:
                            try:
                                from .signal_engine import generate_signals_for_system
                                generate_signals_for_system(b.trading_system, limit_bars=1000)
                            except Exception:
                                continue
                    except Exception:
                        pass
            except Exception as e:
                status.last_error = str(e)
                continue

        status.files_scanned += scanned
        status.files_imported += imported
        status.rows_imported += rows
        status.last_run = now
        status.last_error = ''
        status.save()


_worker: Optional[GlobalIngestionWorker] = None


def get_worker() -> GlobalIngestionWorker:
    global _worker
    if _worker is None:
        _worker = GlobalIngestionWorker()
    return _worker


def start_global_ingestion():
    get_worker().start()


def stop_global_ingestion():
    get_worker().stop()
