from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0013_rename_main_bar_timefra_1a1df7_idx_main_bar_timefra_c20326_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='bar',
            name='dt_server',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Bar Time (source)'),
        ),
    ]

