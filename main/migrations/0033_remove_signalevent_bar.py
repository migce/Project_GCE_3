from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0032_drop_legacy_models'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='signalevent',
            name='bar',
        ),
    ]

