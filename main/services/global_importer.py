from __future__ import annotations

import csv
from dataclasses import dataclass
import io
from datetime import timezone as dt_timezone
from typing import List, Dict

from django.db import transaction, IntegrityError
from django.utils import timezone as dj_tz
from django.utils import timezone

from ..models import MarketDataFile, MarketBar, MarketIndicatorDef, MarketIndicatorValue, MarketImportError
from decimal import Decimal, InvalidOperation
from datetime import datetime

def _parse_local_datetime(date_str: str, time_str: str) -> datetime:
    date_str = (date_str or '').strip()
    time_str = (time_str or '').strip()
    if not date_str or not time_str:
        raise ValueError('Empty date/time')
    if len(date_str) == 8:
        dt_date = datetime.strptime(date_str, '%Y%m%d')
    elif len(date_str) == 6:
        dt_date = datetime.strptime(date_str, '%y%m%d')
    elif len(date_str) == 7 and date_str.isdigit():
        dt_date = datetime.strptime(date_str[-6:], '%y%m%d')
    else:
        dt_date = datetime.strptime(date_str, '%Y-%m-%d')
    t = ''.join(ch for ch in time_str if ch.isdigit())
    if 1 <= len(t) <= 4:
        t = t.zfill(4)
        hh = int(t[:2]); mm = int(t[2:])
        if hh > 23: hh = hh % 24
        if mm > 59: mm = mm % 60
    else:
        hhmm = datetime.strptime(time_str, '%H:%M')
        hh, mm = hhmm.hour, hhmm.minute
    return dt_date.replace(hour=hh, minute=mm, second=0, microsecond=0)

def _to_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    s = str(value).strip().replace(' ', '').replace(',', '.')
    if not s:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None

def _to_int(val: str | None) -> int | None:
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


@dataclass
class ImportResult:
    bars_created: int = 0
    indicator_values_created: int = 0
    rows_read: int = 0
    rows_skipped: int = 0
    parse_errors: int = 0


def import_market_datafile(mdf: MarketDataFile) -> ImportResult:
    feed = mdf.feed
    result = ImportResult()
    error_entries = []  # type: List[MarketImportError]
    top_level_error = None

    delimiter = ','
    try:
        with open(mdf.file_path, 'r', encoding='utf-8-sig') as f:
            sample = f.read(1024)
            f.seek(0)
            try:
                delimiter = csv.Sniffer().sniff(sample).delimiter
            except Exception:
                delimiter = ','

            # Read full content to avoid depending on file handle beyond this block
            content = f.read()

        # Choose delimiter robustly using the header line
        header_line = (content.splitlines()[0] if content else '')
        def _choose_delim(line: str, preferred: str) -> str:
            cands = [preferred, ',', ';', '\t', '|']
            best = preferred
            best_score = -1
            for d in cands:
                parts = [p.strip() for p in line.split(d)] if d else [line]
                lower_parts = [p.lower() for p in parts]
                has_core = all(x in lower_parts for x in ('bar_date','bar_time_hhmm','o','h','l','c'))
                score = (1 if has_core else 0) * 1000 + len(parts)
                if score > best_score:
                    best_score = score
                    best = d
            return best

        delimiter = _choose_delim(header_line, delimiter)
        reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)

        # Normalize headers by stripping whitespace for indicator discovery
        original_headers = list(reader.fieldnames or [])
        headers = [h.strip() for h in original_headers]
        lower = [h.lower() for h in headers]

        # Validate core columns
        required = {'bar_date','bar_time_hhmm','o','h','l','c'}
        if not required.issubset(set(lower)):
            # Log header error and abort early
            error_entries.append(MarketImportError(data_file=mdf, row_number=None, column='', message=f'Header missing required columns (detected delimiter="{delimiter}"): {headers}'))
            top_level_error = top_level_error or Exception('Header missing required columns')
            raise top_level_error

        def idx(name: str) -> int:
            try:
                return lower.index(name.lower())
            except ValueError:
                return -1

        # Indicator columns start strictly after 'c'
        c_idx = idx('c')
        tail = headers[c_idx + 1:] if c_idx >= 0 else headers
        indicator_cols = [h for h in tail if h and h.lower() not in {'symbol','timeframe','bar_date','bar_time_hhmm','tz_offset_min','systemsid','tf_level','o','h','l','c','volume'}]

        # Build a map from normalized (stripped/lower) header -> original key used by DictReader rows.
        header_key_map: Dict[str, str] = {}
        for orig in original_headers:
            if orig is None:
                continue
            s = orig.strip()
            if s:
                header_key_map[s] = orig
                header_key_map[s.lower()] = orig

        # Ensure indicator defs for this feed
        existing = {d.name: d for d in MarketIndicatorDef.objects.filter(feed=feed, name__in=indicator_cols)}
        to_create = [MarketIndicatorDef(feed=feed, name=n, dtype='numeric') for n in indicator_cols if n not in existing]
        if to_create:
            MarketIndicatorDef.objects.bulk_create(to_create, ignore_conflicts=True)
            existing.update({d.name: d for d in MarketIndicatorDef.objects.filter(feed=feed, name__in=indicator_cols)})

        bars_batch: List[MarketBar] = []
        # Keep parsed dt with row to avoid any mismatch on reparse
        rows_batch: List[tuple[datetime, Dict[str, str]]] = []
        batch_size = 2000

        # Remove previous bars produced from this file
        try:
            with transaction.atomic():
                MarketBar.objects.filter(feed=feed, dt__in=[])
        except Exception:
            pass

        for i, row in enumerate(reader, start=2):
            def g(key: str) -> str | None:
                for k in (key, key.upper(), key.capitalize()):
                    if k in row:
                        return row[k]
                return row.get(key) or row.get(key.lower())

            try:
                bar_date = (g('bar_date') or '').strip()
                bar_time = (g('bar_time_hhmm') or '').strip()
                if not bar_date or not bar_time:
                    result.rows_skipped += 1
                    continue
                local_dt = _parse_local_datetime(bar_date, bar_time)
                # Source timestamps are in server local time (Europe/Moscow).
                # Make them aware in current Django timezone so that display matches source.
                dt_val = timezone.make_aware(local_dt, timezone.get_current_timezone())
            except Exception as e:
                result.parse_errors += 1
                result.rows_skipped += 1
                # Log malformed date/time row
                if len(error_entries) < 200:
                    error_entries.append(MarketImportError(data_file=mdf, row_number=i, column='bar_date/bar_time_hhmm', message=f'Date/time parse error: {e}'))
                continue

            o = _to_decimal(g('o'))
            h = _to_decimal(g('h'))
            l = _to_decimal(g('l'))
            c = _to_decimal(g('c'))
            if o is None or h is None or l is None or c is None:
                result.rows_skipped += 1
                if len(error_entries) < 200:
                    miss = ','.join(x for x,v in [('o',o),('h',h),('l',l),('c',c)] if v is None)
                    error_entries.append(MarketImportError(data_file=mdf, row_number=i, column=miss, message='Missing OHLC value(s)'))
                continue

            bars_batch.append(MarketBar(feed=feed, dt=dt_val, dt_server=dt_val, open=o, high=h, low=l, close=c, volume=None))
            rows_batch.append((dt_val, row))
            result.rows_read += 1

            if len(bars_batch) >= batch_size:
                _flush_batches(feed, bars_batch, rows_batch, existing, indicator_cols, header_key_map, result, mdf, error_entries)

        # Flush tail after loop
        if bars_batch:
            _flush_batches(feed, bars_batch, rows_batch, existing, indicator_cols, header_key_map, result, mdf, error_entries)

    except Exception as e:
        top_level_error = e
        # Capture unexpected importer failure
        error_entries.append(MarketImportError(data_file=mdf, row_number=None, column='', message=f'Importer error: {e}'))

    with transaction.atomic():
        # Save accumulated errors (cap to 200 per file)
        if error_entries:
            MarketImportError.objects.bulk_create(error_entries[:200], batch_size=200)
        # Set status
        if top_level_error is not None:
            mdf.status = 'error'
        else:
            mdf.status = 'completed' if result.rows_read > 0 or result.indicator_values_created > 0 else ('error' if result.parse_errors > 0 else 'completed')
        mdf.processed_at = timezone.now()
        mdf.save(update_fields=['status', 'processed_at'])

    return result


