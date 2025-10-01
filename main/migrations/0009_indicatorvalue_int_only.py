from django.db import migrations, models


def copy_old_values(apps, schema_editor):
    IndicatorValue = apps.get_model('main', 'IndicatorValue')
    for iv in IndicatorValue.objects.all().iterator():
        val = None
        # Prefer numeric
        if hasattr(iv, 'value_num') and iv.value_num is not None:
            try:
                val = int(iv.value_num)
            except Exception:
                val = None
        # Map boolean to 1/0
        if val is None and hasattr(iv, 'value_bool') and iv.value_bool is not None:
            val = 1 if iv.value_bool else 0
        # Try to parse text
        if val is None and hasattr(iv, 'value_text') and iv.value_text:
            try:
                val = int(str(iv.value_text).strip())
            except Exception:
                val = None
        if val is not None:
            iv.value_int = val
            iv.save(update_fields=['value_int'])


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0008_bar_indicator_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='indicatorvalue',
            name='value_int',
            field=models.IntegerField(null=True),
        ),
        migrations.RunPython(copy_old_values, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='indicatorvalue',
            name='value_num',
        ),
        migrations.RemoveField(
            model_name='indicatorvalue',
            name='value_text',
        ),
        migrations.RemoveField(
            model_name='indicatorvalue',
            name='value_bool',
        ),
    ]

