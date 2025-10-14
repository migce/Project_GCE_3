"""
Сервис для работы с MetaTrader 5
"""
import MetaTrader5 as mt5
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from ..models import MT5ConnectionSettings, MT5ConnectionLog

logger = logging.getLogger(__name__)


class MT5Service:
    """Сервис для подключения и работы с MetaTrader 5"""
    
    def __init__(self, settings: Optional[MT5ConnectionSettings] = None):
        """
        Инициализация сервиса
        
        Args:
            settings: Настройки подключения. Если не указаны, используются настройки по умолчанию
        """
        self.settings = settings or MT5ConnectionSettings.get_default_settings()
        self.is_connected = False
        self._filling_cache: Dict[str, int] = {}
        
    def connect(self) -> bool:
        """
        Подключение к MT5
        
        Returns:
            bool: True если подключение успешно, False в противном случае
        """
        if not self.settings:
            logger.error("Настройки подключения не найдены")
            return False
            
        try:
            # Параметры подключения
            connect_params = {}
            
            if self.settings.terminal_path:
                connect_params['path'] = self.settings.terminal_path
                
            if self.settings.server:
                connect_params['server'] = self.settings.server
                
            if self.settings.login:
                connect_params['login'] = self.settings.login
                
            if self.settings.password:
                connect_params['password'] = self.settings.password
                
            if self.settings.timeout:
                connect_params['timeout'] = self.settings.timeout
                
            if self.settings.portable:
                connect_params['portable'] = self.settings.portable
            
            # Попытка подключения
            if connect_params:
                result = mt5.initialize(**connect_params)
            else:
                result = mt5.initialize()
            
            if result:
                self.is_connected = True
                account_info = self.get_account_info()
                
                # Логируем успешное подключение
                MT5ConnectionLog.objects.create(
                    settings=self.settings,
                    success=True,
                    account_info=account_info
                )
                
                logger.info(f"Успешное подключение к MT5 с настройками '{self.settings.name}'")
                return True
            else:
                error_msg = f"Ошибка подключения: {mt5.last_error()}"
                logger.error(error_msg)
                
                # Логируем неудачное подключение
                MT5ConnectionLog.objects.create(
                    settings=self.settings,
                    success=False,
                    error_message=error_msg
                )
                
                return False
                
        except Exception as e:
            error_msg = f"Исключение при подключении: {str(e)}"
            logger.error(error_msg)
            
            # Логируем ошибку
            MT5ConnectionLog.objects.create(
                settings=self.settings,
                success=False,
                error_message=error_msg
            )
            
            return False
    
    def disconnect(self) -> None:
        """Отключение от MT5"""
        try:
            mt5.shutdown()
            self.is_connected = False
            logger.info("Отключение от MT5 выполнено")
        except Exception as e:
            logger.error(f"Ошибка при отключении от MT5: {str(e)}")
    
    def get_account_info(self) -> Optional[Dict[str, Any]]:
        """
        Получение информации о торговом счете
        
        Returns:
            dict: Информация о счете или None если не подключен
        """
        if not self.is_connected:
            return None
            
        try:
            account_info = mt5.account_info()
            if account_info:
                return {
                    'login': account_info.login,
                    'server': account_info.server,
                    'name': account_info.name,
                    'company': account_info.company,
                    'currency': account_info.currency,
                    'balance': account_info.balance,
                    'equity': account_info.equity,
                    'margin': account_info.margin,
                    'free_margin': account_info.margin_free,
                    'margin_level': account_info.margin_level,
                    'leverage': account_info.leverage,
                }
            return None
        except Exception as e:
            logger.error(f"Ошибка получения информации о счете: {str(e)}")
            return None
    
    def get_terminal_info(self) -> Optional[Dict[str, Any]]:
        """
        Получение информации о терминале
        
        Returns:
            dict: Информация о терминале или None если не подключен
        """
        if not self.is_connected:
            return None
            
        try:
            terminal_info = mt5.terminal_info()
            if terminal_info:
                return {
                    'community_account': terminal_info.community_account,
                    'community_connection': terminal_info.community_connection,
                    'connected': terminal_info.connected,
                    'dlls_allowed': terminal_info.dlls_allowed,
                    'trade_allowed': terminal_info.trade_allowed,
                    'tradeapi_disabled': terminal_info.tradeapi_disabled,
                    'email_enabled': terminal_info.email_enabled,
                    'ftp_enabled': terminal_info.ftp_enabled,
                    'notifications_enabled': terminal_info.notifications_enabled,
                    'mqid': terminal_info.mqid,
                    'build': terminal_info.build,
                    'maxbars': terminal_info.maxbars,
                    'codepage': terminal_info.codepage,
                    'cpu_cores': terminal_info.cpu_cores,
                    'disk_space': terminal_info.disk_space,
                    'heap_size': terminal_info.heap_size,
                    'memory_available': terminal_info.memory_available,
                    'memory_physical': terminal_info.memory_physical,
                    'memory_total': terminal_info.memory_total,
                    'memory_used': terminal_info.memory_used,
                    'name': terminal_info.name,
                    'company': terminal_info.company,
                    'language': terminal_info.language,
                    'path': terminal_info.path,
                }
            return None
        except Exception as e:
            logger.error(f"Ошибка получения информации о терминале: {str(e)}")
            return None
    
    def get_symbols(self) -> List[str]:
        """
        Получение списка доступных символов
        
        Returns:
            list: Список символов или пустой список если не подключен
        """
        if not self.is_connected:
            return []
            
        try:
            symbols = mt5.symbols_get()
            if symbols:
                return [symbol.name for symbol in symbols]
            return []
        except Exception as e:
            logger.error(f"Ошибка получения списка символов: {str(e)}")
            return []
    
    def test_connection(self) -> Dict[str, Any]:
        """
        Тестирование подключения
        
        Returns:
            dict: Результат тестирования с подробной информацией
        """
        result = {
            'success': False,
            'message': '',
            'account_info': None,
            'terminal_info': None,
            'symbols_count': 0,
            'connection_time': datetime.now()
        }
        
        try:
            if self.connect():
                result['success'] = True
                result['message'] = 'Подключение успешно установлено'
                result['account_info'] = self.get_account_info()
                result['terminal_info'] = self.get_terminal_info()
                result['symbols_count'] = len(self.get_symbols())
            else:
                result['message'] = 'Не удалось установить подключение'
                
        except Exception as e:
            result['message'] = f'Ошибка при тестировании: {str(e)}'
        finally:
            if self.is_connected:
                self.disconnect()
                
        return result
    
    def __enter__(self):
        """Поддержка контекстного менеджера"""
        self.connect()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """На выходе из контекста оставляем соединение открытым.
        Отключение управляется вызывающей стороной/пулом, чтобы избежать
        глобальных shutdown при параллельной работе потоков (WS, мониторинг).
        """
        return False
    
    def get_balance(self) -> Optional[float]:
        """
        Получение текущего баланса счета
        
        Returns:
            float: Баланс счета или None если не подключен
        """
        account_info = self.get_account_info()
        return account_info.get('balance') if account_info else None
    
    def get_equity(self) -> Optional[float]:
        """
        Получение текущего эквити счета
        
        Returns:
            float: Эквити счета или None если не подключен
        """
        account_info = self.get_account_info()
        return account_info.get('equity') if account_info else None
    
    def update_account_data(self) -> bool:
        """
        Обновление данных счета в базе данных
        
        Returns:
            bool: True если обновление успешно
        """
        if not self.settings or not self.is_connected:
            return False
        
        try:
            balance = self.get_balance()
            equity = self.get_equity()
            
            if balance is not None and equity is not None:
                self.settings.balance = balance
                self.settings.equity = equity
                self.settings.last_connection_time = datetime.now()
                self.settings.save()
                return True
                
        except Exception as e:
            logger.error(f"Ошибка обновления данных счета: {str(e)}")
        
        return False

    def get_open_positions(self) -> List[Dict[str, Any]]:
        """
        Get current open positions from MetaTrader 5.

        Returns:
            list: List of positions as dictionaries
        """
        if not self.is_connected:
            return []

        try:
            positions = mt5.positions_get()
            # Broker/server timezone offset (seconds) if available
            try:
                _ti = mt5.terminal_info()
                tz_offset_sec = int(getattr(_ti, 'timezone', 0) or 0)
            except Exception:
                tz_offset_sec = 0
            result: List[Dict[str, Any]] = []
            if not positions:
                return result

            for p in positions:
                # Map MT5 position tuple to dict
                try:
                    pos_type = 'BUY' if int(getattr(p, 'type', 0) or 0) == 0 else 'SELL'
                except Exception:
                    pos_type = str(getattr(p, 'type', ''))

                opened_ts = getattr(p, 'time', None)
                opened_at_iso = None
                opened_ts_int = None
                opened_local_str = None
                if opened_ts:
                    try:
                        opened_ts_int = int(opened_ts)
                    except Exception:
                        opened_ts_int = None
                    try:
                        opened_at_iso = datetime.utcfromtimestamp(int(opened_ts)).strftime('%Y-%m-%dT%H:%M:%SZ')
                    except Exception:
                        opened_at_iso = None
                    try:
                        opened_local_str = datetime.fromtimestamp(int(opened_ts)).strftime('%Y-%m-%d %H:%M:%S')
                    except Exception:
                        opened_local_str = None
                    # Broker/server time string using terminal timezone offset, if provided
                    try:
                        if opened_ts_int is not None:
                            opened_broker_str = datetime.utcfromtimestamp(opened_ts_int + tz_offset_sec).strftime('%Y-%m-%d %H:%M:%S')
                        else:
                            opened_broker_str = None
                    except Exception:
                        opened_broker_str = None

                result.append({
                    'ticket': getattr(p, 'ticket', None),
                    'symbol': getattr(p, 'symbol', ''),
                    'type': pos_type,
                    'volume': float(getattr(p, 'volume', 0) or 0),
                    'price_open': float(getattr(p, 'price_open', 0) or 0),
                    'sl': float(getattr(p, 'sl', 0) or 0),
                    'tp': float(getattr(p, 'tp', 0) or 0),
                    'price_current': float(getattr(p, 'price_current', 0) or 0),
                    'profit': float(getattr(p, 'profit', 0) or 0),
                    'swap': float(getattr(p, 'swap', 0) or 0),
                    'commission': float(getattr(p, 'commission', 0) or 0) if hasattr(p, 'commission') else None,
                    'comment': getattr(p, 'comment', ''),
                    'magic': getattr(p, 'magic', None),
                    # Provide both UTC ISO and unix seconds; UI prefers unix for reliable local rendering
                    'time': opened_at_iso,
                    'time_ts': opened_ts_int,
                    'time_local': opened_local_str,
                    'time_broker': opened_broker_str,
                })

            return result
        except Exception as e:
            logger.error(f"Error fetching MT5 positions: {str(e)}")
            return []

    def get_open_positions_for(self, symbol: Optional[str] = None, magic: Optional[int] = None) -> List[Dict[str, Any]]:
        """Filter open positions by symbol and/or magic."""
        allp = self.get_open_positions() or []
        res = []
        for p in allp:
            if symbol and p.get('symbol') != symbol:
                continue
            if magic is not None and p.get('magic') != magic:
                continue
            res.append(p)
        return res

    # --- Trading actions ---
    def _ensure_symbol(self, symbol: str) -> bool:
        try:
            info = mt5.symbol_info(symbol)
            if info and info.visible:
                return True
            # Try to select even if info is None (symbol might be hidden)
            try:
                mt5.symbol_select(symbol, True)
            except Exception:
                pass
            info2 = mt5.symbol_info(symbol)
            if info2 and info2.visible:
                return True
            # Fallback: attempt case-insensitive or suffix match (e.g., EURUSD.r)
            try:
                allsyms = mt5.symbols_get()
            except Exception:
                allsyms = None
            if allsyms:
                target = symbol.upper()
                cand = None
                for s in allsyms:
                    if getattr(s, 'name', '').upper() == target:
                        cand = s.name
                        break
                if not cand:
                    for s in allsyms:
                        n = getattr(s, 'name', '').upper()
                        if n.startswith(target):
                            cand = s.name
                            break
                if cand:
                    try:
                        mt5.symbol_select(cand, True)
                    except Exception:
                        pass
                    info3 = mt5.symbol_info(cand)
                    if info3 and info3.visible:
                        return True
            return False
        except Exception:
            return False

    def _resolve_trade_symbol(self, symbol: str) -> Optional[str]:
        """Return a visible symbol name suitable for trading.

        Tries the provided name, and if not available, searches for a case-insensitive
        or suffix-matching variant (e.g., EURUSD.r). Ensures the symbol is selected.
        """
        try:
            info = mt5.symbol_info(symbol)
            if info and info.visible:
                return symbol
            # Try to select the provided as-is
            try:
                mt5.symbol_select(symbol, True)
            except Exception:
                pass
            info2 = mt5.symbol_info(symbol)
            if info2 and info2.visible:
                return symbol
            # Scan available symbols for a match
            try:
                allsyms = mt5.symbols_get()
            except Exception:
                allsyms = None
            if allsyms:
                target = symbol.upper()
                for s in allsyms:
                    if getattr(s, 'name', '').upper() == target:
                        mt5.symbol_select(s.name, True)
                        return s.name
                for s in allsyms:
                    n = getattr(s, 'name', '').upper()
                    if n.startswith(target):
                        mt5.symbol_select(s.name, True)
                        return s.name
                # Fallback: normalize (drop non-alnum) and compare
                def _norm(x: str) -> str:
                    try:
                        return ''.join(ch for ch in (x or '') if ch.isalnum()).upper()
                    except Exception:
                        return (x or '').upper()
                norm_target = _norm(symbol)
                for s in allsyms:
                    if _norm(getattr(s, 'name', '')) == norm_target:
                        try:
                            mt5.symbol_select(s.name, True)
                        except Exception:
                            pass
                        return s.name
            return None
        except Exception:
            return None

    def _get_tick(self, symbol: str) -> Optional[Any]:
        try:
            return mt5.symbol_info_tick(symbol)
        except Exception:
            return None

    def get_symbol_bid(self, symbol: str) -> Optional[float]:
        """Return best-effort Bid price for symbol.

        Attempts in order:
        - Ensure symbol is visible/selected, resolving broker-specific name
        - Use symbol_info_tick().bid when available
        - Fallback to symbol_info_double(SYMBOL_BID) which often returns last known price
        """
        try:
            sym = self._ensure_symbol(symbol) or symbol
        except Exception:
            sym = symbol
        # Try live tick first
        try:
            t = self._get_tick(sym)
            if t is not None:
                b = getattr(t, 'bid', None)
                if b is not None and float(b) != 0:
                    return float(b)
        except Exception:
            pass
        # Fallback to last known bid from symbol_info
        try:
            b2 = mt5.symbol_info_double(sym, getattr(mt5, 'SYMBOL_BID', 1))
            if b2 is not None and float(b2) != 0:
                return float(b2)
        except Exception:
            pass
        return None

    def _filling_candidates(self, symbol: str) -> List[int]:
        cands: List[int] = []
        for name in ('ORDER_FILLING_RETURN', 'ORDER_FILLING_IOC', 'ORDER_FILLING_FOK'):
            val = getattr(mt5, name, None)
            if isinstance(val, int) and val not in cands:
                cands.append(val)
        if not cands:
            cands = [0, 1, 2]
        return cands

    def _order_send_with_filling(self, base_request: Dict[str, Any], symbol: str) -> Dict[str, Any]:
        last = None
        for fill in self._filling_candidates(symbol):
            req = dict(base_request)
            req['type_filling'] = fill
            try:
                result = mt5.order_send(req)
                retcode = getattr(result, 'retcode', None)
                success = retcode == getattr(mt5, 'TRADE_RETCODE_DONE', 10009)
                if success:
                    return {
                        'success': True,
                        'retcode': retcode,
                        'message': str(result),
                        'order': getattr(result, 'order', None),
                        'deal': getattr(result, 'deal', None),
                        'filling_used': fill,
                    }
                last = {
                    'success': False,
                    'retcode': retcode,
                    'message': str(result),
                    'filling_used': fill,
                }
            except Exception as e:
                last = {'success': False, 'message': f'order_send error: {str(e)}', 'filling_used': fill}
        return last or {'success': False, 'message': 'order_send failed'}

    def resolve_filling_mode(self, symbol: str, probe_request: Optional[Dict[str, Any]] = None) -> Optional[int]:
        """Resolve and cache a working filling mode for a symbol.

        Strategy:
        - Build candidate list (symbol_info.filling_mode first if present),
          completed by RETURN → IOC → FOK.
        - If probe_request provided, validate candidates with mt5.order_check
          to avoid send-time errors (e.g., retcode 10030 Unsupported filling).
        - Cache first acceptable mode and return it.
        """
        if symbol in self._filling_cache:
            return self._filling_cache[symbol]

        # Candidate list
        cands: List[int] = []
        try:
            info = mt5.symbol_info(symbol)
            mode = getattr(info, 'filling_mode', None) if info else None
            if isinstance(mode, int):
                cands.append(mode)
        except Exception:
            pass
        for name in ('ORDER_FILLING_RETURN', 'ORDER_FILLING_IOC', 'ORDER_FILLING_FOK'):
            val = getattr(mt5, name, None)
            if isinstance(val, int) and val not in cands:
                cands.append(val)

        # If we cannot probe, pick the first candidate (still cached)
        if not probe_request:
            chosen = cands[0] if cands else None
            if chosen is not None:
                self._filling_cache[symbol] = chosen
            return chosen

        # Probe with order_check to avoid unsupported modes
        for fill in cands:
            req = dict(probe_request)
            req['type_filling'] = fill
            try:
                check = mt5.order_check(req)
                retcode = getattr(check, 'retcode', None)
                # 10030 = TRADE_RETCODE_INVALID_FILL/UNSUPPORTED FILLING
                if retcode == 10030:
                    continue
                # Acceptable: anything that's not invalid fill. Even if NO_MONEY etc.,
                # we only care about a working filling mode.
                self._filling_cache[symbol] = fill
                return fill
            except Exception:
                # If order_check fails, try next
                continue

        # Last resort: cache first candidate if exists
        chosen = cands[0] if cands else None
        if chosen is not None:
            self._filling_cache[symbol] = chosen
        return chosen

    def market_buy(self, symbol: str, volume: float, deviation: int = 20, comment: str = 'GCE3 BUY', magic: Optional[int] = None) -> Dict[str, Any]:
        if not self.is_connected:
            return {'success': False, 'message': 'Not connected to MT5'}
        if not symbol:
            return {'success': False, 'message': 'Symbol is required'}
        try:
            if volume is None or float(volume) <= 0:
                return {'success': False, 'message': 'Volume must be > 0'}
        except Exception:
            return {'success': False, 'message': 'Invalid volume'}
        resolved = self._resolve_trade_symbol(symbol)
        if not resolved:
            return {'success': False, 'message': f'Symbol not available: {symbol}'}
        tick = self._get_tick(symbol)
        if not tick:
            return {'success': False, 'message': f'Failed to get tick for {symbol}'}

        price = float(getattr(tick, 'ask', 0) or 0)
        request = {
            'action': mt5.TRADE_ACTION_DEAL,
            'symbol': resolved,
            'volume': float(volume),
            'type': mt5.ORDER_TYPE_BUY,
            'price': price,
            'deviation': deviation,
            'type_time': getattr(mt5, 'ORDER_TIME_GTC', 0),
            'comment': comment,
        }
        fill = self.resolve_filling_mode(resolved, request)
        if fill is not None:
            request['type_filling'] = fill
        if magic is not None:
            request['magic'] = int(magic)
        try:
            result = mt5.order_send(request)
            retcode = getattr(result, 'retcode', None)
            success = retcode == getattr(mt5, 'TRADE_RETCODE_DONE', 10009)
            if success:
                return {
                    'success': True,
                    'retcode': retcode,
                    'message': str(result),
                    'order': getattr(result, 'order', None),
                    'deal': getattr(result, 'deal', None),
                    'filling_used': fill,
                }
            # Fallback: try other filling modes if initial send failed
            fb = self._order_send_with_filling(request, resolved)
            if 'filling_used' not in fb and fill is not None:
                fb['filling_used'] = fill
            return fb
        except Exception as e:
            return {'success': False, 'message': f'BUY error: {str(e)}', 'filling_used': fill}

    def market_sell(self, symbol: str, volume: float, deviation: int = 20, comment: str = 'GCE3 SELL', magic: Optional[int] = None) -> Dict[str, Any]:
        if not self.is_connected:
            return {'success': False, 'message': 'Not connected to MT5'}
        if not symbol:
            return {'success': False, 'message': 'Symbol is required'}
        try:
            if volume is None or float(volume) <= 0:
                return {'success': False, 'message': 'Volume must be > 0'}
        except Exception:
            return {'success': False, 'message': 'Invalid volume'}
        resolved = self._resolve_trade_symbol(symbol)
        if not resolved:
            return {'success': False, 'message': f'Symbol not available: {symbol}'}
        tick = self._get_tick(symbol)
        if not tick:
            return {'success': False, 'message': f'Failed to get tick for {symbol}'}

        price = float(getattr(tick, 'bid', 0) or 0)
        request = {
            'action': mt5.TRADE_ACTION_DEAL,
            'symbol': resolved,
            'volume': float(volume),
            'type': mt5.ORDER_TYPE_SELL,
            'price': price,
            'deviation': deviation,
            'comment': comment,
        }
        request['type_time'] = getattr(mt5, 'ORDER_TIME_GTC', 0)
        fill = self.resolve_filling_mode(resolved, request)
        if fill is not None:
            request['type_filling'] = fill
        if magic is not None:
            request['magic'] = int(magic)
        try:
            result = mt5.order_send(request)
            retcode = getattr(result, 'retcode', None)
            success = retcode == getattr(mt5, 'TRADE_RETCODE_DONE', 10009)
            if success:
                return {
                    'success': True,
                    'retcode': retcode,
                    'message': str(result),
                    'order': getattr(result, 'order', None),
                    'deal': getattr(result, 'deal', None),
                    'filling_used': fill,
                }
            fb = self._order_send_with_filling(request, resolved)
            if 'filling_used' not in fb and fill is not None:
                fb['filling_used'] = fill
            return fb
        except Exception as e:
            return {'success': False, 'message': f'SELL error: {str(e)}', 'filling_used': fill}

    def close_position(self, ticket: int, deviation: int = 20, comment: str = 'GCE3 CLOSE') -> Dict[str, Any]:
        if not self.is_connected:
            return {'success': False, 'message': 'Not connected to MT5'}
        try:
            pos = None
            positions = mt5.positions_get(ticket=ticket)
            if positions:
                pos = positions[0]
            if not pos:
                return {'success': False, 'message': f'Position not found: {ticket}'}
            symbol = getattr(pos, 'symbol', '')
            if not self._ensure_symbol(symbol):
                return {'success': False, 'message': f'Symbol not available: {symbol}'}
            tick = self._get_tick(symbol)
            if not tick:
                return {'success': False, 'message': f'Failed to get tick for {symbol}'}

            pos_type = int(getattr(pos, 'type', 0) or 0)
            vol = float(getattr(pos, 'volume', 0) or 0)
            pos_type_buy = getattr(mt5, 'POSITION_TYPE_BUY', 0)
            # opposite order type and correct price
            if pos_type == pos_type_buy:
                close_type = mt5.ORDER_TYPE_SELL
                price = float(getattr(tick, 'bid', 0) or 0)
            else:
                close_type = mt5.ORDER_TYPE_BUY
                price = float(getattr(tick, 'ask', 0) or 0)

            request = {
                'action': mt5.TRADE_ACTION_DEAL,
                'position': int(ticket),
                'symbol': symbol,
                'volume': vol,
                'type': close_type,
                'price': price,
                'deviation': deviation,
                'type_time': getattr(mt5, 'ORDER_TIME_GTC', 0),
                'comment': comment,
            }
            fill = self.resolve_filling_mode(symbol, request)
            if fill is not None:
                request['type_filling'] = fill
            try:
                result = mt5.order_send(request)
                retcode = getattr(result, 'retcode', None)
                success = retcode == getattr(mt5, 'TRADE_RETCODE_DONE', 10009)
                return {
                    'success': success,
                    'retcode': retcode,
                    'message': str(result),
                    'order': getattr(result, 'order', None),
                    'deal': getattr(result, 'deal', None),
                    'filling_used': fill,
                }
            except Exception as e:
                return {'success': False, 'message': f'Close error: {str(e)}', 'filling_used': fill}
        except Exception as e:
            return {'success': False, 'message': f'Close error: {str(e)}'}

    def close_all(self, only_type: Optional[str] = None) -> Dict[str, Any]:
        if not self.is_connected:
            return {'success': False, 'message': 'Not connected to MT5'}
        try:
            positions = self.get_open_positions() or []
            closed = 0
            errors: List[Dict[str, Any]] = []
            for p in positions:
                if only_type and p.get('type') != only_type:
                    continue
                res = self.close_position(p.get('ticket'))
                if res.get('success'):
                    closed += 1
                else:
                    errors.append({'ticket': p.get('ticket'), 'error': res.get('message')})
            return {'success': True, 'closed': closed, 'errors': errors}
        except Exception as e:
            return {'success': False, 'message': f'Close all error: {str(e)}'}


class MT5Manager:
    """Менеджер для работы с различными настройками MT5"""
    
    @staticmethod
    def get_active_connections() -> List[MT5ConnectionSettings]:
        """Получить все активные настройки подключения"""
        return MT5ConnectionSettings.get_active_settings()
    
    @staticmethod
    def test_all_connections() -> Dict[str, Dict[str, Any]]:
        """
        Тестирование всех активных подключений
        
        Returns:
            dict: Словарь с результатами тестирования для каждой настройки
        """
        results = {}
        
        for settings in MT5Manager.get_active_connections():
            service = MT5Service(settings)
            results[settings.name] = service.test_connection()
            
        return results
    
    @staticmethod
    def get_default_service() -> Optional[MT5Service]:
        """
        Получить сервис с настройками по умолчанию
        
        Returns:
            MT5Service: Сервис или None если настройки по умолчанию не найдены
        """
        default_settings = MT5ConnectionSettings.get_default_settings()
        if default_settings:
            return MT5Service(default_settings)
        return None
