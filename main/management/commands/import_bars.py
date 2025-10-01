"""
Import bars and indicator values from DataFile into database.

Usage examples:
  python manage.py import_bars --file-id 123
  python manage.py import_bars --system-id 1 --pending
  python manage.py import_bars --all-pending
"""

from django.core.management.base import BaseCommand, CommandError

from main.models import DataFile, TradingSystem
from main.services.bar_importer import import_datafile


class Command(BaseCommand):
    help = 'Import bars from DataFile(s) into database.'

    def add_arguments(self, parser):
        parser.add_argument('--file-id', type=int, help='DataFile ID to import')
        parser.add_argument('--system-id', type=int, help='TradingSystem ID to limit pending import')
        parser.add_argument('--pending', action='store_true', help='Import only files with status=pending')
        parser.add_argument('--all-pending', action='store_true', help='Import all pending files')

    def handle(self, *args, **options):
        file_id = options.get('file_id')
        system_id = options.get('system_id')
        only_pending = options.get('pending') or options.get('all_pending')

        files_qs = DataFile.objects.all()
        if file_id:
            try:
                files_qs = DataFile.objects.filter(id=file_id)
            except DataFile.DoesNotExist:
                raise CommandError(f'DataFile with id={file_id} not found')
        else:
            if options.get('all_pending'):
                files_qs = files_qs.filter(status='pending')
            elif system_id:
                files_qs = files_qs.filter(trading_system_id=system_id)
                if only_pending:
                    files_qs = files_qs.filter(status='pending')

        total = files_qs.count()
        if total == 0:
            self.stdout.write(self.style.WARNING('No files to import'))
            return

        ok = 0
        failed = 0
        for df in files_qs.order_by('id'):
            try:
                res = import_datafile(df)
                ok += 1
                self.stdout.write(f"OK {df.id} {df.filename}: bars={res.bars_created} indVals={res.indicator_values_created}")
            except Exception as e:
                failed += 1
                self.stderr.write(f"ERROR {df.id} {df.filename}: {e}")

        self.stdout.write(self.style.SUCCESS(f'Finished. Imported: {ok}, Failed: {failed}'))

