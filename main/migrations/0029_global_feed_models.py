from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0028_tradingsystem_is_sar'),
    ]

    operations = [
        migrations.CreateModel(
            name='Instrument',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('symbol', models.CharField(max_length=32, unique=True)),
                ('name', models.CharField(blank=True, max_length=128)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={'ordering': ['symbol']},
        ),
        migrations.CreateModel(
            name='TFCode',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=10, unique=True)),
                ('minutes', models.PositiveIntegerField(default=1)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={'ordering': ['minutes']},
        ),
        migrations.CreateModel(
            name='DataFeed',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider', models.CharField(default='TS', max_length=32)),
                ('is_active', models.BooleanField(default=True)),
                ('instrument', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='feeds', to='main.instrument')),
                ('tfcode', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='feeds', to='main.tfcode')),
            ],
        ),
        migrations.AddIndex(
            model_name='datafeed',
            index=models.Index(fields=['provider', 'instrument'], name='main_datafe_provide_9d2464_idx'),
        ),
        migrations.AddIndex(
            model_name='datafeed',
            index=models.Index(fields=['instrument', 'tfcode'], name='main_datafe_instrum_0a7f7d_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='datafeed', unique_together={('provider', 'instrument', 'tfcode')},
        ),
        migrations.CreateModel(
            name='MarketBar',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('dt', models.DateTimeField()),
                ('dt_server', models.DateTimeField(blank=True, null=True)),
                ('open', models.DecimalField(decimal_places=6, max_digits=16)),
                ('high', models.DecimalField(decimal_places=6, max_digits=16)),
                ('low', models.DecimalField(decimal_places=6, max_digits=16)),
                ('close', models.DecimalField(decimal_places=6, max_digits=16)),
                ('volume', models.BigIntegerField(blank=True, null=True)),
                ('feed', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='bars', to='main.datafeed')),
            ],
        ),
        migrations.AddIndex(
            model_name='marketbar',
            index=models.Index(fields=['feed', '-dt'], name='main_market_feed_id_b6c67e_idx'),
        ),
        migrations.AddIndex(
            model_name='marketbar',
            index=models.Index(fields=['-dt'], name='main_market__dt_c2dc2f_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='marketbar', unique_together={('feed', 'dt')},
        ),
        migrations.CreateModel(
            name='MarketIndicatorDef',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=64)),
                ('dtype', models.CharField(default='numeric', max_length=16)),
                ('description', models.TextField(blank=True)),
                ('feed', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='indicators', to='main.datafeed')),
            ],
        ),
        migrations.AddIndex(
            model_name='marketindicatordef',
            index=models.Index(fields=['feed', 'name'], name='main_market_feed_id_d1ffd2_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='marketindicatordef', unique_together={('feed', 'name')},
        ),
        migrations.CreateModel(
            name='MarketIndicatorValue',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('value_int', models.IntegerField(null=True)),
                ('bar', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='indicator_values', to='main.marketbar')),
                ('indicator', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='values', to='main.marketindicatordef')),
            ],
        ),
        migrations.AddIndex(
            model_name='marketindicatorvalue',
            index=models.Index(fields=['indicator', 'bar'], name='main_market_indicat_855ac8_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='marketindicatorvalue', unique_together={('bar', 'indicator')},
        ),
        migrations.CreateModel(
            name='MarketDataFile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider', models.CharField(default='TS', max_length=32)),
                ('filename', models.CharField(max_length=255)),
                ('file_path', models.CharField(max_length=500)),
                ('file_size', models.PositiveIntegerField(blank=True, null=True)),
                ('file_modified', models.DateTimeField(blank=True, null=True)),
                ('status', models.CharField(default='pending', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('processed_at', models.DateTimeField(blank=True, null=True)),
                ('feed', models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, to='main.datafeed')),
                ('instrument', models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, to='main.instrument')),
                ('tfcode', models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, to='main.tfcode')),
            ],
        ),
        migrations.AddIndex(
            model_name='marketdatafile',
            index=models.Index(fields=['provider', 'filename'], name='main_market_provide_919060_idx'),
        ),
        migrations.AddIndex(
            model_name='marketdatafile',
            index=models.Index(fields=['feed', '-file_modified'], name='main_market_feed_id_b62b8a_idx'),
        ),
    ]

