from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from datetime import timedelta
from django.db.models import Max
from .models import (
    MT5ConnectionSettings,
    MT5ConnectionLog,
    TradingSystem,
    TimeFrame,
    DataIngestionStatus,
    SignalEvent,
    TradingSystemSignalSettings,
)
from .models import TradingSystemTFBinding, MarketBar
from django.conf import settings as django_settings
from .services.mt5_service import MT5Service, MT5Manager
import sys
import platform
from datetime import datetime
import os
import csv
import glob
from pathlib import Path
import json
from django.views.decorators.csrf import ensure_csrf_cookie

# Create your views here.

def home(request):
    """Главная страница проекта GCE_3"""
    
    # Проверяем доступность MT5
    mt5_available = False
    try:
        import MetaTrader5 as mt5
        mt5_available = True
    except ImportError:
        mt5_available = False
    
    # Получаем статистику MT5
    mt5_settings_count = MT5ConnectionSettings.objects.count()
    
    context = {
        'mt5_available': mt5_available,
        'mt5_settings_count': mt5_settings_count,
    }
    
    return render(request, 'main/home.html', context)

def trading_history(request):
    """Страница торговой истории"""
    context = {
        # Здесь будут данные торговой истории
        'trades': [],  # Заглушка
    }
    return render(request, 'main/trading_history.html', context)

def system_dashboard(request):
    """Системный дашборд с мониторингом MT5"""
    
    # Проверяем доступность MT5
    mt5_available = False
    mt5_version = "Не установлена"
    mt5_terminal_info = "Не подключен"
    
    try:
        import MetaTrader5 as mt5
        mt5_available = True
        
        # Пытаемся инициализировать MT5
        if mt5.initialize():
            terminal_info = mt5.terminal_info()
            if terminal_info:
                mt5_terminal_info = f"{terminal_info.name} {terminal_info.build}"
            account_info = mt5.account_info()
            mt5.shutdown()
        
        # Получаем версию MT5 (приблизительно)
        mt5_version = "5.0"  # Базовая версия
        
    except ImportError:
        pass
    except Exception as e:
        mt5_terminal_info = f"Ошибка: {str(e)}"
    
    # Получаем информацию о системе
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    
    # Получаем настройки MT5
    mt5_settings_count = MT5ConnectionSettings.objects.count()
    mt5_connections = []
    
    for settings in MT5ConnectionSettings.objects.all():
        # Определяем статус подключения на основе последнего обновления
        is_recently_connected = False
        if settings.last_connection_time:
            # Считаем подключение активным, если оно было менее 5 минут назад
            time_diff = timezone.now() - settings.last_connection_time
            is_recently_connected = time_diff.total_seconds() < 300  # 5 минут
        
        connection_data = {
            'id': settings.id,
            'name': settings.name,
            'server': settings.server,
            'login': settings.login,
            'is_connected': is_recently_connected,  # Реальная проверка на основе времени
            'balance': settings.balance,  # Реальные данные из базы
            'equity': settings.equity,    # Реальные данные из базы
            'last_update': settings.last_connection_time.strftime('%Y-%m-%d %H:%M:%S') if settings.last_connection_time else 'Never',
            'error_message': None,
        }
        
        # Попытка получить реальные данные (если MT5 доступен)
        if mt5_available and settings.is_active:
            try:
                from .services.mt5_service import MT5Service
                service = MT5Service(settings)
                
                # Пробуем подключиться и обновить данные (быстро, без длительного ожидания)
                # connection_data['is_connected'] = True  # Комментируем чтобы не замедлять страницу
                    
            except Exception as e:
                connection_data['error_message'] = f'Connection error: {str(e)}'
        
        mt5_connections.append(connection_data)
    
    # Получаем размер базы данных
    db_size = "Неизвестно"
    try:
        from django.conf import settings as django_settings
        db_path = django_settings.DATABASES['default']['NAME']
        if os.path.exists(db_path):
            size = os.path.getsize(db_path)
            if size < 1024:
                db_size = f"{size} байт"
            elif size < 1024 * 1024:
                db_size = f"{size / 1024:.1f} КБ"
            else:
                db_size = f"{size / (1024 * 1024):.1f} МБ"
    except Exception:
        pass
    
    # Расчет uptime (заглушка - в реальности нужно сохранять время запуска)
    system_uptime = "99.9%"
    active_connections = len([c for c in mt5_connections if c['is_connected']])
    
    context = {
        'mt5_available': mt5_available,
        'mt5_version': mt5_version,
        'mt5_terminal_info': mt5_terminal_info,
        'mt5_settings_count': mt5_settings_count,
        'mt5_connections': mt5_connections,
        'python_version': python_version,
        'system_uptime': system_uptime,
        'active_connections': active_connections,
        'db_size': db_size,
    }
    
    return render(request, 'main/system_dashboard.html', context)


def mt5_connect(request):
    """API endpoint for manual MT5 connection"""
    if request.method == 'POST':
        try:
            # Get connection settings ID from request
            settings_id = request.POST.get('settings_id')
            
            if not settings_id:
                return JsonResponse({
                    'success': False,
                    'message': 'Connection settings ID not provided'
                })
            
            # Get settings object
            try:
                settings = MT5ConnectionSettings.objects.get(id=settings_id)
            except MT5ConnectionSettings.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Connection settings not found'
                })
            
            # Try to connect
            with MT5Service(settings) as mt5_service:
                if mt5_service.connect():
                    # Update last connection time and get account info
                    account_info = mt5_service.get_account_info()
                    
                    # Update settings with current balance and equity
                    if account_info:
                        settings.balance = account_info.get('balance')
                        settings.equity = account_info.get('equity')
                        settings.last_connection_time = timezone.now()
                        settings.save()
                    
                    return JsonResponse({
                        'success': True,
                        'message': 'Successfully connected to MT5',
                        'balance': float(settings.balance or 0),
                        'equity': float(settings.equity or 0),
                        'server': settings.server,
                        'login': settings.login
                    })
                else:
                    return JsonResponse({
                        'success': False,
                        'message': 'Failed to connect to MT5. Check your settings.'
                    })
                    
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Connection error: {str(e)}'
            })
    
    return JsonResponse({
        'success': False,
        'message': 'Only POST method allowed'
    })


