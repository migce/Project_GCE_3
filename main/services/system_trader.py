"""
Background worker that executes trades in MT5 for enabled TradingSystem
based on SignalEvent stream (OPEN/CLOSE actions).
"""
from __future__ import annotations

import threading
import time
from typing import Optional
from django.utils import timezone
from django.conf import settings as django_settings

from ..models import TradingSystem, SignalEvent
from ..models import SignalExecutionLog
from .mt5_service import MT5Manager


class SystemTrader:
    def __init__(self, interval_seconds: int = 3):
        self._active = False
        self._thread: Optional[threading.Thread] = None
        self._interval = max(1, int(interval_seconds))

    def start(self):
        if self._thread is None or not self._thread.is_alive():
            self._active = True
            self._thread = threading.Thread(target=self._loop, name='SystemTrader', daemon=True)
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
            time.sleep(self._interval)

    def _tick(self):
        # Get enabled systems
        systems = list(TradingSystem.objects.filter(is_active=True, trading_enabled=True))
        if not systems:
            return
        # Use default MT5 service
        service = MT5Manager.get_default_service()
        if not service:
            return
        with service as svc:
            if not svc.is_connected:
                return
            now = timezone.now()
            max_age_sec = int(getattr(django_settings, 'SYSTEM_TRADER_MAX_SIGNAL_AGE_SECONDS', 120))
            for sys in systems:
                # Execute only fresh signals to avoid backfilling upon enabling trading
                since_cfg = now - timezone.timedelta(seconds=max(10, max_age_sec))
                # When trading has just been enabled, ignore all older signals
                try:
                    since_enabled = getattr(sys, 'updated_at', None) or since_cfg
                    if since_enabled and since_enabled > since_cfg:
                        since = since_enabled
                    else:
                        since = since_cfg
                except Exception:
                    since = since_cfg
                sigs = SignalEvent.objects.filter(
                    trading_system=sys, event_time__gte=since
                ).order_by('event_time', 'action')[:200]
                for s in sigs:
                    if SignalExecutionLog.objects.filter(signal=s).exists():
                        continue
                    self._execute_signal(svc, sys, s)

    def _execute_signal(self, svc, sys: TradingSystem, sig: SignalEvent):
        ok = False
        msg = ''
        try:
            symbol = sys.symbol or 'EURUSD'
            lot = float(sys.lot_size or 0.01)
            magic = getattr(sys, 'magic_number', None)
            if sig.action == 'OPEN':
                # Stop & Reverse behavior (optional)
                sar = getattr(sys, 'is_sar', True)
                allow_multi = bool(getattr(sys, 'multiple_positions', False))
                max_side = int(getattr(sys, 'max_positions_per_side', 5) or 5)
                if sig.direction == 'BUY':
                    if sar:
                        self._close_side(svc, sys, 'SELL')
                    # In non-SAR mode, do not auto-close opposite; skip OPEN if opposite exists
                    if (not sar) and self._has_side(svc, sys, 'SELL'):
                        ok = True
                        msg = 'SELL open, skip BUY (non-SAR)'
                    else:
                        # Check current BUY count
                        cnt = self._side_count(svc, sys, 'BUY')
                        if cnt > 0 and not allow_multi:
                            ok = True
                            msg = 'BUY already open, skipped (single-position mode)'
                        elif allow_multi and cnt >= max_side:
                            ok = True
                            msg = f'BUY side at limit {max_side}, skipped'
                        else:
                            res = svc.market_buy(symbol, lot, magic=magic, comment=f'{sys.system_sid} BUY')
                            ok = bool(res.get('success'))
                            msg = res.get('message', '')
                else:
                    if sar:
                        self._close_side(svc, sys, 'BUY')
                    if (not sar) and self._has_side(svc, sys, 'BUY'):
                        ok = True
                        msg = 'BUY open, skip SELL (non-SAR)'
                    else:
                        cnt = self._side_count(svc, sys, 'SELL')
                        if cnt > 0 and not allow_multi:
                            ok = True
                            msg = 'SELL already open, skipped (single-position mode)'
                        elif allow_multi and cnt >= max_side:
                            ok = True
                            msg = f'SELL side at limit {max_side}, skipped'
                        else:
                            res = svc.market_sell(symbol, lot, magic=magic, comment=f'{sys.system_sid} SELL')
                            ok = bool(res.get('success'))
                            msg = res.get('message', '')
            else:  # CLOSE
                side = 'BUY' if sig.direction == 'BUY' else 'SELL'
                ok = self._close_side(svc, sys, side)
                msg = 'Closed' if ok else 'Close errors'
        except Exception as e:
            ok = False
            msg = str(e)
        finally:
            SignalExecutionLog.objects.create(signal=sig, success=ok, message=msg)

    def _has_side(self, svc, sys: TradingSystem, side: str) -> bool:
        positions = svc.get_open_positions_for(symbol=sys.symbol, magic=getattr(sys, 'magic_number', None))
        return any(p.get('type') == side for p in positions)

    def _side_count(self, svc, sys: TradingSystem, side: str) -> int:
        positions = svc.get_open_positions_for(symbol=sys.symbol, magic=getattr(sys, 'magic_number', None))
        return sum(1 for p in positions if p.get('type') == side)

    def _close_side(self, svc, sys: TradingSystem, side: str, retries: int = 3) -> bool:
        symbol = sys.symbol or 'EURUSD'
        magic = getattr(sys, 'magic_number', None)
        for attempt in range(max(1, retries)):
            positions = svc.get_open_positions_for(symbol=symbol, magic=magic)
            tickets = [p['ticket'] for p in positions if p.get('type') == side]
            if not tickets:
                return True
            all_ok = True
            for t in tickets:
                res = svc.close_position(int(t))
                if not res.get('success'):
                    all_ok = False
            if all_ok:
                verify = svc.get_open_positions_for(symbol=symbol, magic=magic)
                if not any(p.get('type') == side for p in verify):
                    return True
            time.sleep(0.3)
        return False


_trader: Optional[SystemTrader] = None


def get_trader() -> SystemTrader:
    global _trader
    if _trader is None:
        _trader = SystemTrader()
    return _trader


def start_trader():
    get_trader().start()


def stop_trader():
    get_trader().stop()
