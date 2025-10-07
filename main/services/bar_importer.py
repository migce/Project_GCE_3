from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Tuple, Optional

from django.db import transaction
from django.utils import timezone

from ..models import (
    TradingSystem,
    TimeFrame,
    DataFile,
    Bar,
    IndicatorDefinition,
    IndicatorValue,
)
from ..models import (
    Instrument,
    TFCode,
    DataFeed,
    MarketBar,
    MarketIndicatorDef,
    MarketIndicatorValue,
)


@dataclass
class ImportResult:
    bars_created: int = 0
    indicators_created: int = 0
    indicator_values_created: int = 0
    rows_read: int = 0
    rows_skipped: int = 0
    parse_errors: int = 0


KNOWN_BASE_COLUMNS = {
    'symbol', 'timeframe', 'bar_date', 'bar_time_hhmm', 'tz_offset_min',
    'systemsid', 'tf_level', 'o', 'h', 'l', 'c', 'volume'
}


def _parse_local_datetime(date_str: str, time_str: str) -> datetime:
    date_str = (date_str or '').strip()
    time_str = (time_str or '').strip()
    if not date_str or not time_str:
        raise ValueError('Empty date/time')

    # Date: support a few formats
    #  - YYYYMMDD (8)
    #  - YYMMDD (6)
    #  - 1YYMMDD (7) — seen in exports, interpret as YYMMDD
    if len(date_str) == 8:
        dt_date = datetime.strptime(date_str, '%Y%m%d')
    elif len(date_str) == 6:
        dt_date = datetime.strptime(date_str, '%y%m%d')
    elif len(date_str) == 7 and date_str.isdigit():
        dt_date = datetime.strptime(date_str[-6:], '%y%m%d')
    else:
        # Fallback: try locale‑independent
        dt_date = datetime.strptime(date_str, '%Y-%m-%d')

    # Time: support 1–4 digit HHMM without delimiter, pad on the left
    t = ''.join(ch for ch in time_str if ch.isdigit())
    if 1 <= len(t) <= 4:
        t = t.zfill(4)  # e.g., '149' -> '0149'
        hh = int(t[:2])
        mm = int(t[2:])
        # clamp out-of-range minutes/hours defensively
        if hh > 23:
            hh = hh % 24
        if mm > 59:
            mm = mm % 60
    else:
        # fallback to HH:MM
        hhmm = datetime.strptime(time_str, '%H:%M')
        hh, mm = hhmm.hour, hhmm.minute

    # Local/server datetime as provided in CSV (no offset adjustment here)
    local_dt = dt_date.replace(hour=hh, minute=mm, second=0, microsecond=0)
    return local_dt


def _to_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    # Replace comma decimal separator if present
    s = s.replace(' ', '').replace(',', '.')
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _to_int(val: Optional[str]) -> Optional[int]:
    if val is None:
        return None
    s = str(val).strip()
    if s == '':
        return None
    low = s.lower()
    if low in ('true', 'false'):
        return 1 if low == 'true' else 0
    try:
        return int(s)
    except Exception:
        pass
    d = _to_decimal(s)
    if d is None:
        return None
    try:
        return int(d)
    except Exception:
        return None


