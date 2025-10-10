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
from django.db import close_old_connections, OperationalError, transaction

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
                # Ensure per-thread DB connection is fresh
                close_old_connections()
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
        close_old_connections()
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
                    # Import with retries to avoid transient SQLite locks
                    res = None
                    for attempt in range(5):
                        try:
                            close_old_connections()
                            res = import_market_datafile(mdf)
                            break
                        except OperationalError as oe:
                            if 'locked' in str(oe).lower() and attempt < 4:
                                time.sleep(0.2 * (attempt + 1))
                                continue
                            raise
                    imported += 1
                    rows += (res.bars_created or 0)
                    # Generate and persist signals for systems bound to this feed
                    try:
                        from django.utils import timezone as dj_tz
                        from datetime import timedelta
                        from ..models import TradingSystemTFBinding, SignalEvent
                        bindings = list(mdf.feed.system_bindings.all())
                        for b in bindings:
                            try:
                                from .signal_engine import generate_signals_for_system
                                evs = generate_signals_for_system(b.trading_system, limit_bars=1000) or []
                                cutoff = dj_tz.now() - timedelta(days=2)
                                for ev in evs:
                                    # Avoid bloating DB with very old events
                                    if getattr(ev, 'event_time', None) and ev.event_time < cutoff:
                                        continue
                                    # Idempotent insert
                                    for attempt in range(3):
                                        try:
                                            close_old_connections()
                                            with transaction.atomic():
                                                SignalEvent.objects.get_or_create(
                                                    trading_system=ev.trading_system,
                                                    timeframe=ev.timeframe,
                                                    level=getattr(ev, 'level', 1),
                                                    feed=getattr(ev, 'feed', None),
                                                    direction=ev.direction,
                                                    action=getattr(ev, 'action', 'OPEN'),
                                                    event_time=ev.event_time,
                                                    defaults={'rule_text': ev.rule_text, 'ind_values': getattr(ev, 'ind_values', None)},
                                                )
                                            break
                                        except OperationalError as oe:
                                            if 'locked' in str(oe).lower() and attempt < 2:
                                                time.sleep(0.1 * (attempt + 1))
                                                continue
                                            raise
                            except Exception:
                                continue
                    except Exception:
                        pass
            except Exception as e:
                status.last_error = str(e)
                continue

        # Save status with retry (avoids transient locking)
        status.files_scanned += scanned
        status.files_imported += imported
        status.rows_imported += rows
        status.last_run = now
        status.last_error = ''
        for attempt in range(3):
            try:
                close_old_connections()
                with transaction.atomic():
                    status.save()
                break
            except OperationalError as oe:
                if 'locked' in str(oe).lower() and attempt < 2:
                    time.sleep(0.1 * (attempt + 1))
                    continue
                raise


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
