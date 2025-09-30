"""
Django management command to start MT5 connection monitoring

Usage:
    python manage.py mt5_monitor [--interval=30] [--foreground]
"""

import signal
import sys
import time
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from main.services.mt5_monitor import start_monitoring, stop_monitoring, get_monitor
from main.models import MT5MonitoringSettings


class Command(BaseCommand):
    help = 'Start MT5 connection monitoring service'

    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=30,
            help='Health check interval in seconds (default: 30)'
        )
        parser.add_argument(
            '--foreground',
            action='store_true',
            help='Run in foreground (for development/testing)'
        )
        parser.add_argument(
            '--stop',
            action='store_true',
            help='Stop monitoring service'
        )

    def handle(self, *args, **options):
        if options['stop']:
            self.stdout.write("Stopping MT5 monitoring service...")
            stop_monitoring()
            self.stdout.write(
                self.style.SUCCESS('MT5 monitoring service stopped.')
            )
            return

        # Update monitoring settings with provided interval
        if options['interval'] != 30:
            monitoring_settings = MT5MonitoringSettings.get_settings()
            monitoring_settings.health_check_interval = options['interval']
            monitoring_settings.save()
            self.stdout.write(f"Updated health check interval to {options['interval']} seconds")

        self.stdout.write("Starting MT5 monitoring service...")
        
        # Set up signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            self.stdout.write("\nReceived shutdown signal. Stopping monitoring...")
            stop_monitoring()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        try:
            # Start monitoring
            start_monitoring()
            
            monitor = get_monitor()
            if monitor.monitoring_active:
                self.stdout.write(
                    self.style.SUCCESS('MT5 monitoring service started successfully.')
                )
                
                if options['foreground']:
                    self.stdout.write("Running in foreground. Press Ctrl+C to stop.")
                    try:
                        while monitor.monitoring_active:
                            time.sleep(1)
                    except KeyboardInterrupt:
                        self.stdout.write("\nStopping monitoring service...")
                        stop_monitoring()
                        self.stdout.write(
                            self.style.SUCCESS('MT5 monitoring service stopped.')
                        )
                else:
                    self.stdout.write("Service is running in background.")
                    self.stdout.write("Use 'python manage.py mt5_monitor --stop' to stop the service.")
            else:
                self.stdout.write(
                    self.style.ERROR('Failed to start MT5 monitoring service.')
                )
                
        except Exception as e:
            raise CommandError(f'Error starting monitoring service: {str(e)}')