from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

app_name = 'main'

urlpatterns = [
    path('', views.home, name='home'),
    # Auth
    path('auth/login/', auth_views.LoginView.as_view(template_name='main/login.html'), name='login'),
    path('auth/logout/', views.logout_view, name='logout'),
    path('algo-trading/', views.algo_trading, name='algo_trading'),
    path('manual-trading/', views.manual_trading, name='manual_trading'),
    # Async Trading History entry page with progress bar
    path('trading-history/', views.trading_history_async, name='trading_history'),
    path('trading-history/tradestation/', views.trading_history_ts, name='trading_history_ts'),
    path('trading-history/metatrader/', views.trading_history_mt5, name='trading_history_mt5'),
    path('trading/', views.trading_home, name='trading'),
    path('api/system-trading/update', views.api_system_trading_update, name='api_system_trading_update'),
    path('api/system-trading/positions', views.api_system_positions, name='api_system_positions'),
    path('api/system-trading/deals', views.api_system_deals, name='api_system_deals'),
    # Manual trading API
    path('api/mt5/trade/buy', views.mt5_trade_buy, name='mt5_trade_buy'),
    path('api/mt5/trade/sell', views.mt5_trade_sell, name='mt5_trade_sell'),
    path('api/mt5/trade/close_all', views.mt5_close_all, name='mt5_close_all'),
    path('api/mt5/trade/close_position', views.mt5_close_position, name='mt5_close_position'),
    path('api/mt5/connect/', views.connect_mt5, name='mt5_connect'),
    path('api/mt5/disconnect/', views.disconnect_mt5, name='mt5_disconnect'),
    path('api/mt5/status/', views.mt5_status_api, name='mt5_status_api'),
    path('api/mt5/account-overview/', views.mt5_account_overview, name='mt5_account_overview'),
    path('api/monitoring/status/', views.get_monitoring_status_api, name='monitoring_status'),
    path('api/monitoring/start/', views.start_monitoring_service, name='start_monitoring'),
    path('api/monitoring/stop/', views.stop_monitoring_service, name='stop_monitoring'),
    
    # Data ingestion API
    path('api/ingestion/status/', views.ingestion_status_api, name='ingestion_status'),
    path('api/ingestion/logs/', views.ingestion_logs_api, name='ingestion_logs'),
    path('api/ingestion/start/', views.start_ingestion_service, name='start_ingestion'),
    path('api/ingestion/stop/', views.stop_ingestion_service, name='stop_ingestion'),
    # TS Simulation async API
    path('api/sim/ts/start/', views.api_ts_sim_start, name='api_ts_sim_start'),
    path('api/sim/ts/status/', views.api_ts_sim_status, name='api_ts_sim_status'),
    path('api/sim/ts/result/', views.api_ts_sim_result, name='api_ts_sim_result'),
    # Trading Systems API
    path('api/trading-systems/', views.api_trading_systems, name='api_trading_systems'),
    path('api/trading-systems/<int:system_id>/', views.api_trading_system_detail, name='api_trading_system_detail'),
    path('api/trading-systems/<int:system_id>/validate-csv/', views.api_validate_csv_for_system, name='api_validate_csv'),
    path('api/trading-systems/<int:system_id>/process-csv/', views.api_process_csv_to_json, name='api_process_csv'),
    # MT5 default connection open positions API
    path('api/mt5/open_positions/', views.api_mt5_open_positions, name='api_mt5_open_positions'),
    path('api/mt5/open_positions/stream/', views.api_mt5_open_positions_stream, name='api_mt5_open_positions_stream'),
    path('api/mt5/quotes/', views.api_mt5_quotes, name='api_mt5_quotes'),
    path('api/mt5/ohlc/', views.api_mt5_ohlc, name='api_mt5_ohlc'),
]
