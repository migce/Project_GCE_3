import asyncio
import json
from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .services.mt5_service import MT5Manager


def _normalize_positions(rows):
    out = []
    for p in rows or []:
        q = dict(p)
        t = q.get('time')
        try:
            if hasattr(t, 'strftime'):
                q['time'] = t.strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            pass
        out.append(q)
    return out


class Mt5OpenPositionsConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        await self.accept()
        # background task for periodic snapshots
        self._running = True
        # keep a persistent MT5 connection per WS
        self._svc = await sync_to_async(MT5Manager.get_default_service, thread_sensitive=True)()
        # Cache symbols list from DB
        try:
            from .models import TradingSystem
            self._symbols = await sync_to_async(lambda: list(TradingSystem.objects.values_list('symbol', flat=True).distinct()))()
        except Exception:
            self._symbols = []
        self._task = asyncio.create_task(self._loop())

    async def disconnect(self, close_code):
        self._running = False
        try:
            if hasattr(self, '_task'):
                self._task.cancel()
            # Gracefully close MT5 connection
            if getattr(self, '_svc', None):
                try:
                    await sync_to_async(self._svc.disconnect, thread_sensitive=True)()
                except Exception:
                    pass
        except Exception:
            pass

    async def _loop(self):
        try:
            while self._running:
                data = await self._snapshot_once()
                try:
                    await self.send_json(data)
                except Exception:
                    break
                await asyncio.sleep(2)
        except asyncio.CancelledError:
            pass

    async def _snapshot_once(self):
        try:
            if not getattr(self, '_svc', None):
                return {'success': False, 'message': 'Service not initialized'}
            # ensure connected; connect only if needed to avoid churn
            if not self._svc.is_connected:
                ok = await sync_to_async(self._svc.connect, thread_sensitive=True)()
                if not ok:
                    return {'success': False, 'message': 'Failed to connect to MT5'}
            rows = await sync_to_async(self._svc.get_open_positions, thread_sensitive=True)()
            quotes = []
            # fetch quotes for symbols
            try:
                import MetaTrader5 as mt5  # type: ignore
            except Exception:
                mt5 = None
            for sym in (self._symbols or []):
                try:
                    if hasattr(self._svc, 'get_symbol_bid'):
                        bid = await sync_to_async(self._svc.get_symbol_bid, thread_sensitive=True)(sym)
                    else:
                        # fallback path
                        name = (sym or '').strip()
                        if hasattr(self._svc, '_ensure_symbol'):
                            try:
                                resolved = await sync_to_async(self._svc._ensure_symbol, thread_sensitive=True)(name)
                                if resolved:
                                    name = resolved
                            except Exception:
                                pass
                        tick = await sync_to_async(self._svc._get_tick, thread_sensitive=True)(name) if hasattr(self._svc, '_get_tick') else (mt5.symbol_info_tick(name) if mt5 else None)
                        bid = float(getattr(tick, 'bid', 0) or 0) if tick else None
                        if (bid is None or bid == 0) and mt5:
                            try:
                                b2 = mt5.symbol_info_double(name, getattr(mt5, 'SYMBOL_BID', 1))
                                if b2:
                                    bid = float(b2)
                            except Exception:
                                pass
                except Exception:
                    bid = None
                quotes.append({'symbol': sym, 'bid': bid})
            return {
                'success': True,
                'positions': await sync_to_async(_normalize_positions, thread_sensitive=False)(rows),
                'quotes': quotes,
            }
        except Exception as e:
            return {'success': False, 'message': str(e)}
