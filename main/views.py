from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from .models import MT5ConnectionSettings, MT5ConnectionLog
from .services.mt5_service import MT5Service
import sys
import platform
from datetime import datetime
import os
import csv
import glob
from pathlib import Path

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
    
    # TradeStation exports directory
    ts_exports_dir = r'C:\TS_EXPORTS'
    
    context = {
        'ts_exports_dir': ts_exports_dir,
        'directory_exists': os.path.exists(ts_exports_dir)
    }
    
    return render(request, 'main/raw_signals.html', context)


def get_csv_files_api(request):
    """API endpoint to get list of CSV files from TradeStation exports directory"""
    try:
        ts_exports_dir = r'C:\TS_EXPORTS'
        
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
        
        ts_exports_dir = r'C:\TS_EXPORTS'
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
