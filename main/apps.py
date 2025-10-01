from django.apps import AppConfig
import logging
import os
import sys
import threading
import time
from django.db.models.signals import post_migrate
from django.db.backends.signals import connection_created

logger = logging.getLogger(__name__)


class MainConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'main'
    
    def ready(self):
        """Connect lazy initialization hooks to avoid DB access during app import."""
        def _post_migrate_init(sender, **kwargs):
            try:
                self._initialize_monitoring_settings()
            except Exception as e:
                logger.warning(f"Monitoring settings init skipped: {e}")

        # Use post_migrate hook to avoid touching DB during app import
        post_migrate.connect(_post_migrate_init, sender=self)
        logger.info("Main app ready; monitoring settings will initialize after migrations")

        # Optionally auto-start background services (ingestion + MT5 monitoring)
        try:
            if self._should_autostart():
                threading.Thread(target=self._autostart_services, name='AutostartServices', daemon=True).start()
        except Exception as e:
            logger.debug(f"Autostart scheduling skipped: {e}")

        # Configure SQLite connection pragmas for better concurrency
        def _on_conn_created(sender, connection, **kwargs):
            try:
                if getattr(connection, 'vendor', '') == 'sqlite':
                    cur = connection.cursor()
                    try:
                        cur.execute('PRAGMA journal_mode=WAL;')
                    except Exception:
                        pass
                    try:
                        cur.execute('PRAGMA synchronous=NORMAL;')
                    except Exception:
                        pass
            except Exception as e:
                logger.debug(f"SQLite PRAGMA setup skipped: {e}")

        try:
            connection_created.connect(_on_conn_created)
        except Exception:
            pass
    
    def _initialize_monitoring_settings(self):
        """Initialize monitoring settings without auto-starting"""
        try:
            from .models import MT5MonitoringSettings
            monitoring_settings = MT5MonitoringSettings.get_settings()
            logger.info(f"Monitoring settings present - enabled: {monitoring_settings.monitoring_enabled}")
        except Exception as e:
            logger.debug(f"Monitoring settings not available yet: {e}")

    def _should_autostart(self) -> bool:
        """Detect whether this process should start background services.
        Avoid starting during management commands like migrate/tests and prevent runserver double-start.
        """
        argv = ' '.join(sys.argv).lower()
        management_cmds = (
            'migrate', 'makemigrations', 'collectstatic', 'shell', 'dbshell', 'test', 'loaddata', 'dumpdata'
        )
        if any(cmd in argv for cmd in management_cmds):
            return False
        # Avoid duplicate start in autoreload main process
        if 'runserver' in argv:
            return os.environ.get('RUN_MAIN') == 'true'
        return True

    def _autostart_services(self):
        """Start ingestion and MT5 monitoring services after a short delay."""
        try:
            # Short delay to let Django finish booting and DB get ready
            time.sleep(1.0)
            from django.conf import settings as django_settings

            # Start Data Ingestion Service
            if getattr(django_settings, 'AUTOSTART_INGESTION', True):
                try:
                    from .services.ingestion_worker import start_ingestion
                    start_ingestion()
                    logger.info('Data Ingestion Service autostarted')
                except Exception as e:
                    logger.warning(f'Data Ingestion autostart failed: {e}')

            # Start MT5 Monitoring Service (only if enabled in settings model)
            if getattr(django_settings, 'AUTOSTART_MT5_MONITORING', True):
                try:
                    from .models import MT5MonitoringSettings
                    from .services.mt5_monitor import start_monitoring
                    if MT5MonitoringSettings.get_settings().monitoring_enabled:
                        start_monitoring()
                        logger.info('MT5 Monitoring Service autostarted')
                except Exception as e:
                    logger.warning(f'MT5 Monitoring autostart failed: {e}')
        except Exception as outer:
            logger.debug(f"Autostart thread error: {outer}")