def mt5_disconnect(request):
    """API endpoint for manual MT5 disconnection"""
    if request.method == 'POST':
        try:
            settings_id = request.POST.get('settings_id')
            
            if not settings_id:
                return JsonResponse({
                    'success': False,
                    'message': 'Connection settings ID not provided'
                })
            
            # Try to disconnect
            import MetaTrader5 as mt5
            mt5.shutdown()
            
            return JsonResponse({
                'success': True,
                'message': 'Successfully disconnected from MT5'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Disconnection error: {str(e)}'
            })
    
    return JsonResponse({
        'success': False,
        'message': 'Only POST method allowed'
    })


def connect_mt5(request):
    """AJAX endpoint for connecting to MT5 with detailed error logging"""
    if request.method == 'POST':
        try:
            # Get connection settings ID from request
            settings_id = request.POST.get('settings_id')
            
            if not settings_id:
                return JsonResponse({
                    'success': False,
                    'message': 'Connection settings ID not provided'
                })
            
            # Get settings object
            try:
                settings = MT5ConnectionSettings.objects.get(id=settings_id)
            except MT5ConnectionSettings.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': f'Connection settings with ID {settings_id} not found'
                })
            
            # Check MT5 library availability
            try:
                import MetaTrader5 as mt5
            except ImportError as e:
                return JsonResponse({
                    'success': False,
                    'message': f'MetaTrader5 library not available: {str(e)}'
                })
            
            # Try to connect
            try:
                service = MT5Service(settings)
                print(f"[DEBUG] Attempting connection with settings: {settings.name}")
                print(f"[DEBUG] Server: {settings.server}")
                print(f"[DEBUG] Login: {settings.login}")
                print(f"[DEBUG] Terminal path: {settings.terminal_path}")
                
                if service.connect():
                    print("[DEBUG] Connection successful!")
                    
                    # Update last connection time and get account info
                    account_info = service.get_account_info()
                    print(f"[DEBUG] Account info: {account_info}")
                    
                    # Update settings with current balance and equity
                    if account_info:
                        settings.balance = account_info.get('balance')
                        settings.equity = account_info.get('equity')
                        settings.last_connection_time = timezone.now()
                        settings.save()
                        
                        service.disconnect()  # Clean disconnect
                        
                        return JsonResponse({
                            'success': True,
                            'message': 'Successfully connected to MT5',
                            'balance': float(settings.balance) if settings.balance else None,
                            'equity': float(settings.equity) if settings.equity else None,
                            'last_update': settings.last_connection_time.strftime('%Y-%m-%d %H:%M:%S')
                        })
                    else:
                        print("[DEBUG] Could not get account info")
                        service.disconnect()
                        return JsonResponse({
                            'success': False,
                            'message': 'Connected but could not retrieve account information'
                        })
                else:
                    # Get detailed error from MT5
                    last_error = mt5.last_error()
                    print(f"[DEBUG] Connection failed. MT5 error: {last_error}")
                    
                    # Check if MT5 terminal is running
                    terminal_info = mt5.terminal_info()
                    print(f"[DEBUG] Terminal info: {terminal_info}")
                    
                    error_msg = 'Failed to connect to MT5.'
                    if last_error:
                        error_msg += f' Error code: {last_error[0]}, Description: {last_error[1] if len(last_error) > 1 else "No description"}'
                    else:
                        error_msg += ' Check if MT5 terminal is installed and running.'
                    
                    return JsonResponse({
                        'success': False,
                        'message': error_msg
                    })
                    
            except Exception as service_error:
                print(f"[ERROR] Service error: {str(service_error)}")
                import traceback
                traceback.print_exc()
                
                return JsonResponse({
                    'success': False,
                    'message': f'Service error: {str(service_error)}. Check if MT5 terminal is installed and running.'
                })
                
        except Exception as e:
            print(f"[ERROR] General error in connect_mt5: {str(e)}")
            import traceback
            traceback.print_exc()
            
            return JsonResponse({
                'success': False,
                'message': f'Unexpected error: {str(e)}'
            })
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method'
    })


def mt5_status_api(request):
    """API endpoint for getting MT5 connections status"""
    if request.method == 'GET':
        try:
            mt5_connections = []
            
            for settings in MT5ConnectionSettings.objects.all():
                # Check if we have recent health data
                latest_health = None
                try:
                    from .models import MT5ConnectionHealth
                    latest_health = MT5ConnectionHealth.objects.filter(
                        settings=settings
                    ).first()
                except:
                    pass
                
                connection_data = {
                    'id': settings.id,
                    'name': settings.name,
                    'server': settings.server,
                    'login': settings.login,
                    'is_connected': latest_health.is_connected if latest_health else False,
                    'balance': float(settings.balance) if settings.balance else None,
                    'equity': float(settings.equity) if settings.equity else None,
                    'last_update': settings.last_connection_time.strftime('%Y-%m-%d %H:%M:%S') if settings.last_connection_time else 'Never',
                    'ping_ms': latest_health.ping_ms if latest_health else None,
                    'error_message': latest_health.error_message if latest_health and latest_health.error_message else None
                }
                
                mt5_connections.append(connection_data)
            
            return JsonResponse({
                'success': True,
                'connections': mt5_connections
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error: {str(e)}'
            })
    
    return JsonResponse({
        'success': False,
        'message': 'Only GET method allowed'
    })


def disconnect_mt5(request):
    """AJAX endpoint for disconnecting from MT5"""
    if request.method == 'POST':
        try:
            # Get connection settings ID from request
            settings_id = request.POST.get('settings_id')
            
            if not settings_id:
                return JsonResponse({
                    'success': False,
                    'message': 'Connection settings ID not provided'
                })
            
            # Try to disconnect - simple shutdown of MT5
            try:
                import MetaTrader5 as mt5
                mt5.shutdown()
                
                print(f"[DEBUG] MT5 shutdown called for settings ID: {settings_id}")
                
                return JsonResponse({
                    'success': True,
                    'message': 'Successfully disconnected from MT5'
                })
                
            except Exception as e:
                print(f"[ERROR] Error during MT5 shutdown: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'message': f'Disconnection error: {str(e)}'
                })
            
        except Exception as e:
            print(f"[ERROR] General error in disconnect_mt5: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': f'Error: {str(e)}'
            })
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method'
    })


