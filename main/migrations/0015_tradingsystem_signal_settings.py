from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0014_bar_dt_server'),
    ]

    operations = [
        migrations.CreateModel(
            name='TradingSystemSignalSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('signal_logic', models.TextField(blank=True, help_text='Rules DSL, e.g., IF cond THEN BUY ELSE NONE', verbose_name='Signal Logic (IF/THEN/ELSE)')),
                ('signal_base_tf_level', models.PositiveIntegerField(blank=True, help_text='TF level to evaluate rules on (1=M1, 2=M2, ...). Optional.', null=True, verbose_name='Base TF Level')),
                ('signal_indicators', models.TextField(blank=True, help_text='List/mapping of indicator names and their TFs available in rules', verbose_name='Indicators Description')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated')),
                ('trading_system', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='signal_settings', to='main.tradingsystem', verbose_name='Trading System')),
            ],
            options={
                'verbose_name': 'Signal Settings',
                'verbose_name_plural': 'Signal Settings',
            },
        ),
    ]

