from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0020_mt5_terminal_optional'),
    ]

    operations = [
        migrations.AddField(
            model_name='signalevent',
            name='action',
            field=models.CharField(choices=[('OPEN', 'OPEN'), ('CLOSE', 'CLOSE')], default='OPEN', max_length=8),
        ),
        migrations.AddIndex(
            model_name='signalevent',
            index=models.Index(fields=['direction', 'action', '-event_time'], name='main_signal_dir_act_time_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='signalevent',
            unique_together={('trading_system', 'timeframe', 'event_time', 'direction', 'action')},
        ),
    ]

