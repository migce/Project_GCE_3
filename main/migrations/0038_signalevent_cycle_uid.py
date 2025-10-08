from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0037_tradingsystem_multiple_positions'),
    ]

    operations = [
        migrations.AddField(
            model_name='signalevent',
            name='cycle_uid',
            field=models.CharField(max_length=128, null=True, blank=True, db_index=True),
        ),
        migrations.AddIndex(
            model_name='signalevent',
            index=models.Index(fields=['trading_system', 'cycle_uid', '-event_time'], name='main_signalevent_cycle_idx'),
        ),
    ]
