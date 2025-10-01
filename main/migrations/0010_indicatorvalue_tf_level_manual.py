from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0009_indicatorvalue_int_only'),
    ]

    operations = [
        migrations.AddField(
            model_name='indicatorvalue',
            name='tf_level',
            field=models.PositiveIntegerField(blank=True, help_text='TF level index from CSV', null=True, verbose_name='TF Level'),
        ),
        migrations.AddIndex(
            model_name='indicatorvalue',
            index=models.Index(fields=['indicator', 'tf_level'], name='main_indica_ind_tf_lvl_idx'),
        ),
    ]

