from django.apps import AppConfig
import logging
import sys

logger = logging.getLogger(__name__)


class MainConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'main'
    
    def ready(self):
        """Called when Django is ready"""
        # Import here to avoid circular imports
        import os
        from django.conf import settings
        
        # Only perform setup during runserver, skip during migrations/shell
        if 'runserver' in sys.argv:
            self._initialize_monitoring_settings()
            logger.info("Django ready - MT5 monitoring will be controlled via web interface")
    
    def _initialize_monitoring_settings(self):
        """Initialize monitoring settings without auto-starting"""
        try:
            from .models import MT5MonitoringSettings
            
            # Ensure monitoring settings exist
            monitoring_settings = MT5MonitoringSettings.get_settings()
            logger.info(f"Monitoring settings initialized - enabled: {monitoring_settings.monitoring_enabled}")
            
            # If monitoring was enabled but service isn't running, user can start it from web interface
            if monitoring_settings.monitoring_enabled:
                logger.info("Monitoring is enabled - use web interface to start service")
                
        except Exception as e:
            logger.warning(f"Could not initialize monitoring settings: {e}")
