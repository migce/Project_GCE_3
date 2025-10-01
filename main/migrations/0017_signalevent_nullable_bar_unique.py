from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0016_signalevent'),
    ]

    operations = [
        migrations.AlterField(
            model_name='signalevent',
            name='bar',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='signals', to='main.bar', verbose_name='Bar'),
        ),
        migrations.AlterUniqueTogether(
            name='signalevent',
            unique_together={('trading_system', 'timeframe', 'event_time', 'direction')},
        ),
    ]

