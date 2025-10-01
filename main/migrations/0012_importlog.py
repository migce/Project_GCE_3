from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0011_dataingestionstatus'),
    ]

    operations = [
        migrations.CreateModel(
            name='ImportLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('filename', models.CharField(max_length=255)),
                ('action', models.CharField(choices=[('imported', 'Imported'), ('no_change', 'No Change'), ('error', 'Error')], max_length=20)),
                ('rows_imported', models.IntegerField(default=0)),
                ('message', models.TextField(blank=True)),
                ('file_size', models.PositiveIntegerField(null=True, blank=True)),
                ('file_modified', models.DateTimeField(null=True, blank=True)),
                ('trading_system', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='main.tradingsystem')),
                ('timeframe', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='main.timeframe')),
                ('data_file', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='main.datafile')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='importlog',
            index=models.Index(fields=['-created_at'], name='main_importlog_created_desc_idx'),
        ),
        migrations.AddIndex(
            model_name='importlog',
            index=models.Index(fields=['action', '-created_at'], name='main_importlog_action_created_idx'),
        ),
    ]

