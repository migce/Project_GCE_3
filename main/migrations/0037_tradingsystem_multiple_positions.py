from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0036_signalevent_ind_values'),
    ]

    operations = [
        migrations.AddField(
            model_name='tradingsystem',
            name='multiple_positions',
            field=models.BooleanField(default=False, verbose_name='Multiple Positions', help_text='Allow opening additional positions on repeated signals in the same direction'),
        ),
        migrations.AddField(
            model_name='tradingsystem',
            name='max_positions_per_side',
            field=models.PositiveIntegerField(default=5, verbose_name='Max positions per side', help_text='Cap for concurrently open positions per direction when Multiple Positions is enabled'),
        ),
    ]
