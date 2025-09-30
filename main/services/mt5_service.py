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
        """Автоматическое отключение при выходе из контекста"""
        if self.is_connected:
            self.disconnect()
    
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