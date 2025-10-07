from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0035_remove_signalevent_main_signal_system__7b2c63_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='signalevent',
            name='ind_values',
            field=models.JSONField(blank=True, null=True, verbose_name='Indicator values'),
        ),
    ]