def monitoring_status(request):
    """API endpoint to get monitoring service status"""
    try:
        from .services.mt5_monitor import get_monitor
        from .models import MT5MonitoringSettings
        
        monitor = get_monitor()
        settings = MT5MonitoringSettings.get_settings()
        
        return JsonResponse({
            'success': True,
            'monitoring_active': monitor.monitoring_active,
            'monitoring_enabled': settings.monitoring_enabled,
            'auto_reconnect_enabled': settings.auto_reconnect_enabled,
            'health_check_interval': settings.health_check_interval,
            'reconnect_interval': settings.reconnect_interval,
            'max_reconnect_attempts': settings.max_reconnect_attempts,
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error getting monitoring status: {str(e)}'
        })


def start_monitoring_service(request):
    """API endpoint to start monitoring service"""
    if request.method == 'POST':
        try:
            from .services.mt5_monitor import start_monitoring, get_monitor
            from .models import MT5MonitoringSettings
            
            monitor = get_monitor()
            if monitor.monitoring_active:
                return JsonResponse({
                    'success': False,
                    'message': 'Monitoring service is already running',
                    'monitoring_active': monitor.monitoring_active
                })
            
            # Enable monitoring in settings
            monitoring_settings = MT5MonitoringSettings.get_settings()
            monitoring_settings.monitoring_enabled = True
            monitoring_settings.save()
            
            start_monitoring()
            monitor = get_monitor()
            
            return JsonResponse({
                'success': True,
                'message': 'Monitoring service started successfully',
                'monitoring_active': monitor.monitoring_active
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error starting monitoring service: {str(e)}'
            })
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method'
    })


def stop_monitoring_service(request):
    """API endpoint to stop monitoring service"""
    if request.method == 'POST':
        try:
            from .services.mt5_monitor import stop_monitoring, get_monitor
            from .models import MT5MonitoringSettings
            
            monitor = get_monitor()
            if not monitor.monitoring_active:
                return JsonResponse({
                    'success': False,
                    'message': 'Monitoring service is not running',
                    'monitoring_active': monitor.monitoring_active
                })
            
            # Disable monitoring in settings to prevent auto-restart
            monitoring_settings = MT5MonitoringSettings.get_settings()
            monitoring_settings.monitoring_enabled = False
            monitoring_settings.save()
            
            stop_monitoring()
            monitor = get_monitor()
            
            return JsonResponse({
                'success': True,
                'message': 'Monitoring service stopped successfully',
                'monitoring_active': monitor.monitoring_active
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error stopping monitoring service: {str(e)}'
            })
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method'
    })


def get_monitoring_status_api(request):
    """API endpoint to get current monitoring service status"""
    try:
        from .services.mt5_monitor import get_monitor
        from .models import MT5MonitoringSettings
        
        monitor = get_monitor()
        monitoring_settings = MT5MonitoringSettings.get_settings()
        
        return JsonResponse({
            'success': True,
            'monitoring_active': monitor.monitoring_active,
            'monitoring_enabled': monitoring_settings.monitoring_enabled,
            'auto_reconnect_enabled': monitoring_settings.auto_reconnect_enabled,
            'health_check_interval': monitoring_settings.health_check_interval,
            'reconnect_interval': monitoring_settings.reconnect_interval,
            'max_reconnect_attempts': monitoring_settings.max_reconnect_attempts
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error getting monitoring status: {str(e)}'
        })


def raw_signals(request):
    """Raw Signals page for displaying TradeStation CSV exports"""
    
    # TradeStation exports directory (from settings)
    ts_exports_dir = getattr(django_settings, 'TS_EXPORTS_DIR', r'C:\\TS_EXPORTS')
    
    # Получаем количество торговых систем
    trading_systems_count = TradingSystem.objects.count()
    
    context = {
        'ts_exports_dir': ts_exports_dir,
        'directory_exists': os.path.exists(ts_exports_dir),
        'trading_systems_count': trading_systems_count
    }
    
    return render(request, 'main/raw_signals.html', context)


