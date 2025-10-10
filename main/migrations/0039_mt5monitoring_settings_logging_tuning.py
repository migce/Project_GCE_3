from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0038_signalevent_cycle_uid'),
    ]

    operations = [
        migrations.AddField(
            model_name='mt5monitoringsettings',
            name='store_changes_only',
            field=models.BooleanField(default=True, help_text='Reduce health log volume by saving only on state/ping changes and periodic snapshots', verbose_name='Store Changes Only'),
        ),
        migrations.AddField(
            model_name='mt5monitoringsettings',
            name='min_record_interval_sec',
            field=models.PositiveIntegerField(default=60, help_text='Minimum spacing between consecutive health records per connection when disconnected', verbose_name='Min Record Interval (sec)'),
        ),
        migrations.AddField(
            model_name='mt5monitoringsettings',
            name='snapshot_interval_connected_sec',
            field=models.PositiveIntegerField(default=600, help_text='When connected and stable, store at most one record per this interval', verbose_name='Snapshot Interval When Connected (sec)'),
        ),
        migrations.AddField(
            model_name='mt5monitoringsettings',
            name='ping_delta_threshold_ms',
            field=models.PositiveIntegerField(default=100, help_text='Store a record if ping change exceeds this threshold', verbose_name='Ping Change Threshold (ms)'),
        ),
    ]

