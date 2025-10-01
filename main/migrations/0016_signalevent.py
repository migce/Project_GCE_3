from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0015_tradingsystem_signal_settings'),
    ]

    operations = [
        migrations.CreateModel(
            name='SignalEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('direction', models.CharField(choices=[('BUY', 'BUY'), ('SELL', 'SELL')], max_length=8)),
                ('rule_text', models.TextField(blank=True)),
                ('event_time', models.DateTimeField(verbose_name='Event Time')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('bar', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='signals', to='main.bar', verbose_name='Bar')),
                ('timeframe', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='signals', to='main.timeframe', verbose_name='Timeframe')),
                ('trading_system', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='signals', to='main.tradingsystem', verbose_name='Trading System')),
            ],
            options={
                'ordering': ['-event_time'],
            },
        ),
        migrations.AddIndex(
            model_name='signalevent',
            index=models.Index(fields=['trading_system', 'timeframe', '-event_time'], name='main_signal_system__7b2c63_idx'),
        ),
        migrations.AddIndex(
            model_name='signalevent',
            index=models.Index(fields=['bar', 'direction'], name='main_signal_bar_direc_3d9265_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='signalevent',
            unique_together={('trading_system', 'timeframe', 'bar', 'direction')},
        ),
    ]

