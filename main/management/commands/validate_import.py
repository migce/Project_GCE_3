from django.core.management.base import BaseCommand
from django.db.models import Count, Min, Max
from django.utils import timezone

from ...models import (
    MarketBar,
    MarketIndicatorValue,
    MarketIndicatorDef,
    MarketDataFile,
    DataFeed,
    TradingSystem,
    TradingSystemTFBinding,
    SignalEvent,
    MarketImportError,
)


class Command(BaseCommand):
    help = 'Quick integrity and size check for imported market data.'

    def handle(self, *args, **options):
        now = timezone.now()
        self.stdout.write(self.style.NOTICE(f"Integrity check at {now:%Y-%m-%d %H:%M:%S}"))

        ts_count = TradingSystem.objects.count()
        df_count = DataFeed.objects.count()
        bar_count = MarketBar.objects.count()
        iv_count = MarketIndicatorValue.objects.count()
        idef_count = MarketIndicatorDef.objects.count()
        se_count = SignalEvent.objects.count()
        err_count = MarketImportError.objects.count()

        self.stdout.write(f"TradingSystems: {ts_count}")
        self.stdout.write(f"DataFeeds: {df_count}")
        self.stdout.write(f"MarketBars: {bar_count}")
        self.stdout.write(f"IndicatorDefs: {idef_count}")
        self.stdout.write(f"IndicatorValues: {iv_count}")
        self.stdout.write(f"SignalEvents: {se_count}")
        self.stdout.write(f"ImportErrors: {err_count}")

        # Per-feed summary
        self.stdout.write(self.style.NOTICE("Per-feed summary (first 10):"))
        qs = DataFeed.objects.annotate(
            bars_count=Count('bars', distinct=True),
            defs_count=Count('indicators', distinct=True),
        ).values('id', 'provider', 'instrument__symbol', 'tfcode__code', 'bars_count', 'defs_count')[:10]
        for row in qs:
            sym = row.get('instrument__symbol') or '-'
            tf = row.get('tfcode__code') or '-'
            self.stdout.write(f"  Feed {row['id']}: {row['provider']}:{sym}@{tf} -> bars={row['bars_count']}, defs={row['defs_count']}")

        # Time span of bars overall
        span = MarketBar.objects.aggregate(lo=Min('dt'), hi=Max('dt'))
        self.stdout.write(f"Bars time span: {span.get('lo')} .. {span.get('hi')}")

        # Recent import errors (last 5)
        errs = list(MarketImportError.objects.select_related('data_file').order_by('-created_at')[:5])
        if errs:
            self.stdout.write(self.style.WARNING("Recent import errors:"))
            for e in errs:
                self.stdout.write(f"  - {e.created_at:%Y-%m-%d %H:%M:%S} | {e.data_file} | {e.message[:140]}")
        else:
            self.stdout.write("No import errors logged.")

        self.stdout.write(self.style.SUCCESS("Validation finished."))
