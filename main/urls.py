from django.urls import path
from . import views

app_name = 'main'

urlpatterns = [
    path('', views.home, name='home'),
    path('trading-history/', views.trading_history, name='trading_history'),
    path('system-dashboard/', views.system_dashboard, name='system_dashboard'),
    path('raw-signals/', views.raw_signals, name='raw_signals'),
    path('api/mt5/connect/', views.connect_mt5, name='mt5_connect'),
    path('api/mt5/disconnect/', views.disconnect_mt5, name='mt5_disconnect'),
    path('api/mt5/status/', views.mt5_status_api, name='mt5_status_api'),
    path('api/monitoring/status/', views.get_monitoring_status_api, name='monitoring_status'),
    path('api/monitoring/start/', views.start_monitoring_service, name='start_monitoring'),
    path('api/monitoring/stop/', views.stop_monitoring_service, name='stop_monitoring'),
    path('api/csv/files/', views.get_csv_files_api, name='csv_files_api'),
    path('api/csv/data/', views.get_csv_data_api, name='csv_data_api'),
]