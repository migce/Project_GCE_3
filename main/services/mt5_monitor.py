"""
MT5 Connection Monitoring Service

This service handles:
- Regular health checks of MT5 connections
- Automatic reconnection when connections are lost
- Logging of connection status and performance metrics
- Alert notifications when connections fail
"""

import logging
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from django.utils import timezone
from django.conf import settings
from django.db import models
from django.db import close_old_connections, OperationalError, transaction

from ..models import (
    MT5ConnectionSettings, 
    MT5ConnectionHealth, 
    MT5MonitoringSettings
)
from .mt5_service import MT5Service

logger = logging.getLogger(__name__)


class MT5ConnectionMonitor:
    """Service for monitoring MT5 connections and health"""
    
    def __init__(self):
        self.monitoring_active = False
        self.monitor_thread = None
        self.reconnect_attempts = {}  # Track reconnection attempts per connection
    
    def start_monitoring(self):
        """Start the monitoring service"""
        if self.monitoring_active:
            logger.warning("Monitoring is already active")
            return
        
        monitoring_settings = MT5MonitoringSettings.get_settings()
        if not monitoring_settings.monitoring_enabled:
            logger.info("Monitoring is disabled in settings")
            return
        
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            name="MT5-Monitor",
            daemon=True
        )
        self.monitor_thread.start()
        logger.info("MT5 monitoring service started")
    
    def stop_monitoring(self):
        """Stop the monitoring service"""
        self.monitoring_active = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        logger.info("MT5 monitoring service stopped")
    
    def _monitoring_loop(self):
        """Main monitoring loop"""
        monitoring_settings = MT5MonitoringSettings.get_settings()
        
        while self.monitoring_active:
            try:
                close_old_connections()
                # Refresh settings each loop
                monitoring_settings = MT5MonitoringSettings.get_settings()
                
                if not monitoring_settings.monitoring_enabled:
                    logger.info("Monitoring disabled, stopping...")
                    break
                
                # Check all active connections
                active_connections = MT5ConnectionSettings.objects.filter(is_active=True)
                
                for connection in active_connections:
                    self._check_connection_health(connection, monitoring_settings)
                
                # Clean up old health records
                self._cleanup_old_records(monitoring_settings)
                
                # Sleep until next check
                time.sleep(monitoring_settings.health_check_interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {str(e)}")
                time.sleep(10)  # Wait before retrying
        
        self.monitoring_active = False
    
    def _check_connection_health(self, connection: MT5ConnectionSettings, monitoring_settings: MT5MonitoringSettings):
        """Check health of a single connection"""
        start_time = time.time()
        
        try:
            service = MT5Service(connection)
            
            # Attempt connection
            is_connected = service.connect()
            ping_ms = int((time.time() - start_time) * 1000)
            
            health_record = MT5ConnectionHealth(
                settings=connection,
                is_connected=is_connected,
                ping_ms=ping_ms
            )
            
            if is_connected:
                # Get account information
                account_info = service.get_account_info()
                
                if account_info:
                    health_record.balance = account_info.get('balance')
                    health_record.equity = account_info.get('equity')
                    health_record.margin = account_info.get('margin')
                    
                    # Update connection settings with latest data
                    connection.balance = health_record.balance
                    connection.equity = health_record.equity
                    connection.last_connection_time = timezone.now()
                    connection.save()
                
                # Reset reconnection attempts counter
                self.reconnect_attempts[connection.id] = 0
                
                service.disconnect()
                logger.debug(f"Health check OK for {connection.name}: {ping_ms}ms")
                
            else:
                # Connection failed
                health_record.error_message = "Failed to connect to MT5"
                logger.warning(f"Health check FAILED for {connection.name}")
                
                # Attempt auto-reconnection if enabled
                if monitoring_settings.auto_reconnect_enabled:
                    self._attempt_reconnection(connection, monitoring_settings)
            
            # Decide whether to persist a health record to reduce volume
            should_save = True
            try:
                if monitoring_settings.store_changes_only:
                    last = MT5ConnectionHealth.objects.filter(settings=connection).only('is_connected', 'ping_ms', 'check_time').order_by('-check_time').first()
                    if last is not None:
                        now = timezone.now()
                        delta_sec = (now - last.check_time).total_seconds()
                        # State change always persists
                        state_changed = bool(last.is_connected != is_connected)
                        # Consider ping change significant if threshold exceeded and both pings present
                        ping_changed = False
                        try:
                            if last.ping_ms is not None and ping_ms is not None:
                                ping_changed = abs(int(last.ping_ms) - int(ping_ms)) >= int(monitoring_settings.ping_delta_threshold_ms or 0)
                        except Exception:
                            ping_changed = False
                        # Snapshot policies
                        if is_connected:
                            need_snapshot = delta_sec >= int(monitoring_settings.snapshot_interval_connected_sec or 600)
                        else:
                            # When disconnected, keep a sparse record every min_record_interval_sec
                            need_snapshot = delta_sec >= int(monitoring_settings.min_record_interval_sec or 60)
                        should_save = state_changed or ping_changed or need_snapshot or (delta_sec >= 10 * int(monitoring_settings.health_check_interval or 30))
            except Exception:
                should_save = True

            if should_save:
                for attempt in range(3):
                    try:
                        close_old_connections()
                        with transaction.atomic():
                            health_record.save()
                        break
                    except OperationalError as oe:
                        if 'locked' in str(oe).lower() and attempt < 2:
                            time.sleep(0.1 * (attempt + 1))
                            continue
                        raise
            else:
                logger.debug(f"Health record suppressed for {connection.name} (stable)")
            
        except Exception as e:
            # Save failed health record
            health_record = MT5ConnectionHealth(
                settings=connection,
                is_connected=False,
                ping_ms=None,
                error_message=str(e)
            )
            try:
                last = MT5ConnectionHealth.objects.filter(settings=connection).only('is_connected', 'check_time').order_by('-check_time').first()
                should_save_err = True
                if last is not None and last.is_connected is False:
                    # Collapse repeated error logs within min_record_interval_sec
                    delta_sec = (timezone.now() - last.check_time).total_seconds()
                    should_save_err = delta_sec >= int(MT5MonitoringSettings.get_settings().min_record_interval_sec or 60)
                if should_save_err:
                    for attempt in range(3):
                        try:
                            close_old_connections()
                            with transaction.atomic():
                                health_record.save()
                            break
                        except OperationalError as oe:
                            if 'locked' in str(oe).lower() and attempt < 2:
                                time.sleep(0.1 * (attempt + 1))
                                continue
                            raise
            except Exception:
                try:
                    close_old_connections()
                    health_record.save()
                except Exception:
                    pass
            
            logger.error(f"Health check error for {connection.name}: {str(e)}")
    
    def _attempt_reconnection(self, connection: MT5ConnectionSettings, monitoring_settings: MT5MonitoringSettings):
        """Attempt to reconnect a failed connection"""
        connection_id = connection.id
        
        # Initialize reconnection attempts if not exists
        if connection_id not in self.reconnect_attempts:
            self.reconnect_attempts[connection_id] = 0
        
        # Check if we've exceeded max attempts
        if self.reconnect_attempts[connection_id] >= monitoring_settings.max_reconnect_attempts:
            logger.warning(f"Max reconnection attempts reached for {connection.name}")
            return
        
        # Increment attempt counter
        self.reconnect_attempts[connection_id] += 1
        
        logger.info(f"Attempting reconnection {self.reconnect_attempts[connection_id]}/{monitoring_settings.max_reconnect_attempts} for {connection.name}")
        
        try:
            service = MT5Service(connection)
            if service.connect():
                logger.info(f"Reconnection successful for {connection.name}")
                
                # Update connection data
                account_info = service.get_account_info()
                if account_info:
                    connection.balance = account_info.get('balance')
                    connection.equity = account_info.get('equity')
                    connection.last_connection_time = timezone.now()
                    connection.save()
                
                service.disconnect()
                
                # Reset attempts counter on success
                self.reconnect_attempts[connection_id] = 0
                
                # Log successful reconnection
                from ..models import MT5ConnectionLog
                MT5ConnectionLog.objects.create(
                    settings=connection,
                    success=True,
                    account_info=account_info
                )
                
            else:
                logger.warning(f"Reconnection failed for {connection.name}")
                
        except Exception as e:
            logger.error(f"Reconnection error for {connection.name}: {str(e)}")
    
    def _cleanup_old_records(self, monitoring_settings: MT5MonitoringSettings):
        """Clean up old health records"""
        try:
            cutoff_date = timezone.now() - timedelta(days=monitoring_settings.health_records_retention_days)
            
            deleted_count = MT5ConnectionHealth.objects.filter(
                check_time__lt=cutoff_date
            ).delete()[0]
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old health records")
        except Exception as e:
            logger.error(f"Error cleaning up old records: {str(e)}")


# Global monitor instance
_monitor_instance = None

def get_monitor() -> MT5ConnectionMonitor:
    """Get or create the global monitor instance"""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = MT5ConnectionMonitor()
    return _monitor_instance

def start_monitoring():
    """Start the global monitoring service"""
    monitor = get_monitor()
    monitor.start_monitoring()

def stop_monitoring():
    """Stop the global monitoring service"""
    monitor = get_monitor()
    monitor.stop_monitoring()
