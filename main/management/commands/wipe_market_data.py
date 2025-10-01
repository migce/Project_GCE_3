from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from ...models import Bar, IndicatorValue, DataFile, ImportLog, DataIngestionStatus


class Command(BaseCommand):
    help = "Clear imported market data (bars, indicator values, import logs) and reset ingestion status. Keeps trading systems and timeframes."

    def add_arguments(self, parser):
        parser.add_argument('--delete-files', action='store_true', help='Delete DataFile rows (will be re-collected). By default, files are kept and reset to pending.')

    def handle(self, *args, **options):
        delete_files = options.get('delete_files', False)
        with transaction.atomic():
            iv_cnt = IndicatorValue.objects.count()
            IndicatorValue.objects.all().delete()

            bar_cnt = Bar.objects.count()
            Bar.objects.all().delete()

            log_cnt = ImportLog.objects.count()
            ImportLog.objects.all().delete()

            if delete_files:
                df_cnt = DataFile.objects.count()
                DataFile.objects.all().delete()
            else:
                qs = DataFile.objects.all()
                df_cnt = qs.count()
                qs.update(status='pending', rows_processed=None, processed_at=None, error_message='')

            st = DataIngestionStatus.get()
            st.files_scanned = 0
            st.files_imported = 0
            st.rows_imported = 0
            st.last_run = None
            st.last_error = ''
            st.save()

        self.stdout.write(self.style.SUCCESS(
            f"Cleared: Bars={bar_cnt}, IndicatorValues={iv_cnt}, ImportLogs={log_cnt}, DataFiles={'deleted' if delete_files else df_cnt}"
        ))

