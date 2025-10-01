from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from .models import MT5ConnectionSettings, MT5ConnectionLog, TradingSystem, TimeFrame, DataFile, DataIngestionStatus
from django.conf import settings as django_settings
from .services.mt5_service import MT5Service
import sys
import platform
from datetime import datetime
import os
import csv
import glob
from pathlib import Path
import json

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
            
            # Определяем разделитель
            delimiter = ','
            with open(file_path, 'r', encoding='utf-8-sig') as file:
                sample = file.read(1024)
                sniffer = csv.Sniffer()
                try:
                    delimiter = sniffer.sniff(sample).delimiter
                except:
                    delimiter = ','
            
            # Обрабатываем файл
            processed_data = {
                'system_info': {
                    'system_sid': system.system_sid,
                    'name': system.name,
                    'symbol': system.symbol,
                    'timeframes_count': system.timeframes_count,
                    'time_offset_minutes': system.time_offset_minutes
                },
                'timeframes': {}
            }
            
            # Читаем CSV файл
            with open(file_path, 'r', encoding='utf-8-sig') as file:
                reader = csv.DictReader(file, delimiter=delimiter)
                
                # Обрабатываем каждый таймфрейм
                for timeframe in system.timeframes.all():
                    timeframe_data = []
                    file.seek(0)
                    reader = csv.DictReader(file, delimiter=delimiter)
                    
                    for row in reader:
                        if not any(row.values()):  # Пропускаем пустые строки
                            continue
                        
                        try:
                            # Формируем данные OHLC
                            ohlc_data = {}
                            
                            if timeframe.datetime_column and timeframe.datetime_column in row:
                                ohlc_data['datetime'] = row[timeframe.datetime_column]
                            
                            if timeframe.open_column and timeframe.open_column in row:
                                ohlc_data['open'] = float(row[timeframe.open_column]) if row[timeframe.open_column] else None
                            
                            if timeframe.high_column and timeframe.high_column in row:
                                ohlc_data['high'] = float(row[timeframe.high_column]) if row[timeframe.high_column] else None
                            
                            if timeframe.low_column and timeframe.low_column in row:
                                ohlc_data['low'] = float(row[timeframe.low_column]) if row[timeframe.low_column] else None
                            
                            if timeframe.close_column and timeframe.close_column in row:
                                ohlc_data['close'] = float(row[timeframe.close_column]) if row[timeframe.close_column] else None
                            
                            if timeframe.volume_column and timeframe.volume_column in row:
                                ohlc_data['volume'] = float(row[timeframe.volume_column]) if row[timeframe.volume_column] else None
                            
                            timeframe_data.append(ohlc_data)
                            
                        except (ValueError, TypeError) as e:
                            # Пропускаем строки с ошибками преобразования
                            continue
                    
                    processed_data['timeframes'][f'timeframe_{timeframe.id}'] = {
                        'config': {
                            'open_column': timeframe.open_column,
                            'high_column': timeframe.high_column,
                            'low_column': timeframe.low_column,
                            'close_column': timeframe.close_column,
                            'volume_column': timeframe.volume_column,
                            'datetime_column': timeframe.datetime_column,
                            'datetime_format': timeframe.datetime_format
                        },
                        'data': timeframe_data
                    }
            
            # Сохраняем обработанный файл в базу данных
            data_file, created = DataFile.objects.get_or_create(
                trading_system=system,
                filename=filename,
                defaults={
                    'file_path': file_path,
                    'json_data': processed_data,
                    'is_processed': True,
                    'processed_at': timezone.now()
                }
            )
            
            if not created:
                # Обновляем существующий файл
                data_file.json_data = processed_data
                data_file.is_processed = True
                data_file.processed_at = timezone.now()
                data_file.save()
            
            return JsonResponse({
                'success': True,
                'filename': filename,
                'system_name': system.name,
                'processed_data': processed_data,
                'data_file_id': data_file.id,
                'total_records': sum(len(tf['data']) for tf in processed_data['timeframes'].values())
            })
            
        except TradingSystem.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Trading system not found'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error processing CSV: {str(e)}'
            })
    
    return JsonResponse({
        'success': False,
        'message': 'Method not allowed'
    })


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


def start_ingestion_service(request):
    if request.method == 'POST':
        try:
            from .services.ingestion_worker import start_ingestion
            start_ingestion()
            st = DataIngestionStatus.get()
            st.active = True
            st.save(update_fields=['active', 'updated_at'])
            return JsonResponse({'success': True, 'active': True, 'scan_interval': st.scan_interval})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    return JsonResponse({'success': False, 'message': 'Only POST allowed'})


def stop_ingestion_service(request):
    if request.method == 'POST':
        try:
            from .services.ingestion_worker import stop_ingestion
            stop_ingestion()
            st = DataIngestionStatus.get()
            st.active = False
            st.save(update_fields=['active', 'updated_at'])
            return JsonResponse({'success': True, 'active': False})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    return JsonResponse({'success': False, 'message': 'Only POST allowed'})