def import_datafile(data_file: DataFile) -> ImportResult:
    system: TradingSystem = data_file.trading_system
    timeframe: TimeFrame | None = data_file.timeframe

    # Try to infer timeframe from filename if missing
    if timeframe is None:
        try:
            tf_code = data_file.filename.rsplit('.', 1)[0].split('_')[-1]
            timeframe = TimeFrame.objects.filter(trading_system=system, timeframe=tf_code).first()
        except Exception:
            timeframe = None
    if timeframe is None:
        raise ValueError('Timeframe not set and cannot be inferred from filename')

    delimiter = ','
    with open(data_file.file_path, 'r', encoding='utf-8-sig') as f:
        sample = f.read(1024)
        f.seek(0)
        try:
            delimiter = csv.Sniffer().sniff(sample).delimiter
        except Exception:
            delimiter = ','

        reader = csv.DictReader(f, delimiter=delimiter)
        # Normalize headers and detect indicator columns strictly by position:
        # take only columns AFTER the base price columns (o,h,l,c). Volume does not affect the split.
        headers = [h.strip() for h in reader.fieldnames or []]
        lower = [h.lower() for h in headers]

        def _idx(name: str) -> int:
            try:
                return lower.index(name.lower())
            except ValueError:
                return -1

        # Prefer index of 'c' if present; otherwise fallback to max of o/h/l/c found
        idx_c = _idx('c')
        if idx_c >= 0:
            last_base_idx = idx_c
        else:
            last_base_idx = max(_idx('o'), _idx('h'), _idx('l'))
        if last_base_idx >= 0 and last_base_idx + 1 < len(headers):
            tail = headers[last_base_idx + 1 :]
            # Even in the tail, guard against reserved/base names accidentally placed later
            indicator_cols = [h for h in tail if h and h.lower() not in KNOWN_BASE_COLUMNS]
        else:
            # Fallback to old behavior if base columns are not detected
            indicator_cols = [h for h in headers if h.lower() not in KNOWN_BASE_COLUMNS]

        # Ensure indicators exist
        existing_defs = {
            d.name: d for d in IndicatorDefinition.objects.filter(trading_system=system, name__in=indicator_cols)
        }
        to_create = [IndicatorDefinition(trading_system=system, name=name, dtype='numeric')
                     for name in indicator_cols if name not in existing_defs]
        if to_create:
            IndicatorDefinition.objects.bulk_create(to_create, ignore_conflicts=True)
            existing_defs.update({d.name: d for d in IndicatorDefinition.objects.filter(trading_system=system, name__in=indicator_cols)})

        result = ImportResult()

        # Remove previous bars produced from this file in a short transaction
        try:
            with transaction.atomic():
                Bar.objects.filter(data_file=data_file).delete()
        except Exception:
            Bar.objects.filter(data_file=data_file).delete()

        bar_buffer: List[Bar] = []
        rows_buffer: List[Dict[str, str]] = []
        iv_buffer: List[IndicatorValue] = []
        batch_size = 2000

        for i, row in enumerate(reader, start=2):
                # Parse base fields (case-insensitive keys)
                def g(key: str) -> str | None:
                    for k in (key, key.upper(), key.capitalize()):
                        if k in row:
                            return row[k]
                    # fallback by lowercasing all keys
                    return row.get(key) or row.get(key.lower())

                try:
                    # Validate presence of mandatory fields
                    bar_date = (g('bar_date') or '').strip()
                    bar_time = (g('bar_time_hhmm') or '').strip()
                    if not bar_date or not bar_time:
                        result.rows_skipped += 1
                        continue

                    # Parse local/server datetime first (CSV already aligned to MT server time)
                    local_dt = _parse_local_datetime(bar_date, bar_time)
                    # Take time as-is from CSV (no auto UTC shifting); store aware-as-UTC to keep Django happy
                    dt_val = timezone.make_aware(local_dt, dt_timezone.utc)
                except Exception:
                    result.parse_errors += 1
                    result.rows_skipped += 1
                    continue

                # Parse OHLC and ensure they are all present (skip incomplete rows)
                o = _to_decimal(g('o'))
                h = _to_decimal(g('h'))
                l = _to_decimal(g('l'))
                c = _to_decimal(g('c'))
                if o is None or h is None or l is None or c is None:
                    # Incomplete bar row; likely partially written or malformed line
                    result.rows_skipped += 1
                    continue

                b = Bar(
                    trading_system=system,
                    timeframe=timeframe,
                    data_file=data_file,
                    dt=dt_val,
                    dt_server=dt_val,
                    open=o,
                    high=h,
                    low=l,
                    close=c,
                    volume=None,
                    symbol=g('symbol') or system.symbol,
                    source_row=i,
                )
                bar_buffer.append(b)
                rows_buffer.append(row)
                result.rows_read += 1

                if len(bar_buffer) >= batch_size:
                    # Commit batch in its own short transaction to avoid long DB locks
                    with transaction.atomic():
                        Bar.objects.bulk_create(bar_buffer, batch_size=batch_size)
                        result.bars_created += len(bar_buffer)
                        # Query back bars to ensure PKs across backends
                        dts = [b.dt for b in bar_buffer]
                        bar_map = {b.dt: b for b in Bar.objects.filter(timeframe=timeframe, dt__in=dts)}
                        for row_buf in rows_buffer:
                            try:
                                local_dt = _parse_local_datetime(
                                    (row_buf.get('bar_date') or row_buf.get('BAR_DATE') or ''),
                                    (row_buf.get('bar_time_hhmm') or row_buf.get('BAR_TIME_HHMM') or '')
                                )
                                dt_val = timezone.make_aware(local_dt, dt_timezone.utc)
                            except Exception:
                                continue
                            bar = bar_map.get(dt_val)
                            if not bar:
                                continue
                            for col in indicator_cols:
                                val = row_buf.get(col)
                                ival = _to_int(val)
                                if ival is None:
                                    continue
                                ind = existing_defs[col]
                                # Ignore TF_Level from CSV; always bind to the timeframe level
                                iv_buffer.append(IndicatorValue(
                                    bar=bar,
                                    indicator=ind,
                                    value_int=ival,
                                    tf_level=int(timeframe.level or 0)
                                ))
                    if iv_buffer:
                        IndicatorValue.objects.bulk_create(iv_buffer, batch_size=batch_size)
                        result.indicator_values_created += len(iv_buffer)
                        iv_buffer.clear()
                    # Dual-write this batch to global feed layer (optional)
                    try:
                        from django.conf import settings as django_settings
                        dual = getattr(django_settings, 'DUAL_WRITE_GLOBAL_FEED', True)
                    except Exception:
                        dual = True
                    if dual:
                        try:
                            _dual_write_global_feed(system, timeframe, bar_buffer, rows_buffer, indicator_cols)
                        except Exception:
                            pass
                    # clear buffers only when we actually flushed a full batch
                    bar_buffer.clear()
                    rows_buffer.clear()

        if bar_buffer:
            with transaction.atomic():
                Bar.objects.bulk_create(bar_buffer, batch_size=batch_size)
                result.bars_created += len(bar_buffer)
                dts = [b.dt for b in bar_buffer]
                bar_map = {b.dt: b for b in Bar.objects.filter(timeframe=timeframe, dt__in=dts)}
                for row_buf in rows_buffer:
                    try:
                        local_dt = _parse_local_datetime(
                            (row_buf.get('bar_date') or row_buf.get('BAR_DATE') or ''),
                            (row_buf.get('bar_time_hhmm') or row_buf.get('BAR_TIME_HHMM') or '')
                        )
                        dt_val = timezone.make_aware(local_dt, dt_timezone.utc)
                    except Exception:
                        continue
                    bar = bar_map.get(dt_val)
                    if not bar:
                        continue
                    for col in indicator_cols:
                        val = row_buf.get(col)
                        ival = _to_int(val)
                        if ival is None:
                            continue
                        ind = existing_defs[col]
                        # Ignore TF_Level from CSV; always bind to the timeframe level
                        iv_buffer.append(IndicatorValue(
                            bar=bar,
                            indicator=ind,
                            value_int=ival,
                            tf_level=int(timeframe.level or 0)
                        ))
                if iv_buffer:
                    IndicatorValue.objects.bulk_create(iv_buffer, batch_size=batch_size)
                    result.indicator_values_created += len(iv_buffer)

        # Dual-write to global feed layer (optional)
        try:
            from django.conf import settings as django_settings
            dual = getattr(django_settings, 'DUAL_WRITE_GLOBAL_FEED', True)
        except Exception:
            dual = True

        if dual:
            try:
                _dual_write_global_feed(system, timeframe, bar_buffer, rows_buffer, indicator_cols)
            except Exception:
                # Do not fail legacy import on dual write issues
                pass

        # finalize DataFile status in its own short transaction
        with transaction.atomic():
            data_file.status = 'completed'
            data_file.rows_processed = result.rows_read
            data_file.processed_at = timezone.now()
            data_file.save(update_fields=['status', 'rows_processed', 'processed_at'])

    return result