def get_csv_files_api(request):
    """API endpoint to get list of CSV files from TradeStation exports directory"""
    try:
        ts_exports_dir = getattr(django_settings, 'TS_EXPORTS_DIR', r'C:\\TS_EXPORTS')
        
        # Optional per-system directory override
        system_id = request.GET.get('system_id')
        if system_id:
            try:
                system = TradingSystem.objects.get(id=system_id)
                ts_exports_dir = system.get_data_dir() if hasattr(system, 'get_data_dir') else getattr(django_settings, 'TS_EXPORTS_DIR', r'C\\TS_EXPORTS')
            except TradingSystem.DoesNotExist:
                pass

        if not os.path.exists(ts_exports_dir):
            return JsonResponse({
                'success': False,
                'message': 'TradeStation exports directory not found',
                'files': []
            })
        
        # Get all CSV files
        csv_files = []
        for file_path in glob.glob(os.path.join(ts_exports_dir, '*.csv')):
            file_name = os.path.basename(file_path)
            file_stat = os.stat(file_path)
            
            csv_files.append({
                'name': file_name,
                'size': file_stat.st_size,
                'modified': datetime.fromtimestamp(file_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                'path': file_path
            })
        
        # Sort by modification time (newest first)
        csv_files.sort(key=lambda x: x['modified'], reverse=True)
        
        return JsonResponse({
            'success': True,
            'files': csv_files,
            'count': len(csv_files)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error getting CSV files: {str(e)}',
            'files': []
        })


def get_csv_data_api(request):
    """API endpoint to get data from specific CSV file"""
    try:
        filename = request.GET.get('filename')
        if not filename:
            return JsonResponse({
                'success': False,
                'message': 'Filename parameter is required'
            })
        
        ts_exports_dir = getattr(django_settings, 'TS_EXPORTS_DIR', r'C\\TS_EXPORTS')
        # Optional per-system directory override
        system_id = request.GET.get('system_id')
        if system_id:
            try:
                system = TradingSystem.objects.get(id=system_id)
                ts_exports_dir = system.get_data_dir() if hasattr(system, 'get_data_dir') else getattr(django_settings, 'TS_EXPORTS_DIR', r'C\\TS_EXPORTS')
            except TradingSystem.DoesNotExist:
                pass
        file_path = os.path.join(ts_exports_dir, filename)
        
        # Security check - ensure file is in the exports directory
        if not file_path.startswith(ts_exports_dir) or not os.path.exists(file_path):
            return JsonResponse({
                'success': False,
                'message': 'File not found or access denied'
            })
        
        # Read CSV file
        data = []
        headers = []
        
        with open(file_path, 'r', encoding='utf-8') as csvfile:
            # Try to detect delimiter
            sample = csvfile.read(1024)
            csvfile.seek(0)
            
            # Common delimiters in TradeStation exports
            delimiter = ','
            if ';' in sample:
                delimiter = ';'
            elif '\t' in sample:
                delimiter = '\t'
            
            reader = csv.reader(csvfile, delimiter=delimiter)
            
            # Read headers
            try:
                headers = next(reader)
            except StopIteration:
                headers = []
            
            # Read data (limit to first 1000 rows for performance)
            row_count = 0
            for row in reader:
                if row_count >= 1000:
                    break
                if row:  # Skip empty rows
                    data.append(row)
                    row_count += 1
        
        return JsonResponse({
            'success': True,
            'filename': filename,
            'headers': headers,
            'data': data,
            'row_count': len(data),
            'total_rows': row_count,
            'delimiter': delimiter
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error reading CSV file: {str(e)}'
        })


# Trading Systems API

def api_trading_systems(request):
    """API для получения списка торговых систем"""
    if request.method == 'GET':
        try:
            systems = []
            for system in TradingSystem.objects.all():
                system_data = {
                    'id': system.id,
                    'system_sid': system.system_sid,
                    'name': system.name,
                    'symbol': system.symbol,
                    'timeframes_count': system.timeframes_count,
                    'time_offset_minutes': system.time_offset_minutes,
                    'data_dir': system.get_data_dir() if hasattr(system, 'get_data_dir') else getattr(django_settings, 'TS_EXPORTS_DIR', r'C\\TS_EXPORTS'),
                    'created_at': system.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'timeframes': []
                }
                
                # Добавляем информацию о таймфреймах
                for timeframe in system.timeframes.all():
                    timeframe_data = {
                        'id': timeframe.id,
                        'open_column': timeframe.open_column,
                        'high_column': timeframe.high_column,
                        'low_column': timeframe.low_column,
                        'close_column': timeframe.close_column,
                        'volume_column': timeframe.volume_column,
                        'datetime_column': timeframe.datetime_column,
                        'datetime_format': timeframe.datetime_format
                    }
                    system_data['timeframes'].append(timeframe_data)
                
                systems.append(system_data)
            
            return JsonResponse({
                'success': True,
                'systems': systems,
                'count': len(systems)
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error getting trading systems: {str(e)}'
            })
    
    return JsonResponse({
        'success': False,
        'message': 'Method not allowed'
    })


def api_trading_system_detail(request, system_id):
    """API для получения детальной информации о торговой системе"""
    if request.method == 'GET':
        try:
            system = TradingSystem.objects.get(id=system_id)
            
            system_data = {
                'id': system.id,
                'system_sid': system.system_sid,
                'name': system.name,
                'symbol': system.symbol,
                'timeframes_count': system.timeframes_count,
                'time_offset_minutes': system.time_offset_minutes,
                'data_dir': system.get_data_dir() if hasattr(system, 'get_data_dir') else getattr(django_settings, 'TS_EXPORTS_DIR', r'C\\TS_EXPORTS'),
                'created_at': system.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'timeframes': [],
                'data_files': []
            }
            
            # Добавляем информацию о таймфреймах
            for timeframe in system.timeframes.all():
                timeframe_data = {
                    'id': timeframe.id,
                    'open_column': timeframe.open_column,
                    'high_column': timeframe.high_column,
                    'low_column': timeframe.low_column,
                    'close_column': timeframe.close_column,
                    'volume_column': timeframe.volume_column,
                    'datetime_column': timeframe.datetime_column,
                    'datetime_format': timeframe.datetime_format
                }
                system_data['timeframes'].append(timeframe_data)
            
            # Добавляем информацию о файлах данных
            for data_file in system.data_files.all():
                file_data = {
                    'id': data_file.id,
                    'filename': data_file.filename,
                    'file_path': data_file.file_path,
                    'is_processed': data_file.is_processed,
                    'created_at': data_file.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'processed_at': data_file.processed_at.strftime('%Y-%m-%d %H:%M:%S') if data_file.processed_at else None,
                    'json_data': data_file.json_data
                }
                system_data['data_files'].append(file_data)
            
            return JsonResponse({
                'success': True,
                'system': system_data
            })
            
        except TradingSystem.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Trading system not found'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error getting trading system: {str(e)}'
            })
    
    return JsonResponse({
        'success': False,
        'message': 'Method not allowed'
    })


