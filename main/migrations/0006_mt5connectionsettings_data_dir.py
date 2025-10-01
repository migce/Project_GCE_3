from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0005_tradingsystem_data_dir'),
    ]

    operations = [
        migrations.AddField(
            model_name='mt5connectionsettings',
            name='data_dir',
            field=models.CharField(
                max_length=500,
                blank=True,
                verbose_name='Папка с данными',
                help_text='Полный путь к папке, где искать файлы системы. Если пусто, используется глобальная TS_EXPORTS_DIR.'
            ),
        ),
    ]

