from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0007_remove_mt5connectionsettings_data_dir'),
    ]

    operations = [
        migrations.CreateModel(
            name='IndicatorDefinition',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=64, verbose_name='Name')),
                ('dtype', models.CharField(choices=[('numeric', 'Numeric'), ('boolean', 'Boolean'), ('string', 'String')], default='numeric', max_length=16)),
                ('description', models.TextField(blank=True)),
                ('trading_system', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='indicators', to='main.tradingsystem', verbose_name='Trading System')),
            ],
            options={
                'verbose_name': 'Indicator',
                'verbose_name_plural': 'Indicators',
                'unique_together': {('trading_system', 'name')},
            },
        ),
        migrations.CreateModel(
            name='Bar',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('dt', models.DateTimeField(db_index=True, verbose_name='Datetime (UTC)')),
                ('open', models.DecimalField(decimal_places=10, max_digits=20, null=True)),
                ('high', models.DecimalField(decimal_places=10, max_digits=20, null=True)),
                ('low', models.DecimalField(decimal_places=10, max_digits=20, null=True)),
                ('close', models.DecimalField(decimal_places=10, max_digits=20, null=True)),
                ('volume', models.BigIntegerField(blank=True, null=True)),
                ('symbol', models.CharField(blank=True, max_length=20)),
                ('source_row', models.PositiveIntegerField(blank=True, null=True)),
                ('data_file', models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name='bars', to='main.datafile', verbose_name='Source File')),
                ('timeframe', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='bars', to='main.timeframe', verbose_name='Timeframe')),
                ('trading_system', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='bars', to='main.tradingsystem', verbose_name='Trading System')),
            ],
            options={
                'ordering': ['-dt'],
                'unique_together': {('timeframe', 'dt')},
            },
        ),
        migrations.CreateModel(
            name='IndicatorValue',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('value_num', models.DecimalField(decimal_places=10, max_digits=20, null=True)),
                ('value_text', models.CharField(blank=True, max_length=255, null=True)),
                ('value_bool', models.BooleanField(null=True)),
                ('bar', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='indicator_values', to='main.bar', verbose_name='Bar')),
                ('indicator', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='values', to='main.indicatordefinition', verbose_name='Indicator')),
            ],
            options={
                'verbose_name': 'Indicator Value',
                'verbose_name_plural': 'Indicator Values',
                'unique_together': {('bar', 'indicator')},
            },
        ),
        migrations.AddIndex(
            model_name='indicatordefinition',
            index=models.Index(fields=['trading_system', 'name'], name='main_indica_system__c1d71b_idx'),
        ),
        migrations.AddIndex(
            model_name='bar',
            index=models.Index(fields=['timeframe', '-dt'], name='main_bar_timefra_1a1df7_idx'),
        ),
        migrations.AddIndex(
            model_name='bar',
            index=models.Index(fields=['trading_system', '-dt'], name='main_bar_trading_03b8a3_idx'),
        ),
        migrations.AddIndex(
            model_name='indicatorvalue',
            index=models.Index(fields=['indicator', 'bar'], name='main_indica_indicat_861b1f_idx'),
        ),
    ]