def api_validate_csv_for_system(request, system_id):
    """API для валидации CSV файла согласно конфигурации торговой системы"""
    if request.method == 'POST':
        try:
            # Получаем торговую систему
            system = TradingSystem.objects.get(id=system_id)
            
            # Получаем имя файла из запроса
            filename = request.POST.get('filename')
            if not filename:
                return JsonResponse({
                    'success': False,
                    'message': 'Filename not provided'
                })
            
            # Полный путь к файлу
            file_path = os.path.join(system.get_data_dir() if hasattr(system, 'get_data_dir') else getattr(django_settings, 'TS_EXPORTS_DIR', r'C\\TS_EXPORTS'), filename)
            
            if not os.path.exists(file_path):
                return JsonResponse({
                    'success': False,
                    'message': f'File not found: {filename}'
                })
            
            # Читаем CSV файл
            validation_results = []
            csv_data = []
            
            # Определяем разделитель
            delimiter = ','
            with open(file_path, 'r', encoding='utf-8-sig') as file:
                sample = file.read(1024)
                sniffer = csv.Sniffer()
                try:
                    delimiter = sniffer.sniff(sample).delimiter
                except:
                    delimiter = ','
            
            # Читаем файл
            with open(file_path, 'r', encoding='utf-8-sig') as file:
                reader = csv.reader(file, delimiter=delimiter)
                
                # Читаем заголовки
                try:
                    headers = next(reader)
                except StopIteration:
                    return JsonResponse({
                        'success': False,
                        'message': 'CSV file is empty'
                    })
                
                # Валидируем каждый таймфрейм
                for timeframe in system.timeframes.all():
                    validation_result = {
                        'timeframe_id': timeframe.id,
                        'valid': True,
                        'errors': [],
                        'warnings': []
                    }
                    
                    # Проверяем обязательные колонки
                    required_columns = []
                    if timeframe.open_column:
                        required_columns.append(timeframe.open_column)
                    if timeframe.high_column:
                        required_columns.append(timeframe.high_column)
                    if timeframe.low_column:
                        required_columns.append(timeframe.low_column)
                    if timeframe.close_column:
                        required_columns.append(timeframe.close_column)
                    if timeframe.datetime_column:
                        required_columns.append(timeframe.datetime_column)
                    
                    # Проверяем наличие колонок в заголовках
                    missing_columns = []
                    for col in required_columns:
                        if col not in headers:
                            missing_columns.append(col)
                    
                    if missing_columns:
                        validation_result['valid'] = False
                        validation_result['errors'].append(f'Missing columns: {", ".join(missing_columns)}')
                    
                    # Проверяем объемы (опционально)
                    if timeframe.volume_column and timeframe.volume_column not in headers:
                        validation_result['warnings'].append(f'Volume column "{timeframe.volume_column}" not found')
                    
                    validation_results.append(validation_result)
                
                # Читаем первые несколько строк для примера
                file.seek(0)
                reader = csv.reader(file, delimiter=delimiter)
                next(reader)  # Пропускаем заголовки
                
                row_count = 0
                for row in reader:
                    if row_count >= 5:  # Читаем только первые 5 строк для примера
                        break
                    if row:
                        csv_data.append(row)
                        row_count += 1
            
            return JsonResponse({
                'success': True,
                'filename': filename,
                'system_name': system.name,
                'headers': headers,
                'sample_data': csv_data,
                'validation_results': validation_results,
                'is_valid': all(result['valid'] for result in validation_results)
            })
            
        except TradingSystem.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Trading system not found'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error validating CSV: {str(e)}'
            })
    
    return JsonResponse({
        'success': False,
        'message': 'Method not allowed'
    })


def api_process_csv_to_json(request, system_id):
    """API для обработки CSV файла и конвертации в JSON согласно конфигурации системы"""
    # Legacy CSV preview/import endpoint removed in global-only mode
    return JsonResponse({'success': False, 'message': 'Legacy CSV endpoint disabled (global feed only).'}, status=410)


def ingestion_status_api(request):
    """API endpoint to get data ingestion worker status and KPIs"""
    if request.method == 'GET':
        st = DataIngestionStatus.get()
        return JsonResponse({
            'success': True,
            'active': st.active,
            'scan_interval': st.scan_interval,
            'last_run': st.last_run.isoformat() if st.last_run else None,
            'files_scanned': st.files_scanned,
            'files_imported': st.files_imported,
            'rows_imported': st.rows_imported,
            'last_error': st.last_error or None,
        })
    return JsonResponse({'success': False, 'message': 'Only GET allowed'})


def ingestion_logs_api(request):
    """Return last 20 MarketDataFile changes in global-only mode."""
    if request.method == 'GET':
        from .models import MarketDataFile
        qs = MarketDataFile.objects.all().order_by('-processed_at', '-file_modified')[:20]
        data = []
        for m in qs:
            data.append({
                'filename': m.filename,
                'provider': m.provider,
                'feed': str(m.feed) if m.feed_id else None,
                'status': m.status,
                'file_size': m.file_size,
                'file_modified': m.file_modified.isoformat() if m.file_modified else None,
                'processed_at': m.processed_at.isoformat() if m.processed_at else None,
            })
        return JsonResponse({'success': True, 'logs': data})
    return JsonResponse({'success': False, 'message': 'Only GET allowed'})


def start_ingestion_service(request):
    if request.method == 'POST':
        try:
            from .services.global_ingestion_worker import start_global_ingestion
            start_global_ingestion()
            st = DataIngestionStatus.get()
            st.active = True
            st.save(update_fields=['active', 'updated_at'])
            return JsonResponse({'success': True, 'active': True, 'scan_interval': st.scan_interval})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    return JsonResponse({'success': False, 'message': 'Only POST allowed'})


def raw_signals_overview(request):
    """Raw Signals: compact per-system overview with last bar timestamps per TF."""
    systems_qs = TradingSystem.objects.all().prefetch_related('timeframes')
    # Compute last_dt per TF via TF Binding -> MarketBar
    last_by_tf = {}
    for sys in systems_qs:
        for tf in sys.timeframes.all():
            try:
                bind = TradingSystemTFBinding.objects.filter(trading_system=sys, level=getattr(tf, 'level', None)).select_related('feed').first()
                if bind:
                    last = MarketBar.objects.filter(feed=bind.feed).order_by('-dt').values_list('dt', flat=True).first()
                    if last:
                        last_by_tf[tf.id] = last
            except Exception:
                continue

    systems = []
    for sys in systems_qs:
        tfs = list(sys.timeframes.all())
        tf_infos = []
        for tf in tfs:
            tf_infos.append({
                'id': tf.id,
                'timeframe': getattr(tf, 'timeframe', None),
                'level': getattr(tf, 'level', None),
                'last_dt': last_by_tf.get(tf.id),
                'last_server_dt': last_by_tf.get(tf.id),
            })

        # Build recent signals (last 10) with Close and PnL in pips
        signals_rows = []
        total_pips = 0.0
        try:
            base_level = getattr(sys.signal_settings, 'signal_base_tf_level', None) or 1
        except Exception:
            base_level = 1
        base_tf = next((x for x in tfs if getattr(x, 'level', None) == base_level), None)
        evs = list(SignalEvent.objects.filter(trading_system=sys, level=base_level, action='OPEN').order_by('-event_time')[:11])

        def get_close(ev):
            return _get_close_for_event(ev)

        pip_scale = 100 if 'JPY' in (sys.symbol or '').upper() else 10000
        # We show PnL on the previous (older) signal row, because the trade is closed at the current signal.
        # evs is newest->oldest; for row i>0 we compute PnL between evs[i] (older, opened here) and evs[i-1] (newer, closed here).
        for i, ev in enumerate(evs[:10]):
                close_cur = get_close(ev)
                pnl = None
                if i > 0:
                    newer = evs[i - 1]
                    close_newer = get_close(newer)
                    if close_cur is not None and close_newer is not None:
                        pnl = (close_newer - close_cur) * pip_scale if ev.direction == 'BUY' else (close_cur - close_newer) * pip_scale
                        total_pips += pnl
                signals_rows.append({
                    'time': ev.event_time,
                    'direction': ev.direction,
                    'close': close_cur,
                    'pips': pnl,
                })

        systems.append({
            'id': sys.id,
            'system_sid': sys.system_sid,
            'symbol': sys.symbol,
            'timeframes_count': getattr(sys, 'timeframes_count', len(tfs)),
            'timeframes': tf_infos,
            'signals': signals_rows,
            'signals_total_pips': total_pips,
        })

    return render(request, 'main/raw_signals.html', {'systems': systems})


