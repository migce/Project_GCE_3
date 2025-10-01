from django.core.management.base import BaseCommand
from django.utils import timezone

from ...models import TradingSystem
from ...services.signal_engine import generate_signals_for_system
from ...models import SignalEvent


class Command(BaseCommand):
    help = 'Preview generated signals for a trading system using configured Signal Logic.'

    def add_arguments(self, parser):
        parser.add_argument('system_sid', type=str, help='TradingSystem.system_sid')
        parser.add_argument('--limit', type=int, default=200, help='Bars to evaluate (base TF)')
        parser.add_argument('--save', action='store_true', help='Persist generated signals (SignalEvent)')

    def handle(self, *args, **options):
        sid = options['system_sid']
        limit = options['limit']
        try:
            system = TradingSystem.objects.get(system_sid=sid)
        except TradingSystem.DoesNotExist:
            self.stderr.write(self.style.ERROR(f'System {sid} not found'))
            return

        events = generate_signals_for_system(system, limit_bars=limit)
        if not events:
            self.stdout.write('No signals generated')
            return

        if options['save']:
            # De-dup and bulk create
            from django.db import transaction
            with transaction.atomic():
                # unique_together ensures no duplicates
                for ev in events:
                    obj, created = SignalEvent.objects.get_or_create(
                        trading_system=ev.trading_system,
                        timeframe=ev.timeframe,
                        event_time=ev.event_time,
                        direction=ev.direction,
                        defaults={'rule_text': ev.rule_text, 'bar': ev.bar},
                    )
                    if not created and obj.bar_id is None and ev.bar_id:
                        obj.bar = ev.bar
                        obj.save(update_fields=['bar'])
            self.stdout.write(self.style.SUCCESS(f'Saved {len(events)} signals (deduped by unique constraint)'))
        else:
            for ev in events[-50:]:  # print last 50
                self.stdout.write(f"{ev.event_time:%Y-%m-%d %H:%M:%S} {ev.direction} {system.system_sid} {ev.timeframe.timeframe}")
