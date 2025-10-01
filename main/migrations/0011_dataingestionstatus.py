from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0010_indicatorvalue_tf_level_manual'),
    ]

    operations = [
        migrations.CreateModel(
            name='DataIngestionStatus',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('active', models.BooleanField(default=False)),
                ('scan_interval', models.PositiveIntegerField(default=5, help_text='Scan interval in seconds')),
                ('last_run', models.DateTimeField(blank=True, null=True)),
                ('files_scanned', models.PositiveIntegerField(default=0)),
                ('files_imported', models.PositiveIntegerField(default=0)),
                ('rows_imported', models.PositiveIntegerField(default=0)),
                ('last_error', models.TextField(blank=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Data Ingestion Status',
                'verbose_name_plural': 'Data Ingestion Status',
            },
        ),
    ]