def stop_ingestion_service(request):
    if request.method == 'POST':
        try:
            from .services.global_ingestion_worker import stop_global_ingestion
            stop_global_ingestion()
            st = DataIngestionStatus.get()
            st.active = False
            st.save(update_fields=['active', 'updated_at'])
            return JsonResponse({'success': True, 'active': False})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    return JsonResponse({'success': False, 'message': 'Only POST allowed'})


# --- Trading history derived from signals ---
def _get_close_for_event(ev):
    # Global feed via event.feed if present, else TF binding
    try:
        if getattr(ev, 'feed_id', None):
            mb = MarketBar.objects.filter(feed_id=ev.feed_id, dt=ev.event_time).first()
            if mb and mb.close is not None:
                return float(mb.close)
        lvl = getattr(ev, 'level', None) or getattr(getattr(ev, 'timeframe', None), 'level', None)
        ts = getattr(ev, 'trading_system', None)
        if ts and lvl:
            bind = TradingSystemTFBinding.objects.filter(trading_system=ts, level=int(lvl)).select_related('feed').first()
            if bind:
                mb = MarketBar.objects.filter(feed=bind.feed, dt=ev.event_time).first()
                if mb and mb.close is not None:
                    return float(mb.close)
    except Exception:
        pass
    return None


def trading_history_ts(request):
    systems = list(TradingSystem.objects.all().order_by('system_sid'))
    system_id = request.GET.get('system')
    tf_level = request.GET.get('tf')
    limit = int(request.GET.get('limit') or 200)

    system = None
    if system_id:
        try:
            system = TradingSystem.objects.get(id=system_id)
        except TradingSystem.DoesNotExist:
            system = None
    if not system and systems:
        system = systems[0]

    trades = []
    total_pips = 0.0
    wins = 0
    total = 0
    selected_tf = None
    base_level = 1
    if system:
        try:
            base_level = getattr(system, 'signal_settings', None).signal_base_tf_level or 1
        except Exception:
            base_level = 1
        if tf_level:
            try:
                base_level = int(tf_level)
            except Exception:
                pass
        # Keep selected_tf only for display; events are filtered by level
        selected_tf = TimeFrame.objects.filter(trading_system=system, level=base_level).first()

        # Use the same source as admin: persisted SignalEvent rows,
        # additionally filtered by the bound feed for this TF level (if any).
        fetch_n = max(2 * limit + 10, 50)
        qs = SignalEvent.objects.filter(trading_system=system, level=base_level)
        try:
            bind = TradingSystemTFBinding.objects.filter(trading_system=system, level=base_level).select_related('feed').first()
            if bind and bind.feed_id:
                qs = qs.filter(feed_id=bind.feed_id)
        except Exception:
            pass
        evs = list(qs.order_by('-event_time')[:fetch_n])
        evs = list(reversed(evs))  # oldest→newest for sequential pairing

        pip_scale = 100 if 'JPY' in (system.symbol or '').upper() else 10000
        open_ev = None
        for ev in evs:
            if getattr(ev, 'action', 'OPEN') == 'OPEN':
                # start a position if none is open
                if open_ev is None:
                    open_ev = ev
                else:
                    # Fallback to reversal close if explicit CLOSE not present before next OPEN
                    close_ev = ev
                    open_price = _get_close_for_event(open_ev)
                    close_price = _get_close_for_event(close_ev)
                    pnl = None
                    if open_price is not None and close_price is not None:
                        pnl = (close_price - open_price) * pip_scale if open_ev.direction == 'BUY' else (open_price - close_price) * pip_scale
                        total_pips += pnl
                        total += 1
                        if pnl > 0:
                            wins += 1
                    trades.append({
                        'open_time': open_ev.event_time,
                        'open_dir': open_ev.direction,
                        'open_price': open_price,
                        'open_id': getattr(open_ev, 'id', None),
                        'close_time': close_ev.event_time,
                        'close_price': close_price,
                        'close_id': getattr(close_ev, 'id', None),
                        'pips': pnl,
                    })
                    open_ev = ev  # treat this OPEN as start of next trade
            else:  # action == 'CLOSE'
                if open_ev is not None:
                    close_ev = ev
                    open_price = _get_close_for_event(open_ev)
                    close_price = _get_close_for_event(close_ev)
                    pnl = None
                    if open_price is not None and close_price is not None:
                        pnl = (close_price - open_price) * pip_scale if open_ev.direction == 'BUY' else (open_price - close_price) * pip_scale
                        total_pips += pnl
                        total += 1
                        if pnl > 0:
                            wins += 1
                    trades.append({
                        'open_time': open_ev.event_time,
                        'open_dir': open_ev.direction,
                        'open_price': open_price,
                        'open_id': getattr(open_ev, 'id', None),
                        'close_time': close_ev.event_time,
                        'close_price': close_price,
                        'close_id': getattr(close_ev, 'id', None),
                        'pips': pnl,
                    })
                    open_ev = None

    # Keep only last requested number of trades
    trades = trades[-limit:]
    win_rate = (wins / total * 100.0) if total else 0.0

    context = {
        'systems': systems,
        'selected_system': system,
        'selected_tf': selected_tf,
        'base_level': base_level,
        'trades': list(reversed(trades)),
        'total_pips': total_pips,
        'win_rate': win_rate,
        'total_trades': total,
    }
    return render(request, 'main/trading_history_ts.html', context)


