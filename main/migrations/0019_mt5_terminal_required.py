from django.db import migrations, models


def fill_null_terminal_path(apps, schema_editor):
    Settings = apps.get_model('main', 'MT5ConnectionSettings')
    for s in Settings.objects.filter(terminal_path__isnull=True):
        s.terminal_path = ''
        s.save(update_fields=['terminal_path'])


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0018_tradingsystem_magic_number'),
    ]

    operations = [
        migrations.RunPython(fill_null_terminal_path, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='mt5connectionsettings',
            name='terminal_path',
            field=models.CharField(
                max_length=500,
                verbose_name='Путь к терминалу MT5',
                help_text='Полный путь к исполняемому файлу terminal64.exe',
                null=False,
                blank=False,
            ),
        ),
    ]

