from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0041_tradingsystem_spread_pips'),
    ]

    operations = [
        migrations.AlterField(
            model_name='marketindicatordef',
            name='name',
            field=models.CharField(max_length=255),
        ),
    ]

