from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0040_marketimporterror'),
    ]

    operations = [
        migrations.AddField(
            model_name='tradingsystem',
            name='spread_pips',
            field=models.DecimalField(decimal_places=2, default=0.0, help_text='Per-trade spread to subtract from PnL (in pips)', max_digits=10, verbose_name='Spread (pips)'),
        ),
    ]

