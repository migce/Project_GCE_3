from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0029_global_feed_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='tradingsystemsignalsettings',
            name='use_global_feed',
            field=models.BooleanField(default=False, help_text='If enabled, rules read data from provider-agnostic global feed with TF level bindings', verbose_name='Use Global Feed'),
        ),
        migrations.CreateModel(
            name='TradingSystemTFBinding',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('level', models.PositiveIntegerField()),
                ('feed', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='system_bindings', to='main.datafeed')),
                ('trading_system', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='tf_bindings', to='main.tradingsystem')),
            ],
            options={
                'verbose_name': 'TF Binding',
                'verbose_name_plural': 'TF Bindings',
            },
        ),
        migrations.AddIndex(
            model_name='tradingsystemtfbinding',
            index=models.Index(fields=['trading_system', 'level'], name='main_tradin_trading_9a39c2_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='tradingsystemtfbinding',
            unique_together={('trading_system', 'level')},
        ),
    ]

