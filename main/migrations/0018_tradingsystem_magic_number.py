from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0017_signalevent_nullable_bar_unique'),
    ]

    operations = [
        migrations.AddField(
            model_name='tradingsystem',
            name='magic_number',
            field=models.IntegerField(blank=True, null=True, verbose_name='Magic Number', help_text='MT5 Expert Advisor magic number for mapping/filtering'),
        ),
    ]

