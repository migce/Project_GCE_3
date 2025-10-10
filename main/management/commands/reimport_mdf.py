from django.core.management.base import BaseCommand, CommandError

from ...models import MarketDataFile, MarketImportError
from ...services.global_importer import import_market_datafile


class Command(BaseCommand):
    help = 'Re-import one or more MarketDataFile records by id or filename substring.'

    def add_arguments(self, parser):
        parser.add_argument('--id', type=int, dest='id', help='MarketDataFile id')
        parser.add_argument('--filename', dest='filename', help='Filename substring match')

    def handle(self, *args, **opts):
        mid = opts.get('id')
        fname = opts.get('filename')
        qs = MarketDataFile.objects.all()
        if mid is not None:
            qs = qs.filter(id=mid)
        if fname:
            qs = qs.filter(filename__icontains=fname)
        qs = list(qs.order_by('id'))
        if not qs:
            raise CommandError('No MarketDataFile found for provided filters')
        for mdf in qs:
            self.stdout.write(self.style.NOTICE(f'Re-importing: {mdf.id} {mdf.filename}'))
            res = import_market_datafile(mdf)
            self.stdout.write(self.style.SUCCESS(f'  Bars: {res.bars_created}, IVs: {res.indicator_values_created}, rows read: {res.rows_read}, skipped: {res.rows_skipped}, parse_errors: {res.parse_errors}'))
            errs = list(MarketImportError.objects.filter(data_file=mdf).order_by('-created_at')[:3])
            if errs:
                self.stdout.write(self.style.WARNING('  Recent errors:'))
                for e in errs:
                    self.stdout.write(f'    - {e.created_at:%Y-%m-%d %H:%M:%S} | {e.message[:160]}')