def trading_history_mt5(request):
    systems = list(MT5ConnectionSettings.objects.all().order_by('-is_default', 'name'))
    systems_magic = list(TradingSystem.objects.filter(magic_number__isnull=False).order_by('system_sid'))
    settings_id = request.GET.get('conn')
    sys_magic_id = request.GET.get('sys')
    days = int(request.GET.get('days') or 7)
    selected = None
    if settings_id:
        try:
            selected = MT5ConnectionSettings.objects.get(id=settings_id)
        except MT5ConnectionSettings.DoesNotExist:
            selected = None
    if not selected and systems:
        selected = systems[0]

    deals = []
    summary = {'trades': 0, 'profit': 0.0}
    error = None
    selected_system = None
    selected_magic = None
    if sys_magic_id:
        try:
            selected_system = TradingSystem.objects.get(id=sys_magic_id)
            selected_magic = selected_system.magic_number
        except TradingSystem.DoesNotExist:
            selected_system = None
    if selected:
        try:
            from .services.mt5_service import MT5Service
            from datetime import datetime, timedelta, timezone as dt_tz
            import MetaTrader5 as mt5
            with MT5Service(selected) as svc:
                if svc.is_connected:
                    try:
                        acc = mt5.account_info()
                        context_account_login = getattr(acc, 'login', None)
                    except Exception:
                        context_account_login = None
                    # Direct calls history_deals_get with different variants (no history_select)
                    raw = []
                    attempts = []

                    def try_direct(frm, to, label):
                        try:
                            res = mt5.history_deals_get(frm, to)
                        except Exception:
                            res = None
                        cnt = len(res) if res else 0
                        attempts.append((label, cnt))
                        return res or []

                    try:
                        import calendar
                    except Exception:
                        calendar = None

                    now_local = datetime.now()
                    now_utc_naive = datetime.utcnow()
                    now_utc_aware = now_utc_naive.replace(tzinfo=dt_tz.utc)

                    # 1) Local naive
                    raw = try_direct(now_local - timedelta(days=days), now_local, 'local-naive-dt')
                    # 2) Naive UTC
                    if not raw:
                        raw = try_direct(now_utc_naive - timedelta(days=days), now_utc_naive, 'utc-naive-dt')
                    # 3) Aware UTC
                    if not raw:
                        raw = try_direct(now_utc_aware - timedelta(days=days), now_utc_aware, 'utc-aware-dt')
                    # 4) Epoch seconds UTC
                    if not raw and calendar is not None:
                        try:
                            frm_ts = calendar.timegm((now_utc_naive - timedelta(days=days)).timetuple())
                            to_ts = calendar.timegm(now_utc_naive.timetuple())
                            raw = try_direct(frm_ts, to_ts, 'utc-epoch-seconds')
                        except Exception:
                            pass
                    # 5) Wider margin
                    if not raw:
                        raw = try_direct(now_local - timedelta(days=days+1), now_local + timedelta(days=1), 'local-margin')

                    if not raw:
                        err = mt5.last_error()
                        error = f"No deals for period. last_error: {err}; attempts={attempts}"
                    for d in raw:
                        # Filter only buy/sell (ignore balance operations)
                        t = getattr(d, 'type', None)
                        typ = 'BUY' if t == 0 else ('SELL' if t == 1 else None)
                        if not typ:
                            continue
                        if selected_magic is not None and getattr(d, 'magic', None) != selected_magic:
                            continue
                        # d.time is in seconds (broker server time). Keep naive local display or convert to UTC consistently.
                        deals.append({
                            'time': datetime.fromtimestamp(getattr(d, 'time', 0) or 0),
                            'symbol': d.symbol,
                            'direction': typ,
                            'volume': float(getattr(d, 'volume', 0) or 0),
                            'price': float(getattr(d, 'price', 0) or 0),
                            'profit': float(getattr(d, 'profit', 0) or 0),
                            'comment': getattr(d, 'comment', ''),
                            'ticket': getattr(d, 'ticket', None),
                            'magic': getattr(d, 'magic', None),
                        })
                        summary['trades'] += 1
                        summary['profit'] += float(getattr(d, 'profit', 0) or 0)
                else:
                    error = 'MT5 connection failed'
        except Exception as e:
            error = str(e)

    context = {
        'connections': systems,
        'systems_magic': systems_magic,
        'selected_system_magic': selected_system,
        'selected_conn': selected,
        'days': days,
        'deals': sorted(deals, key=lambda x: x['time'], reverse=True)[:500],
        'summary': summary,
        'error': error,
        'connected_login': locals().get('context_account_login'),
    }
    return render(request, 'main/trading_history_mt5.html', context)


def trading_home(request):
    systems = TradingSystem.objects.all().order_by('system_sid')
    context = {
        'systems_count': systems.count(),
    }
    return render(request, 'main/trading_home.html', context)


@ensure_csrf_cookie
def trading_positions(request):
    """Show current open positions from MetaTrader 5."""
    positions = []
    error = None
    account = None

    try:
        service = MT5Manager.get_default_service()
        if not service:
            error = 'Default MT5 connection settings are not configured.'
        else:
            with service as svc:
                if svc.is_connected:
                    account = svc.get_account_info()
                    positions = svc.get_open_positions()
                else:
                    error = 'Failed to connect to MT5.'
    except Exception as e:
        error = str(e)

    context = {
        'positions': positions,
        'account': account,
        'error': error,
    }
    return render(request, 'main/trading_positions.html', context)


# --- Manual trading API ---
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie


@require_POST
def mt5_trade_buy(request):
    symbol = request.POST.get('symbol') or request.GET.get('symbol') or 'EURUSD'
    try:
        volume = float(request.POST.get('volume') or request.GET.get('volume') or 0.01)
    except Exception:
        volume = 0.01
    service = MT5Manager.get_default_service()
    if not service:
        return JsonResponse({'success': False, 'message': 'Default MT5 settings not configured'})

    with service as svc:
        if not svc.is_connected:
            return JsonResponse({'success': False, 'message': 'Failed to connect to MT5'})
        res = svc.market_buy(symbol, volume)
        return JsonResponse(res)


