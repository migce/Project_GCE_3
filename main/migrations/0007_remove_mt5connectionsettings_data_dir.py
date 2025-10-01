from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0006_mt5connectionsettings_data_dir'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='mt5connectionsettings',
            name='data_dir',
        ),
    ]

