"""
Collector for global feed files -> MarketDataFile rows, based on TF Bindings.

It scans the per-system data directory and matches TradeStation export files
using the legacy filename pattern but targets DataFeed via TF bindings:

  collector_{SYSTEM_SID}_{SYMBOL}_{TF}.csv

This allows us to populate MarketDataFile without relying on legacy DataFile.
"""
from __future__ import annotations

import os
import glob
from datetime import datetime, timezone as dt_timezone
from typing import Tuple

from ..models import TradingSystem, TradingSystemTFBinding, MarketDataFile, Instrument, TFCode, DataFeed
from django.conf import settings as django_settings


def collect_for_system(system: TradingSystem) -> Tuple[int, int, int]:
    created = updated = skipped = 0
    data_dir = system.get_data_dir() if hasattr(system, 'get_data_dir') else None
    if not data_dir:
        return 0, 0, 0

    bindings = list(TradingSystemTFBinding.objects.filter(trading_system=system).select_related('feed__tfcode'))
    if not bindings:
        return 0, 0, 0

    for b in bindings:
        tf_code = getattr(b.feed.tfcode, 'code', None) or 'M1'
        pattern = os.path.join(data_dir, f"collector_{system.system_sid}_{system.symbol}_{tf_code}.csv")
        for file_path in glob.glob(pattern):
            try:
                stat = os.stat(file_path)
                filename = os.path.basename(file_path)
                obj, was_created = MarketDataFile.objects.get_or_create(
                    provider='TS', filename=filename, feed=b.feed,
                    defaults={
                        'file_path': file_path,
                        'file_size': stat.st_size,
                        'file_modified': datetime.fromtimestamp(stat.st_mtime, tz=dt_timezone.utc),
                        'status': 'pending',
                    }
                )
                if was_created:
                    created += 1
                else:
                    changed = False
                    if obj.file_path != file_path:
                        obj.file_path = file_path
                        changed = True
                    if obj.file_size != stat.st_size:
                        obj.file_size = stat.st_size
                        changed = True
                    new_mtime = datetime.fromtimestamp(stat.st_mtime, tz=dt_timezone.utc)
                    if obj.file_modified != new_mtime:
                        obj.file_modified = new_mtime
                        changed = True
                    if changed:
                        obj.status = 'pending'
                        obj.save()
                        updated += 1
                    else:
                        skipped += 1
            except Exception:
                continue

    return created, updated, skipped


def _parse_symbol_tf(filename: str) -> Tuple[str | None, str | None]:
    """Parse symbol and TF code from filename like collector_ANY_SYMBOL_TF.csv.

    Accepts both 3- or 4-part names (collector_SID_SYMBOL_TF.csv or collector_SYMBOL_TF.csv).
    """
    name = os.path.basename(filename)
    if not name.lower().endswith('.csv'):
        return None, None
    base = name[:-4]
    parts = base.split('_')
    if len(parts) < 3:
        return None, None
    # Prefer last two parts as SYMBOL, TF
    symbol = parts[-2]
    tf_code = parts[-1]
    if not symbol or not tf_code:
        return None, None
    return symbol, tf_code


def collect_global_dir(base_dir: str | None = None) -> Tuple[int, int, int]:
    """Scan TS_EXPORTS_DIR (or provided base_dir) for collector files and upsert MarketDataFile rows.

    Does not require TradingSystem. Creates Instrument, TFCode and DataFeed lazily.
    Returns (created, updated, skipped).
    """
    created = updated = skipped = 0
    if not base_dir:
        base_dir = getattr(django_settings, 'TS_EXPORTS_DIR', r'C\\TS_EXPORTS')
    try:
        names = [os.path.join(base_dir, n) for n in os.listdir(base_dir) if n.lower().endswith('.csv') and n.lower().startswith('collector_')]
    except Exception:
        names = []
    for path in names:
        symbol, tf_code = _parse_symbol_tf(path)
        if not symbol or not tf_code:
            continue
        try:
            inst, _ = Instrument.objects.get_or_create(symbol=symbol)
            tf, _ = TFCode.objects.get_or_create(code=tf_code)
            feed, _ = DataFeed.objects.get_or_create(provider='TS', instrument=inst, tfcode=tf)
            stat = os.stat(path)
            mdf, was_created = MarketDataFile.objects.get_or_create(provider='TS', filename=os.path.basename(path), feed=feed,
                                                                    defaults={
                                                                        'file_path': path,
                                                                        'file_size': stat.st_size,
                                                                        'file_modified': datetime.fromtimestamp(stat.st_mtime, tz=dt_timezone.utc),
                                                                        'status': 'pending',
                                                                    })
            if was_created:
                created += 1
            else:
                changed = False
                if mdf.file_path != path:
                    mdf.file_path = path; changed = True
                if mdf.file_size != stat.st_size:
                    mdf.file_size = stat.st_size; changed = True
                new_mtime = datetime.fromtimestamp(stat.st_mtime, tz=dt_timezone.utc)
                if mdf.file_modified != new_mtime:
                    mdf.file_modified = new_mtime; changed = True
                if changed:
                    mdf.status = 'pending'
                    mdf.save()
                    updated += 1
                else:
                    skipped += 1
        except Exception:
            continue
    return created, updated, skipped
