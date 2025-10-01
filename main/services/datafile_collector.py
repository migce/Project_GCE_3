"""
Service for scanning a trading system data directory and syncing DataFile rows.
"""
import os
import glob
from datetime import datetime, timezone as dt_timezone
from typing import Tuple, List
from django.utils import timezone
from ..models import TradingSystem, TimeFrame, DataFile


def _parse_timeframe_from_filename(filename: str) -> str:
    """Extract timeframe code from filename like collector_SID_SYMBOL_TF.csv"""
    name = os.path.basename(filename)
    if not name.lower().endswith('.csv'):
        return ''
    base = name[:-4]  # strip .csv
    parts = base.split('_')
    if len(parts) < 4:
        return ''
    return parts[-1]


def collect_for_system(system: TradingSystem) -> Tuple[int, int, int]:
    """
    Scan system directory and upsert DataFile records.

    Returns: (created, updated, skipped)
    """
    created = updated = skipped = 0
    errors: List[str] = []
    data_dir = system.get_data_dir()
    pattern = os.path.join(data_dir, system.get_file_pattern())
    matches = []
    try:
        matches = glob.glob(pattern)
    except Exception:
        matches = []
    # Fallback: broad scan if pattern found nothing
    if not matches:
        prefix = f"collector_{system.system_sid}_{system.symbol}_"
        try:
            for name in os.listdir(data_dir):
                if name.lower().endswith('.csv') and name.startswith(prefix):
                    matches.append(os.path.join(data_dir, name))
        except Exception:
            pass

    for file_path in matches:
        try:
            stat = os.stat(file_path)
            filename = os.path.basename(file_path)
            tf_code = _parse_timeframe_from_filename(filename)

            timeframe = None
            if tf_code:
                timeframe = TimeFrame.objects.filter(trading_system=system, timeframe=tf_code).first()

            df, is_created = DataFile.objects.get_or_create(
                trading_system=system,
                filename=filename,
                defaults={
                    'file_path': file_path,
                    'file_size': stat.st_size,
                    'file_modified': datetime.fromtimestamp(stat.st_mtime, tz=dt_timezone.utc),
                    'status': 'pending',
                    'timeframe': timeframe,
                }
            )

            if is_created:
                created += 1
            else:
                has_changes = False
                if df.file_path != file_path:
                    df.file_path = file_path
                    has_changes = True
                if df.file_size != stat.st_size:
                    df.file_size = stat.st_size
                    has_changes = True
                new_mtime = datetime.fromtimestamp(stat.st_mtime, tz=dt_timezone.utc)
                if df.file_modified != new_mtime:
                    df.file_modified = new_mtime
                    has_changes = True
                if timeframe and df.timeframe_id != timeframe.id:
                    df.timeframe = timeframe
                    has_changes = True
                if has_changes:
                    # reset status to pending so downstream processing re-runs
                    df.status = 'pending'
                    df.save()
                    updated += 1
                else:
                    skipped += 1
        except Exception as e:
            errors.append(f"{os.path.basename(file_path)}: {e}")
            continue

    # expose errors for admin UI
    try:
        collect_for_system.last_errors = errors  # type: ignore[attr-defined]
    except Exception:
        pass

    return created, updated, skipped


def collect_for_timeframe(timeframe: TimeFrame) -> Tuple[int, int, int]:
    """
    Scan timeframe-specific file in its system directory and upsert DataFile.

    Returns: (created, updated, skipped)
    """
    system = timeframe.trading_system
    data_dir = system.get_data_dir() if hasattr(system, 'get_data_dir') else None
    if not data_dir:
        return 0, 0, 0

    pattern = os.path.join(data_dir, timeframe.get_filename_pattern())
    created = updated = skipped = 0

    for file_path in glob.glob(pattern):
        try:
            stat = os.stat(file_path)
            filename = os.path.basename(file_path)

            df, is_created = DataFile.objects.get_or_create(
                trading_system=system,
                timeframe=timeframe,
                filename=filename,
                defaults={
                    'file_path': file_path,
                    'file_size': stat.st_size,
                    'file_modified': datetime.fromtimestamp(stat.st_mtime, tz=dt_timezone.utc),
                    'status': 'pending',
                }
            )

            if is_created:
                created += 1
            else:
                has_changes = False
                if df.file_path != file_path:
                    df.file_path = file_path
                    has_changes = True
                if df.file_size != stat.st_size:
                    df.file_size = stat.st_size
                    has_changes = True
                new_mtime = datetime.fromtimestamp(stat.st_mtime, tz=dt_timezone.utc)
                if df.file_modified != new_mtime:
                    df.file_modified = new_mtime
                    has_changes = True
                if has_changes:
                    df.status = 'pending'
                    df.save()
                    updated += 1
                else:
                    skipped += 1
        except Exception:
            continue

    return created, updated, skipped
