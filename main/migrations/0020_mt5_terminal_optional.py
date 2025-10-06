from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0019_mt5_terminal_required'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mt5connectionsettings',
            name='terminal_path',
            field=models.CharField(
                max_length=500,
                verbose_name='Путь к терминалу MT5',
                help_text='Полный путь к исполняемому файлу terminal64.exe',
                null=True,
                blank=True,
            ),
        ),
    ]

