from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0024_rename_main_bar_timefra_1a1df7_idx_main_bar_timefra_c20326_idx_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='SignalExecutionLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('executed_at', models.DateTimeField(auto_now_add=True)),
                ('success', models.BooleanField(default=False)),
                ('message', models.TextField(blank=True)),
                ('signal', models.OneToOneField(on_delete=models.deletion.CASCADE, related_name='execution', to='main.signalevent')),
            ],
            options={},
        ),
        migrations.AddIndex(
            model_name='signalexecutionlog',
            index=models.Index(fields=['-executed_at'], name='main_signalexec_time_idx'),
        ),
    ]