# -----------------------------
# Global feed dual-write helpers
# -----------------------------

def _tf_minutes(code: str) -> int:
    m = {
        'M1': 1, 'M2': 2, 'M5': 5, 'M15': 15, 'M30': 30,
        'H1': 60, 'H4': 240, 'D1': 1440, 'W1': 10080, 'MN1': 43200,
    }
    return m.get(code.upper(), 1)


def _get_feed(symbol: str, tf_code: str, provider: str = 'TS') -> DataFeed:
    inst, _ = Instrument.objects.get_or_create(symbol=symbol)
    tf, _ = TFCode.objects.get_or_create(code=tf_code, defaults={'minutes': _tf_minutes(tf_code)})
    feed, _ = DataFeed.objects.get_or_create(provider=provider, instrument=inst, tfcode=tf)
    return feed


def _ensure_global_indicator_defs(feed: DataFeed, names: list[str]) -> dict[str, MarketIndicatorDef]:
    existing = {d.name: d for d in MarketIndicatorDef.objects.filter(feed=feed, name__in=names)}
    to_create = [MarketIndicatorDef(feed=feed, name=n, dtype='numeric') for n in names if n not in existing]
    if to_create:
        MarketIndicatorDef.objects.bulk_create(to_create, ignore_conflicts=True)
        existing.update({d.name: d for d in MarketIndicatorDef.objects.filter(feed=feed, name__in=names)})
    return existing


