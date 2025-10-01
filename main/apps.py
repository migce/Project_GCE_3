from django.apps import AppConfig
import logging
import sys
from django.db.models.signals import post_migrate

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
    
    def _initialize_monitoring_settings(self):
        """Initialize monitoring settings without auto-starting"""
        try:
            from .models import MT5MonitoringSettings
            monitoring_settings = MT5MonitoringSettings.get_settings()
            logger.info(f"Monitoring settings present - enabled: {monitoring_settings.monitoring_enabled}")
        except Exception as e:
            logger.debug(f"Monitoring settings not available yet: {e}")
