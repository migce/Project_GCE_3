from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0027_rename_main_bar_timefra_1a1df7_idx_main_bar_timefra_c20326_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='tradingsystem',
            name='is_sar',
            field=models.BooleanField(
                default=True,
                verbose_name='SAR (Stop & Reverse)',
                help_text='If enabled, OPEN signals reverse the position (close opposite side)'
            ),
        ),
    ]