def _dual_write_global_feed(system: TradingSystem, timeframe: TimeFrame, bar_buffer: list[Bar], rows_buffer: list[dict[str, str]], indicator_cols: list[str]) -> None:
    # Resolve feed by system symbol and timeframe code
    symbol = (system.symbol or 'EURUSD') if hasattr(system, 'symbol') else 'EURUSD'
    tf_code = timeframe.timeframe if hasattr(timeframe, 'timeframe') else 'M1'
    feed = _get_feed(symbol, tf_code)

    # Build MarketBar batch
    mb_batch: list[MarketBar] = []
    for b in bar_buffer:
        mb_batch.append(MarketBar(
            feed=feed,
            dt=b.dt,
            dt_server=getattr(b, 'dt_server', None),
            open=b.open,
            high=b.high,
            low=b.low,
            close=b.close,
            volume=b.volume if hasattr(b, 'volume') else None,
        ))

    if mb_batch:
        MarketBar.objects.bulk_create(mb_batch, ignore_conflicts=True, batch_size=2000)

    # Map dt -> MarketBar for indicator linking
    dts = [b.dt for b in bar_buffer]
    bar_map = {b.dt: b for b in MarketBar.objects.filter(feed=feed, dt__in=dts)}

    # Ensure indicator defs
    defs = _ensure_global_indicator_defs(feed, indicator_cols)

    # Build indicator values
    iv_batch: list[MarketIndicatorValue] = []
    for row in rows_buffer:
        try:
            local_dt = _parse_local_datetime(
                (row.get('bar_date') or row.get('BAR_DATE') or ''),
                (row.get('bar_time_hhmm') or row.get('BAR_TIME_HHMM') or '')
            )
            dt_val = timezone.make_aware(local_dt, dt_timezone.utc)
        except Exception:
            continue
        bar = bar_map.get(dt_val)
        if not bar:
            continue
        for col in indicator_cols:
            ival = _to_int(row.get(col))
            if ival is None:
                continue
            ind = defs.get(col)
            if not ind:
                continue
            iv_batch.append(MarketIndicatorValue(bar=bar, indicator=ind, value_int=ival))

    if iv_batch:
        MarketIndicatorValue.objects.bulk_create(iv_batch, ignore_conflicts=True, batch_size=2000)