def _flush_batches(feed, bars_batch, rows_batch, defs_map, indicator_cols, header_key_map, result: ImportResult, mdf: MarketDataFile, error_entries: List[MarketImportError]):
    with transaction.atomic():
        MarketBar.objects.bulk_create(bars_batch, batch_size=2000, ignore_conflicts=True)
        result.bars_created += len(bars_batch)
        # Query back existing/new bars; Django returns aware datetimes in UTC when USE_TZ=True.
        dts = [b.dt for b in bars_batch]
        qs_bars = MarketBar.objects.filter(feed=feed, dt__in=dts)
        def _key_utc(dt):
            try:
                return dj_tz.make_naive(dt, dj_tz.utc)
            except Exception:
                return dt
        bar_map = {_key_utc(b.dt): b for b in qs_bars}
        ivs: List[MarketIndicatorValue] = []
        for dt_val, row in rows_batch:
            # Normalize lookup key to UTC-naive to align with DB-returned values
            mb = bar_map.get(_key_utc(dt_val))
            if not mb:
                continue
            for col in indicator_cols:
                # Resolve the exact row key from normalized header name to handle trailing spaces/case
                key = header_key_map.get(col) or header_key_map.get(col.lower()) or col
                raw = row.get(key)
                ival = _to_int(raw)
                if ival is None:
                    # Log non-empty invalid values once in a while (cap overall per file)
                    try:
                        s = ('' if raw is None else str(raw).strip())
                        if s and len(error_entries) < 200:
                            error_entries.append(MarketImportError(data_file=mdf, row_number=None, column=col, message=f'Invalid indicator value: {s}'))
                    except Exception:
                        pass
                    continue
                ind = defs_map.get(col)
                if not ind:
                    continue
                ivs.append(MarketIndicatorValue(bar=mb, indicator=ind, value_int=ival))
        if ivs:
            try:
                MarketIndicatorValue.objects.bulk_create(ivs, batch_size=5000, ignore_conflicts=True)
                result.indicator_values_created += len(ivs)
            except IntegrityError as e:
                # Surface a clear error for admin with likely cause
                msg = str(e)
                cause = 'bar_id' if 'bar_id' in msg.lower() else ('indicator_id' if 'indicator_id' in msg.lower() else 'unknown')
                hint = f'Possible missing {cause} for some rows (timezone mismatch or missing indicator def).'
                if len(error_entries) < 200:
                    error_entries.append(MarketImportError(data_file=mdf, row_number=None, column=cause, message=f'FK error while saving indicator values: {msg}. {hint}'))
                raise
    bars_batch.clear()
    rows_batch.clear()
