from django.db import migrations, models


def populate_level_and_feed(apps, schema_editor):
    SignalEvent = apps.get_model('main', 'SignalEvent')
    TimeFrame = apps.get_model('main', 'TimeFrame')
    TradingSystemTFBinding = apps.get_model('main', 'TradingSystemTFBinding')
    DataFeed = apps.get_model('main', 'DataFeed')

    for ev in SignalEvent.objects.all().iterator():
        lvl = getattr(ev, 'level', None) or 0
        if lvl <= 0:
            # derive from timeframe
            try:
                if ev.timeframe_id:
                    tf = TimeFrame.objects.filter(id=ev.timeframe_id).first()
                    if tf and getattr(tf, 'level', None):
                        ev.level = int(tf.level)
            except Exception:
                pass
        # feed from binding if missing
        if not getattr(ev, 'feed_id', None):
            try:
                if ev.trading_system_id and ev.level:
                    bind = TradingSystemTFBinding.objects.filter(trading_system_id=ev.trading_system_id, level=ev.level).first()
                    if bind:
                        ev.feed_id = bind.feed_id
            except Exception:
                pass
        try:
            ev.save(update_fields=['level', 'feed'])
        except Exception:
            try:
                ev.save()
            except Exception:
                pass


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0030_signalsettings_use_global_feed_and_tf_binding'),
    ]

    operations = [
        migrations.AlterField(
            model_name='signalevent',
            name='timeframe',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name='signals', to='main.timeframe', verbose_name='Timeframe'),
        ),
        migrations.AddField(
            model_name='signalevent',
            name='level',
            field=models.PositiveIntegerField(default=1, verbose_name='TF Level'),
        ),
        migrations.AddField(
            model_name='signalevent',
            name='feed',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name='signal_events', to='main.datafeed'),
        ),
        migrations.AddIndex(
            model_name='signalevent',
            index=models.Index(fields=['trading_system', 'level', '-event_time'], name='main_signal_trading_1fbab6_idx'),
        ),
        migrations.AddIndex(
            model_name='signalevent',
            index=models.Index(fields=['feed', '-event_time'], name='main_signal_feed_id_44f9a9_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='signalevent',
            unique_together={('trading_system', 'level', 'event_time', 'direction', 'action')},
        ),
        migrations.RunPython(populate_level_and_feed, migrations.RunPython.noop),
    ]
