from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0022_rename_main_bar_timefra_1a1df7_idx_main_bar_timefra_c20326_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='tradingsystem',
            name='trading_enabled',
            field=models.BooleanField(default=False, help_text='If enabled, signals may execute real trades for this system', verbose_name='Allow Trading'),
        ),
        migrations.AddField(
            model_name='tradingsystem',
            name='lot_size',
            field=models.DecimalField(decimal_places=2, default=0.01, help_text='Default lot size to use for trades (e.g., 0.01)', max_digits=10, verbose_name='Lot Size'),
        ),
    ]

