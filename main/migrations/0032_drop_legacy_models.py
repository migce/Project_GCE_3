from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0031_signalevent_feed_level'),
    ]

    operations = [
        migrations.DeleteModel(name='IndicatorValue'),
        migrations.DeleteModel(name='IndicatorDefinition'),
        migrations.DeleteModel(name='Bar'),
        migrations.DeleteModel(name='DataFile'),
        migrations.DeleteModel(name='ImportLog'),
    ]