@require_POST
def mt5_trade_sell(request):
    symbol = request.POST.get('symbol') or request.GET.get('symbol') or 'EURUSD'
    try:
        volume = float(request.POST.get('volume') or request.GET.get('volume') or 0.01)
    except Exception:
        volume = 0.01
    service = MT5Manager.get_default_service()
    if not service:
        return JsonResponse({'success': False, 'message': 'Default MT5 settings not configured'})

    with service as svc:
        if not svc.is_connected:
            return JsonResponse({'success': False, 'message': 'Failed to connect to MT5'})
        res = svc.market_sell(symbol, volume)
        return JsonResponse(res)


@require_POST
def mt5_close_all(request):
    side = request.POST.get('side') or request.GET.get('side')
    if side:
        side = side.upper()
        if side not in ('BUY', 'SELL'):
            side = None
    service = MT5Manager.get_default_service()
    if not service:
        return JsonResponse({'success': False, 'message': 'Default MT5 settings not configured'})
    with service as svc:
        if not svc.is_connected:
            return JsonResponse({'success': False, 'message': 'Failed to connect to MT5'})
        res = svc.close_all(only_type=side)
        return JsonResponse(res)


@require_POST
def mt5_close_position(request):
    try:
        ticket = int(request.POST.get('ticket') or request.GET.get('ticket'))
    except Exception:
        return JsonResponse({'success': False, 'message': 'Ticket is required'})
    service = MT5Manager.get_default_service()
    if not service:
        return JsonResponse({'success': False, 'message': 'Default MT5 settings not configured'})
    with service as svc:
        if not svc.is_connected:
            return JsonResponse({'success': False, 'message': 'Failed to connect to MT5'})
        res = svc.close_position(ticket)
        return JsonResponse(res)


@ensure_csrf_cookie
def system_trading(request):
    systems = TradingSystem.objects.all().order_by('system_sid')
    return render(request, 'main/system_trading.html', { 'systems': systems })


from django.views.decorators.http import require_POST

@require_POST
def api_system_trading_update(request):
    try:
        sid = int(request.POST.get('id'))
    except Exception:
        return JsonResponse({'success': False, 'message': 'Invalid system id'})
    enabled_raw = request.POST.get('enabled')
    lot_raw = request.POST.get('lot')
    try:
        sys = TradingSystem.objects.get(id=sid)
    except TradingSystem.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'System not found'})
    # Parse values
    enabled = True if str(enabled_raw) in ('1', 'true', 'True', 'on') else False
    try:
        lot = float((lot_raw or '0.01').replace(',', '.'))
        if lot <= 0:
            raise ValueError('Lot must be positive')
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Invalid lot: {e}'})
    # Save
    sys.trading_enabled = enabled
    sys.lot_size = lot
    sys.save(update_fields=['trading_enabled', 'lot_size'])
    return JsonResponse({'success': True})


from django.views.decorators.http import require_GET

@require_GET
def api_system_positions(request):
    try:
        sid = int(request.GET.get('id'))
    except Exception:
        return JsonResponse({'success': False, 'message': 'Invalid system id'})
    try:
        sys = TradingSystem.objects.get(id=sid)
    except TradingSystem.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'System not found'})
    try:
        service = MT5Manager.get_default_service()
        if not service:
            return JsonResponse({'success': False, 'message': 'MT5 default service not configured'})
        positions = []
        from datetime import datetime as _dt
        with service as svc:
            if svc.is_connected:
                sys_magic = getattr(sys, 'magic_number', None)
                raw = svc.get_open_positions_for(symbol=sys.symbol, magic=sys_magic)
                # Fallback: if ничего не нашли по magic, попробуем по одному символу (включая manual trades с magic=0)
                if not raw:
                    raw = svc.get_open_positions_for(symbol=sys.symbol, magic=None)
                # Normalize datetime for JSON
                for p in raw:
                    q = dict(p)
                    t = q.get('time')
                    if hasattr(t, 'strftime'):
                        q['time'] = t.strftime('%Y-%m-%d %H:%M:%S')
                    positions.append(q)
        return JsonResponse({'success': True, 'positions': positions})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@require_GET
def api_system_deals(request):
    try:
        sid = int(request.GET.get('id'))
    except Exception:
        return JsonResponse({'success': False, 'message': 'Invalid system id'})
    days = int(request.GET.get('days') or 7)
    try:
        sys = TradingSystem.objects.get(id=sid)
    except TradingSystem.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'System not found'})

    try:
        import MetaTrader5 as mt5
        from datetime import datetime, timedelta, timezone as dt_tz
        service = MT5Manager.get_default_service()
        deals = []
        with service as svc:
            if svc and svc.is_connected:
                to_naive_utc = datetime.utcnow()
                from_naive_utc = to_naive_utc - timedelta(days=days)
                raw = mt5.history_deals_get(from_naive_utc, to_naive_utc) or []
                magic = getattr(sys, 'magic_number', None)
                # 1) Сначала пробуем строгий фильтр symbol+magic
                strict = []
                for d in raw:
                    t = getattr(d, 'type', None)
                    typ = 'BUY' if t == 0 else ('SELL' if t == 1 else None)
                    if not typ:
                        continue
                    if getattr(d, 'symbol', '') != (sys.symbol or ''):
                        continue
                    if magic is not None and getattr(d, 'magic', None) != magic:
                        continue
                    strict.append(d)
                used = strict
                # 2) Если ничего не нашли по magic, ослабляем до symbol-only (поддержка ручных сделок с magic=0)
                if magic is not None and not strict:
                    used = [d for d in raw if getattr(d, 'symbol', '') == (sys.symbol or '') and getattr(d, 'type', None) in (0, 1)]
                for d in used:
                    t = getattr(d, 'type', None)
                    typ = 'BUY' if t == 0 else ('SELL' if t == 1 else None)
                    deals.append({
                        'time': datetime.fromtimestamp(getattr(d, 'time', 0) or 0).strftime('%Y-%m-%d %H:%M:%S'),
                        'symbol': d.symbol,
                        'direction': typ,
                        'volume': float(getattr(d, 'volume', 0) or 0),
                        'price': float(getattr(d, 'price', 0) or 0),
                        'profit': float(getattr(d, 'profit', 0) or 0),
                        'ticket': getattr(d, 'ticket', None),
                    })
        return JsonResponse({'success': True, 'deals': deals[:500]})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})




