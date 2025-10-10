from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0039_mt5monitoring_settings_logging_tuning'),
    ]

    operations = [
        migrations.CreateModel(
            name='MarketImportError',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('row_number', models.PositiveIntegerField(blank=True, null=True)),
                ('column', models.CharField(blank=True, max_length=64)),
                ('message', models.TextField(blank=True)),
                ('data_file', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='import_errors', to='main.marketdatafile')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='marketimporterror',
            index=models.Index(fields=['data_file', '-created_at'], name='main_mierr_file_created_idx'),
        ),
        migrations.AddIndex(
            model_name='marketimporterror',
            index=models.Index(fields=['-created_at'], name='main_mierr_created_desc_idx'),
        ),
    ]

